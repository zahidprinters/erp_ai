"""
Frappe-backed integration tests: idempotency, audit confirmation security,
shipment preview/confirm/cancel flow, partial-failure rollback, and live
DocType metadata verification.

Run with:  bench --site spi.local run-tests --app erp_ai
"""
import json
import unittest
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase

from erp_ai import api as api_mod
from erp_ai import draft_workflow as draft_workflow_mod
from erp_ai.conversation import (
    guided_answer,
    guided_start,
    load_guided,
)
from erp_ai.draft_workflow import confirm_draft, create_draft, get_draft
from erp_ai.idempotency import check_idempotency, claim_idempotency
from erp_ai.schema import DOCTYPE_SCHEMAS


def _uniq(prefix):
    return "%s-%s" % (prefix, frappe.generate_hash(length=8))


class TestIdempotencyUnique(FrappeTestCase):
    """Idempotency keys: DB unique constraint + pending/processing blocking."""

    def test_claim_new_then_pending_is_duplicate(self):
        key = _uniq("idem")
        r1 = claim_idempotency(key, "sess", "Administrator", "create", "Item",
                               {"item_name": "X"})
        self.assertEqual(r1["status"], "new")
        r2 = claim_idempotency(key, "sess", "Administrator", "create", "Item",
                               {"item_name": "X"})
        self.assertEqual(r2["status"], "duplicate")
        self.assertEqual(r2["action_id"], r1["action_id"])

    def test_claim_forbidden_for_other_user(self):
        key = _uniq("idem_forbid")
        claim_idempotency(key, "sess", "Administrator", "create", "Item",
                          {"item_name": "X"})
        r2 = claim_idempotency(key, "sess", "guest@example.com", "create", "Item",
                               {"item_name": "X"})
        self.assertEqual(r2["status"], "forbidden")

    def test_check_sees_pending(self):
        key = _uniq("idem_check")
        claim_idempotency(key, "sess", "Administrator", "create", "Item",
                          {"item_name": "X"})
        got = check_idempotency(key, user="Administrator")
        self.assertIsNotNone(got)
        self.assertIn(got["status"], ("pending", "processing", "completed"))

    def test_unique_index_exists(self):
        rows = frappe.db.sql(
            "SELECT CONSTRAINT_NAME FROM information_schema.TABLE_CONSTRAINTS "
            "WHERE table_name='tabAI Assistant Action' AND constraint_type='UNIQUE'")
        names = [r[0] for r in rows]
        self.assertIn("unique_idempotency_key", names)

    def test_db_blocks_raw_duplicate_insert(self):
        key = _uniq("idem_raw")
        frappe.get_doc({
            "doctype": "AI Assistant Action", "user": "Administrator",
            "session_id": "t1", "action": "create", "target_doctype": "Item",
            "status": "pending", "nonce": "a", "idempotency_key": key,
        }).insert()
        with self.assertRaises(frappe.UniqueValidationError):
            frappe.get_doc({
                "doctype": "AI Assistant Action", "user": "Administrator",
                "session_id": "t2", "action": "create", "target_doctype": "Item",
                "status": "pending", "nonce": "b", "idempotency_key": key,
            }).insert()

    def test_concurrent_duplicate_is_blocked_by_db(self):
        """Two in-memory inserts for the same idempotency_key must not both
        succeed - the DB unique index is the final gate."""
        key = _uniq("concurrent")
        frappe.get_doc({
            "doctype": "AI Assistant Action", "user": "Administrator",
            "session_id": "c1", "action": "create", "target_doctype": "Item",
            "status": "pending", "nonce": "a", "idempotency_key": key,
        }).insert()
        frappe.db.commit()
        with self.assertRaises(frappe.UniqueValidationError):
            frappe.get_doc({
                "doctype": "AI Assistant Action", "user": "Administrator",
                "session_id": "c2", "action": "create", "target_doctype": "Item",
                "status": "pending", "nonce": "b", "idempotency_key": key,
            }).insert()

    def test_claim_pending_blocks_new_claim(self):
        """A pending action must prevent a fresh claim on the same key."""
        key = _uniq("pending_block")
        r1 = claim_idempotency(key, "s1", "Administrator", "create", "Item",
                               {"item_name": "X"})
        self.assertEqual(r1["status"], "new")
        r2 = claim_idempotency(key, "s2", "Administrator", "create", "Item",
                               {"item_name": "Y"})
        self.assertEqual(r2["status"], "duplicate")
        self.assertEqual(r2["action_id"], r1["action_id"])

    def test_completed_key_blocks_fresh_claim(self):
        """A completed action must still block a fresh claim on the same key."""
        key = _uniq("completed_block")
        r1 = claim_idempotency(key, "s1", "Administrator", "create", "Item",
                               {"item_name": "Z"})
        self.assertEqual(r1["status"], "new")
        frappe.db.set_value("AI Assistant Action", r1["action_id"],
                            "status", "completed")
        frappe.db.commit()
        r2 = claim_idempotency(key, "s2", "Administrator", "create", "Item",
                               {"item_name": "different"})
        self.assertEqual(r2["status"], "duplicate")
        self.assertEqual(r2["action_id"], r1["action_id"])

class TestAuditConfirmationSecurity(FrappeTestCase):

    """confirm_draft must verify ownership, nonce, expiry, status, preview hash."""

    def _make_customer_draft(self):
        session = _uniq("audit")
        r = create_draft(
            session=session, action="create", target_doctype="Customer",
            draft_data={"customer_name": session, "customer_group": "All Customer Groups"},
            user="Administrator")
        return session, r

    def _make_item_draft(self):
        """Item has no site-custom mandatory fields, so confirmations succeed
        deterministically on both this site and a fresh CI site."""
        session = _uniq("audit")
        ig = frappe.db.get_value("Item Group", {"is_group": 0}, "name", order_by="lft asc")
        data = {"item_name": session, "stock_uom": "Nos"}
        if ig:
            data["item_group"] = ig
        r = create_draft(
            session=session, action="create", target_doctype="Item",
            draft_data=data, user="Administrator")
        return session, r

    def test_confirm_rejects_wrong_user(self):
        session, r = self._make_customer_draft()
        # Pass action_id explicitly so the ownership guard (not the
        # session+user lookup) is what's under test.
        res = confirm_draft(session=session, action_id=r["name"], user="guest@example.com")
        self.assertIn("different user", str(res))

    def test_confirm_rejects_wrong_nonce(self):
        session, r = self._make_customer_draft()
        res = confirm_draft(session=session, user="Administrator", expected_nonce="bogus")
        self.assertIn("mismatch", str(res))

    def test_confirm_rejects_expired(self):
        session, r = self._make_customer_draft()
        action = frappe.get_doc("AI Assistant Action", r["name"])
        action.expires_on = "2020-01-01 00:00:00"
        action.save()
        frappe.db.commit()
        res = confirm_draft(session=session, user="Administrator")
        self.assertTrue(isinstance(res, dict))
        self.assertIn("expired", str(res).lower())

    def test_confirm_rejects_changed_preview(self):
        session, r = self._make_customer_draft()
        frappe.db.set_value("AI Assistant Action", r["name"],
                            "draft_data", json.dumps({"customer_name": "MUTATED"}))
        frappe.db.commit()
        res = confirm_draft(session=session, user="Administrator")
        self.assertTrue(isinstance(res, dict))
        self.assertIn("has changed", str(res))

    def test_second_confirm_is_rejected(self):
        session, r = self._make_item_draft()
        res1 = confirm_draft(session=session, user="Administrator")
        self.assertTrue(isinstance(res1, dict) and res1.get("name"), res1)
        res2 = confirm_draft(session=session, action_id=r["name"], user="Administrator")
        self.assertIn("no longer available", str(res2))

    def test_success_records_full_result_payload(self):
        session, r = self._make_item_draft()
        res = confirm_draft(session=session, user="Administrator")
        self.assertTrue(isinstance(res, dict) and res.get("name"), res)
        action = frappe.get_doc("AI Assistant Action", r["name"])
        self.assertEqual(action.status, "completed")
        self.assertEqual(action.target_docname, res["name"])
        stored = json.loads(action.draft_data or "{}")
        self.assertIn("result", stored)
        self.assertIn("changed_fields", stored)
        self.assertIn("rollback_reference", stored)
        self.assertEqual(stored["rollback_reference"]["target_docname"], res["name"])

    def test_live_mandatory_custom_field_is_named(self):
        """Fields made mandatory by another app (e.g. tax NTN/CNIC) get a clear
        listable error instead of a cryptic database failure."""
        from erp_ai.mcp.server import _validate_required_fields
        # Customer carries a site-custom mandatory fbr_ntn_cnic field
        meta = frappe.get_meta("Customer")
        if not any(df.fieldname == "fbr_ntn_cnic" for df in meta.fields):
            self.skipTest("no custom mandatory Customer fields on this site")
        err = _validate_required_fields("Customer", {"customer_name": "X"})
        self.assertIsNotNone(err)
        self.assertIn("Missing required fields", err)
        self.assertIn("NTN", err)


class TestShipmentPreviewConfirmCancel(FrappeTestCase):
    """Shipment draft -> confirm flow via the public API, plus cancel semantics.

These tests exercise the real workflow endpoint surface instead of the old
chat-marker helpers, which were removed during the hardening pass.
"""

    def test_workflow_receipt_creates_auditable_draft(self):
        user = "Administrator"
        res = api_mod.workflow_shipment_receipt(
            {"text": "received 10 x ABC-001 from Ship Test Ltd at warehouse Raw Materials"}
        )
        self.assertTrue(res.get("ok"), res)
        self.assertEqual(res.get("mode"), "draft_shipment")
        draft_id = res.get("draft_id")
        self.assertTrue(draft_id)

        action = frappe.get_doc("AI Assistant Action", draft_id)
        self.assertEqual(action.status, "pending")
        self.assertEqual(action.target_doctype, "Purchase Receipt")
        self.assertEqual(action.user, user)
        # The draft must be bound to a real session id — never the literal
        # string "None" (that was the original bug) nor empty.
        self.assertTrue(action.session_id, "session_id must be populated")
        self.assertNotEqual(action.session_id, "None")

    def test_workflow_receipt_draft_confirms_and_creates_document(self):
        user = "Administrator"
        res = api_mod.workflow_shipment_receipt(
            {
                "text": "received 2 x TST-CONF-ITEM from Ship Test Ltd at warehouse Raw Materials",
                "remarks": "integration test",
            }
        )
        self.assertTrue(res.get("ok"), res)
        draft_id = res.get("draft_id")

        confirmed = api_mod.confirm_workflow_action(draft_id, user)
        self.assertTrue(confirmed.get("ok") or confirmed.get("name"), confirmed)

        action = frappe.get_doc("AI Assistant Action", draft_id)
        self.assertEqual(action.status, "completed")
        self.assertIn("rollback_reference", action)
        rb = frappe.parse_json(action.rollback_reference)
        self.assertIn("target_docname", rb)
        self.assertTrue(rb["target_docname"])

    def test_workflow_receipt_cancel_rejects_another_user(self):
        res = api_mod.workflow_shipment_receipt(
            {"text": "received 1 x TST-CANCEL-ITEM from Ship Test Ltd"}
        )
        draft_id = res.get("draft_id")

        cancel_res = api_mod.cancel_workflow_action(draft_id, "not-the-owner")

        # Only the action owner (or an allowed path) should cancel.
        self.assertFalse(cancel_res.get("ok"), cancel_res)


class TestPartialFailureRollback(FrappeTestCase):
    """Master data created mid-workflow must roll back when the receipt fails."""

    class _FakeMCP:
        """Returns success for supplier/item creation, failure for receipts."""

        def __init__(self):
            self.calls = []

        def call_tool(self, name, args=None):
            self.calls.append((name, args))
            doctype = (args or {}).get("doctype", "")
            if name == "query_doctype":
                return {"count": 0}
            if name == "create_document" and doctype == "Supplier":
                return {"success": True, "name": "ROLLBACK-SUPPLIER", "doctype": "Supplier"}
            if name == "create_document" and doctype == "Item":
                return {"success": True, "name": "ROLLBACK-ITEM", "doctype": "Item"}
            if name == "create_document" and doctype == "Purchase Receipt":
                return {"error": "receipt failed"}
            if name == "create_document" and doctype == "Stock Entry":
                return {"error": "stock entry failed"}
            return {"count": 0}

    def test_shipment_masters_rolled_back_on_failure(self):
        from erp_ai.workflows.shipment import create_shipment_receipt
        warehouse = frappe.db.get_value("Warehouse", {"is_group": 0}, "name")
        if not warehouse:
            self.skipTest("requires a site with at least one leaf Warehouse")
        data = {
            "supplier": "ROLLBACK-SUPPLIER", "remarks": "test",
            "warehouse": warehouse,
            "items": [{"item_code": "ROLLBACK-ITEM", "qty": 5}],
        }
        mcp = self._FakeMCP()
        result = create_shipment_receipt(data, mcp)
        self.assertFalse(result.get("ok"))
        self.assertFalse(frappe.db.exists("Supplier", "ROLLBACK-SUPPLIER"))
        self.assertFalse(frappe.db.exists("Item", "ROLLBACK-ITEM"))


class TestLiveDocTypeMetadata(FrappeTestCase):
    """Every schema doctype must exist in live metadata with its required fields.

    Doctypes provided by optional companion apps (HRMS) are only asserted when
    that app is installed, mirroring production reality on stock ERPNext v15.
    """

    HRMS_ONLY: "frozenset[str]" = frozenset({
        "Leave Application", "Expense Claim", "Attendance",
        "Payroll Entry", "Salary Structure",
    })

    def _hrms_installed(self):
        return "hrms" in frappe.get_installed_apps()

    def test_all_schema_doctypes_exist_with_required_fields(self):
        missing_dt = []
        missing_fields = []
        hrms_ok = self._hrms_installed()
        for doctype, schema in DOCTYPE_SCHEMAS.items():
            if doctype in self.HRMS_ONLY and not hrms_ok:
                continue  # provided by the hrms app, not installed here
            try:
                meta = frappe.get_meta(doctype)
            except Exception:
                missing_dt.append(doctype)
                continue
            fieldnames = {f.fieldname for f in meta.fields}
            for req in schema.get("required", []):
                if req not in fieldnames:
                    missing_fields.append("%s.%s" % (doctype, req))
        self.assertEqual(missing_dt, [], "DocTypes missing from live metadata: %s" % missing_dt)
        self.assertEqual(missing_fields, [], "Required fields missing from live metadata: %s" % missing_fields)

    def test_no_nonconformance_report_in_schema(self):
        """NCR is not a stock v15 doctype; the registry must not reference it."""
        self.assertNotIn("Nonconformance Report", DOCTYPE_SCHEMAS)


class TestGenericDepartmentExecution(FrappeTestCase):
    """Registry doctypes beyond the six bespoke builders must be executable
    through the draft -> confirm pipeline (BOM, WO, Asset, HR, Project, ...)."""

    def _confirm(self, doctype, data):
        session = _uniq("gen")
        create_draft(session=session, action="create", target_doctype=doctype,
                     draft_data=data, user="Administrator")
        return confirm_draft(session=session, user="Administrator")

    def test_project_execution_via_confirm(self):
        name = "GenProj " + frappe.generate_hash(length=6)
        company = frappe.defaults.get_global_default("company")
        data = {"project_name": name}
        if company:
            data["company"] = company
        res = self._confirm("Project", data)
        self.assertTrue(res.get("name"), res)
        self.assertTrue(frappe.db.exists("Project", res["name"]))

    def test_task_execution_via_confirm(self):
        subject = "GenTask " + frappe.generate_hash(length=6)
        res = self._confirm("Task", {"subject": subject})
        self.assertTrue(res.get("name"), res)
        self.assertTrue(frappe.db.exists("Task", res["name"]))

    def test_auto_confirm_on_yes_creates_document(self):
        """A reply of "yes" while a guided action is in the ready state
        auto-confirms the draft and creates the document."""
        session = _uniq("auto_yes")
        data = {"item_name": "AutoYes-" + session, "item_group": "Products",
                "stock_uom": "Nos", "standard_rate": 0, "opening_stock": 0}
        reply = guided_start(session=session, user="Administrator", doctype="Item", data=data)
        self.assertIn("Reply yes", reply)
        # The guided flow should now be in ready state.
        state = load_guided(session=session, user="Administrator")
        self.assertIsNotNone(state)
        self.assertEqual(state.get("status"), "ready")
        # A bare "yes" auto-confirms.
        yes_reply = guided_answer(session=session, user="Administrator", prompt="yes")
        self.assertTrue(yes_reply)
        self.assertIn("Created", yes_reply)
        self.assertTrue(frappe.db.exists("Item", {"item_name": data["item_name"]}))
        # The guided session should now be cleared.
        self.assertIsNone(load_guided(session=session, user="Administrator"))

    def test_affirmative_variants_auto_confirm(self):
        """Common affirmative phrasings all auto-confirm the ready draft."""
        for prompt in ("yeah", "yep", "yup", "y", "sure", "go ahead",
                        "do it", "correct", "right", "create it", "make it"):
            with self.subTest(prompt=prompt):
                session = _uniq("auto_var")
                data = {"item_name": "AutoVar-" + session, "item_group": "Products",
                        "stock_uom": "Nos", "standard_rate": 0, "opening_stock": 0}
                guided_start(session=session, user="Administrator", doctype="Item", data=data)
                reply = guided_answer(session=session, user="Administrator", prompt=prompt)
                self.assertTrue(reply and "Created" in reply, prompt)
                self.assertTrue(frappe.db.exists("Item", {"item_name": data["item_name"]}))
                frappe.db.delete("Item", {"item_name": data["item_name"]})
                frappe.db.commit()

    def test_negative_reply_keeps_draft_pending(self):
        """A clear negative while in ready state does NOT confirm; the flow
        is stopped and the draft stays pending."""
        session = _uniq("auto_no")
        data = {"item_name": "AutoNo-" + session, "item_group": "Products",
                "stock_uom": "Nos", "standard_rate": 0, "opening_stock": 0}
        guided_start(session=session, user="Administrator", doctype="Item", data=data)
        no_reply = guided_answer(session=session, user="Administrator", prompt="no")
        self.assertIn("leave it", no_reply.lower())
        self.assertFalse(frappe.db.exists("Item", {"item_name": data["item_name"]}))
        # The action stays pending (not confirmed, not cancelled by the guided path).
        draft = get_draft(session=session, user="Administrator")
        self.assertIsNotNone(draft)
        self.assertEqual(draft.get("status"), "pending")

    def test_non_affirmative_does_not_auto_confirm(self):
        """Ambiguous / non-affirmative replies do not auto-confirm."""
        session = _uniq("auto_neut")
        data = {"item_name": "AutoNeut-" + session, "item_group": "Products",
                "stock_uom": "Nos", "standard_rate": 0, "opening_stock": 0}
        guided_start(session=session, user="Administrator", doctype="Item", data=data)
        reply = guided_answer(session=session, user="Administrator", prompt="maybe later")
        # Should not have created the document and should keep the ready state.
        self.assertFalse("Created" in reply, reply)
        self.assertFalse(frappe.db.exists("Item", {"item_name": data["item_name"]}))
        # Should still be in ready state (the reply was not negative enough to clear).
        state = load_guided(session=session, user="Administrator")
        self.assertIsNotNone(state)
        self.assertEqual(state.get("status"), "ready")

    def test_auto_confirm_rejects_expired_action(self):
        """An expired ready action must not be auto-confirmed; the user gets a
        clear refusal and the guided session is cleared."""
        session = _uniq("auto_exp")
        data = {"item_name": "AutoExp-" + session, "item_group": "Products",
                "stock_uom": "Nos", "standard_rate": 0, "opening_stock": 0}
        guided_start(session=session, user="Administrator", doctype="Item", data=data)
        # Manually expire the underlying action so confirm_draft rejects it.
        draft = get_draft(session=session, user="Administrator")
        self.assertIsNotNone(draft)
        action = frappe.get_doc("AI Assistant Action", draft["name"])
        action.status = "pending"
        action.expires_on = frappe.utils.add_to_date(frappe.utils.now_datetime(), minutes=-5)
        action.save()
        frappe.db.commit()
        reply = guided_answer(session=session, user="Administrator", prompt="yes")
        self.assertTrue(reply)
        self.assertIn("expired", reply.lower())
        self.assertFalse(frappe.db.exists("Item", {"item_name": data["item_name"]}))

    def test_task_inherits_print_url(self):
        subject = "GenTaskURL " + frappe.generate_hash(length=6)
        res = self._confirm("Task", {"subject": subject})
        self.assertTrue(res.get("name"), res)
        self.assertIn("print_format", res.get("print_url", ""))

    def test_rollback_on_mid_execution_failure(self):
        """If MCP raises mid-execution, no document is persisted and the
        action is marked failed (single transaction boundary)."""
        from erp_ai.workflows.shipment import create_shipment_receipt
        session = _uniq("rbk")
        create_draft(session=session, action="create", target_doctype="Item",
                     draft_data={"item_name": session, "item_group": "Raw Material",
                                 "stock_uom": "Nos"},
                     user="Administrator")
        class _BoomMCP:
            def call_tool(self, name, args=None):
                raise RuntimeError("simulated mid-execution crash")
        with mock.patch.object(draft_workflow_mod, "FrappeMCP", return_value=_BoomMCP()):
            res = confirm_draft(session=session, user="Administrator")
        self.assertTrue(isinstance(res, dict) and res.get("error"), res)
        self.assertFalse(frappe.db.exists("Item", {"item_name": session}))
        # The action record itself survives with a failed status for the audit
        actions = frappe.get_all("AI Assistant Action",
                                 filters={"session_id": session},
                                 fields=["status", "failure_reason"])
        self.assertTrue(actions and actions[0]["status"] == "failed")


class TestInfrastructureEndpoints(FrappeTestCase):
    """The new whitelisted infrastructure endpoints behave correctly."""

    def test_barcode_lookup_empty_code(self):
        from erp_ai.barcode import resolve_barcode
        res = resolve_barcode("")
        self.assertFalse(res.get("ok"))

    def test_barcode_lookup_finds_item_by_code(self):
        name = "BC-ITEM-" + frappe.generate_hash(length=6)
        ig = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
        frappe.get_doc({"doctype": "Item", "item_code": name, "item_name": name,
                        "item_group": ig or "Products", "stock_uom": "Nos",
                        "is_stock_item": 0}).insert()
        frappe.db.commit()
        from erp_ai.barcode import resolve_barcode
        res = resolve_barcode(name)
        self.assertTrue(res.get("ok"))
        self.assertEqual(res.get("doctype"), "Item")

    def test_knowledge_freshness_shape(self):
        res = api_mod.knowledge_freshness()
        self.assertIn("sources", res)
        self.assertIn("total", res)
        for src in res["sources"]:
            self.assertIn("citation", src)
            self.assertIn("fresh", src)

    def test_citation_for_known_doctype(self):
        """The citation must be verifiable: source id resolves in the
        registry, url present, doctype echoed back."""
        res = api_mod.citation_for("Sales Invoice")
        metadata = res["citation"]
        self.assertTrue(metadata)
        self.assertIn("ERPNext", metadata["title"])
        self.assertEqual(metadata["source_id"], "erpnext_selling")
        self.assertIn("docs.frappe.io", metadata["url"])
        self.assertEqual(metadata["doctype"], "Sales Invoice")

    def test_audit_history_scoped_to_caller(self):
        session, r = TestAuditConfirmationSecurity._make_customer_draft(self)
        res = api_mod.audit_history(session=session)
        recs = res.get("records", [])
        for rec in recs:
            self.assertNotEqual(rec.get("user", ""), "guest@example.com")


if __name__ == "__main__":
    unittest.main()
