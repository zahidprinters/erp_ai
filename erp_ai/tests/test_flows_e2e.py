"""
Flow-level end-to-end tests (Phase 3.1).

These assert the *user-visible* contract, not the unit contract: they drive the
whole path a real user takes and check the observable outcome (documents, audit
records, guided state) on a seeded site.

1. Guided conversation: missing field -> question -> answers -> ready -> create.
2. Draft -> confirm: document created, audit action recorded, and a repeated
   confirm is idempotent (reported, no duplicate document).

Both run in the ``frappe-tests`` CI job (``bench --site test_site run-tests
--app erp_ai``) as well as locally against a seeded site.

Run with:  bench --site <site> run-tests --app erp_ai
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from erp_ai.conversation import guided_answer, guided_start, load_guided
from erp_ai.draft_workflow import confirm_draft, create_draft


def _uniq(prefix):
	return "%s-%s" % (prefix, frappe.generate_hash(length=8))


class TestGuidedConversationFlow(FrappeTestCase):
	"""The guided flow end to end: ask -> answer -> ready -> create."""

	def test_missing_field_is_asked_then_flow_completes(self):
		session = _uniq("e2e-guided")
		item_name = "E2E Item " + session

		# 1. Start with no data: the flow must ask for the first required field
		#    and park in the collecting state.
		reply = guided_start(session=session, user="Administrator", doctype="Item", data={})
		state = load_guided(session=session, user="Administrator")
		self.assertIsNotNone(state, "guided session was not created")
		self.assertEqual(state["status"], "collecting")
		self.assertEqual(state["pending_field"], "item_name")
		self.assertIn("item", reply.lower(), reply)

		# 2. Answer it: the flow advances to the next question (the first
		#    optional follow-up) instead of completing or dropping the answer.
		guided_answer(session=session, user="Administrator", prompt=item_name)
		state = load_guided(session=session, user="Administrator")
		self.assertEqual(state["status"], "collecting")
		self.assertEqual(state["pending_field"], "standard_rate")
		self.assertEqual(state["data"].get("item_name"), item_name)

		# 3. Skip the optional follow-ups: the flow reaches the ready preview.
		guided_answer(session=session, user="Administrator", prompt="skip")
		reply = guided_answer(session=session, user="Administrator", prompt="skip")
		state = load_guided(session=session, user="Administrator")
		self.assertEqual(state["status"], "ready")
		self.assertIn("Reply yes", reply)

		# 4. Confirm: document created, audit action completed, session cleared.
		final = guided_answer(session=session, user="Administrator", prompt="yes")
		self.assertIn("Created", final, final)
		self.assertTrue(frappe.db.exists("Item", {"item_name": item_name}))
		self.assertIsNone(load_guided(session=session, user="Administrator"))
		actions = frappe.get_all(
			"AI Assistant Action",
			filters={"session_id": session},
			fields=["status", "target_doctype", "target_docname"],
		)
		self.assertTrue(actions, "no audit action recorded for the guided flow")
		self.assertEqual(actions[0]["target_doctype"], "Item")
		self.assertEqual(actions[0]["status"], "completed")
		self.assertTrue(actions[0]["target_docname"])


class TestDraftConfirmFlow(FrappeTestCase):
	"""Draft -> confirm end to end, including idempotent re-confirm."""

	def _draft_task(self, session, subject):
		create_draft(
			session=session,
			action="create",
			target_doctype="Task",
			draft_data={"subject": subject},
			user="Administrator",
		)

	def test_confirm_creates_document_and_records_action(self):
		session = _uniq("e2e-confirm")
		subject = "E2E Task " + session
		self._draft_task(session, subject)

		# The draft exists and is pending before confirmation.
		actions = frappe.get_all(
			"AI Assistant Action",
			filters={"session_id": session},
			fields=["name", "status"],
		)
		self.assertTrue(actions)
		self.assertEqual(actions[0]["status"], "pending")

		res = confirm_draft(session=session, user="Administrator")
		self.assertTrue(res.get("name"), res)
		# Document exists and the audit action records the outcome.
		self.assertTrue(frappe.db.exists("Task", res["name"]))
		action = frappe.get_doc("AI Assistant Action", actions[0]["name"])
		self.assertEqual(action.status, "completed")
		self.assertEqual(action.target_docname, res["name"])
		self.assertTrue(action.confirmed_at)

	def test_reconfirm_is_idempotent_and_creates_no_duplicate(self):
		session = _uniq("e2e-idem")
		subject = "E2E Idem " + session
		self._draft_task(session, subject)
		res = confirm_draft(session=session, user="Administrator")
		self.assertTrue(res.get("name"), res)

		action_name = frappe.get_value("AI Assistant Action", {"session_id": session}, "name")
		again = confirm_draft(session=session, user="Administrator", action_id=action_name)
		# The repeat is reported truthfully as already handled, and it did not
		# execute a second time.
		self.assertTrue(again.get("already_handled"), again)
		self.assertTrue(again.get("already_completed"), again)
		self.assertEqual(again.get("name"), res["name"])
		self.assertEqual(frappe.db.count("Task", {"subject": subject}), 1)
