"""Rewrite bare LLM Provider values to their label-form option string.

The ``llm_provider`` Select ships label-style options ("ollama|Ollama (Local -
Free)"). Sites created before that change stored the bare key ("ollama"),
which now fails Select validation on every save of AI Settings — and makes
``init_singles`` abort a fresh ``install-app``. This patch normalizes stored
data so both eras of sites validate cleanly.
"""

import frappe


def execute():
	stored = frappe.db.get_single_value("AI Settings", "llm_provider")
	if not stored or "|" in stored:
		return  # empty or already label-form

	field = frappe.get_meta("AI Settings").get_field("llm_provider")
	for option in (field.options or "").split("\n"):
		option = option.strip()
		if option and option.split("|", 1)[0] == stored:
			frappe.db.set_single_value("AI Settings", "llm_provider", option)
			return
	# Unknown bare value: leave it; validate_deployment_settings reports it.
