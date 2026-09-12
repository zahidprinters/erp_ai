import frappe
from frappe.model.document import Document


class AIAssistantAction(Document):
    def get_preview_hash(self):
        return getattr(self, "preview_hash", None)

    def get_failure_reason(self):
        return getattr(self, "failure_reason", None)

    def get_idempotency_key(self):
        return getattr(self, "idempotency_key", None)
