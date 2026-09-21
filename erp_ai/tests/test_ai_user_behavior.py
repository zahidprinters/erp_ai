"""Self-checks for the AI User Behavior learning log (mocked, no site needed).

Run with:  python -m pytest erp_ai/tests/test_ai_user_behavior.py
or:        bench --site <site> run-tests --app erp_ai
"""

import unittest
from types import SimpleNamespace
from unittest import mock

import frappe

from erp_ai.erp_ai.doctype.ai_user_behavior import ai_user_behavior as b

# Sentinel for "frappe.local.session was unbound before this test".
_UNBOUND = object()


class RecordTests(unittest.TestCase):
	"""Bind the session on frappe.local (the repo's bare-test mechanism) —
	patching the ``frappe.session`` proxy itself fails while unbound."""

	def setUp(self):
		self._prev = getattr(frappe.local, "session", _UNBOUND)
		frappe.local.session = SimpleNamespace(user="u1")

	def tearDown(self):
		try:
			frappe.local.session = self._prev
		except Exception:
			pass

	def test_record_truncates_and_inserts_ignore_permissions(self):
		seen = {}

		def fake_get_doc(d):
			seen.update(d)
			return mock.Mock(insert=lambda **kw: seen.setdefault("inserted", kw))

		with mock.patch.object(b.frappe, "get_doc", side_effect=fake_get_doc):
			b.record(prompt="x" * 5000, session_id="s", intent="i", outcome="success")

		self.assertEqual(seen["user"], "u1")
		self.assertEqual(seen["doctype"], "AI User Behavior")
		self.assertEqual(len(seen["prompt"]), b.PROMPT_MAX)
		self.assertEqual(seen["inserted"], {"ignore_permissions": True})

	def test_record_never_raises_and_logs(self):
		with (
			mock.patch.object(b.frappe, "get_doc", side_effect=RuntimeError("db down")),
			mock.patch.object(b, "log_error_safely") as les,
		):
			b.record(prompt="p", outcome="failed")  # must not raise
		les.assert_called_once()

	def test_record_skips_without_session_user(self):
		frappe.local.session = SimpleNamespace()  # no user attribute
		with mock.patch.object(b.frappe, "get_doc") as gd:
			b.record(prompt="p")  # no usable session -> silently skipped
		gd.assert_not_called()


class PatternTests(unittest.TestCase):
	def setUp(self):
		b._cache["at"] = 0.0
		b._cache["value"] = None

	def test_patterns_shape_and_raw_examples_are_manager_only(self):
		rows = [{"intent": "llm_chat", "n": 3}]
		with (
			mock.patch.object(b.frappe, "get_all", return_value=rows),
			mock.patch.object(b.frappe, "get_roles", return_value=["Accounts User"]),
		):
			out = b.get_org_patterns()
		self.assertEqual(out["top_intents"], rows)
		self.assertNotIn("recent_failures", out)  # raw prompts: managers only

		with (
			mock.patch.object(b.frappe, "get_all", return_value=rows),
			mock.patch.object(b.frappe, "get_roles", return_value=["System Manager"]),
		):
			out = b.get_org_patterns()
		self.assertEqual(out["recent_failures"], rows)

	def test_prompt_block_aggregates_only_and_caches(self):
		rows = [{"intent": "llm_chat", "n": 7}]
		with (
			mock.patch.object(b.frappe, "get_all", return_value=rows),
			mock.patch.object(b.frappe, "get_roles", return_value=["System Manager"]),
		):
			block = b.prompt_block()
		self.assertIn("llm_chat", block)
		self.assertNotIn("prompt", block)  # aggregates only, never raw user text

		with mock.patch.object(b.frappe, "get_all", side_effect=AssertionError("cache miss: hit the db")):
			self.assertIn("llm_chat", b.prompt_block())  # served from cache


class FeedbackTests(unittest.TestCase):
	"""apply_feedback: thumbs-down marks the last turn corrected; up is a no-op."""

	def setUp(self):
		self._prev = getattr(frappe.local, "session", _UNBOUND)
		frappe.local.session = SimpleNamespace(user="u1")

	def tearDown(self):
		try:
			frappe.local.session = self._prev
		except Exception:
			pass

	def test_thumbs_down_marks_last_turn_corrected(self):
		row = mock.Mock()
		row.correction_count = 2  # explicit int: int(Mock) would raise
		with (
			mock.patch.object(b.frappe, "get_all", return_value=[{"name": "AB-1"}]),
			mock.patch.object(b.frappe, "get_doc", return_value=row),
		):
			out = b.apply_feedback(session_id="s", helpful=0)
		self.assertEqual(out, {"updated": 1})
		self.assertEqual(row.outcome, "corrected")
		self.assertEqual(row.correction_count, 3)

	def test_thumbs_up_needs_no_write(self):
		with mock.patch.object(b.frappe, "get_all") as ga, mock.patch.object(b.frappe, "get_doc") as gd:
			out = b.apply_feedback(session_id="s", helpful=1)
		self.assertEqual(out, {"updated": 0})
		ga.assert_not_called()
		gd.assert_not_called()

	def test_never_raises(self):
		with (
			mock.patch.object(b.frappe, "get_all", side_effect=RuntimeError("db down")),
			mock.patch.object(b, "log_error_safely") as les,
		):
			self.assertEqual(b.apply_feedback(session_id="s", helpful=0), {"updated": 0})
		les.assert_called_once()


class DraftHelpTests(unittest.TestCase):
	"""draft_help_for_repeated_failures: inactive, keyworded, idempotent."""

	def _run(self, failures, get_all_returns, threshold=5):
		import erp_ai.tasks as tasks
		from erp_ai.erp_ai.doctype.ai_user_behavior import ai_user_behavior as behavior

		# Patch tasks.frappe wholesale: touching real frappe.db from a bare
		# test raises "object is not bound" (werkzeug Local proxy unbound).
		fake = mock.MagicMock()
		fake.get_all.side_effect = list(get_all_returns)
		with (
			mock.patch.object(tasks, "frappe", fake),
			mock.patch.object(behavior, "get_org_patterns", return_value={"failure_intents": failures}),
		):
			out = tasks.draft_help_for_repeated_failures(threshold=threshold)
		payloads = [c.args[0] for c in fake.get_doc.call_args_list if c.args and isinstance(c.args[0], dict)]
		return out, payloads, fake

	def test_drafts_inactive_keyworded_article(self):
		out, payloads, fake = self._run(
			[{"intent": "create_sales_order", "n": 7}], [[], [{"failure_reason": "boom"}]]
		)
		self.assertEqual(out["drafted"], 1)
		self.assertEqual(len(payloads), 1)
		self.assertEqual(payloads[0]["is_active"], 0)  # never auto-published
		self.assertEqual(payloads[0]["keywords"], "ai-auto:create_sales_order")
		self.assertIn("create_sales_order", payloads[0]["title"])
		self.assertIn("boom", payloads[0]["content"])  # raw reason only in body
		fake.get_doc.return_value.insert.assert_called_once_with(ignore_permissions=True)

	def test_skips_intent_that_already_has_a_draft(self):
		out, payloads, fake = self._run([{"intent": "create_sales_order", "n": 7}], [["ART-1"]])
		self.assertEqual(out["drafted"], 0)
		self.assertEqual(out["skipped_existing"], 1)
		fake.get_doc.assert_not_called()  # no draft inserted

	def test_below_threshold_never_drafts(self):
		out, payloads, fake = self._run([{"intent": "llm_chat", "n": 4}], [[], []])
		self.assertEqual(out["drafted"], 0)
		fake.get_doc.assert_not_called()
