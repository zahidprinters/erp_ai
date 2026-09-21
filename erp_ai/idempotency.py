# ---------------------------------------------------------------------------
# Idempotency & retry-safe writes.
#
# Prevents duplicate document creation when a request is retried due to
# network timeouts or transient failures. Uses the AI Assistant Action
# DocType's idempotency_key field.
# ---------------------------------------------------------------------------
from typing import Any, Dict, Optional

# Single expiry clock shared with erp_ai.draft_workflow (see erp_ai.audit).
from erp_ai.audit import ACTION_EXPIRY_MINUTES, log_error_safely


def ensure_unique_index():
	"""Create the unique index on AI Assistant Action.idempotency_key (idempotent).

	Called from install/migrate hooks only — never from the request path. Running
	DDL on a request takes metadata locks on a hot table and previously ran on
	every claim that found no existing row, so it is a migration-time concern.

	The index is what makes concurrent claims race-safe: the second INSERT with
	the same key raises DuplicateEntryError instead of creating a second action.
	NULL keys (drafts without an idempotency key) are unaffected as MySQL treats
	multiple NULLs as distinct. Frappe's ``add_unique`` is a no-op when the
	constraint already exists.
	"""
	import frappe

	try:
		frappe.db.add_unique(
			"AI Assistant Action", ["idempotency_key"], constraint_name="unique_idempotency_key"
		)
	except Exception as exc:
		# Legacy rows with duplicate '' keys would block the index; check-then-insert
		# still applies as a best-effort guard in that case.
		# Title first, message second (frappe.log_error swaps only when the first
		# arg is multi-line); the Error Log title is capped at 140 chars, so the
		# previously-long first argument raised from inside this except block.
		log_error_safely("erp_ai.idempotency: unique index not created", str(exc))


def check_idempotency(key: str, user: str = None) -> Optional[Dict[str, Any]]:
	"""Check if an operation with this key was already completed or is in progress.

	Treats pending and processing keys as duplicates (race condition safe).
	Returns the previous result if found, None if not seen before.
	"""
	import frappe

	if not key:
		return None
	existing = frappe.get_all(
		"AI Assistant Action",
		filters={"idempotency_key": key, "status": ["in", ["pending", "processing", "completed"]]},
		fields=["name", "target_docname", "target_doctype", "draft_data", "user", "status"],
		limit_page_length=1,
	)
	if existing:
		# Verify ownership
		if user and existing[0]["user"] != user:
			return {"status": "forbidden", "action_id": existing[0]["name"]}
		return {
			"status": existing[0]["status"],
			"action_id": existing[0]["name"],
			"docname": existing[0]["target_docname"],
			"doctype": existing[0]["target_doctype"],
			"data": frappe.parse_json(existing[0]["draft_data"] or "{}"),
		}
	return None


def claim_idempotency(
	key: str, session: str, user: str, action: str, target_doctype: str, proposed_data: Dict[str, Any]
) -> Dict[str, Any]:
	"""Claim an idempotency key for an operation about to be performed.

	Race-safe: the unique index on ``idempotency_key`` guarantees exactly one
	INSERT wins; a concurrent (or retried) claim raises DuplicateEntryError and
	is reported as a duplicate. The index is created by the install/migrate
	hooks (``ensure_unique_index``), not on this request path. Returns
	{"status": "new", ...} or {"status": "duplicate"/"forbidden", ...}.
	"""
	import frappe

	if not key:
		return {"status": "no_key"}
	# Check for existing (including pending/processing for race safety)
	existing = frappe.get_all(
		"AI Assistant Action",
		filters={"idempotency_key": key, "status": ["in", ["pending", "processing", "completed"]]},
		fields=["name", "user", "status"],
		limit_page_length=1,
	)
	if existing:
		if existing[0]["user"] != user:
			return {"status": "forbidden", "action_id": existing[0]["name"]}
		return {"status": "duplicate", "action_id": existing[0]["name"]}
	nonce = frappe.generate_hash(length=12)
	expires_on = frappe.utils.add_to_date(frappe.utils.now_datetime(), minutes=ACTION_EXPIRY_MINUTES)
	doc = frappe.get_doc(
		{
			"doctype": "AI Assistant Action",
			"user": user,
			"session_id": session,
			"action": action,
			"target_doctype": target_doctype,
			"status": "pending",
			"draft_data": frappe.as_json(
				{
					"proposed_changes": proposed_data,
					"claimed_at": str(frappe.utils.now_datetime()),
				}
			),
			"nonce": nonce,
			"expires_on": expires_on,
			"idempotency_key": key,
		}
	)
	try:
		doc.insert()
	except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
		# Lost the race: another request claimed this key first.
		return {"status": "duplicate", "action_id": None}
	return {"status": "new", "action_id": doc.name, "nonce": nonce}


def generate_idempotency_key(session: str, action: str, target_doctype: str, data: Dict[str, Any]) -> str:
	"""Generate a deterministic idempotency key from operation parameters."""
	import hashlib
	import json

	canonical = json.dumps(
		{
			"session": session,
			"action": action,
			"doctype": target_doctype,
			"data": data,
		},
		sort_keys=True,
		default=str,
	)
	return hashlib.sha256(canonical.encode()).hexdigest()[:24]
