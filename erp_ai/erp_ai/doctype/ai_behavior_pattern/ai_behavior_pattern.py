# See license.txt for the full text of the MIT License.

"""AI Behavior Pattern — the nightly materialized view of the behavior log.

Rows are (intent -> use/fail/correction counts), refreshed once a day by
``erp_ai.tasks.refresh_behavior_patterns``. ``prompt_block`` reads this table
when it is fresh instead of aggregating the (possibly huge) event log live,
so chat stays cheap however big the log grows. Raw prompts never enter this
table — only counts and one truncated failure reason.
"""

import frappe
from frappe.model.document import Document


class AIBehaviorPattern(Document):
	"""Controller: rows are owned by the nightly task, not by users."""
