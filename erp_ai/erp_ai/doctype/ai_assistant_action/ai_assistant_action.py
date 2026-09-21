import frappe
from frappe.model.document import Document

# Terminal states: an action in one of these has finished its lifecycle.
# `pending -> processing -> completed|failed` and `pending -> expired|cancelled`
# are the only legal shapes; see the guard in validate().
TERMINAL_STATUSES = frozenset({"completed", "failed", "expired", "cancelled"})


class AIAssistantAction(Document):
	def validate(self):
		"""Enforce the one-way action lifecycle.

		Reviving a terminal action would let a second confirmation re-execute
		work that already ran — the exact double-execution the pending/processing
		claim exists to prevent — so a terminal -> non-terminal transition is
		rejected outright. Administrators needing a re-run create a new action.

		``frappe.db.get_value`` is used rather than ``self.is_new()`` because it
		is correct regardless of when the naming rule assigns ``self.name``: a
		row that does not exist yet has no previous status to protect.
		"""
		previous = frappe.db.get_value(self.doctype, self.name, "status") if self.name else None
		if not previous:
			return  # brand-new action — nothing to compare against
		if previous in TERMINAL_STATUSES and self.status not in TERMINAL_STATUSES:
			frappe.throw(
				frappe._("AI Assistant Action {0} is {1} and cannot be reopened as {2}.").format(
					self.name, previous, self.status
				)
			)

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
