"""
Draft-then-confirm workflow for all ERPNext operations.

Flow:
1. User speaks naturally → AI detects intent (doctype)
2. AI extracts available data from prompt
3. AI checks required fields → asks for missing ones
4. AI stores the draft as an `AI Assistant Action` record (status=pending)
5. When complete → AI shows preview/overview
6. User confirms → AI creates document (Draft)
7. User says "submit" → AI submits document
8. User modifies → AI updates draft, shows updated preview
"""

import json
import re

import frappe

from erp_ai.audit import ACTION_EXPIRY_MINUTES, log_error_safely
from erp_ai.mcp.server import FrappeMCP

# Single source of truth for doctype schemas — imported from erp_ai.schema.
# This module owns draft/confirm/workflow logic only.
from erp_ai.schema import (
	DOCTYPE_SCHEMAS,
	get_all_doctypes,
	get_defaults,
	get_label,
	get_optional_fields,
	get_required_fields,
	get_schema,
)

# =============================================================================
# UOM CONVERSION FACTORS (relative to base unit)
# Base units: Gram (weight), Meter (length), Litre (volume), Nos (count)
# =============================================================================

UOM_CONVERSIONS = {
	# Weight (base: Gram)
	"Gram": ("weight", 1),
	"Microgram": ("weight", 0.000001),
	"Milligram": ("weight", 0.001),
	"Kg": ("weight", 1000),
	"Tonne": ("weight", 1000000),
	"Quintal": ("weight", 100000),
	"Carat": ("weight", 0.2),
	"Ounce": ("weight", 28.3495),
	"Pound": ("weight", 453.592),
	"Stone": ("weight", 6350.29),
	"Grain": ("weight", 0.0648),
	"Dram": ("weight", 1.7718),
	# Length (base: Meter)
	"Meter": ("length", 1),
	"Millimeter": ("length", 0.001),
	"Centimeter": ("length", 0.01),
	"Decimeter": ("length", 0.1),
	"Kilometer": ("length", 1000),
	"Inch": ("length", 0.0254),
	"Foot": ("length", 0.3048),
	"Yard": ("length", 0.9144),
	"Mile": ("length", 1609.34),
	"Fathom": ("length", 1.8288),
	"Hand": ("length", 0.1016),
	"Micrometer": ("length", 0.000001),
	"Nanometer": ("length", 0.000000001),
	# Volume (base: Litre)
	"Litre": ("volume", 1),
	"Millilitre": ("volume", 0.001),
	"Centilitre": ("volume", 0.01),
	"Decilitre": ("volume", 0.1),
	"Cubic Meter": ("volume", 1000),
	"Cubic Centimeter": ("volume", 0.001),
	"Cubic Millimeter": ("volume", 0.000001),
	"Cubic Inch": ("volume", 0.0163871),
	"Cubic Foot": ("volume", 28.3168),
	"Gallon (UK)": ("volume", 4.54609),
	"Gallon Liquid (US)": ("volume", 3.78541),
	# Count
	"Nos": ("count", 1),
	"Unit": ("count", 1),
	"Pair": ("count", 1),
	"Set": ("count", 1),
	"Box": ("count", 1),
	"Dozen": ("count", 12),
	"Piece": ("count", 1),
}


def convert_uom(qty, from_uom, to_uom):
	"""Convert quantity from one UOM to another. Returns converted qty or None if incompatible."""
	from_info = UOM_CONVERSIONS.get(from_uom)
	to_info = UOM_CONVERSIONS.get(to_uom)
	if not from_info or not to_info:
		return None
	if from_info[0] != to_info[0]:  # Different categories (weight vs length)
		return None
	# Convert: qty * from_factor / to_factor
	return qty * from_info[1] / to_info[1]


def get_uom_category(uom_name):
	"""Get the category of a UOM (weight, length, volume, count)."""
	info = UOM_CONVERSIONS.get(uom_name)
	return info[0] if info else None


# =============================================================================
# DRAFT STORE — AI Assistant Action is the ONLY authoritative store
# =============================================================================
# Pending workflow state lives in `AI Assistant Action` (status + draft_data).
# The legacy chat-marker store (`[DRAFT]` / `[DRAFT_CLEARED]` rows in
# `AI Chat Message`) was deleted: two stores for one lifecycle desynchronise
# whenever one path reads what another wrote. `get_draft` below is a thin read
# view over the action record — a projection, never a second source of truth.


def get_draft(session, user=None):
	"""Get pending action from AI Assistant Action DocType.

	Returns a dict for the caller to display a preview / prompt confirmation,
	or None if no pending action exists for the session.

	Parameters
	----------
	session : str
	    Browser session identifier (kept for UI correlation only; auth is the
	    user).
	user : str, optional
	    Authenticated user (defaults to frappe.session.user).

	Returns
	-------
	dict or None
	    Action dict with keys: name, user, session_id, action, target_doctype,
	    status, draft_data, nonce, expires_on, document_version
	    or None if no pending action found.
	"""
	user = user or frappe.session.user
	action_name = _get_action(session=session, user=user, status="pending")
	if not action_name:
		return None
	action = frappe.get_doc("AI Assistant Action", action_name)
	return {
		"name": action.name,
		"user": action.user,
		"session_id": action.session_id,
		"action": action.action,
		"target_doctype": action.target_doctype,
		"status": action.status,
		"draft_data": json.loads(action.draft_data) if action.draft_data else {},
		"nonce": action.nonce,
		"expires_on": action.expires_on,
		"document_version": action.document_version,
	}


# ---------------------------------------------------------------------------
# Phase 2 — dedicated, user-bound draft persistence (AI Assistant Action).
# This is the ONE authoritative store of pending operations; the legacy
# chat-marker drafts were removed (see the DRAFT STORE note above).
# ---------------------------------------------------------------------------


def _get_action(action_id=None, session=None, user=None, status="pending"):
	"""Resolve an AI Assistant Action, or None.

	Exactly one of ``action_id`` or (``session``+``user``) may be provided, and
	the return type follows the selector: an ``action_id`` yields the full
	Document (the caller reads/mutates it), while the session lookup yields just
	the *name* string (the caller only needs to address the action). Callers must
	not assume a Document on the session branch.
	"""
	user = user or frappe.session.user
	if action_id:
		return (
			frappe.get_doc("AI Assistant Action", action_id)
			if frappe.db.exists("AI Assistant Action", action_id)
			else None
		)
	if session:
		return frappe.db.get_value(
			"AI Assistant Action",
			{"user": user, "session_id": session, "status": status},
			"name",
		)
	return None


def _supersede(action_name):
	"""Move a superseded pending action into the terminal ``cancelled`` state.

	Replaces the previous best-effort cleanup, which called ``.cancel()`` and
	``.delete()`` on the action *name* (a ``str``, because the session branch of
	``_get_action`` returns a name) and therefore always raised, was swallowed,
	and left the old action behind. Two pending actions per session+user meant
	the session lookup in ``confirm_draft`` could pick the stale one and execute
	a draft the user had already replaced.
	"""
	try:
		action = frappe.get_doc("AI Assistant Action", action_name)
		action.status = "cancelled"
		action.failure_reason = "Superseded by a newer draft"
		action.save(ignore_permissions=True)
	except Exception:
		frappe.log_error(
			frappe.get_traceback(),
			"erp_ai.draft_workflow: could not supersede action %s" % action_name,
		)


def create_draft(session, action, target_doctype, draft_data, user=None):
	"""Persist a pending operation to the AI Assistant Action DocType.

	Parameters
	----------
	session : str
	    Browser session identifier (kept for UI correlation only; auth is the user).
	action : str
	    One of 'create', 'submit', 'update'.
	target_doctype : str
	    ERPNext DocType the pending operation targets (e.g. 'Sales Invoice').
	draft_data : dict
	    Collected document fields to be used at confirmation time.
	user : str, optional
	    Authenticated user (defaults to frappe.session.user).

	Returns
	-------
	dict
	    {'name': action_name, 'nonce': nonce, 'expires_on': ..., 'preview_hash': ...}
	    on success, or {'error': ...} on failure.
	"""
	user = user or frappe.session.user
	now = frappe.utils.now_datetime()
	expiry = frappe.utils.add_to_date(now, minutes=ACTION_EXPIRY_MINUTES)

	# Supersede any stale pending action for this session/user: the new draft
	# must be the only confirmable action, or confirm_draft's session lookup can
	# resolve the stale one.
	_existing = _get_action(session=session, user=user, status="pending")
	if _existing:
		_supersede(_existing)

	import secrets

	nonce = secrets.token_hex(16)
	normalized = _normalize_draft_data(target_doctype, draft_data)
	preview_hash = generate_preview_hash(target_doctype, normalized)

	doc = frappe.get_doc(
		{
			"doctype": "AI Assistant Action",
			"user": user,
			"session_id": str(session),
			"action": action,
			"target_doctype": target_doctype,
			"status": "pending",
			"draft_data": json.dumps(normalized, default=str),
			"nonce": nonce,
			"expires_on": expiry.isoformat(),
			"document_version": 1,
			"preview_hash": preview_hash,
		}
	)
	doc.insert()
	# Creation joins the caller's transaction; confirm_draft's finalisation
	# commit is the boundary that makes the action durable.
	return {
		"name": doc.name,
		"nonce": nonce,
		"expires_on": expiry.isoformat(),
		"preview_hash": preview_hash,
		"draft_data": draft_data,
	}


def _normalize_draft_data(doctype, draft_data):
	"""Return a stable copy of the draft payload used for preview hashing.

	This keeps the preview hash stable even when the caller passed extra or
	inconsistently ordered junk that does not affect execution.
	"""
	if not isinstance(draft_data, dict):
		return {}

	schema = DOCTYPE_SCHEMAS.get(doctype, {})
	allowed = set(schema.get("required", []) + schema.get("optional", []))
	normalized = {}
	for key, value in draft_data.items():
		if key in allowed:
			normalized[key] = value
	return normalized


def _claim_action(action_id):
	"""Atomically transition a pending AI Assistant Action to ``processing``.

	The claim is a conditional UPDATE (``status = 'pending'`` guard), so
	exactly one concurrent confirmation wins the transition; every other
	caller sees an unchanged row and loses. Returns True only when this call
	performed the transition.

	``frappe.db.set_value`` cannot be used for the claim signal: it always
	returns ``None`` on every supported Frappe 15 backend, so its return
	value cannot tell us whether the row actually changed. The raw cursor's
	``rowcount`` is the reliable, driver-independent signal for that.
	"""
	frappe.db.sql(
		"UPDATE `tabAI Assistant Action` SET `status` = 'processing' "
		"WHERE `name` = %s AND `status` = 'pending'",
		action_id,
	)
	return bool(getattr(frappe.db._cursor, "rowcount", 0))


def confirm_draft(session, user=None, expected_nonce=None, action_id=None):
	"""Confirm (create) a pending operation using the AI Assistant Action store.

	The caller should identify the exact pending action by ``action_id`` for
	non-interactive flows. In a chat flow the caller may omit it; the action is
	then resolved to the single pending action owned by ``user`` in ``session``
	(exactly one can exist because ``create_draft`` clears any earlier pending
	action for the same session+user).

	Confirmation is bound to the action owner, session, nonce, expiry, status,
	and the preview hash that was stored when the draft was created.

	On success the action is atomically moved through a transient ``processing``
	state to ``completed``. On execution failure the action is moved to ``failed``
	with a recorded reason, so failed attempts are not treated as completed.
	Partial inserts from a failed attempt are rolled back before the failure is
	recorded, so a failed action never commits half a document.

	Idempotent: the action record is the only state store, a terminal action is
	never re-executed, and a repeated confirm reports the recorded outcome.
	"""
	user = user or frappe.session.user

	if not action_id:
		action_id = _get_action(session=session, user=user, status="pending")
		if not action_id:
			return {"error": "Nothing to confirm. Start by telling me what you want to create."}

	action = _get_action(action_id=action_id)
	if not action:
		return {"error": "No such action"}

	if action.user != user:
		return {"error": "This action belongs to a different user"}

	if session is not None and action.session_id != str(session):
		return {"error": "Session mismatch for this action"}

	if action.status != "pending":
		# Idempotent re-confirm: a terminal action is never re-executed, but the
		# recorded outcome is reported so a retried request (client timeout after
		# a successful confirmation) gets a truthful answer instead of a dead end.
		return {
			"error": "The pending action is no longer available (status: %s)" % action.status,
			"already_handled": True,
			"already_completed": action.status == "completed",
			"status": action.status,
			"doctype": action.target_doctype,
			"name": action.target_docname,
		}

	expires_on = action.expires_on
	if isinstance(expires_on, str):
		expires_on = frappe.parse_datetime(expires_on)
	if expires_on and expires_on < frappe.utils.now_datetime():
		return {"error": "This draft has expired. Please start over."}

	if expected_nonce and action.nonce != expected_nonce:
		return {"error": "Confirmation token mismatch. Please use the latest confirmation link."}

	try:
		stored_preview_hash = getattr(action, "preview_hash", None)
		stored_preview_hash = (
			stored_preview_hash.get("preview_hash")
			if isinstance(stored_preview_hash, dict)
			else stored_preview_hash
		)
		draft_data = json.loads(action.draft_data) if action.draft_data else {}
	except (ValueError, TypeError):
		return {"error": "Draft data is corrupted"}

	target_doctype = action.target_doctype
	if not target_doctype:
		return {"error": "Draft does not specify a target DocType"}

	current_hash = generate_preview_hash(target_doctype, draft_data)
	if stored_preview_hash and current_hash != stored_preview_hash:
		return {"error": "The draft has changed since it was previewed. Please preview again."}

	# Atomically claim the action so concurrent confirmations cannot both execute.
	claimed = _claim_action(action_id)
	if not claimed:
		return {"error": "Action expired or could not be claimed"}

	# Executing the draft can insert a document and then fail on a later step, so
	# the failure paths must be able to discard exactly that partial work. A full
	# ``frappe.db.rollback()`` is too blunt here: it would also undo the claim
	# above and — when ``create_draft``'s insert has not been committed yet (same
	# transaction) — the action row itself, so the failure would vanish from the
	# audit trail instead of being recorded. A savepoint scopes the rollback to
	# the execution only.
	save_point = "erp_ai_confirm_exec"
	frappe.db.savepoint(save_point)

	try:
		mcp = FrappeMCP()
		result = create_document_from_draft(target_doctype, draft_data, mcp)

		if isinstance(result, dict) and result.get("error"):
			# Discard partial inserts from the failed attempt before the failure
			# is recorded: create_document_from_draft may have saved a document
			# and then failed on a later step. Without this rollback the partial
			# document would be committed by record_failure's own commit.
			frappe.db.rollback(save_point=save_point)
			_finalise_action(
				action_id,
				status="failed",
				target_docname=None,
				failure_reason=result.get("error") or "create_document returned an error",
				result_payload=result,
			)
			return result

		_finalise_action(
			action_id,
			status="completed",
			target_docname=(result.get("name") if isinstance(result, dict) and result.get("name") else None),
			failure_reason=None,
			confirmed_at=frappe.utils.now(),
			result_payload=result if isinstance(result, dict) else {},
		)

		# No second store to keep in sync: the action record above IS the outcome.
		return result
	except Exception as exc:
		# Same reasoning as the error-result branch: never commit a partial
		# document as the side effect of recording the failure — and only undo
		# the execution, not the action record that carries the failure.
		frappe.db.rollback(save_point=save_point)
		_finalise_action(
			action_id,
			status="failed",
			target_docname=None,
			failure_reason=str(exc),
			result_payload={"error": str(exc)},
		)
		log_error_safely(
			"erp_ai: confirm_draft failed for %s" % action_id,
			str(exc),
			context={
				"action_id": action_id,
				"doctype": target_doctype,
				"session": action.session_id,
				"user": user,
			},
			retryable=exc,
		)
		return {"error": "Confirmation failed. Please try again."}


def _rollback_reference(action_id, target_docname, summary):
	"""Build the stable pointer persisted on a completed/failed action.

	Always carries the action id, the target DocType/docname and the preview
	hash captured when the draft was created, so an operator can verify that the
	payload which executed is exactly the payload that was confirmed. The
	reference therefore points at the *created document* (plus the confirmed
	snapshot), not merely at the executing payload.
	"""
	stored = (
		frappe.db.get_value(
			"AI Assistant Action", action_id, ["target_doctype", "preview_hash"], as_dict=True
		)
		or {}
	)
	return {
		"action_id": action_id,
		"target_doctype": stored.get("target_doctype"),
		"target_docname": target_docname,
		"preview_hash": stored.get("preview_hash"),
		"result_summary": summary,
	}


def _finalise_action(
	action_id,
	status,
	target_docname=None,
	failure_reason=None,
	confirmed_at=None,
	result_payload=None,
	rollback_ref=None,
	changed_fields=None,
):
	"""Persist the final action state used by confirmation and audit.

	Delegates to the audit module so the trail holds the complete outcome
	(result payload, changed fields, rollback reference) in one consistent format.
	This is the single audit-boundary commit for the action lifecycle.

	A ``rollback_reference`` is always persisted: if the caller supplied one it is
	used verbatim; otherwise a stable reference is synthesized from the action
	record so operators can always navigate from a completed/failed action back to
	the originating session/request, even when the caller did not manage its own
	audit record.
	"""
	import frappe

	from erp_ai import audit

	if status == "failed":
		if not rollback_ref:
			rollback_ref = _rollback_reference(
				action_id,
				target_docname,
				{
					"status": "failed",
					"error": failure_reason or "unknown",
					"confirmed_at": str(confirmed_at) if confirmed_at else None,
				},
			)
		audit.record_failure(
			action_id,
			failure_reason or "unknown",
			rollback_ref=rollback_ref,
		)
		return

	# Compute changed_fields if caller didn't supply them
	if not changed_fields and result_payload and isinstance(result_payload, dict):
		try:
			stored = json.loads(frappe.db.get_value("AI Assistant Action", action_id, "draft_data") or "{}")
		except (ValueError, TypeError):
			stored = {}
		previous = (stored.get("proposed_changes") or {}).keys()
		skip_keys = {"name", "doctype", "print_url", "stock_entry"}
		changed_fields = sorted(set(previous) & {k for k in result_payload.keys() if k not in skip_keys})

	if not rollback_ref:
		rollback_ref = _rollback_reference(
			action_id,
			target_docname,
			{
				k: v
				for k, v in (result_payload or {}).items()
				if k in ("name", "doctype", "status", "steps", "message", "error")
			},
		)

	audit.record_completion(
		action_id,
		target_docname=target_docname,
		result=result_payload or {},
		rollback_ref=rollback_ref,
		changed_fields=changed_fields,
		confirmed_at=confirmed_at,
	)


# =============================================================================
# FIELD EXTRACTION — natural language → structured data
# =============================================================================


def extract_item_fields(prompt):
	"""Extract item fields from natural language with UOM support."""
	p = prompt
	data = {}

	# Item name - extract words after "item" until price/stock/group or number+unit
	_name_patterns = [
		# "add item NAME ..."
		r"(?:add|create|banao|banaiye)\s+(?:a\s+|new\s+)?(?:item|product|itm)\s+([A-Za-z][A-Za-z0-9 .&]+?)(?=\s+(?:price|rate|cost|keemat|per|stock|qty|quantity|group|category|@)\b|\s+\d+\s*(?:mm|cm|meter|inch|foot|feet|kg|gram|gm|g|pcs|nos|unit|liter|litre|ml)\b|\s*[,;]|$)",
		# "NAME resived/recived 20 leter" (name first)
		r"^([A-Za-z][A-Za-z0-9 .&]{2,30}?)\s+(?:resived|recived|resiv|reciv|aa gaya|milay|mile)\s+\d+\s*(?:kg|liter|litre|leters|liters|gram|gm|ml|mm|meter|inch|foot|piece|leter)\b",
		# "named NAME ..."
		r"(?:named|name|called|ka naam|naam)\s+([A-Za-z][A-Za-z0-9 .&]+?)(?=\s+(?:price|rate|cost|keemat|per|stock|qty|quantity|group|category)\b|\s+\d+\s*(?:mm|cm|meter|inch|foot|feet|kg|gram|gm|g)\b|\s*[,;]|$)",
		# "lubrication oil 20 liter..." (leading words before quantity+unit)
		r"^([a-z][a-z0-9 .&]+?)\s+\d+\s*(?:kg|kilo|kilogram|gram|gm|g|mm|millimeter|cm|centimeter|meter|inch|foot|feet|literal|liter|litre|ml|millilitre|pcs|nos|unit)",
	]
	for _pat in _name_patterns:
		m = re.search(_pat, p, re.I)
		if m:
			name = m.group(1).strip().rstrip(",").strip()
			name = re.sub(
				r"\s+(?:size|sz|diameter|dia|length|len|leanth|width|height|thickness)\s*$",
				"",
				name,
				flags=re.I,
			)
			if len(name) >= 2:
				data["item_name"] = name
				break

	# Item group
	m = re.search(
		r"(?:group|category)[:]?\s*([^,;.]+?)(?:\s*(?:price|rate|cost|keemat|py|stock|qty|quantity|opening)\b|$)",
		p,
		re.I,
	)
	if m:
		data["item_group"] = m.group(1).strip()

	# Price patterns: "20 per gram", "10 pkr on 150 ml", "price is 20 per mm"
	# First try: "X pkr on Y unit" (price for a quantity)
	m = re.search(
		r"(?:price|rate|cost|keemat|py)?\s*(?:is|=|:)?\s*([0-9][0-9,.]*)\s*(?:rs|rupees|pkr|/-)?\s*(?:per|on)\s*([0-9][0-9,.]*)\s*(ml|millilitre|liter|litre|leter|leters|liters|litres|l|gram|gm|g|kg|mm|cm|meter|inch|foot|piece|unit|nos)",
		p,
		re.I,
	)
	if m:
		price_val = float(m.group(1).replace(",", ""))
		qty_val = float(m.group(2).replace(",", ""))
		unit = m.group(3).lower()
		if qty_val > 0:
			data["standard_rate"] = round(price_val / qty_val, 4)  # Price per unit
		else:
			data["standard_rate"] = price_val
		uom_map = {
			"ml": "Millilitre",
			"millilitre": "Millilitre",
			"liter": "Litre",
			"litre": "Litre",
			"l": "Litre",
			"leter": "Litre",
			"leters": "Litre",
			"liters": "Litre",
			"litres": "Litre",
			"gram": "Gram",
			"gm": "Gram",
			"g": "Gram",
			"kg": "Kg",
			"mm": "Millimeter",
			"cm": "Centimeter",
			"meter": "Meter",
			"inch": "Inch",
			"foot": "Foot",
			"piece": "Nos",
			"unit": "Nos",
			"nos": "Nos",
		}
		data["stock_uom"] = uom_map.get(unit, "Nos")
	else:
		# Simple per-unit: "20 per gram"
		m = re.search(
			r"(?:price|rate|cost|keemat|py)?\s*(?:is|=|:)?\s*([0-9][0-9,.]*)\s*(?:rs|rupees|pkr|/-)?\s*(?:per|on)\s*(?:[0-9]+\s*)?(gram|gm|g|kg|kilo|kilogram|mm|millimeter|cm|centimeter|meter|inch|foot|feet|piece|unit|nos|ml|millilitre|liter|litre|l)",
			p,
			re.I,
		)
		if m:
			data["standard_rate"] = float(m.group(1).replace(",", ""))
			unit = m.group(2).lower()
			uom_map = {
				"gram": "Gram",
				"gm": "Gram",
				"g": "Gram",
				"kg": "Kg",
				"kilo": "Kg",
				"kilogram": "Kg",
				"mm": "Millimeter",
				"millimeter": "Millimeter",
				"cm": "Centimeter",
				"centimeter": "Centimeter",
				"meter": "Meter",
				"inch": "Inch",
				"foot": "Foot",
				"feet": "Foot",
				"piece": "Nos",
				"unit": "Nos",
				"nos": "Nos",
				"ml": "Millilitre",
				"millilitre": "Millilitre",
				"liter": "Litre",
				"litre": "Litre",
				"l": "Litre",
			}
			data["stock_uom"] = uom_map.get(unit, "Nos")
		else:
			# Simple price
			m = (
				re.search(r"(?:price|rate|cost|keemat|py)\s*(?:is|=|:|ki hai)\s*([0-9][0-9,.]*)", p, re.I)
				or re.search(r"(?:price|rate|cost|keemat|py)[:=]?\s*([0-9][0-9,.]*)", p, re.I)
				or re.search(r"([0-9][0-9,.]*)\s*(?:rs|rupees|pkr|/-)\b", p, re.I)
			)
			if m:
				data["standard_rate"] = float(m.group(1).replace(",", ""))
	# Stock with unit: "4kg", "4 kg", "we have 4kg", "4000 grams", "12 inches", "20 leter"
	# Prefer "stock is X unit" and "we have X unit" patterns, fall back to last qty+unit
	m = re.search(
		r"(?:stock|qty|quantity|opening|received|milay|mile|we have)\s+(?:is|=|:)?\s*([0-9][0-9,.]*)\s*(kg|kilo|kilogram|gram|gm|g|mm|millimeter|cm|centimeter|meter|inch|foot|feet|liter|litre|leter|leters|liters|litres|l|ml|millilitre)\b",
		p,
		re.I,
	)
	if not m:
		# Fall back: get all matches of "quantity unit", prefer the one with liter/gram (larger units)
		matches = list(
			re.finditer(
				r"([0-9][0-9,.]*)\s*(kg|kilo|kilogram|gram|gm|g|mm|millimeter|cm|centimeter|meter|inch|foot|feet|literal|liter|litre|leter|leters|liters|litres|l|ml|millilitre|pcs|nos|unit)",
				p,
				re.I,
			)
		)
		# Prefer kg/liter/liter over ml/gram for stock
		for match in reversed(matches):
			unit = match.group(2).lower()
			if unit in (
				"kg",
				"kilo",
				"kilogram",
				"literal",
				"liter",
				"litre",
				"leter",
				"leters",
				"liters",
				"litres",
			):
				m = match
				break
		else:
			if matches:
				m = matches[-1]  # Take the last one
	if not m:
		# Still no match, try simple search
		m = re.search(
			r"(?:we have|stock|qty|quantity|opening|received|milay|mile|aa gaya)?\s*([0-9][0-9,.]*)\s*(kg|kilo|kilogram|gram|gm|g|mm|millimeter|cm|centimeter|meter|inch|foot|feet|liter|litre|leter|leters|liters|litres|l|ml|millilitre)\b",
			p,
			re.I,
		)
	if m:
		qty = float(m.group(1).replace(",", ""))
		unit = m.group(2).lower()
		uom_map = {
			"kg": "Kg",
			"kilo": "Kg",
			"kilogram": "Kg",
			"gram": "Gram",
			"gm": "Gram",
			"g": "Gram",
			"mm": "Millimeter",
			"millimeter": "Millimeter",
			"cm": "Centimeter",
			"centimeter": "Centimeter",
			"meter": "Meter",
			"inch": "Inch",
			"foot": "Foot",
			"feet": "Foot",
			"liter": "Litre",
			"litre": "Litre",
			"l": "Litre",
			"leter": "Litre",
			"leters": "Litre",
			"liters": "Litre",
			"litres": "Litre",
			"ml": "Millilitre",
			"millilitre": "Millilitre",
		}
		stock_uom = uom_map.get(unit, "Nos")
		# Convert if UOM already set from price
		if "stock_uom" in data and data["stock_uom"] != stock_uom:
			converted = convert_uom(qty, stock_uom, data["stock_uom"])
			if converted is not None:
				data["opening_stock"] = converted
			else:
				data["opening_stock"] = qty
				data["stock_uom"] = stock_uom
		else:
			data["opening_stock"] = qty
			if "stock_uom" not in data:
				data["stock_uom"] = stock_uom
	else:
		# Simple stock
		m = re.search(
			r"(?:stock|qty|quantity|opening|received|milay|mile)\s*(?:of|is|=|:)?\s*([0-9][0-9,.]*)", p, re.I
		) or re.search(r"([0-9][0-9,.]*)\s*(?:pcs|nos|units|pieces|dozen)\b", p, re.I)
		if m:
			data["opening_stock"] = float(m.group(1).replace(",", ""))

	return data


def extract_invoice_fields(prompt):
	"""Extract invoice fields from natural language."""
	p = prompt
	data = {}
	# Customer / Supplier
	m = re.search(r"(?:for|to|customer|client|ke liye)\s+([A-Za-z0-9 .&-]{2,40}?)(?:,|\.|\d|$)", p, re.I)
	if m:
		data["customer"] = m.group(1).strip()
	# Items: '2 pump springs @ 500'
	items = []
	for m in re.finditer(
		r"([0-9,.]+)\s*(?:pcs|nos|units)?\s*([A-Za-z][A-Za-z0-9 -]{2,40}?)\s*(?:@|at|rate|price)\s*([0-9,.]+)",
		p,
		re.I,
	):
		q = float(m.group(1).replace(",", ""))
		nm = m.group(2).strip()
		r = float(m.group(3).replace(",", ""))
		items.append({"description": nm, "qty": q, "rate": r})
	if items:
		data["items"] = items
	# Discount
	m = re.search(r"(?:discount|disc)\s*([0-9][0-9,.]*)\s*%?", p, re.I)
	if m:
		data["discount_percent"] = float(m.group(1).replace(",", ""))
	# Due date
	m = re.search(r"due\s*(?:in|date)?\s*([0-9]+)\s*(?:days?|din)?", p, re.I)
	if m:
		data["due_days"] = int(m.group(1))
	return data


def extract_party_fields(prompt, party_type="customer"):
	"""Extract customer/supplier fields."""
	p = prompt
	data = {}
	field = "customer_name" if party_type == "customer" else "supplier_name"
	m = re.search(
		r"(?:named|name|called|ka naam|naam)[:]?\s*([^,;.]+?)(?:\s*(?:group|mobile|phone|email|contact)\b|,|;|$)",
		p,
		re.I,
	)
	if not m:
		m = re.search(
			r"(?:add|create|banao|banaiye)\s*(?:a\s+|new\s+)?(?:customer|client|supplier|vendor)[:\-]?\s*([A-Za-z][A-Za-z0-9 .&\-]{2,40}?)(?=\s+(?:group|mobile|phone|email|contact)\b|,|;|$)",
			p,
			re.I,
		)
	if m:
		data[field] = m.group(1).strip().rstrip(",").strip()
	# Mobile
	m = re.search(r"(?:mobile|phone|contact|number)[:]?\s*([0-9+\-() ]{7,15})", p, re.I)
	if m:
		data["mobile_no"] = m.group(1).strip()
	# Email
	m = re.search(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", p)
	if m:
		data["email"] = m.group(1).strip()
	# Group
	m = re.search(r"(?:group|category)[:]?\s*([^,;.]+)", p, re.I)
	if m:
		data[f"{party_type}_group"] = m.group(1).strip()
	return data


# =============================================================================
# MISSING FIELDS CHECK
# =============================================================================


def safe_parse_json(payload, label="payload"):
	"""Parse JSON safely without crashing the workflow on bad model output."""
	if not payload:
		return None
	if isinstance(payload, (dict, list)):
		return payload
	if isinstance(payload, str):
		try:
			return json.loads(payload)
		except ValueError as exc:
			log_error_safely("erp_ai: invalid %s" % label, str(exc))
			return None
	return None


def get_missing_fields(doctype, data):
	"""Check which required fields are still missing/empty.

	A field is treated as missing when it is absent, empty, or an empty
	collection for fields that must contain at least one entry.
	"""
	schema = DOCTYPE_SCHEMAS.get(doctype)
	if not schema:
		return []
	missing = []
	required = schema.get("required", [])
	for field in required:
		val = data.get(field)
		if val is None or val == "" or (field == "items" and not val):
			missing.append(field)
	return missing


def get_missing_labels(doctype, missing_fields):
	"""Get human-readable labels for missing fields."""
	schema = DOCTYPE_SCHEMAS.get(doctype)
	if not schema:
		return missing_fields
	labels = schema.get("labels", {})
	return [labels.get(f, f.replace("_", " ").title()) for f in missing_fields]


# =============================================================================
# PREVIEW GENERATOR
# =============================================================================


def generate_preview_hash(doctype, draft_data):
	"""Stable hash for the proposed action preview.

	This is used to detect drift between the preview shown to the user and
	the data actually confirmed. Only the fields that matter for execution
	should influence the hash.
	"""
	relevant = {}
	schema = DOCTYPE_SCHEMAS.get(doctype, {})
	for field in schema.get("required", []) + schema.get("optional", []):
		val = draft_data.get(field)
		if val is not None:
			relevant[field] = val
	payload = json.dumps(
		{"doctype": doctype, "data": relevant},
		sort_keys=True,
		default=str,
	)
	# Deterministic hash required: frappe.generate_hash() ignores its txt
	# argument and always returns a random token, which would make every
	# preview hash unique and break the drift check between preview and
	# confirmation.
	return frappe.utils.sha256_hash(payload)[:16]


def generate_preview(doctype, data):
	"""Generate a human-readable preview."""
	schema = DOCTYPE_SCHEMAS.get(doctype, {})
	labels = schema.get("labels", {})
	lines = []

	if doctype == "Item":
		lines.append("📦 New Item Preview:")
		lines.append("  Name: %s" % data.get("item_name", "-"))
		lines.append("  Group: %s" % data.get("item_group", "Products"))
		rate = data.get("standard_rate", 0)
		if isinstance(rate, float) and rate < 1:
			lines.append("  Price: %.4f" % rate)
		else:
			lines.append("  Price: %s" % format(rate, ",.0f"))
		lines.append("  UOM: %s" % data.get("stock_uom", "Nos"))
		if data.get("opening_stock"):
			lines.append("  Opening Stock: %s" % format(data["opening_stock"], ",.0f"))

	elif doctype == "Sales Invoice":
		lines.append("🧾 Sales Invoice Preview:")
		lines.append("  Customer: %s" % data.get("customer", "-"))
		lines.append("  Items:")
		for i, it in enumerate(data.get("items", []), 1):
			qty = it.get("qty", 1)
			rate = it.get("rate", 0)
			total = qty * rate
			desc = it.get("description", it.get("item_code", "-"))
			lines.append(
				"    %d. %s — %g × %s = %s"
				% (
					i,
					desc,
					qty,
					format(rate, ",.0f"),
					format(total, ",.0f"),
				)
			)
		subtotal = sum(it.get("qty", 1) * it.get("rate", 0) for it in data.get("items", []))
		lines.append("  Subtotal: %s" % format(subtotal, ",.0f"))
		if data.get("discount_percent"):
			disc = subtotal * data["discount_percent"] / 100.0
			lines.append("  Discount (%s%%): -%s" % (data["discount_percent"], format(disc, ",.0f")))
			lines.append("  Total: %s" % format(subtotal - disc, ",.0f"))
		else:
			lines.append("  Total: %s" % format(subtotal, ",.0f"))

	elif doctype == "Purchase Invoice":
		lines.append("📋 Purchase Invoice Preview:")
		lines.append("  Supplier: %s" % data.get("supplier", "-"))
		lines.append("  Items:")
		for i, it in enumerate(data.get("items", []), 1):
			qty = it.get("qty", 1)
			rate = it.get("rate", 0)
			total = qty * rate
			desc = it.get("description", it.get("item_code", "-"))
			lines.append(
				"    %d. %s — %g × %s = %s"
				% (
					i,
					desc,
					qty,
					format(rate, ",.0f"),
					format(total, ",.0f"),
				)
			)
		subtotal = sum(it.get("qty", 1) * it.get("rate", 0) for it in data.get("items", []))
		lines.append("  Subtotal: %s" % format(subtotal, ",.0f"))
		if data.get("discount_percent"):
			disc = subtotal * data["discount_percent"] / 100.0
			lines.append("  Discount (%s%%): -%s" % (data["discount_percent"], format(disc, ",.0f")))
			lines.append("  Total: %s" % format(subtotal - disc, ",.0f"))
		else:
			lines.append("  Total: %s" % format(subtotal, ",.0f"))

	elif doctype == "Customer":
		lines.append("👤 New Customer Preview:")
		lines.append("  Name: %s" % data.get("customer_name", "-"))
		if data.get("mobile_no"):
			lines.append("  Mobile: %s" % data["mobile_no"])
		if data.get("email"):
			lines.append("  Email: %s" % data["email"])
		if data.get("customer_group"):
			lines.append("  Group: %s" % data["customer_group"])

	elif doctype == "Supplier":
		lines.append("🏭 New Supplier Preview:")
		lines.append("  Name: %s" % data.get("supplier_name", "-"))
		if data.get("mobile_no"):
			lines.append("  Mobile: %s" % data["mobile_no"])
		if data.get("email"):
			lines.append("  Email: %s" % data["email"])
		if data.get("supplier_group"):
			lines.append("  Group: %s" % data["supplier_group"])

	else:
		lines.append("📄 %s Preview:" % doctype)
		for k, v in data.items():
			label = labels.get(k, k.replace("_", " ").title())
			lines.append("  %s: %s" % (label, v))

	return "\n".join(lines)


# =============================================================================
# INTENT DETECTION → DOCTYPE
# =============================================================================

INTENT_MAP = {
	"create item": "Item",
	"add item": "Item",
	"item banao": "Item",
	"item banaiye": "Item",
	"item create": "Item",
	"item add": "Item",
	"new item": "Item",
	"nyaa item": "Item",
	"create sales invoice": "Sales Invoice",
	"add invoice": "Sales Invoice",
	"invoice banao": "Sales Invoice",
	"invoice banaiye": "Sales Invoice",
	"make invoice": "Sales Invoice",
	"bill banao": "Sales Invoice",
	"create sales order": "Sales Order",
	"add sales order": "Sales Order",
	"sales order banao": "Sales Order",
	"create purchase order": "Purchase Order",
	"add purchase order": "Purchase Order",
	"purchase order banao": "Purchase Order",
	"purchase order banaiye": "Purchase Order",
	"make purchase order": "Purchase Order",
	"create po": "Purchase Order",
	"add po": "Purchase Order",
	"po banao": "Purchase Order",
	"po banaiye": "Purchase Order",
	"make po": "Purchase Order",
	"create purchase receipt": "Purchase Receipt",
	"add purchase receipt": "Purchase Receipt",
	"purchase receipt banao": "Purchase Receipt",
	"purcahse receipt banaiye": "Purchase Receipt",
	"create purchase invoice": "Purchase Invoice",
	"add purchase invoice": "Purchase Invoice",
	"purchase invoice banao": "Purchase Invoice",
	"purchase invoice banaiye": "Purchase Invoice",
	"make purchase invoice": "Purchase Invoice",
	"make a purchase invoice": "Purchase Invoice",
	"create a purchase invoice": "Purchase Invoice",
	"add a purchase invoice": "Purchase Invoice",
	"make sales invoice": "Sales Invoice",
	"make a sales invoice": "Sales Invoice",
	"create a sales invoice": "Sales Invoice",
	"add a sales invoice": "Sales Invoice",
	"create customer": "Customer",
	"add customer": "Customer",
	"customer banao": "Customer",
	"customer banaiye": "Customer",
	"new customer": "Customer",
	"create supplier": "Supplier",
	"add supplier": "Supplier",
	"supplier banao": "Supplier",
	"supplier banaiye": "Supplier",
	"new supplier": "Supplier",
	"vendor banao": "Supplier",
	"create payment": "Payment Entry",
	"add payment": "Payment Entry",
	"payment banao": "Payment Entry",
	"payment banaiye": "Payment Entry",
	"receive payment": "Payment Entry",
	"make payment": "Payment Entry",
}


def detect_intent(prompt):
	pl = prompt.lower().strip()
	# Sort keys longest-first so more specific phrases (e.g. "purchase invoice")
	# match before shorter ones (e.g. "invoice" or "po").
	for kw, doctype in sorted(INTENT_MAP.items(), key=lambda item: -len(item[0])):
		if kw in pl:
			return doctype
	if re.search(r"\b(add|create|banao|banaiye)\b.*\b(item|product|itm)\b", pl):
		return "Item"
	if re.search(r"\b(add|create|banao|banaiye|make)\b.*\b(invoice|bill)\b", pl):
		if re.search(r"\b(purchase|supplier|vendor|buy)\b", pl):
			return "Purchase Invoice"
		return "Sales Invoice"
	if re.search(r"\b(add|create|banao|banaiye)\b.*\b(customer|client)\b", pl):
		return "Customer"
	if re.search(r"\b(add|create|banao|banaiye)\b.*\b(supplier|vendor)\b", pl):
		return "Supplier"
	if re.search(r"\b(payment|receive|paid|pay)\b", pl) and re.search(r"\b(from|to|se|ko)\b", pl):
		return "Payment Entry"
	# Item arrival: "resived 20 leter", "recived 100 kg", "aa gaya 50 liter"
	if re.search(
		r"\b(resived|recived|resiv|reciv|aa gaya|aagya|milay|mile)\b.+\b(kg|liter|litre|leters|liters|gram|gm|ml|mm|meter|inch|leter)\b",
		pl,
	):
		return "Item"
	# Stock with qty and price: "20 leter price", "100 kg rate"
	if re.search(
		r"\b\d+\s*(kg|liter|litre|leters|liters|gram|gm|ml|mm|meter|inch|leter)\b.+\b(price|rate|cost|keemat)\b",
		pl,
	):
		return "Item"
	# "po" alone → Purchase Order (explicit). "purchase" alone is ambiguous → None (clarification needed)
	if re.search(r"\b(add|create|banao|banaiye|make)\b.*\bpo\b", pl) and not re.search(
		r"\b(invoice|receipt|order)\b", pl
	):
		return "Purchase Order"
	# bare "purchase" or "buy" with no document type → ambiguous, return None for clarification
	return None


# =============================================================================
# ENTITY RESOLUTION (exact + fuzzy, with user selection)
# =============================================================================


def _scoped_read(doctype, filters, fields, limit=1):
	"""Permission-aware read used by entity resolution.

	``frappe.db.get_value``/``frappe.db.get_all`` apply no permissions at all,
	so a user restricted by User Permissions (company, item, warehouse, ...)
	could resolve and read documents outside their scope. ``frappe.get_list``
	applies the role check and the row-level filters; a DocType the user may
	not read yields no candidates instead of an exception, so resolution fails
	closed with a clarification instead of leaking a name.
	"""
	try:
		return frappe.get_list(doctype, filters=filters, fields=fields, limit_page_length=limit)
	except frappe.PermissionError:
		return []


def resolve_item(name, mcp=None, limit=5):
	"""Resolve an item name/code to ERPNext Item records.

	Tries exact code match first, then fuzzy name search. Returns a list of
	candidate dicts with name, item_code, item_name, stock_uom, standard_rate.
	Caller should present candidates and ask user to pick when multiple match.
	"""
	if not name:
		return []
	if mcp is None:
		mcp = FrappeMCP()
	# 1. Exact code match
	code = name.strip().upper()
	by_code = _scoped_read(
		"Item", {"item_code": code}, ["name", "item_code", "item_name", "stock_uom", "standard_rate"]
	)
	if by_code:
		return by_code
	# 2. Exact item_name match
	by_name = _scoped_read(
		"Item", {"item_name": name.strip()}, ["name", "item_code", "item_name", "stock_uom", "standard_rate"]
	)
	if by_name:
		return by_name
	# 3. Fuzzy search via MCP (now permission-safe)
	found = mcp.call_tool("search_documents", {"query": name, "doctype": "Item", "limit": limit})
	results = found.get("results", [])
	candidates = []
	for r in results:
		candidates.extend(
			_scoped_read(
				"Item",
				{"name": r["name"]},
				["name", "item_code", "item_name", "stock_uom", "standard_rate", "is_stock_item"],
			)
		)
	# 4. Fallback: try partial name match
	if not candidates:
		like = "%" + name.strip() + "%"
		candidates = _scoped_read(
			"Item",
			{"item_name": ["like", like]},
			["name", "item_code", "item_name", "stock_uom", "standard_rate", "is_stock_item"],
			limit,
		)
	return candidates


def resolve_party(name, doctype, mcp=None, limit=5):
	"""Resolve a customer/supplier name to ERPNext party records.

	doctype: 'Customer' or 'Supplier'
	Returns list of candidate dicts with name, customer_name/supplier_name.
	"""
	if not name:
		return []
	if mcp is None:
		mcp = FrappeMCP()
	field = "customer_name" if doctype == "Customer" else "supplier_name"
	# 1. Exact match
	by_name = _scoped_read(doctype, {field: name.strip()}, ["name", field])
	if by_name:
		return by_name
	# 2. Fuzzy search
	found = mcp.call_tool("search_documents", {"query": name, "doctype": doctype, "limit": limit})
	results = found.get("results", [])
	candidates = []
	for r in results:
		candidates.extend(_scoped_read(doctype, {"name": r["name"]}, ["name", field]))
	# 3. Partial match fallback
	if not candidates:
		like = "%" + name.strip() + "%"
		candidates = _scoped_read(doctype, {field: ["like", like]}, ["name", field], limit)
	return candidates


def pick_candidate(candidates, label="record", key="name"):
	"""Return a human-readable candidate list string for the user to choose from.

	Caller parses the user's selection index and picks the matching candidate.
	"""
	if not candidates:
		return None
	if len(candidates) == 1:
		return candidates[0]
	lines = [f"Multiple {label} found. Please pick one:"]
	for i, c in enumerate(candidates, 1):
		name_val = c.get(key, c.get("item_code", c.get("customer_name", c.get("supplier_name", "-"))))
		extra = c.get("item_name") or c.get("customer_name") or c.get("supplier_name") or ""
		lines.append(f"  {i}. {name_val}" + (f" ({extra})" if extra and extra != name_val else ""))
	return {"_candidates": candidates, "_prompt": "\n".join(lines)}


# =============================================================================
# CLARIFICATION QUESTIONS
# =============================================================================


def clarification_needed(intent, data, missing_fields):
	"""Return a clarification question string if the intent is ambiguous or
	critical fields are missing, else None."""
	if not intent:
		return None
	questions = []
	# Ambiguous purchase intent — user said "purchase" or "buy" without specifying
	if intent == "Purchase Invoice" and not data.get("supplier") and not data.get("items"):
		questions.append("Did you mean a Purchase Order, Purchase Receipt, or Purchase Invoice?")
	# Missing required fields
	for mf in missing_fields:
		questions.append(f"I still need: {mf}")
	return "\n".join(questions) if questions else None


# =============================================================================
# DOCUMENT CREATION
# =============================================================================


def create_document_from_draft(doctype, data, mcp):
	"""Create an ERP document from a draft.

	Does NOT commit: the caller's transaction boundary (confirm_draft) is the
	single commit point so multi-step workflows are atomic from the caller's
	perspective. Returns the create_document result dict.
	"""
	schema = DOCTYPE_SCHEMAS.get(doctype, {})
	defaults = schema.get("defaults", {})
	for k, v in defaults.items():
		if k not in data or data[k] is None:
			data[k] = v
	if doctype == "Item":
		result = _create_item_doc(data, mcp)
	elif doctype == "Sales Invoice":
		result = _create_sales_invoice_doc(data, mcp)
	elif doctype == "Purchase Invoice":
		result = _create_purchase_invoice_doc(data, mcp)
	elif doctype == "Customer":
		result = _create_customer_doc(data, mcp)
	elif doctype == "Supplier":
		result = _create_supplier_doc(data, mcp)
	elif doctype == "Payment Entry":
		result = _create_payment_entry_doc(data, mcp)
	elif doctype == "Purchase Receipt":
		result = _create_purchase_receipt_doc(data, mcp)
	elif doctype in DOCTYPE_SCHEMAS:
		# Generic, schema-driven creation covers every registry doctype
		# (BOM, Work Order, Job Card, Quality Inspection, Asset*, Employee,
		# Project, Task, RFQ, ...). Field names are verified against live
		# metadata by the integration tests.
		result = _create_generic_doc(doctype, data, mcp)
	else:
		return {"error": f"Unsupported doctype: {doctype}"}
	return result


def _create_generic_doc(doctype, data, mcp):
	"""Create any registry doctype from its schema: map known fields, apply
	child tables, and hand off to the permission-checked MCP create tool."""
	schema = DOCTYPE_SCHEMAS.get(doctype, {})
	allowed = set(schema.get("required", []) + schema.get("optional", []))
	doc_data = {"doctype": doctype}
	for key in allowed:
		val = data.get(key)
		if val not in (None, ""):
			doc_data[key] = val
	child = schema.get("child_table")
	if child:
		rows = data.get(child["fieldname"])
		if isinstance(rows, list) and rows:
			allowed_child = set(child.get("required", []) + child.get("optional", []))
			doc_data[child["fieldname"]] = [
				{k: v for k, v in row.items() if k in allowed_child and v not in (None, "")} for row in rows
			]
	result = mcp.call_tool("create_document", {"doctype": doctype, "data": doc_data})
	if isinstance(result, dict) and not result.get("error") and result.get("name"):
		result["print_url"] = (
			"/api/method/frappe.utils.print_format.download_pdf"
			"?doctype=%s&name=%s&format=Standard"
			% (frappe.utils.quote(doctype), frappe.utils.quote(result["name"]))
		)
	return result


def _create_purchase_receipt_doc(data, mcp):
	"""Create a Purchase Receipt with required ERPNext fields populated."""
	import frappe

	schema = DOCTYPE_SCHEMAS.get("Purchase Receipt", {})
	allowed = set(schema.get("required", []) + schema.get("optional", []))
	doc_data = {"doctype": "Purchase Receipt"}
	for key in allowed:
		val = data.get(key)
		if val not in (None, ""):
			doc_data[key] = val
	child = schema.get("child_table")
	if child:
		rows = data.get(child["fieldname"])
		if isinstance(rows, list) and rows:
			allowed_child = set(child.get("required", []) + child.get("optional", []))
			doc_data[child["fieldname"]] = [
				{k: v for k, v in row.items() if k in allowed_child and v not in (None, "")} for row in rows
			]
			# Workflow drafts (e.g. "received 2 x SKU at warehouse X") carry the
			# target warehouse at the top level, but a Purchase Receipt stores it
			# on each row — push it down when the row omits it, or ERPNext
			# rejects the row with "Warehouse is mandatory for stock Item".
			top_warehouse = data.get("warehouse")
			if top_warehouse:
				for row in doc_data[child["fieldname"]]:
					row.setdefault("warehouse", top_warehouse)
	# Ensure supplier exists
	supplier = doc_data.get("supplier")
	if supplier:
		supplier_exists = mcp.call_tool(
			"query_doctype", {"doctype": "Supplier", "filters": {"supplier_name": supplier}}
		)
		if supplier_exists.get("count", 0) == 0:
			try:
				# Ensure supplier group exists
				if not frappe.db.exists("Supplier Group", "All Supplier Groups"):
					frappe.get_doc(
						{
							"doctype": "Supplier Group",
							"supplier_group_name": "All Supplier Groups",
							"is_group": 1,
						}
					).insert()
				# Build supplier data with mandatory custom fields
				supplier_data = {
					"doctype": "Supplier",
					"supplier_name": supplier,
					"supplier_type": "Company",
					"supplier_group": "All Supplier Groups",
				}
				# Provide placeholder for mandatory custom fields (e.g. FBR NTN/CNIC)
				meta = frappe.get_meta("Supplier")
				for df in meta.fields:
					if (
						df.reqd
						and df.fieldname not in supplier_data
						and df.fieldname not in ("naming_series", "supplier_name")
					):
						if df.fieldname in ("fbr_ntn_cnic", "ntn", "cnic"):
							supplier_data[df.fieldname] = "0000000"
						elif df.fieldtype in ("Data", "Int", "Check"):
							supplier_data[df.fieldname] = ""
						elif df.fieldtype == "Select":
							supplier_data[df.fieldname] = "No"
				frappe.get_doc(supplier_data).insert()
			except Exception as e:
				frappe.log_error("erp_ai: supplier creation failed", str(e))
	# Ensure items exist
	for item in doc_data.get("items", []):
		item_code = item.get("item_code")
		if item_code and not frappe.db.exists("Item", item_code):
			try:
				item_data = {
					"doctype": "Item",
					"item_code": item_code,
					"item_name": item_code,
					"item_group": "Products",
					"stock_uom": "Nos",
					"is_stock_item": 1,
				}
				# Provide placeholder for mandatory custom fields
				meta = frappe.get_meta("Item")
				for df in meta.fields:
					if (
						df.reqd
						and df.fieldname not in item_data
						and df.fieldname not in ("naming_series", "item_name", "item_code")
					):
						if df.fieldtype in ("Data", "Int", "Check"):
							item_data[df.fieldname] = ""
						elif df.fieldtype == "Select":
							item_data[df.fieldname] = "No"
				frappe.get_doc(item_data).insert()
			except Exception as e:
				frappe.log_error("erp_ai: item creation failed", str(e))
	# Populate required ERPNext fields that are not in our schema
	company = doc_data.get("company") or frappe.defaults.get_global_default("company")
	doc_data["company"] = company
	currency = frappe.defaults.get_global_default("currency") or company
	doc_data["currency"] = currency
	doc_data["price_list_currency"] = currency
	doc_data["exchange_rate"] = 1.0
	doc_data["conversion_rate"] = 1.0
	# Compute net_total from items
	net_total = sum(
		(item.get("qty", 0) or 0) * (item.get("rate", 0) or 0) for item in doc_data.get("items", [])
	)
	doc_data["net_total"] = net_total
	doc_data["base_net_total"] = net_total
	doc_data["net_total_in_words"] = ""
	result = mcp.call_tool("create_document", {"doctype": "Purchase Receipt", "data": doc_data})
	if isinstance(result, dict) and not result.get("error") and result.get("name"):
		result["print_url"] = (
			"/api/method/frappe.utils.print_format.download_pdf"
			"?doctype=%s&name=%s&format=Standard"
			% (frappe.utils.quote("Purchase Receipt"), frappe.utils.quote(result["name"]))
		)
	return result


def _create_item_doc(data, mcp):
	item_name = data.get("item_name", "").strip()
	if not item_name:
		return {"error": "item_name required"}
	existing = frappe.db.get_value("Item", {"item_name": item_name}, "name")
	if existing:
		return {"error": f"Item '{item_name}' already exists ({existing})", "duplicate": True}
	code = item_name.replace(" ", "-").upper()
	ig = data.get("item_group", "Products")
	uom = data.get("stock_uom", "Nos")
	if not frappe.db.exists("Item Group", ig):
		try:
			frappe.get_doc({"doctype": "Item Group", "item_group_name": ig}).insert()
		except Exception:
			pass
	doc_data = {
		"doctype": "Item",
		"item_code": code,
		"item_name": item_name,
		"item_group": ig,
		"stock_uom": uom,
		"is_stock_item": data.get("is_stock_item", 1),
		"standard_rate": data.get("standard_rate", 0),
	}
	# Optional Item fields the operator tool advertises. They were dropped here
	# before, so a caller-supplied description/valuation rate vanished silently.
	for opt in ("description", "valuation_rate"):
		if data.get(opt) not in (None, ""):
			doc_data[opt] = data[opt]
	result = mcp.call_tool("create_document", {"doctype": "Item", "data": doc_data})
	if "error" in result:
		doc_data["item_code"] = code + "-" + frappe.generate_hash(length=4).upper()
		result = mcp.call_tool("create_document", {"doctype": "Item", "data": doc_data})
	if "error" in result:
		return result
	if data.get("opening_stock"):
		wh = "Stores - SPI" if frappe.db.exists("Warehouse", "Stores - SPI") else "Stores"
		se = mcp.call_tool(
			"create_document",
			{
				"doctype": "Stock Entry",
				"data": {
					"doctype": "Stock Entry",
					"stock_entry_type": "Material Receipt",
					"company": frappe.defaults.get_global_default("company"),
					"items": [
						{
							"item_code": result["name"],
							"qty": data["opening_stock"],
							"t_warehouse": wh,
							"basic_rate": data.get("standard_rate", 0),
						}
					],
				},
			},
		)
		if "error" not in se:
			result["stock_entry"] = se.get("name")
	return result


def _create_sales_invoice_doc(data, mcp):
	customer = data.get("customer")
	if not customer:
		return {"error": "customer required"}
	items = data.get("items", [])
	if not items:
		return {"error": "items required"}
	exists = mcp.call_tool("query_doctype", {"doctype": "Customer", "filters": {"name": customer}})
	if exists.get("count", 0) == 0:
		return {"error": f"Customer '{customer}' not found"}
	final_items = []
	for it in items:
		desc = it.get("description", it.get("item_code", ""))
		found = mcp.call_tool("search_documents", {"query": desc, "doctype": "Item", "limit": 1})
		res = found.get("results", [])
		code = res[0]["name"] if res else desc
		final_items.append({"item_code": code, "qty": it.get("qty", 1), "rate": it.get("rate", 0)})
	si_data = {
		"doctype": "Sales Invoice",
		"customer": customer,
		"company": frappe.defaults.get_global_default("company"),
		"update_stock": 1 if data.get("update_stock") else 0,
		"items": final_items,
	}
	if data.get("taxes_and_charges"):
		si_data["taxes_and_charges"] = data["taxes_and_charges"]
	result = mcp.call_tool("create_document", {"doctype": "Sales Invoice", "data": si_data})
	if "error" in result:
		return result
	result["print_url"] = (
		f"/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Invoice&name={result.get('name')}&format=Standard"
	)
	return result


def _create_purchase_invoice_doc(data, mcp):
	supplier = data.get("supplier")
	if not supplier:
		return {"error": "supplier required"}
	items = data.get("items", [])
	if not items:
		return {"error": "items required"}
	exists = mcp.call_tool("query_doctype", {"doctype": "Supplier", "filters": {"name": supplier}})
	if exists.get("count", 0) == 0:
		return {"error": f"Supplier '{supplier}' not found"}
	final_items = []
	for it in items:
		desc = it.get("description", it.get("item_code", ""))
		found = mcp.call_tool("search_documents", {"query": desc, "doctype": "Item", "limit": 1})
		res = found.get("results", [])
		code = res[0]["name"] if res else desc
		final_items.append({"item_code": code, "qty": it.get("qty", 1), "rate": it.get("rate", 0)})
	pi_data = {
		"doctype": "Purchase Invoice",
		"supplier": supplier,
		"company": frappe.defaults.get_global_default("company"),
		"update_stock": 1 if data.get("update_stock") else 0,
		"items": final_items,
	}
	if data.get("taxes_and_charges"):
		pi_data["taxes_and_charges"] = data["taxes_and_charges"]
	result = mcp.call_tool("create_document", {"doctype": "Purchase Invoice", "data": pi_data})
	if "error" in result:
		return result
	result["print_url"] = (
		f"/api/method/frappe.utils.print_format.download_pdf?doctype=Purchase%20Invoice&name={result.get('name')}&format=Standard"
	)
	return result


def _resolve_customer_group(preferred=None):
	"""Return a valid non-group Customer Group (ERPNext rejects group nodes)."""
	if preferred and frappe.db.get_value("Customer Group", preferred, "is_group") == 0:
		return preferred
	try:
		default = frappe.db.get_single_value("Selling Settings", "customer_group")
	except Exception:
		default = None
	if default and frappe.db.get_value("Customer Group", default, "is_group") == 0:
		return default
	return frappe.db.get_value("Customer Group", {"is_group": 0}, "name", order_by="lft asc")


def _resolve_territory(preferred=None):
	"""Return a valid non-group Territory."""
	if preferred and frappe.db.get_value("Territory", preferred, "is_group") == 0:
		return preferred
	try:
		default = frappe.db.get_single_value("Selling Settings", "territory")
	except Exception:
		default = None
	if default and frappe.db.get_value("Territory", default, "is_group") == 0:
		return default
	return frappe.db.get_value("Territory", {"is_group": 0}, "name", order_by="lft asc")


def _resolve_supplier_group(preferred=None):
	"""Return a valid non-group Supplier Group."""
	if preferred and frappe.db.get_value("Supplier Group", preferred, "is_group") == 0:
		return preferred
	try:
		default = frappe.db.get_single_value("Buying Settings", "supplier_group")
	except Exception:
		default = None
	if default and frappe.db.get_value("Supplier Group", default, "is_group") == 0:
		return default
	return frappe.db.get_value("Supplier Group", {"is_group": 0}, "name", order_by="lft asc")


def _create_customer_doc(data, mcp):
	name = data.get("customer_name", "").strip()
	if not name:
		return {"error": "customer_name required"}
	doc_data = {
		"doctype": "Customer",
		"customer_name": name,
		"customer_group": _resolve_customer_group(data.get("customer_group")) or "All Customer Groups",
		"territory": _resolve_territory(data.get("territory")) or "All Territories",
	}
	if data.get("mobile_no"):
		doc_data["mobile_no"] = data["mobile_no"]
	if data.get("email"):
		doc_data["email_id"] = data["email"]
	for opt in ("customer_type", "default_currency", "website"):
		if data.get(opt) not in (None, ""):
			doc_data[opt] = data[opt]
	result = mcp.call_tool("create_document", {"doctype": "Customer", "data": doc_data})
	return result


def _create_supplier_doc(data, mcp):
	name = data.get("supplier_name", "").strip()
	if not name:
		return {"error": "supplier_name required"}
	doc_data = {
		"doctype": "Supplier",
		"supplier_name": name,
		"supplier_group": _resolve_supplier_group(data.get("supplier_group")) or "All Supplier Groups",
	}
	if data.get("mobile_no"):
		doc_data["mobile_no"] = data["mobile_no"]
	if data.get("email"):
		doc_data["email_id"] = data["email"]
	for opt in ("country", "default_currency", "website"):
		if data.get(opt) not in (None, ""):
			doc_data[opt] = data[opt]
	result = mcp.call_tool("create_document", {"doctype": "Supplier", "data": doc_data})
	return result


def _create_payment_entry_doc(data, mcp):
	party = data.get("party")
	amount = data.get("paid_amount", 0)
	if not party or not amount:
		return {"error": "party and paid_amount required"}
	doc_data = {
		"doctype": "Payment Entry",
		"payment_type": data.get("payment_type", "Receive"),
		"party_type": data.get("party_type", "Customer"),
		"party": party,
		"paid_amount": amount,
		"received_amount": data.get("received_amount", amount),
		"company": frappe.defaults.get_global_default("company"),
	}
	if data.get("reference_no"):
		doc_data["reference_no"] = data["reference_no"]
	result = mcp.call_tool("create_document", {"doctype": "Payment Entry", "data": doc_data})
	return result
