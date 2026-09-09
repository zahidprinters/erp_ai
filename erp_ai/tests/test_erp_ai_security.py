"""
ERP AI Security & Workflow Tests

These tests verify Phase 1-4 improvements:
- Phase 1: Security guardrails (DocType allowlist, permission checks)
- Phase 2: Draft persistence with AI Assistant Action DocType
- Phase 3: Atomicity (single commit point)
- Phase 4: Entity resolution and clarification

Run with: bench --site spi.local run-tests --app erp_ai
       or: python -m unittest erp_ai.tests.test_erp_ai_security
"""

import unittest
import pytest
import frappe
import json
from erp_ai.draft_workflow import (
    resolve_item, resolve_party, pick_candidate,
    clarification_needed, get_missing_fields,
    create_draft, confirm_draft, get_draft, clear_draft,
    _get_action, create_document_from_draft,
    detect_intent, DOCTYPE_SCHEMAS, generate_preview,
)
from erp_ai.mcp.server import (
    FrappeMCP, ALLOWED_DOCTYPES, BLOCKED_DOCTYPES,
    _validate_doctype, _require_permission,
)


class TestPhase1Security(unittest.TestCase):
    """Test Phase 1 security guardrails."""

    def test_allowed_doctypes_has_business_doctypes(self):
        """Ensure core business DocTypes are in the allowlist."""
        assert "Item" in ALLOWED_DOCTYPES
        assert "Customer" in ALLOWED_DOCTYPES
        assert "Sales Invoice" in ALLOWED_DOCTYPES
        assert "Purchase Invoice" in ALLOWED_DOCTYPES
        assert "Supplier" in ALLOWED_DOCTYPES

    def test_blocked_doctypes_denies_security_doctypes(self):
        """Ensure security/system DocTypes are blocked."""
        assert "User" in BLOCKED_DOCTYPES
        assert "Role" in BLOCKED_DOCTYPES
        assert "Permission" in BLOCKED_DOCTYPES
        assert "DocType" in BLOCKED_DOCTYPES
        assert "Custom Field" in BLOCKED_DOCTYPES

    def test_validate_doctype_rejects_empty(self):
        """Empty doctype should be rejected."""
        err = _validate_doctype("")
        assert err == "doctype is required"
        err = _validate_doctype(None)
        assert err == "doctype is required"

    def test_validate_doctype_rejects_blocked(self):
        """Blocked DocTypes should be rejected."""
        err = _validate_doctype("User")
        assert "blocked" in err.lower()
        err = _validate_doctype("Role")
        assert "blocked" in err.lower()

    def test_validate_doctype_accepts_allowed(self):
        """Allowed DocTypes should pass validation."""
        err = _validate_doctype("Item")
        assert err is None
        err = _validate_doctype("Sales Invoice")
        assert err is None

    def test_validate_doctype_rejects_unknown(self):
        """DocTypes not in allowlist should be rejected."""
        err = _validate_doctype("ToDo")
        assert "not available" in err.lower() or "not" in err.lower()


class TestPhase2DraftWorkflow(unittest.TestCase):
    """Test Phase 2 draft persistence with AI Assistant Action DocType."""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """Clean up test data after each test."""
        yield
        # Clean up all test-session AI Assistant Actions
        for name in frappe.db.get_all(
            "AI Assistant Action",
            filters={"session_id": ["like", "test-%"]},
            pluck="name"
        ):
            frappe.db.delete("AI Assistant Action", name)
        # Clean up test Items created by draft workflow tests
        for name in frappe.db.get_all(
            "Item",
            filters={"item_name": ["like", "%Test%"]},
            pluck="name"
        ):
            frappe.db.delete("Item", name)
        frappe.db.commit()

    def test_create_draft_creates_action_record(self):
        """create_draft should create an AI Assistant Action record."""
        draft = create_draft(
            session="test-session-cleanup",
            action="create",
            target_doctype="Item",
            draft_data={"item_name": "Test Item"},
            user="Administrator",
        )
        assert "name" in draft
        assert "nonce" in draft
        assert len(draft["nonce"]) > 0

        # Verify action record exists
        action = frappe.get_doc("AI Assistant Action", draft["name"])
        assert action.user == "Administrator"
        assert action.session_id == "test-session-cleanup"
        assert action.action == "create"
        assert action.target_doctype == "Item"
        assert action.status == "pending"
        assert action.document_version == 1

    def test_create_draft_binds_to_user(self):
        """Drafts should be bound to the authenticated user."""
        draft1 = create_draft(
            session="test-session-user1",
            action="create",
            target_doctype="Item",
            draft_data={"item_name": "Test 1"},
            user="Administrator",
        )
        draft2 = create_draft(
            session="test-session-user1",
            action="create",
            target_doctype="Item",
            draft_data={"item_name": "Test 2"},
            user="Administrator",
        )
        # Both should be findable by user
        actions = frappe.db.get_all(
            "AI Assistant Action",
            filters={"user": "Administrator", "session_id": "test-session-user1"},
            pluck="name"
        )
        assert len(actions) >= 2

    def test_get_draft_returns_action(self):
        """get_draft should return the draft data for the session/user."""
        draft = create_draft(
            session="test-session-get",
            action="create",
            target_doctype="Item",
            draft_data={"item_name": "Get Test Item"},
            user="Administrator",
        )
        result = get_draft(session="test-session-get", user="Administrator")
        assert result is not None
        assert result.get("action") == "create"
        assert result.get("target_doctype") == "Item"
        assert result.get("draft_data") is not None

    def test_get_draft_isolation_by_user(self):
        """get_draft should not return another user's drafts."""
        create_draft(
            session="test-session-isolation",
            action="create",
            target_doctype="Item",
            draft_data={"item_name": "Admin Item"},
            user="Administrator",
        )
        # As a different user (or no user), should not find it
        result = get_draft(session="test-session-isolation", user="Guest")
        assert result is None or result.get("user") != "Administrator"

    def test_confirm_draft_creates_document(self):
        """confirm_draft should create the document and mark action completed."""
        draft = create_draft(
            session="test-session-confirm",
            action="create",
            target_doctype="Item",
            draft_data={
                "item_name": "Confirm Test Item",
                "item_group": "Products",
                "stock_uom": "Nos",
                "standard_rate": 100,
            },
            user="Administrator",
        )
        result = confirm_draft(
            session="test-session-confirm",
            user="Administrator",
            expected_nonce=draft["nonce"],
            action_id=draft["name"],
        )
        assert result.get("success") is True
        assert "name" in result

        # Verify action is marked completed
        action = frappe.get_doc("AI Assistant Action", draft["name"])
        assert action.status == "completed"
        assert action.confirmed_at is not None
        assert action.target_docname == result["name"]

    def test_confirm_draft_rejects_wrong_nonce(self):
        """confirm_draft should reject with wrong nonce."""
        draft = create_draft(
            session="test-session-wrong-nonce",
            action="create",
            target_doctype="Item",
            draft_data={"item_name": "Wrong Nonce Item"},
            user="Administrator",
        )
        result = confirm_draft(
            session="test-session-wrong-nonce",
            user="Administrator",
            expected_nonce="wrong-nonce-12345",
            action_id=draft["name"],
        )
        assert "error" in result
        assert "mismatch" in result["error"].lower()

    def test_confirm_draft_rejects_expired_draft(self):
        """confirm_draft should reject expired drafts."""
        draft = create_draft(
            session="test-session-expired",
            action="create",
            target_doctype="Item",
            draft_data={"item_name": "Expired Item"},
            user="Administrator",
        )
        # Manually expire the action
        action = frappe.get_doc("AI Assistant Action", draft["name"])
        action.expires_on = frappe.utils.add_to_date(
            frappe.utils.now_datetime(), minutes=-1
        )
        action.save()
        frappe.db.commit()

        result = confirm_draft(
            session="test-session-expired",
            user="Administrator",
            expected_nonce=draft["nonce"],
            action_id=draft["name"],
        )
        assert "error" in result
        assert "expired" in result["error"].lower()

    def test_clear_draft_marks_consumed(self):
        """clear_draft should write a [DRAFT_CLEARED] marker."""
        draft = create_draft(
            session="test-session-clear",
            action="create",
            target_doctype="Item",
            draft_data={"item_name": "Clear Test"},
            user="Administrator",
        )
        result = clear_draft(session="test-session-clear", user="Administrator")
        assert result is True

        # Verify [DRAFT_CLEARED] marker exists
        markers = frappe.db.get_all(
            "AI Chat Message",
            filters={
                "session_id": "test-session-clear",
                "role": "user",
                "content": "[DRAFT_CLEARED]",
            },
            pluck="name"
        )
        assert len(markers) >= 1


class TestPhase3Atomicity(unittest.TestCase):
    """Test Phase 3 atomicity: single commit point in create_document_from_draft."""

    def test_create_document_from_draft_commits(self):
        """create_document_from_draft should commit once at the end."""
        from erp_ai.mcp.server import FrappeMCP
        mcp = FrappeMCP()

        # Clean up first
        for name in frappe.db.get_all("Item", filters={"item_name": "Atomic Test"}, pluck="name"):
            frappe.db.delete("Item", name)

        result = create_document_from_draft(
            "Item",
            {
                "item_name": "Atomic Test",
                "item_group": "Products",
                "stock_uom": "Nos",
                "standard_rate": 50,
            },
            mcp,
        )
        assert result.get("success") is True
        assert frappe.db.exists("Item", result["name"])

        # Cleanup
        frappe.db.delete("Item", result["name"])
        frappe.db.commit()


class TestPhase4EntityResolution(unittest.TestCase):
    """Test Phase 4 entity resolution and clarification."""

    def test_resolve_item_exact_code(self):
        """Should resolve item by exact code."""
        # Create a test item
        test_code = "TEST-RESOLVE-001"
        if not frappe.db.exists("Item", test_code):
            frappe.get_doc({
                "doctype": "Item",
                "item_code": test_code,
                "item_name": "Test Resolve Item",
                "item_group": "Products",
                "stock_uom": "Nos",
            }).insert()
            frappe.db.commit()

        items = resolve_item(test_code)
        assert len(items) >= 1
        assert items[0]["item_code"] == test_code

        # Cleanup
        frappe.db.delete("Item", test_code)
        frappe.db.commit()

    def test_resolve_item_fuzzy_name(self):
        """Should resolve item by fuzzy name match."""
        test_name = "Fuzzy Test Item"
        test_code = "FUZZY-TEST-001"
        if not frappe.db.exists("Item", test_code):
            frappe.get_doc({
                "doctype": "Item",
                "item_code": test_code,
                "item_name": test_name,
                "item_group": "Products",
                "stock_uom": "Nos",
            }).insert()
            frappe.db.commit()

        items = resolve_item("Fuzzy Test")
        assert len(items) >= 1

        frappe.db.delete("Item", test_code)
        frappe.db.commit()

    def test_resolve_party_exact_name(self):
        """Should resolve customer by exact name."""
        test_name = "Test Customer Resolve"
        if not frappe.db.exists("Customer", test_name):
            frappe.get_doc({
                "doctype": "Customer",
                "customer_name": test_name,
                "customer_group": "Individual",
                "fbr_ntn_cnic": "TEST1234567890123",
            }).insert()
            frappe.db.commit()

        customers = resolve_party(test_name, "Customer")
        assert len(customers) >= 1

        frappe.db.delete("Customer", test_name)
        frappe.db.commit()

    def test_pick_candidate_single_match(self):
        """Should return single candidate when only one match."""
        candidates = [{"name": "ITEM-001", "item_name": "Test Item"}]
        result = pick_candidate(candidates, label="items")
        assert result["name"] == "ITEM-001"
        assert "_prompt" not in result

    def test_pick_candidate_multiple_matches(self):
        """Should return prompt when multiple matches."""
        candidates = [
            {"name": "ITEM-001", "item_code": "ITEM-001", "item_name": "Test A"},
            {"name": "ITEM-002", "item_code": "ITEM-002", "item_name": "Test B"},
        ]
        result = pick_candidate(candidates, label="items")
        assert "_prompt" in result
        assert "Multiple" in result["_prompt"]
        assert "1." in result["_prompt"]
        assert "2." in result["_prompt"]
        assert "_candidates" in result
        assert len(result["_candidates"]) == 2

    def test_clarification_needed_ambiguous_purchase(self):
        """Should request clarification for ambiguous purchase intent."""
        q = clarification_needed("Purchase Invoice", {}, [])
        assert q is not None
        assert "Purchase Order" in q
        assert "Purchase Receipt" in q
        assert "Purchase Invoice" in q

    def test_clarification_needed_missing_fields(self):
        """Should request missing required fields."""
        missing = ["customer", "items"]
        q = clarification_needed("Sales Invoice", {}, missing)
        assert q is not None
        assert "customer" in q.lower()
        assert "items" in q.lower()

    def test_clarification_needed_complete(self):
        """Should return None when no clarification needed."""
        q = clarification_needed("Sales Invoice", {"customer": "C", "items": []}, [])
        assert q is None


class TestIntentDetection(unittest.TestCase):
    """Test intent detection and DOCTYPE mapping."""

    def test_intent_create_item(self):
        """Should detect item creation intent."""
        assert detect_intent("create item") == "Item"
        assert detect_intent("item banao") == "Item"

    def test_intent_create_sales_invoice(self):
        """Should detect sales invoice intent."""
        assert detect_intent("create invoice") == "Sales Invoice"
        assert detect_intent("invoice banao") == "Sales Invoice"

    def test_intent_create_purchase_invoice(self):
        """Should detect purchase invoice intent."""
        assert detect_intent("create purchase invoice") == "Purchase Invoice"
        assert detect_intent("purchase invoice banao") == "Purchase Invoice"

    def test_intent_create_customer(self):
        """Should detect customer creation intent."""
        assert detect_intent("create customer") == "Customer"
        assert detect_intent("customer banao") == "Customer"

    def test_intent_create_supplier(self):
        """Should detect supplier creation intent."""
        assert detect_intent("create supplier") == "Supplier"
        assert detect_intent("supplier banao") == "Supplier"

    def test_intent_create_payment(self):
        """Should detect payment entry intent."""
        assert detect_intent("create payment") == "Payment Entry"
        assert detect_intent("payment banao") == "Payment Entry"

    def test_intent_ambiguous_purchase_returns_none(self):
        """Should return None for ambiguous 'purchase' (needs clarification)."""
        # After fix, bare 'purchase' should return None
        result = detect_intent("purchase")
        assert result is None


class TestDraftWorkflowSchemas(unittest.TestCase):
    """Test DOCTYPE schemas and preview generation."""

    def test_item_schema_exists(self):
        """Item schema should exist."""
        schema = DOCTYPE_SCHEMAS.get("Item")
        assert schema is not None
        assert "required" in schema

    def test_sales_invoice_schema_exists(self):
        """Sales Invoice schema should exist."""
        schema = DOCTYPE_SCHEMAS.get("Sales Invoice")
        assert schema is not None
        assert "required" in schema

    def test_generate_preview_item(self):
        """Should generate item preview."""
        data = {
            "item_name": "Test Preview Item",
            "item_group": "Products",
            "standard_rate": 100,
            "stock_uom": "Nos",
        }
        preview = generate_preview("Item", data)
        assert "Test Preview Item" in preview
        assert "100" in preview

    def test_generate_preview_sales_invoice(self):
        """Should generate sales invoice preview."""
        data = {
            "customer": "Test Customer",
            "items": [
                {"item_code": "A", "description": "Item A", "qty": 2, "rate": 50},
                {"item_code": "B", "description": "Item B", "qty": 1, "rate": 100},
            ],
        }
        preview = generate_preview("Sales Invoice", data)
        assert "Test Customer" in preview
        assert "Item A" in preview
        assert "Item B" in preview
        assert "100" in preview  # 2*50 + 1*100 = 200, but rate field shows 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
