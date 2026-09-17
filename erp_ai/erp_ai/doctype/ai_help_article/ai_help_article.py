import frappe
from frappe.model.document import Document


class AIHelpArticle(Document):
    def validate(self):
        if self.example_queries:
            self.example_queries = self.example_queries.strip()

    def get_parsed_examples(self):
        """Return example queries as a list."""
        if not self.example_queries:
            return []
        return [q.strip() for q in self.example_queries.split("\n") if q.strip()]
