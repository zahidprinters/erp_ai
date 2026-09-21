# ---------------------------------------------------------------------------
# Scheduled maintenance for ERP AI.
#
# Registered in hooks.scheduler_events. Every function here is idempotent and
# bounded (batched) so a backlog cannot turn a scheduler tick into a long
# transaction. Lifecycle transitions go through the document API rather than
# raw SQL so they stay auditable and pass the transition guard in
# AIAssistantAction.validate.
# ---------------------------------------------------------------------------
import frappe

ACTION_DOCTYPE = "AI Assistant Action"
BATCH_SIZE = 500


def expire_stale_actions(batch_size: int = BATCH_SIZE) -> dict:
	"""Hourly: expire unconfirmed drafts and reclaim abandoned claims.

	Two stale states exist and both must be closed out, because a stale action
	holds an idempotency key and therefore blocks the caller's retry:

	- ``pending`` past ``expires_on``: the user never confirmed it → ``expired``.
	- ``processing`` past ``expires_on``: the worker holding the claim died
	  mid-request (killed, crashed, timed out) → ``failed``, so retries work.

	Returns counts for the scheduler log.
	"""
	now = frappe.utils.now_datetime()
	counts = {"expired": 0, "reclaimed": 0}

	stale_pending = frappe.db.get_all(
		ACTION_DOCTYPE,
		filters={"status": "pending", "expires_on": ["<", now]},
		pluck="name",
		order_by="modified asc",
		limit_page_length=batch_size,
	)
	for name in stale_pending:
		if _close_action(name, "expired", "Expired before confirmation"):
			counts["expired"] += 1

	stale_processing = frappe.db.get_all(
		ACTION_DOCTYPE,
		filters={"status": "processing", "expires_on": ["<", now]},
		pluck="name",
		order_by="modified asc",
		limit_page_length=batch_size,
	)
	for name in stale_processing:
		if _close_action(name, "failed", "Abandoned mid-execution (stale claim)"):
			counts["reclaimed"] += 1

	frappe.db.commit()
	if counts["expired"] or counts["reclaimed"]:
		frappe.logger("erp_ai").info(
			"erp_ai: expire_stale_actions expired=%s reclaimed=%s" % (counts["expired"], counts["reclaimed"])
		)
	return counts


def _close_action(name: str, status: str, reason: str) -> bool:
	"""Move one action into a terminal state; returns False if it was skipped.

	Per-row isolation: one unreadable row must not abort the batch, and losing a
	race against the user's own confirm/cancel is not an error.
	"""
	try:
		action = frappe.get_doc(ACTION_DOCTYPE, name)
		if action.status not in ("pending", "processing"):
			return False
		action.status = status
		if status == "failed" and not action.failure_reason:
			action.failure_reason = reason
		action.save(ignore_permissions=True)
		return True
	except Exception:
		frappe.log_error(
			frappe.get_traceback(),
			"erp_ai.tasks: could not close %s as %s" % (name, status),
		)
		return False


def cleanup_expired_actions(days: int = 30, batch_size: int = BATCH_SIZE) -> dict:
	"""Daily: delete closed actions older than ``days``.

	Only terminal, already-audited rows are removed (completed/failed/expired/
	cancelled). Completed actions are kept by default because their
	``rollback_reference`` is the audit pointer back to the created document —
	raise ``days`` rather than expect instant deletion.
	"""
	cutoff = frappe.utils.add_days(frappe.utils.now_datetime(), -abs(days))
	stale = frappe.db.get_all(
		ACTION_DOCTYPE,
		filters={
			"status": ["in", ["failed", "expired", "cancelled"]],
			"modified": ["<", cutoff],
		},
		pluck="name",
		order_by="modified asc",
		limit_page_length=batch_size,
	)
	for name in stale:
		try:
			frappe.delete_doc(ACTION_DOCTYPE, name, ignore_permissions=True, force=True)
		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				"erp_ai.tasks: could not delete action %s" % name,
			)
	frappe.db.commit()
	return {"deleted": len(stale)}


PATTERN_DOCTYPE = "AI Behavior Pattern"
ARTICLE_DOCTYPE = "AI Help Article"
FAIL_THRESHOLD = 5


def refresh_behavior_patterns() -> dict:
	"""Daily: materialize org-level behavior aggregates into AI Behavior Pattern.

	``prompt_block`` reads those rows when they are fresh (<26h) instead of
	scanning the live event log, so chat stays O(10 rows) however big the log
	grows. Counts only — raw prompts never enter this table; one truncated
	failure reason per intent is kept for the admin's benefit.
	"""
	from erp_ai.erp_ai.doctype.ai_user_behavior import ai_user_behavior as behavior

	patterns = behavior.get_org_patterns()
	merged: dict = {}
	for row in patterns.get("top_intents", []):
		if row.get("intent"):
			merged.setdefault(row["intent"], {"use": 0, "fail": 0, "corr": 0})["use"] = int(row["n"])
	for row in patterns.get("failure_intents", []):
		if row.get("intent"):
			merged.setdefault(row["intent"], {"use": 0, "fail": 0, "corr": 0})["fail"] = int(row["n"])
	for row in patterns.get("corrected", []):
		if row.get("intent"):
			merged.setdefault(row["intent"], {"use": 0, "fail": 0, "corr": 0})["corr"] = int(
				row.get("corrections") or 0
			)
	samples = {}
	for row in patterns.get("recent_failures", []):
		if row.get("intent") and row.get("failure_reason") and row["intent"] not in samples:
			samples[row["intent"]] = str(row["failure_reason"])[:500]

	for intent, vals in merged.items():
		try:
			name = frappe.db.exists(PATTERN_DOCTYPE, intent)
			if name:
				doc = frappe.get_doc(PATTERN_DOCTYPE, name)
			else:
				doc = frappe.get_doc({"doctype": PATTERN_DOCTYPE, "intent": intent})
			doc.use_count = vals["use"]
			doc.fail_count = vals["fail"]
			doc.correction_count = vals["corr"]
			doc.sample_failure = samples.get(intent)
			if name:
				doc.save(ignore_permissions=True)
			else:
				doc.insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				"erp_ai.tasks: could not refresh pattern %s" % intent,
			)

	stale = [name for name in frappe.get_all(PATTERN_DOCTYPE, pluck="name") if name not in merged]
	for name in stale:
		try:
			frappe.delete_doc(PATTERN_DOCTYPE, name, ignore_permissions=True, force=True)
		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				"erp_ai.tasks: could not drop stale pattern %s" % name,
			)

	behavior.reset_patterns_cache()
	frappe.db.commit()
	if merged or stale:
		frappe.logger("erp_ai").info(
			"erp_ai: refresh_behavior_patterns rows=%s stale=%s" % (len(merged), len(stale))
		)
	return {"patterns": len(merged), "stale_removed": len(stale)}


def draft_help_for_repeated_failures(threshold: int = FAIL_THRESHOLD) -> dict:
	"""Daily: turn repeatedly-failing intents into INACTIVE help-article drafts.

	Learning must not bypass humans: every draft is ``is_active=0`` and
	keyworded ``ai-auto:<intent>`` so it only exists for a human to review,
	edit, and activate. Idempotent — an intent that already has an ``ai-auto``
	draft is skipped, so the same failure cannot pile up duplicate drafts.
	"""
	try:
		from erp_ai.erp_ai.doctype.ai_user_behavior import ai_user_behavior as behavior

		candidates = [
			r
			for r in behavior.get_org_patterns().get("failure_intents", [])
			if r.get("intent") and int(r.get("n") or 0) >= threshold
		]
	except Exception:
		frappe.log_error(
			frappe.get_traceback(),
			"erp_ai.tasks: could not read failure patterns for help drafts",
		)
		return {"drafted": 0, "skipped_existing": 0, "candidates": 0}

	drafted = skipped = 0
	for row in candidates[:10]:  # bounded: a bad night cannot spam drafts
		intent = row["intent"]
		keyword = "ai-auto:%s" % intent
		try:
			# ponytail: like-match can over-match a superstring intent
			# (ai-auto:stock_issue also matches ai-auto:stock_issue_v2) — the
			# worst case is skipping a draft, never a duplicate. Upgrade path:
			# a dedicated intent field on the article once needed.
			if frappe.get_all(
				ARTICLE_DOCTYPE, filters={"keywords": ["like", keyword]}, pluck="name", limit_page_length=1
			):
				skipped += 1
				continue
			sample = frappe.get_all(
				"AI User Behavior",
				filters={"outcome": "failed", "intent": intent},
				fields=["failure_reason"],
				order_by="creation desc",
				limit_page_length=1,
			)
			reason = str((sample or [{}])[0].get("failure_reason") or "no recorded failure reason")[:400]
			frappe.get_doc(
				{
					"doctype": ARTICLE_DOCTYPE,
					"title": "[AI draft] %s keeps failing — review and fix guidance" % intent,
					"category": "Troubleshooting",
					"description": (
						"Auto-drafted from %s logged failures of intent '%s'. "
						"Edit, verify, then set Active." % (row["n"], intent)
					),
					"content": (
						"## What the assistant keeps getting wrong\n"
						"Intent: **%s** — failed **%s** times in the behavior log.\n\n"
						"Most recent failure reason (truncated):\n\n> %s\n\n"
						"## For the human reviewer\n"
						"- Reproduce the failure, then replace this section with the"
						" correct step-by-step path.\n"
						"- Delete this draft if the failures were a one-off or are"
						" already fixed.\n"
						"- Set **Active** only once the guidance is verified —"
						" inactive drafts never reach users." % (intent, row["n"], reason)
					),
					"keywords": keyword,
					"is_active": 0,
				}
			).insert(ignore_permissions=True)
			drafted += 1
		except Exception:
			frappe.log_error(
				frappe.get_traceback(),
				"erp_ai.tasks: could not draft help article for %s" % intent,
			)
	frappe.db.commit()
	if drafted or skipped:
		frappe.logger("erp_ai").info(
			"erp_ai: draft_help_for_repeated_failures drafted=%s skipped=%s" % (drafted, skipped)
		)
	return {"drafted": drafted, "skipped_existing": skipped, "candidates": len(candidates)}
