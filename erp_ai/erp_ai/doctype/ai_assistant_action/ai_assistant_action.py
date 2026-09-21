import frappe
from frappe.model.document import Document

# Terminal states: an action in one of these has finished its lifecycle.
# `pending -> processing -> completed|failed` and `pending -> expired|cancelled`
# are the only legal shapes; see the guard in validate().
TERMINAL_STATUSES = frozenset({"completed", "failed", "expired", "cancelled"})


class AIAssistantAction(Document):
	# Written once at creation and never again: the identity of the action and the
	# evidence binding it to the preview the user actually saw. If any of these could
	# be edited after the fact the row would stop being evidence - a caller could
	# re-point a completed action at another session/nonce, or silently extend an
	# expired draft's confirmation window. Lifecycle fields (status, target_docname,
	# *_at, failure_reason, draft_data, rollback_reference, changed_fields) stay
	# writable because the pending -> completed|failed transition writes them.
	IMMUTABLE_FIELDS = (
		"user",
		"session_id",
		"action",
		"target_doctype",
		"nonce",
		"preview_hash",
		"expires_on",
		"idempotency_key",
		"raw_input",
		"llm_provider",
		"llm_model",
	)

	def validate(self):
		"""Enforce the one-way lifecycle and the immutable audit identity.

		Reviving a terminal action would let a second confirmation re-execute work
		that already ran - the exact double-execution the pending/processing claim
		exists to prevent - so a terminal -> non-terminal transition is rejected
		outright. Administrators needing a re-run create a new action.

		On top of that a terminal row is frozen: the recorded outcome is evidence an
		operator may later rely on, so nothing may change once the action finished.
		For pending rows the identity/evidence fields in ``IMMUTABLE_FIELDS`` are
		already frozen, so a confirmable action cannot be re-pointed at another
		session, nonce or expiry window.

		``frappe.db.get_doc`` is used rather than ``self.is_new()`` because it is
		correct regardless of when the naming rule assigns ``self.name``: a row that
		does not exist yet has no previous state to protect.
		"""
		if not self.name:
			return  # brand-new action - nothing to compare against
		try:
			previous = frappe.get_doc(self.doctype, self.name)
		except frappe.DoesNotExistError:
			return  # insert in progress - no stored state yet

		if previous.status in TERMINAL_STATUSES:
			if self.status not in TERMINAL_STATUSES:
				frappe.throw(
					frappe._("AI Assistant Action {0} is {1} and cannot be reopened as {2}.").format(
						self.name, previous.status, self.status
					)
				)
			if self._changed_fields_vs(previous):
				frappe.throw(
					frappe._(
						"AI Assistant Action {0} is {1}: a finished action is an immutable audit "
						"record and cannot be modified."
					).format(self.name, previous.status)
				)
			return

		if previous.status == "pending":
			tampered = [field for field in self.IMMUTABLE_FIELDS if self.get(field) != previous.get(field)]
			if tampered:
				frappe.throw(
					frappe._(
						"AI Assistant Action {0}: field(s) {1} can no longer be changed after creation."
					).format(self.name, ", ".join(tampered))
				)

	def _changed_fields_vs(self, previous) -> list:
		"""Field names whose value differs from the stored document."""
		changed = []
		for df in self.meta.fields:
			fieldname = df.fieldname
			if not fieldname or df.fieldtype in ("Section Break", "Column Break", "Tab Break"):
				continue
			if self.get(fieldname) != previous.get(fieldname):
				changed.append(fieldname)
		# modified/modified_by are bumped by the framework on every save and are not
		# part of the audit evidence.
		return [f for f in changed if f not in ("modified", "modified_by")]

	def __contains__(self, key):
		if hasattr(self, key):
			return True
		try:
			return frappe.db.has_column(self.doctype, key)
		except Exception:
			return False

	def get_preview_hash(self):
		return getattr(self, "preview_hash", None)

	def get_failure_reason(self):
		return getattr(self, "failure_reason", None)

	def get_idempotency_key(self):
		return getattr(self, "idempotency_key", None)
