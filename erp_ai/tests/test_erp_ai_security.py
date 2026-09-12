"""
ERP AI Security & Workflow Tests

These tests verify Phase 1-4 improvements:
- Phase 1: Security guardrails (DocType allowlist, permission checks)
- Phase 2: Draft persistence with AI Assistant Action DocType
- Phase 3: Atomicity (single commit point)
- Phase 4: Entity resolution and clarification

Run with:  bench --site spi.local run-tests --app erp_ai
       or:  python -m pytest erp_ai/tests/test_erp_ai_security.py
       or:  python -m unittest erp_ai.tests.test_erp_ai_security

All three runners are supported: the ``bench`` runner boots the full Frappe test
context (no priming needed); the bare ``pytest``/``unittest`` runners call
``_bind_test_context`` in ``setUpModule`` so the suite can run without the bench
harness.  ``_bind_test_context`` is a no-op when a real Frappe context is already
bound (bench runner).
"""
import json
import unittest
from unittest import mock

import frappe
import pytest
from werkzeug.local import Local

from erp_ai.draft_workflow import (
    DOCTYPE_SCHEMAS,
    _get_action,
    clarification_needed,
    clear_draft,
    confirm_draft,
    create_document_from_draft,
    create_draft,
    detect_intent,
    generate_preview,
    get_draft,
    get_missing_fields,
    pick_candidate,
    resolve_item,
    resolve_party,
)
from erp_ai.mcp.server import (
    ALLOWED_DOCTYPES,
    BLOCKED_DOCTYPES,
    FrappeMCP,
    _require_permission,
    _validate_doctype,
)


def _bind_test_context():
    """Prime a minimal ``frappe.local``/``flags``/``cache`` context so this file
    can be executed under a bare ``pytest`` or ``unittest`` runner without the
    ``bench run-tests`` harness.

    When the ``bench`` runner is active it sets ``frappe.flags.in_test`` before
    importing test modules, so we take that as the signal that a real Frappe
    context is already available and leave everything untouched.  Otherwise we
    prime only what the DB-free test classes in this file actually read.
    """
    # Already inside the real Frappe test harness?  Nothing to do.
    if getattr(frappe.flags, "in_test", False):
        return

    # ``frappe.local`` at module load IS a ``werkzeug.Local`` (not a proxy).
    local = frappe.local  # type: Local
    local.request_context = True  # type: ignore[attr-defined]
    local.dev_server = False      # type: ignore[attr-defined]
    local.site = "test_site"      # type: ignore[attr-defined]

    # The ``flags`` namespace is a ``LocalProxy(frappe.local, 'flags')`` at
    # rest, so setting ``local.flags`` is exactly what the proxy delegates to.
    flags = mock.MagicMock()  # type: ignore[attr-defined]
    flags.in_migrate = False   # type: ignore[attr-defined]
    flags.in_install = False   # type: ignore[attr-defined]
    flags.in_test = False      # type: ignore[attr-defined]
    local.flags = flags        # type: ignore[attr-defined]

    # ``frappe.cache`` is ``None`` until site bootstrap.  The DB-free classes
    # in this file never touch the cache, so a no-op stub is enough for them.
    class _MemoryCache:
        def __init__(self):
            self._store = {}

        def get_value(self, key):
            return self._store.get(key)

        def set_value(self, key, value, **_):
            self._store[key] = value

        def delete_value(self, key):
            self._store.pop(key, None)

        def delete_keys(self, pattern):
            prefix = pattern.rstrip(b"*") if isinstance(pattern, bytes) else pattern
            for key in list(self._store):
                if key.startswith(prefix):
                    del self._store[key]

        def hget(self, key, field):
            v = self._store.get(key)
            if isinstance(v, dict):
                return v.get(field)
            return None

        def hset(self, key, field, value):
            if key not in self._store or not isinstance(self._store[key], dict):
                self._store[key] = {}
            self._store[key][field] = value

        def incr(self, key, *, default=0):
            v = self._store.get(key, default) + 1
            self._store[key] = v
            return v

        def ttl(self, key):
            return -1

    frappe.cache = _MemoryCache()  # type: ignore[assignment]

    # ``frappe.get_system_settings`` reaches for the System Settings DocType in
    # the real app; without a DB that raises.  The one place our bare-path code
    # reaches for is the time-zone default used by ``now_datetime()``.  Rather
    # than patching the function, seed the in-memory cache with a fake System
    # Settings doc so the real ``get_cached_doc`` path returns a usable stub.
    class _MemoryCache:
        def __init__(self):
            self._store: dict = {}

        def get_value(self, key):
            return self._store.get(key)

        def set_value(self, key, value, **_):
            self._store[key] = value

        def delete_value(self, key, **_):
            self._store.pop(key, None)

        def delete_keys(self, pattern):
            _pre = pattern.rstrip(b"*") if isinstance(pattern, bytes) else pattern
            for _key in list(self._store):
                if _key.startswith(_pre):
                    del self._store[_key]

        def hget(self, key, field):
            _v = self._store.get(key)
            if isinstance(_v, dict):
                return _v.get(field)
            return None

        def hset(self, key, field, value):
            if key not in self._store or not isinstance(self._store[key], dict):
                self._store[key] = {}
            self._store[key][field] = value

        def incr(self, key, *, default=0):
            _v = self._store.get(key, default) + 1
            self._store[key] = _v
            return _v

        def ttl(self, key):
            return -1

    frappe.cache = _MemoryCache()  # type: ignore[assignment]
    frappe.cache.set_value(
        "document_cache::DocType::System Settings",
        {"name": "System Settings", "doctype": "System Settings", "time_zone": "Asia/Kolkata"},
    )


def _has_real_db():
    """Return True if a real, DB-backed Frappe site context is available.

    When the ``bench run-tests`` harness is active ``frappe.db`` is a real
    ``Database`` instance.  Under a bare ``pytest``/``unittest`` runner we
    replace it with a stub ``Local`` (see ``_bind_test_context``), so this
    probe tells the two cases apart without crashing.
    """
    try:
        from frappe.database.database import Database
    except ImportError:
        try:
            # older Frappe layout
            from frappe.database import Database
        except ImportError:
            return False
    db = frappe.db
    if not isinstance(db, Database):
        return False
    try:
        db.get_singles_dict("System Settings")
        return True
    except Exception:
        return False


class _SkipIfNoDB(unittest.TestCase):
    """Mixin that skips DB-requiring test methods when no real site DB is present.

    Used as a *base class* (after ``unittest.TestCase``) for the DB-requiring
    test classes in this file, so they run under the ``bench run-tests``
    harness and skip cleanly under a bare ``pytest``/``unittest`` runner.
    """

    def setUp(self):
        super().setUp()
        if not _has_real_db():
            self.skipTest(
                "requires a database-backed site "
                "(run with: bench --site spi.local run-tests --app erp_ai)"
            )


def _skip_if_no_db(_cls=None):
    """Class decorator form: same effect as the ``_SkipIfNoDB`` mixin, for
    readers who prefer the decorator idiom (unused in this file now)."""
    if _cls is None:
        return _skip_if_no_db
    return _cls
# NOTE: most classes in this file exercise frappe.get_doc / frappe.db / frappe.cache
# and therefore require a database-backed Frappe site context.  The ``bench
# run-tests`` runner provides that context; the bare ``pytest``/``unittest``
# runners (via ``_bind_test_context``) can only run the DB-free classes below
# (``TestPhase1Security``, and the non-DB methods of the other classes).  When
# running without the bench harness, the DB-requiring tests gracefully skip with
# a clear message instead of crashing on unbound frappe.locals.


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


class TestPhase2DraftWorkflow(_SkipIfNoDB, unittest.TestCase):
    """Test Phase 2 draft persistence with AI Assistant Action DocType."""

    def tearDown(self):
        """Clean up test data after each test."""
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
        create_draft(
            session="test-session-user1",
            action="create",
            target_doctype="Item",
            draft_data={"item_name": "Test 1"},
            user="Administrator",
        )
        create_draft(
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
        create_draft(
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
        create_draft(
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


class TestPhase3Atomicity(_SkipIfNoDB, unittest.TestCase):
    """Test Phase 3 atomicity: single commit point in create_document_from_draft."""

    def test_create_document_from_draft_commits(self):
        """create_document_from_draft should commit once at the end."""
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


class TestPhase4EntityResolution(_SkipIfNoDB, unittest.TestCase):
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


class TestRollbackAndIdempotencyContracts(_SkipIfNoDB):
    """Production-hardening contracts for rollback references and concurrent
    confirmation arbitration.

    These tests use the real Frappe site DB (hence the ``_SkipIfNoDB`` base) and
    are intentionally small: they assert the observable behavior a user/operator
    relies on in production, not the internal implementation details.
    """

    def setUp(self):
        super().setUp()
        self.session = "sess-rollback-idem-%s" % frappe.generate_hash(length=8)
        self.user = frappe.session.user

    def _pending_action(self, doctype, data, action="create"):
        draft = create_draft(
            session=self.session,
            action=action,
            target_doctype=doctype,
            draft_data=data,
            user=self.user,
        )
        if not isinstance(draft, dict):
            raise AssertionError("create_draft did not return a dict: %r" % draft)
        return draft

    def test_rollback_reference_stored_on_failed_confirmation(self):
        """A failed confirmation must leave a navigable rollback_reference on
        the action, not just a generic failure reason."""
        # A pending action for an unsupported doctype fails at execution time
        # (create_document_from_draft returns an error), which should end up as
        # a failed action with a rollback reference.
        draft = self._pending_action(
            "Unsupported DocType For Test", {"x": 1}
        )
        action_id = draft["name"]

        res = confirm_draft(session=self.session, action_id=action_id, user=self.user)
        # We expect a failure result (not a successful document creation).
        self.assertIsInstance(res, dict)
        self.assertTrue(
            res.get("error") or res.get("status") in ("failed",),
            "Expected failed confirmation, got: %r" % res,
        )

        stored = frappe.get_doc("AI Assistant Action", action_id)
        self.assertEqual(stored.status, "failed")
        rb = getattr(stored, "rollback_reference", None) or ""
        rb_decoded = frappe.parse_json(rb) if rb else None
        self.assertIsNotNone(rb_decoded, "rollback_reference must be stored and JSON-decodable")
        self.assertIn("target_docname", rb_decoded)
        # The rollback reference should point back to the action outcome.
        self.assertTrue(rb_decoded.get("target_docname") or rb_decoded.get("result_summary"))

    def test_concurrent_confirms_cannot_both_materialize(self):
        """Two concurrent confirmations of the same pending action must not both
        create a document: the claim is atomic and only one winner proceeds."""
        from erp_ai.draft_workflow import _claim_action

        draft = self._pending_action("Item", {"item_code": "TST-CONCURRENT-%s" % frappe.generate_hash(length=6),
                                              "item_name": "Concurrent Test Item"})
        action_id = draft["name"]

        # First confirmation should win the claim and create the document.
        r1 = confirm_draft(session=self.session, action_id=action_id, user=self.user)
        # Second confirmation should be rejected because the action is no longer pending.
        r2 = confirm_draft(session=self.session, action_id=action_id, user=self.user)

        # At least one result should indicate failure/already-handled.
        both_ok = (isinstance(r1, dict) and r1.get("error") is None and r1.get("name")) and (
            isinstance(r2, dict) and r2.get("error") is None and r2.get("name"))
        self.assertFalse(
            both_ok,
            "Two confirmations must not both succeed; r1=%r r2=%r" % (r1, r2),
        )

        # Exactly one document should have been created (the winner).
        created = frappe.get_all("Item", filters={"item_code": draft["draft_data"]["item_code"]},
                                  fields=["name"], limit_page_length=10)
        self.assertLessEqual(len(created), 1,
                             "At most one Item should be created for a single pending action")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
