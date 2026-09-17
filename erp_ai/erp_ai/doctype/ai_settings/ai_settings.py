import frappe
from frappe.model.document import Document


class AISettings(Document):
	def validate(self):
		"""Refuse to store a configuration the assistant cannot run with.

		The LLM backend is site state, and a missing value used to surface
		mid-chat as an unexplained auth or connection error. Enforcement belongs
		at the settings boundary instead (audit point 14: missing runtime
		configuration is a release blocker, not a silent degradation).

		``get_provider_models`` / ``fetch_ollama_models`` lived here as two more
		whitelisted copies of ``erp_ai.api.list_available_models`` (which the
		settings form calls, and which is permission-gated); both had no callers
		and have been deleted (audit points 5/11).
		"""
		from erp_ai.llm import validate_deployment_settings

		problem = validate_deployment_settings(self)
		if problem:
			frappe.throw(problem, title="AI Settings")
