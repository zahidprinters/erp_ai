from frappe.model.document import Document
import frappe


class AISettings(Document):
	pass


@frappe.whitelist()
def get_provider_models(provider=None):
	"""Return available models for the given provider.

	Used by the AI Settings form to populate the model dropdown dynamically
	when the user changes the LLM Provider select.

	:param provider: The provider name (e.g. "Ollama (Local)", "OpenRouter")
	:return: List of model strings for the dropdown options
	"""
	from erp_ai.llm import PROVIDER_MODELS

	if not provider:
		provider = frappe.db.get_single_value("AI Settings", "llm_provider") or "Ollama (Local)"

	return PROVIDER_MODELS.get(provider, [])


@frappe.whitelist()
def fetch_ollama_models():
	"""Fetch available models from a running Ollama instance.

	Calls http://localhost:11434/api/tags and returns model names.
	Used to dynamically populate the dropdown with actual local models.
	"""
	import requests
	try:
		resp = requests.get("http://localhost:11434/api/tags", timeout=5)
		if resp.status_code == 200:
			data = resp.json()
			models = [m["name"] for m in data.get("models", [])]
			return sorted(models)
	except Exception:
		pass
	return []