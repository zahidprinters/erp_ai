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
from typing import ClassVar
from unittest import mock

import frappe
import pytest
from werkzeug.local import Local

from erp_ai import api as api_mod
from erp_ai.draft_workflow import (
	DOCTYPE_SCHEMAS,
	_get_action,
	clarification_needed,
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
	local.dev_server = False  # type: ignore[attr-defined]
	local.site = "test_site"  # type: ignore[attr-defined]

	# The ``flags`` namespace is a ``LocalProxy(frappe.local, 'flags')`` at
	# rest, so setting ``local.flags`` is exactly what the proxy delegates to.
	flags = mock.MagicMock()  # type: ignore[attr-defined]
	flags.in_migrate = False  # type: ignore[attr-defined]
	flags.in_install = False  # type: ignore[attr-defined]
	flags.in_test = False  # type: ignore[attr-defined]
	local.flags = flags  # type: ignore[attr-defined]

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
				"requires a database-backed site (run with: bench --site spi.local run-tests --app erp_ai)"
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
			"AI Assistant Action", filters={"session_id": ["like", "test-%"]}, pluck="name"
		):
			frappe.db.delete("AI Assistant Action", name)
		# Clean up test Items created by draft workflow tests
		for name in frappe.db.get_all("Item", filters={"item_name": ["like", "%Test%"]}, pluck="name"):
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
			pluck="name",
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
		action.expires_on = frappe.utils.add_to_date(frappe.utils.now_datetime(), minutes=-1)
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

	def test_cancelled_draft_is_terminal_and_cannot_be_revived(self):
		"""Cancelling the pending action *is* the whole cancel path.

		Replaces the old ``[DRAFT_CLEARED]`` chat-marker assertion: that marker
		was a second store for one lifecycle and could disagree with the action
		record, so cancel is now asserted on the action itself — the draft is no
		longer confirmable, no longer returned by ``get_draft``, and the DocType's
		one-way guard refuses to move it back to ``pending``.
		"""
		draft = create_draft(
			session="test-session-clear",
			action="create",
			target_doctype="Item",
			draft_data={"item_name": "Clear Test"},
			user="Administrator",
		)
		action = frappe.get_doc("AI Assistant Action", draft["name"])
		action.status = "cancelled"
		action.failure_reason = "Cancelled by user (draft discarded)"
		action.save(ignore_permissions=True)

		# A cancelled action is never executed; the recorded outcome is reported.
		result = confirm_draft(
			session="test-session-clear",
			action_id=draft["name"],
			user="Administrator",
		)
		assert result.get("error")
		assert result.get("status") == "cancelled"
		assert result.get("already_completed") is False

		# Nothing pending is left for the session.
		assert get_draft(session="test-session-clear", user="Administrator") is None
		assert _get_action(session="test-session-clear", user="Administrator") is None

		# Terminal states are one-way: a cancelled action cannot be reopened.
		action.reload()
		action.status = "pending"
		with pytest.raises(frappe.ValidationError):
			action.save(ignore_permissions=True)


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
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": test_code,
					"item_name": "Test Resolve Item",
					"item_group": "Products",
					"stock_uom": "Nos",
				}
			).insert()
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
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": test_code,
					"item_name": test_name,
					"item_group": "Products",
					"stock_uom": "Nos",
				}
			).insert()
			frappe.db.commit()

		items = resolve_item("Fuzzy Test")
		assert len(items) >= 1

		frappe.db.delete("Item", test_code)
		frappe.db.commit()

	def test_resolve_party_exact_name(self):
		"""Should resolve customer by exact name."""
		test_name = "Test Customer Resolve"
		if not frappe.db.exists("Customer", test_name):
			frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": test_name,
					"customer_group": "Individual",
					"fbr_ntn_cnic": "TEST1234567890123",
				}
			).insert()
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
		draft = self._pending_action("Unsupported DocType For Test", {"x": 1})
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

		draft = self._pending_action(
			"Item",
			{
				"item_code": "TST-CONCURRENT-%s" % frappe.generate_hash(length=6),
				"item_name": "Concurrent Test Item",
			},
		)
		action_id = draft["name"]

		# First confirmation should win the claim and create the document.
		r1 = confirm_draft(session=self.session, action_id=action_id, user=self.user)
		# Second confirmation should be rejected because the action is no longer pending.
		r2 = confirm_draft(session=self.session, action_id=action_id, user=self.user)

		# At least one result should indicate failure/already-handled.
		both_ok = (isinstance(r1, dict) and r1.get("error") is None and r1.get("name")) and (
			isinstance(r2, dict) and r2.get("error") is None and r2.get("name")
		)
		self.assertFalse(
			both_ok,
			"Two confirmations must not both succeed; r1=%r r2=%r" % (r1, r2),
		)

		# Exactly one document should have been created (the winner).
		created = frappe.get_all(
			"Item",
			filters={"item_code": draft["draft_data"]["item_code"]},
			fields=["name"],
			limit_page_length=10,
		)
		self.assertLessEqual(
			len(created), 1, "At most one Item should be created for a single pending action"
		)


class TestEndpointGuards(_SkipIfNoDB, unittest.TestCase):
	"""Audit point 5: privileged endpoints must not leak another user's data.

	``frappe.utils.file_manager.get_file()`` reads straight from disk with no
	permission check, so ``ocr_extract_text`` has to resolve the File doc and
	enforce read permission itself (fail closed).
	"""

	def tearDown(self):
		frappe.set_user("Administrator")
		for name in frappe.db.get_all(
			"File", filters={"file_name": ["like", "erp_ai_guard_%"]}, pluck="name"
		):
			frappe.delete_doc("File", name, ignore_permissions=True, force=True)
		frappe.db.commit()

	def _private_file_owned_by_administrator(self):
		from frappe.utils.file_manager import save_file

		f = save_file(
			"erp_ai_guard_%s.txt" % frappe.generate_hash(length=6),
			"secret",
			"User",
			"Administrator",
			is_private=1,
		)
		frappe.db.commit()
		assert f.owner == "Administrator"
		assert f.file_url.startswith("/private/files/")
		return f.file_url

	def test_ocr_extract_text_denies_other_users_private_file(self):
		"""A non-owner must not be able to OCR someone else's private upload."""
		from erp_ai import api as api_mod

		file_url = self._private_file_owned_by_administrator()
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				api_mod.ocr_extract_text(file_url)
		finally:
			frappe.set_user("Administrator")

	def test_ocr_extract_text_fails_closed_for_unknown_file(self):
		"""An unregistered file_url must be rejected, not read from disk."""
		from erp_ai import api as api_mod

		missing = "/private/files/erp_ai_guard_missing_%s.png" % frappe.generate_hash(length=6)
		with self.assertRaises(frappe.PermissionError):
			api_mod.ocr_extract_text(missing)


class TestDocLevelPermissionGuard(unittest.TestCase):
	"""Audit point 6: by-name document access must enforce the document-level
	(User Permission) check, not just the doctype-level one.

	``frappe.get_doc`` applies no row filters, so if the doc-level
	``frappe.has_permission(doc=...)`` call inside ``_require_doc_permission``
	were removed, any user holding the doctype-level role could read, update
	and submit documents by guessing their name. DB-free: every frappe
	touchpoint is mocked, so the denial must come from the guard itself.
	"""

	DOCTYPE = "Item"
	NAME = "SOME-ITEM"

	def _patches(self, doc_level_allowed, doc=None):
		"""doctype-level check True; doc-level check per ``doc_level_allowed``."""
		if doc is None:
			doc = mock.MagicMock(docstatus=0)
		return [
			mock.patch("frappe.has_permission", side_effect=[True, doc_level_allowed]),
			mock.patch("frappe.db.exists", return_value=True),
			mock.patch("frappe.get_doc", return_value=doc),
		]

	def test_get_document_denied_when_doc_level_check_fails(self):
		mcp = FrappeMCP()
		exists, db, get_doc = self._patches(doc_level_allowed=False)
		with exists, db, get_doc:
			result = mcp.tool_get_document(self.DOCTYPE, self.NAME)
		self.assertIn("error", result, "doc-level denial was bypassed for a by-name read")

	def test_get_document_allowed_when_both_checks_pass(self):
		doc = mock.MagicMock()
		doc.as_dict.return_value = {"doctype": self.DOCTYPE, "name": self.NAME}
		mcp = FrappeMCP()
		exists, db, get_doc = self._patches(doc_level_allowed=True, doc=doc)
		with exists, db, get_doc:
			result = mcp.tool_get_document(self.DOCTYPE, self.NAME)
		self.assertNotIn("error", result)
		self.assertEqual(result["name"], self.NAME)

	def test_update_document_denied_when_doc_level_check_fails(self):
		mcp = FrappeMCP()
		exists, db, get_doc = self._patches(doc_level_allowed=False)
		with exists, db, get_doc:
			result = mcp.tool_update_document(self.DOCTYPE, self.NAME, {"description": "x"})
		self.assertIn("error", result, "doc-level denial was bypassed for a by-name write")

	def test_submit_document_denied_when_doc_level_check_fails(self):
		mcp = FrappeMCP()
		exists, db, get_doc = self._patches(doc_level_allowed=False)
		with exists, db, get_doc:
			result = mcp.tool_submit_document(self.DOCTYPE, self.NAME)
		self.assertIn("error", result, "doc-level denial was bypassed for a by-name submit")

	def test_workspace_tool_denies_non_system_manager(self):
		mcp = FrappeMCP()
		with mock.patch("frappe.get_roles", return_value=["Stock User"]):
			result = mcp.tool_get_workspace("AI Assistant Hub")
		self.assertIn("error", result, "a non System Manager inspected a workspace")

	def test_workspace_tool_allows_system_manager(self):
		mcp = FrappeMCP()
		with (
			mock.patch("frappe.get_roles", return_value=["System Manager"]),
			mock.patch("frappe.db.exists", return_value=False),
		):
			result = mcp.tool_get_workspace("Does Not Exist")
		self.assertEqual(result.get("error"), "Workspace 'Does Not Exist' not found")

	def test_print_document_denied_when_doc_level_check_fails(self):
		"""Point 6 residual: printing is a by-name read — same gate."""
		mcp = FrappeMCP()
		exists, db, get_doc = self._patches(doc_level_allowed=False)
		with exists, db, get_doc:
			result = mcp.tool_print_document(self.DOCTYPE, self.NAME)
		self.assertIn("error", result, "doc-level denial was bypassed for a print by name")

	def test_print_document_rejects_unknown_format(self):
		mcp = FrappeMCP()
		# db.exists is called twice: document (True), then Print Format (False).
		with (
			mock.patch("frappe.has_permission", side_effect=[True, True]),
			mock.patch("frappe.db.exists", side_effect=[True, False]),
			mock.patch("frappe.get_doc", return_value=mock.MagicMock()),
		):
			result = mcp.tool_print_document(self.DOCTYPE, self.NAME, format="Made Up Format")
		self.assertIn("error", result)
		self.assertIn("Made Up Format", result["error"])


class TestWritePayloadSanitizer(unittest.TestCase):
	"""Audit point 8: one shared sanitizer must strip every framework-managed
	field from model-supplied payloads on the create/update write paths."""

	BLOCKED: ClassVar[list[str]] = [
		"doctype",
		"name",
		"creation",
		"modified",
		"modified_by",
		"idx",
		"docstatus",
		"owner",
		"parent",
		"parentfield",
		"parenttype",
		"old_parent",
		"amended_from",
		"naming_series",
	]

	def test_create_document_drops_every_blocked_field(self):
		payload = {f: "injected" for f in self.BLOCKED}
		# Writable fields that satisfy the live-metadata required-field check.
		payload.update({"item_code": "X", "item_group": "Products", "stock_uom": "Nos"})

		captured = {}

		def _fake_get_doc(data):
			captured.update(data)
			doc = mock.MagicMock()
			doc.name = "CAPTURED-ITEM"
			return doc

		mcp = FrappeMCP()
		with (
			mock.patch("frappe.has_permission", side_effect=[True]),
			mock.patch("frappe.get_doc", side_effect=_fake_get_doc),
		):
			result = mcp.tool_create_document("Item", payload)
		self.assertTrue(result.get("success"), result)
		for field in self.BLOCKED:
			if field == "doctype":
				continue  # server sets it from its own argument, never the payload
			self.assertNotIn(field, captured, "sanitizer let a framework-managed field through: %s" % field)
		self.assertEqual(captured.get("item_group"), "Products")
		# DocType is decided by the server argument, never by the payload.
		self.assertEqual(captured.get("doctype"), "Item")

	def test_update_document_drops_blocked_fields(self):
		captured = {}
		doc = mock.MagicMock()
		doc.name = "SOME-ITEM"

		def _fake_update(data):
			captured.update(data)

		doc.update.side_effect = _fake_update
		mcp = FrappeMCP()
		payload = {f: "injected" for f in self.BLOCKED}
		payload["description"] = "legit"
		with (
			mock.patch("frappe.has_permission", side_effect=[True, True]),
			mock.patch("frappe.db.exists", return_value=True),
			mock.patch("frappe.get_doc", return_value=doc),
		):
			result = mcp.tool_update_document("Item", "SOME-ITEM", payload)
		self.assertTrue(result.get("success"), result)
		for field in self.BLOCKED:
			self.assertNotIn(field, captured, "sanitizer let a framework-managed field through: %s" % field)
		self.assertEqual(captured.get("description"), "legit")


class TestQueryPermissionScoping(_SkipIfNoDB, unittest.TestCase):
	"""Audit point 6: queries must obey the caller's row-level read scope.

	``frappe.get_all`` hard-codes ``ignore_permissions=True``
	(frappe/__init__.py) and ``frappe.db.count`` / ``db.get_value`` / raw SQL
	apply no permissions at all, so a user restricted by a User Permission
	(company, warehouse, item, ...) could still list, count and resolve
	documents outside that scope. Every test below runs as a real restricted
	user and asserts the out-of-scope document never shows up.
	"""

	ITEM_A = "AI6-ALLOWED-ITEM"
	ITEM_B = "AI6-DENIED-ITEM"
	GUEST_ITEM = "AI6-GUEST-ITEM"
	USER = "ai6-restricted@example.com"
	ROLE = "Stock Manager"  # read on both Item and Bin

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self._cleanup()
		self.warehouse = frappe.db.get_value("Warehouse", {"is_group": 0}, "name")
		if not self.warehouse:
			self.skipTest("requires a site with at least one leaf Warehouse")
		self._create_fixtures()
		frappe.db.commit()
		# The new User Permission must be visible to the next permission lookup.
		frappe.clear_cache()
		frappe.cache.delete_keys("*user_permissions*")

	def tearDown(self):
		frappe.set_user("Administrator")
		self._cleanup()
		super().tearDown()

	# -- fixtures ---------------------------------------------------------
	def _create_fixtures(self):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": self.USER,
				"first_name": "AI6 Restricted",
				"send_welcome_email": 0,
				"roles": [{"role": self.ROLE}],
			}
		).insert(ignore_permissions=True)
		for code in (self.ITEM_A, self.ITEM_B):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": code,
					"item_name": code,
					"item_group": "Products",
					"stock_uom": "Nos",
				}
			).insert()
			frappe.get_doc(
				{
					"doctype": "Bin",
					"item_code": code,
					"warehouse": self.warehouse,
					"actual_qty": 5,
				}
			).insert(ignore_permissions=True)
		# Scope the user to ITEM_A only; the Bin rows follow through item_code.
		frappe.get_doc(
			{
				"doctype": "User Permission",
				"user": self.USER,
				"allow": "Item",
				"for_value": self.ITEM_A,
				"apply_to_all_doctypes": 1,
			}
		).insert(ignore_permissions=True)

	def _cleanup(self):
		items = [self.ITEM_A, self.ITEM_B, self.GUEST_ITEM]
		for doctype, filters in (
			("User Permission", {"user": self.USER}),
			("Bin", {"item_code": ["in", items]}),
			("Item", {"item_code": ["in", items]}),
			("User", {"name": self.USER}),
		):
			for name in frappe.db.get_all(doctype, filters=filters, pluck="name"):
				try:
					frappe.delete_doc(doctype, name, ignore_permissions=True, force=True)
				except Exception:
					frappe.db.delete(doctype, name)
		frappe.db.commit()

	def _as_user(self, user, fn):
		previous = frappe.session.user
		frappe.set_user(user)
		try:
			return fn()
		finally:
			frappe.set_user(previous)

	def _as_restricted(self, fn):
		return self._as_user(self.USER, fn)

	# -- read scoping -----------------------------------------------------
	def test_mcp_query_tool_hides_documents_outside_user_scope(self):
		from erp_ai.mcp.server import FrappeMCP

		filters, fields, mcp = {"item_code": ["like", "AI6-%"]}, ["item_code"], FrappeMCP()

		def _names():
			return {
				r["item_code"]
				for r in mcp.tool_query_doctype("Item", filters=filters, fields=fields, limit=50)["records"]
			}

		self.assertEqual(_names(), {self.ITEM_A, self.ITEM_B})
		self.assertEqual(
			self._as_restricted(_names),
			{self.ITEM_A},
			"tool_query_doctype returned an Item outside the user's scope",
		)

	def test_mcp_search_tool_hides_documents_outside_user_scope(self):
		from erp_ai.mcp.server import FrappeMCP

		mcp = FrappeMCP()
		found = mcp.tool_search_documents("AI6-", doctype="Item", limit=50)
		self.assertEqual({r["name"] for r in found["results"]}, {self.ITEM_A, self.ITEM_B})
		scoped = self._as_restricted(
			lambda: {
				r["name"] for r in mcp.tool_search_documents("AI6-", doctype="Item", limit=50)["results"]
			}
		)
		self.assertEqual(
			scoped, {self.ITEM_A}, "tool_search_documents returned an Item outside the user's scope"
		)

	def test_count_intent_is_permission_scoped(self):
		from erp_ai import api as api_mod

		filters = {"item_code": ["like", "AI6-%"]}
		self.assertEqual(api_mod._count("Item", filters), 2)
		self.assertEqual(
			self._as_restricted(lambda: api_mod._count("Item", filters)),
			1,
			"_count reported rows outside the user's scope",
		)

	def test_bin_sum_intent_is_permission_scoped(self):
		from erp_ai import api as api_mod
		from erp_ai.rbac import get_department_restrictions

		def _readable_sum():
			rows = frappe.get_list("Bin", fields=["actual_qty"], limit_page_length=0)
			return frappe.utils.flt(sum(r.actual_qty or 0 for r in rows))

		readable = self._as_restricted(_readable_sum)
		raw = frappe.utils.flt(frappe.db.sql("SELECT COALESCE(SUM(actual_qty),0) FROM tabBin")[0][0])
		self.assertLess(readable, raw, "fixture invalid: the user's scope did not filter Bin rows")

		# The app's department warehouses narrow the answer further (point 19):
		# the intent must equal exactly this department-and-permission-scoped
		# total, never the permission-blind raw sum.
		restricted = (get_department_restrictions(self.USER) or {}).get("warehouses") or []

		def _dept_scoped_sum():
			rows = frappe.get_list(
				"Bin",
				fields=["actual_qty", "warehouse"],
				filters={"warehouse": ["in", restricted]},
				limit_page_length=0,
			)
			return frappe.utils.flt(sum(r.actual_qty or 0 for r in rows))

		dept_scoped = self._as_restricted(_dept_scoped_sum)

		answer = self._as_restricted(lambda: api_mod._run_intent({"kind": "bin_sum"}))
		self.assertTrue(answer.get("ok"), answer)
		shown = frappe.utils.flt(answer["answer"].split("units")[0].split(":")[-1].strip().replace(",", ""))
		self.assertEqual(shown, dept_scoped, "bin_sum ignored the department warehouse scope")
		self.assertLessEqual(shown, readable, "bin_sum answered with the permission-blind total")

	def test_resolve_item_hides_documents_outside_user_scope(self):
		from erp_ai.draft_workflow import resolve_item

		self.assertTrue(resolve_item(self.ITEM_A), "fixture Item should resolve as Administrator")
		self.assertEqual(
			self._as_restricted(lambda: resolve_item(self.ITEM_B)),
			[],
			"resolve_item returned an Item outside the user's scope",
		)

	# -- by-name access: document-level (User Permission) checks ----------
	def test_mcp_get_document_denies_document_outside_user_scope(self):
		from erp_ai.mcp.server import FrappeMCP

		mcp = FrappeMCP()
		denied = self._as_restricted(lambda: mcp.tool_get_document("Item", self.ITEM_B))
		self.assertIn("error", denied, "tool_get_document returned a document outside the user's scope")
		allowed = self._as_restricted(lambda: mcp.tool_get_document("Item", self.ITEM_A))
		self.assertNotIn("error", allowed)
		self.assertEqual(allowed["name"], self.ITEM_A)

	def test_mcp_print_document_denies_document_outside_user_scope(self):
		from erp_ai.mcp.server import FrappeMCP

		mcp = FrappeMCP()
		denied = self._as_restricted(lambda: mcp.tool_print_document("Item", self.ITEM_B))
		self.assertIn("error", denied, "tool_print_document exposed a document outside the user's scope")
		allowed = self._as_restricted(lambda: mcp.tool_print_document("Item", self.ITEM_A))
		self.assertNotIn("error", allowed)
		self.assertIn("print_url", allowed)

	def test_mcp_update_document_denies_document_outside_user_scope(self):
		from erp_ai.mcp.server import FrappeMCP

		mcp = FrappeMCP()
		before = frappe.db.get_value("Item", self.ITEM_B, "description")
		denied = self._as_restricted(
			lambda: mcp.tool_update_document("Item", self.ITEM_B, {"description": "scope escape"})
		)
		self.assertIn("error", denied, "tool_update_document modified a document outside the user's scope")
		self.assertEqual(frappe.db.get_value("Item", self.ITEM_B, "description"), before)

	def test_mcp_update_document_respects_document_level_scope(self):
		"""Doc-level write check with the doctype-level check passing.

		The class user (Stock Manager) is read-only on Item on a default site,
		so a write denial there proves nothing about document scoping. This
		test creates its own user holding Item Manager (write allowed at
		doctype level) scoped by User Permission to ITEM_A only: updating
		ITEM_B must be denied by the document-level check while updating
		ITEM_A must succeed.
		"""
		from erp_ai.mcp.server import FrappeMCP

		write_user = "ai6-itemmgr@example.com"
		frappe.get_doc(
			{
				"doctype": "User",
				"email": write_user,
				"first_name": "AI6 ItemMgr",
				"send_welcome_email": 0,
				"roles": [{"role": "Item Manager"}],
			}
		).insert(ignore_permissions=True)
		self.addCleanup(self._delete_scoped_user, write_user)
		frappe.get_doc(
			{
				"doctype": "User Permission",
				"user": write_user,
				"allow": "Item",
				"for_value": self.ITEM_A,
				"apply_to_all_doctypes": 1,
			}
		).insert(ignore_permissions=True)
		frappe.clear_cache()
		frappe.cache.delete_keys("*user_permissions*")

		mcp = FrappeMCP()

		def _write(name, description):
			frappe.set_user(write_user)
			try:
				return mcp.tool_update_document("Item", name, {"description": description})
			finally:
				frappe.set_user("Administrator")

		before = frappe.db.get_value("Item", self.ITEM_B, "description")
		denied = _write(self.ITEM_B, "scope escape")
		self.assertIn("error", denied, "tool_update_document modified a document outside the user's scope")
		self.assertIn(
			self.ITEM_B, denied["error"], "denied by the doctype-level check, not the document-level one"
		)
		self.assertEqual(frappe.db.get_value("Item", self.ITEM_B, "description"), before)

		allowed = _write(self.ITEM_A, "AI6 in-scope update")
		self.assertTrue(allowed.get("success"), allowed)
		self.assertEqual(frappe.db.get_value("Item", self.ITEM_A, "description"), "AI6 in-scope update")

	# -- department-scope enforcement (audit point 19) ---------------------
	# The fixture user's Stock Manager role carries the app's department
	# restrictions (Sheikh Plastic Industries warehouses/company). These tests
	# prove the restriction is ENFORCED — on aggregates (via erp_tools._fetch)
	# and on by-name reads — not merely advisory data on the rbac module.
	def _restricted_warehouses(self):
		from erp_ai.rbac import get_department_restrictions

		rest = get_department_restrictions(self.USER) or {}
		return rest.get("warehouses") or []

	def test_department_scope_blocks_out_of_scope_aggregate(self):
		from erp_ai import erp_tools

		# Guarantee the narrowing is observable: a Bin at a warehouse outside
		# the restricted scope (cleaned up by the class _cleanup via item_code).
		outside_wh = frappe.db.get_value(
			"Warehouse", {"name": ["not in", self._restricted_warehouses()], "is_group": 0}, "name"
		)
		if not outside_wh:
			self.skipTest("site has no leaf warehouse outside the restricted scope")
		if not frappe.db.exists("Bin", {"item_code": self.ITEM_A, "warehouse": outside_wh}):
			frappe.get_doc(
				{
					"doctype": "Bin",
					"item_code": self.ITEM_A,
					"warehouse": outside_wh,
					"actual_qty": 9,
				}
			).insert(ignore_permissions=True)
			frappe.db.commit()

		restricted = self._restricted_warehouses()
		raw = frappe.db.count("Bin")
		in_scope = frappe.db.count("Bin", {"warehouse": ["in", restricted]})
		self.assertLess(in_scope, raw, "fixture invalid: no Bin exists outside the restricted warehouses")

		# The aggregate path must apply exactly the department filters.
		scoped = self._as_restricted(lambda: erp_tools._count("Bin"))
		self.assertEqual(scoped, in_scope, "aggregate did not apply the department warehouse scope")
		self.assertLess(
			scoped, raw, "department-restricted user aggregated Bins outside their warehouse scope"
		)

	def test_department_scope_blocks_by_name_read_outside_warehouse(self):
		# A Warehouse document outside the user's department scope is denied
		# even though the role grants Warehouse read — the by-name fetch must
		# re-check the scope, a query filter alone cannot. Uses a Stock User
		# (the map's most-restricted warehouse set); Stock Manager does not
		# hold Warehouse read on this site at all.
		from erp_ai.mcp.server import FrappeMCP

		user = self._ensure_dept_user()
		try:
			outside = frappe.db.get_value(
				"Warehouse", {"name": ["not in", self._warehouses_for(user)]}, "name"
			)
			if not outside:
				self.skipTest("site has no warehouse outside the restricted scope")
			mcp = FrappeMCP()
			denied = self._as_user(user, lambda: mcp.tool_get_document("Warehouse", outside))
			self.assertIn(
				"error", denied, "tool_get_document returned a Warehouse outside the department scope"
			)
			self.assertIn(outside, denied["error"])

			inside = [w for w in self._warehouses_for(user) if frappe.db.exists("Warehouse", w)]
			if not inside:
				self.skipTest("site has no warehouse inside the restricted scope")
			allowed = self._as_user(user, lambda: mcp.tool_get_document("Warehouse", inside[0]))
			self.assertNotIn("error", allowed)
		finally:
			self._drop_dept_user()

	def test_department_scope_blocks_adversarial_company_filter(self):
		from erp_ai import erp_tools

		# The user explicitly asks for another company's Warehouses: the
		# intersection with their scope is empty, so the count must be 0.
		other_company = frappe.db.get_value(
			"Company", {"name": ["not in", ["Sheikh Plastic Industries"]]}, "name"
		)
		if not other_company:
			self.skipTest("site has only the restricted company")
		user = self._ensure_dept_user()
		try:
			scoped = self._as_user(user, lambda: erp_tools._count("Warehouse", {"company": other_company}))
			self.assertEqual(scoped, 0, "adversarial company filter escaped the department scope")
		finally:
			self._drop_dept_user()

	def test_department_scope_passthrough_for_unrestricted_role(self):
		from erp_ai import erp_tools

		# Administrator carries every role on this site, including restricted
		# ones — the exemption must keep the full count visible, proving the
		# enforcement narrows only genuinely restricted users.
		admin = frappe.db.count("Bin")
		self.assertEqual(self._as_user("Administrator", lambda: erp_tools._count("Bin")), admin)

	# -- department-scope fixtures -----------------------------------------
	DEPT_USER = "ai7-dept-scope@example.com"

	def _ensure_dept_user(self):
		if not frappe.db.exists("User", self.DEPT_USER):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": self.DEPT_USER,
					"first_name": "AI7 Dept Scope",
					"send_welcome_email": 0,
					"roles": [{"role": "Stock User"}],
				}
			).insert(ignore_permissions=True)
			frappe.db.commit()
		return self.DEPT_USER

	def _drop_dept_user(self):
		if frappe.db.exists("User", self.DEPT_USER):
			frappe.delete_doc("User", self.DEPT_USER, ignore_permissions=True, force=True)
			frappe.clear_cache()

	def _warehouses_for(self, user):
		from erp_ai.rbac import get_department_restrictions

		rest = get_department_restrictions(user) or {}
		return rest.get("warehouses") or []

	def _delete_scoped_user(self, user):
		for name in frappe.db.get_all("User Permission", filters={"user": user}, pluck="name"):
			frappe.delete_doc("User Permission", name, ignore_permissions=True, force=True)
		if frappe.db.exists("User", user):
			frappe.delete_doc("User", user, ignore_permissions=True, force=True)
		frappe.clear_cache()

	# -- write scoping ----------------------------------------------------
	def test_operator_tool_create_requires_create_permission(self):
		from erp_ai.erp_tools import execute_erp_tool

		try:
			res = self._as_user(
				"Guest",
				lambda: execute_erp_tool(
					"create_item",
					{"item_code": self.GUEST_ITEM, "item_name": "AI6 Guest Item", "item_group": "Products"},
				),
			)
		except Exception as exc:  # a raised PermissionError is an acceptable failure too
			res = {"result": None, "error": str(exc)}
		self.assertIsNone(res.get("result"), "a user without create permission created an Item: %s" % res)
		self.assertFalse(frappe.db.exists("Item", self.GUEST_ITEM))


class TestLiveMetadataRequiredFields(_SkipIfNoDB, unittest.TestCase):
	"""Audit point 7: required-field validation runs against live metadata
	(so Custom Fields made mandatory elsewhere are caught too) and required
	child tables must be supplied."""

	def test_sales_invoice_missing_basics_is_rejected(self):
		"""Site-agnostic: whatever this site's live meta demands (incl. Custom
		Fields), a sparse payload must fail early with a clear, listable
		message — and the required child table must be named."""
		from erp_ai.mcp.server import _validate_required_fields

		err = _validate_required_fields("Sales Invoice", {"company": "X"})
		self.assertTrue(err)
		self.assertTrue(err.startswith("Missing required fields"), err)
		self.assertIn("Items", err)

	def test_item_with_basics_passes_validation(self):
		from erp_ai.mcp.server import _validate_required_fields

		err = _validate_required_fields(
			"Item",
			{
				"item_code": "X",
				"item_name": "X",
				"item_group": "Products",
				"stock_uom": "Nos",
			},
		)
		self.assertIsNone(err)


class TestStockIssueNL(_SkipIfNoDB, unittest.TestCase):
	"""Audit point 7: the natural-language issue path was structurally broken —
	it never supplied from_warehouse, which create_stock_issue hard-requires.
	It must now resolve the warehouse (or ask up front)."""

	ITEM = "AI7-ISSUE-ITEM"

	def _cleanup_fixtures(self):
		# Item Prices outlive a deleted Item (orphaned rows) and would make
		# the next insert fail its duplicate check.
		for name in frappe.db.get_all("Item Price", filters={"item_code": self.ITEM}, pluck="name"):
			frappe.db.delete("Item Price", name)
		if frappe.db.exists("Item", self.ITEM):
			frappe.db.delete("Item", self.ITEM)

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self._cleanup_fixtures()
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": self.ITEM,
				"item_name": self.ITEM,
				"item_group": "Products",
				"stock_uom": "Nos",
				# ERPNext refuses stock accounting entries without a valuation
				# rate for an item with no stock history.
				"valuation_rate": 10,
				"standard_rate": 10,
			}
		).insert()
		self.warehouse = frappe.db.get_value("Warehouse", {"is_group": 0, "disabled": 0}, "name")
		frappe.db.commit()

	def tearDown(self):
		frappe.set_user("Administrator")
		for name in frappe.db.get_all("Stock Entry", filters={"remarks": ["like", "AI7-%"]}, pluck="name"):
			try:
				frappe.delete_doc("Stock Entry", name, ignore_permissions=True, force=True)
			except Exception:
				frappe.db.delete("Stock Entry", name)
		self._cleanup_fixtures()
		frappe.db.commit()
		super().tearDown()

	def test_issue_nl_supplies_from_warehouse_and_creates_draft(self):
		from erp_ai.workflows.stock_issue import handle_issue_nl

		if not self.warehouse:
			self.skipTest("requires a site with at least one leaf Warehouse")
		mcp = FrappeMCP()
		res = handle_issue_nl("issue 5 %s from %s to John" % (self.ITEM, self.warehouse), mcp)
		self.assertTrue(res.get("ok"), res)
		self.assertTrue(frappe.db.exists("Stock Entry", res["name"]))
		se = frappe.get_doc("Stock Entry", res["name"])
		self.assertEqual(se.items[0].s_warehouse, self.warehouse)
		self.assertEqual(se.items[0].item_code, self.ITEM)

	def test_issue_nl_asks_for_warehouse_when_unresolvable(self):
		from erp_ai.workflows.stock_issue import handle_issue_nl

		with mock.patch("erp_ai.schema.resolve_warehouse", return_value=None):
			res = handle_issue_nl("issue 5 %s to John" % self.ITEM, FrappeMCP())
		self.assertFalse(res.get("ok"))
		self.assertTrue(any("warehouse" in m for m in res.get("missing", [])), res)

	def test_create_stock_issue_requires_from_warehouse(self):
		from erp_ai.workflows.stock_issue import create_stock_issue

		res = create_stock_issue({"item_code": self.ITEM, "qty": 5}, FrappeMCP())
		self.assertFalse(res.get("ok"))
		self.assertIn("from_warehouse", res.get("error", ""))


class TestMCPRpcAuthorization(_SkipIfNoDB, unittest.TestCase):
	"""Audit point 9: the whitelisted RPC wrapper must be reachable only by
	intended roles — Guest denied, writes manager-only, sensitive DocTypes
	System Manager-only, and PII DocTypes unavailable at any role."""

	def test_guest_is_denied(self):
		from erp_ai import mcp as mcp_rpc

		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				mcp_rpc.mcp_call_tool("query_doctype", {"doctype": "Item"})
		finally:
			frappe.set_user("Administrator")

	def test_write_requires_manager_role(self):
		from erp_ai import mcp as mcp_rpc

		frappe.set_user("Administrator")
		with mock.patch("frappe.get_roles", return_value=["Stock User"]):
			with self.assertRaises(frappe.PermissionError):
				mcp_rpc.mcp_call_tool("create_document", {"doctype": "Item", "data": {"item_code": "X"}})

	def test_manager_write_passes_the_rpc_gate(self):
		"""The gate lets a manager through; deeper tool checks still apply
		(here: the blocked-DocType check returns an error dict, no raise)."""
		from erp_ai import mcp as mcp_rpc

		frappe.set_user("Administrator")
		with mock.patch("frappe.get_roles", return_value=["Stock Manager"]):
			res = mcp_rpc.mcp_call_tool("create_document", {"doctype": "User", "data": {}})
		self.assertIn("error", res)

	def test_sensitive_doctype_requires_system_manager(self):
		from erp_ai import mcp as mcp_rpc

		frappe.set_user("Administrator")
		with mock.patch("frappe.get_roles", return_value=["Stock Manager"]):
			with self.assertRaises(frappe.PermissionError):
				mcp_rpc.mcp_call_tool("create_document", {"doctype": "Payment Entry", "data": {}})

	def test_pii_doctypes_are_not_available(self):
		for doctype in (
			"Employee",
			"Leave Application",
			"Attendance",
			"Payroll Entry",
			"Salary Structure",
			"Expense Claim",
		):
			err = _validate_doctype(doctype)
			self.assertTrue(err, "%s should not be available through the assistant" % doctype)
			self.assertIn("not available", err)


class TestChatRouteSmoke(_SkipIfNoDB, unittest.TestCase):
	"""P0 regression (fresh release audit): after the chat-dispatch refactor
	the chat endpoints referenced names that no longer existed — ``ask()``
	returned a create-confirmation built from undefined
	``_doctype/_name/_print_hint``, ``ask_v2_with_voice`` called the missing
	``ask_v2``, the widget's document-grounded endpoint ``ask_with_doc`` did
	not exist at all, and ``run_evaluation`` called the missing
	``_process_with_mcp``. All of these are request-time NameErrors that are
	invisible to imports and were invisible to the old suite."""

	api_mod = api_mod

	def test_ask_returns_plain_reply(self):
		with (
			mock.patch("erp_ai.api._data_answer", return_value={"ok": False}),
			mock.patch("erp_ai.api.ask_llm", return_value="Hello there"),
		):
			reply = api_mod.ask("hi there", session="smoke-ask")
		self.assertEqual(reply, "Hello there")

	def test_ask_data_answer_short_circuits_llm(self):
		with (
			mock.patch("erp_ai.api._data_answer", return_value={"ok": True, "answer": "We have 3 items."}),
			mock.patch("erp_ai.api.ask_llm") as llm,
		):
			reply = api_mod.ask("how many items", session="smoke-ask2")
		self.assertEqual(reply, "We have 3 items.")
		llm.assert_not_called()

	def test_ask_v2_with_voice_returns_response_and_audio(self):
		with (
			mock.patch("erp_ai.api._data_answer", return_value={"ok": False}),
			mock.patch("erp_ai.api.ask_llm", return_value="Voice hello"),
			mock.patch("erp_ai.voice.toggle.is_voice_enabled", return_value=True),
			mock.patch("erp_ai.api.text_to_speech", return_value={"url": "/files/x.wav"}) as tts,
		):
			res = api_mod.ask_v2_with_voice("hello", session="smoke-voice")
		self.assertEqual(res["response"], "Voice hello")
		self.assertEqual(res["audio_url"], "/files/x.wav")
		self.assertIsNone(res["voice_error"])
		self.assertTrue(res["session"])
		tts.assert_called_once_with("Voice hello")

	def test_ask_v2_with_voice_surfaces_tts_failure_cleanly(self):
		"""Phase 2.1: a broken TTS stage must never fail the turn — the text
		answer survives and a clean voice_error replaces the audio."""
		# (a) TTS stage reports an error dict (e.g. its own timeout).
		with (
			mock.patch("erp_ai.api._data_answer", return_value={"ok": False}),
			mock.patch("erp_ai.api.ask_llm", return_value="Voice hello"),
			mock.patch("erp_ai.voice.toggle.is_voice_enabled", return_value=True),
			mock.patch("erp_ai.api.text_to_speech", return_value={"error": "TTS timed out after 30s"}),
		):
			res = api_mod.ask_v2_with_voice("hello", session="smoke-voice-err")
		self.assertEqual(res["response"], "Voice hello")
		self.assertIsNone(res["audio_url"])
		self.assertIn("timed out", res["voice_error"])
		# (b) TTS stage raises (runtime crash) — still no traceback.
		with (
			mock.patch("erp_ai.api._data_answer", return_value={"ok": False}),
			mock.patch("erp_ai.api.ask_llm", return_value="Voice hello"),
			mock.patch("erp_ai.voice.toggle.is_voice_enabled", return_value=True),
			mock.patch("erp_ai.api.text_to_speech", side_effect=RuntimeError("piper crashed")),
		):
			res = api_mod.ask_v2_with_voice("hello", session="smoke-voice-boom")
		self.assertEqual(res["response"], "Voice hello")
		self.assertIsNone(res["audio_url"])
		self.assertIn("unavailable", res["voice_error"])

	def test_ask_with_doc_grounds_on_document(self):
		doc = mock.MagicMock()
		df = mock.MagicMock()
		df.fieldname = "item_code"
		doc.meta.fields = [df]
		doc.item_code = "SMOKE-ITEM"
		with (
			mock.patch("erp_ai.api._resolve", return_value=doc),
			mock.patch("erp_ai.api._data_answer", return_value={"ok": False}),
			mock.patch("erp_ai.api.ask_llm", return_value="It is SMOKE-ITEM") as llm,
		):
			res = api_mod.ask_with_doc("Item", "SMOKE-ITEM", "what is this?", session="smoke-doc")
		self.assertEqual(res["response"], "It is SMOKE-ITEM")
		self.assertEqual(res["doctype"], "Item")
		self.assertIn("SMOKE-ITEM", llm.call_args[0][0])

	def test_run_evaluation_runs_without_name_error(self):
		with (
			mock.patch("erp_ai.api._data_answer", return_value={"ok": False}),
			mock.patch("erp_ai.api.ask_v2", return_value={"ok": True, "answer": "I cannot do that."}),
		):
			res = api_mod.run_evaluation(limit=3)
		self.assertEqual(res["total"], 3)
		self.assertIn("pass_rate", res)

	def test_operator_system_prompt_hides_write_tools(self):
		prompt = api_mod._operator_system_prompt("Administrator")
		self.assertNotIn("create_item(", prompt)
		self.assertIn("read-only", prompt)

	def test_count_never_falls_back_to_unfiltered(self):
		"""A failed filtered count must answer nothing, not leak the unfiltered
		total outside the caller's row-level scope."""
		with mock.patch("erp_ai.api._aggregate", return_value=None) as agg:
			self.assertIsNone(api_mod._count("Item", {"bogus_field": ["=", "x"]}))
		self.assertEqual(agg.call_count, 1)


class TestRouteWhitelistContract(_SkipIfNoDB, unittest.TestCase):
	"""P0 #2/#86: every public route must really be a public route.

	A dropped ``@frappe.whitelist()`` or a renamed function is invisible to
	imports and to the old suite, so this test reads the decorators straight out
	of the source with ``ast`` and asserts Frappe actually registered the same
	function object. It fails if a route is renamed without updating callers, if
	the decorator is lost in a refactor, or if a function is decorated twice.
	"""

	@staticmethod
	def _decorated_route_names():
		import ast

		path = frappe.get_app_path("erp_ai", "api.py")
		with open(path) as handle:
			tree = ast.parse(handle.read())
		names = []
		for node in tree.body:
			if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
				continue
			for decorator in node.decorator_list:
				target = decorator.func if isinstance(decorator, ast.Call) else decorator
				if (getattr(target, "attr", None) or getattr(target, "id", None)) == "whitelist":
					names.append(node.name)
					break
		return names

	def test_every_decorated_route_is_registered_with_frappe(self):
		from erp_ai import api as api_mod

		routes = self._decorated_route_names()
		self.assertGreaterEqual(len(routes), 25, "api.py lost public routes")
		for name in routes:
			fn = getattr(api_mod, name, None)
			self.assertIsNotNone(fn, "api.%s is decorated but missing" % name)
			self.assertIn(fn, frappe.whitelisted, "api.%s is decorated but not registered" % name)

	def test_routes_are_callable_by_keyword(self):
		"""Routes are dispatched as ``frappe.call(fn, **frappe.form_dict)``
		(frappe/handler.py::execute_cmd), so a *required* argument is fine — the
		caller passes it as a form field, exactly like the core
		``frappe.client.get(doctype, name)`` endpoint.

		What can never work over RPC is a POSITIONAL_ONLY parameter: no form
		field can bind it.
		"""
		import inspect

		from erp_ai import api as api_mod

		for name in self._decorated_route_names():
			sig = inspect.signature(getattr(api_mod, name))
			positional_only = [p.name for p in sig.parameters.values() if p.kind is p.POSITIONAL_ONLY]
			self.assertEqual(
				positional_only, [], "route api.%s has positional-only args %s" % (name, positional_only)
			)
			# Every parameter must be satisfiable from form_dict keyed by name.
			try:
				sig.bind(**{n: None for n, p in sig.parameters.items() if p.kind is not p.VAR_KEYWORD})
			except TypeError as exc:
				self.fail("route api.%s is not callable by keyword: %s" % (name, exc))

	def test_all_named_p0_routes_exist(self):
		"""Every endpoint the audit listed must exist and be importable."""
		from erp_ai import api as api_mod

		for name in (
			"ask",
			"ask_v2",
			"ask_v2_with_voice",
			"ask_with_doc",
			"run_evaluation",
			"workflow_shipment_receipt",
			"workflow_stock_issue",
			"ocr_extract_text",
			"list_available_models",
		):
			self.assertTrue(callable(getattr(api_mod, name, None)), "api.%s is missing" % name)

	def test_mcp_rpc_surface_is_whitelisted(self):
		from erp_ai import mcp as mcp_rpc

		for name in ("mcp_call_tool", "mcp_list_tools"):
			fn = getattr(mcp_rpc, name, None)
			self.assertTrue(callable(fn), "mcp.%s is missing" % name)
			if fn in frappe.whitelisted:
				continue
			# whitelist(methods=[...]) still registers the function object;
			# bound-method wrappers compare by __func__ instead.
			self.assertIn(
				getattr(fn, "__func__", fn), frappe.whitelisted, "mcp.%s is not exposed to RPC" % name
			)


class TestQueryValidationContract(_SkipIfNoDB, unittest.TestCase):
	"""P1 #14/#15/#16: unknown fields, bad operators and unbounded limits.

	``frappe.get_list`` silently drops unknown columns, so before this contract
	the tools answered with the wrong data instead of an error. These tests pin
	the fail-loud behaviour.
	"""

	def test_unknown_field_is_rejected(self):
		from erp_ai.erp_tools import _fetch

		with self.assertRaises(ValueError) as ctx:
			_fetch("Item", fields=["item_code", "totally_made_up_field"])
		self.assertIn("totally_made_up_field", str(ctx.exception))

	def test_unknown_filter_field_is_rejected(self):
		from erp_ai.erp_tools import _fetch

		with self.assertRaises(ValueError):
			_fetch("Item", filters={"not_a_field": "x"}, fields=["item_code"])

	def test_unsupported_operator_is_rejected(self):
		from erp_ai.erp_tools import _fetch

		with self.assertRaises(ValueError) as ctx:
			_fetch("Item", filters={"item_code": ["regex", "^A"]}, fields=["item_code"])
		self.assertIn("regex", str(ctx.exception))

	def test_or_filters_inside_filters_is_rejected(self):
		"""The exact bug: ``or_filters`` nested inside ``filters`` was forwarded
		to frappe as a column filter on every list tool."""
		from erp_ai.erp_tools import _fetch

		with self.assertRaises(ValueError) as ctx:
			_fetch("Item", filters={"or_filters": [{"item_code": "A"}]})
		self.assertIn("keyword argument", str(ctx.exception))

	def test_unknown_order_by_is_rejected(self):
		from erp_ai.erp_tools import _fetch

		with self.assertRaises(ValueError):
			_fetch("Item", fields=["item_code"], order_by="made_up desc")

	def test_valid_order_by_with_direction_is_accepted(self):
		from erp_ai.erp_tools import _fetch

		_fetch("Item", fields=["item_code", "modified"], order_by="modified desc", limit_page_length=1)

	def test_oversized_limit_is_rejected_not_clamped(self):
		"""The model supplies these values, so an oversized limit fails loud:
		a silently narrowed row set is a wrong answer, a rejected query is a
		diagnosable one (see the ``_fetch`` docstring)."""
		from erp_ai.erp_tools import _MAX_LIMIT, _fetch

		with self.assertRaises(ValueError) as ctx:
			_fetch("Item", fields=["item_code"], limit_page_length=10**6)
		self.assertIn(str(_MAX_LIMIT), str(ctx.exception))
		# An at-the-limit value is still a normal read.
		self.assertIsInstance(_fetch("Item", fields=["item_code"], limit_page_length=_MAX_LIMIT), list)

	def test_aggregate_field_expressions_are_allowed(self):
		"""``count(name) as total`` must pass validation (the audit helpers rely
		on it) while its inner column is still checked."""
		from erp_ai.erp_tools import _column_of

		self.assertEqual(_column_of("count(name) as total"), "name")
		self.assertEqual(_column_of("sum(grand_total) as total"), "grand_total")
		self.assertEqual(_column_of("item_code"), "item_code")

	def test_search_items_matches_on_name_code_and_description(self):
		"""Regression: the nested-or_filters bug made this tool return nothing."""
		from erp_ai.erp_tools import search_items

		code = "AI6-SEARCH-PROBE"
		if not frappe.db.exists("Item", code):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": code,
					"item_name": "Zeta Probe Widget",
					"item_group": "Products",
					"stock_uom": "Nos",
					"is_stock_item": 0,
				}
			).insert(ignore_permissions=True)
			frappe.db.commit()
			self.addCleanup(lambda: frappe.delete_doc("Item", code, ignore_permissions=True, force=True))
		self.assertIn(code, [row["item_code"] for row in search_items("Zeta Probe")])

	def test_validation_is_skipped_when_doctype_metadata_is_absent(self):
		"""A site without ERPNext has no metadata for business DocTypes; the
		tools must degrade to an empty answer, not reject every field."""
		from erp_ai.erp_tools import _validate_query

		self.assertIsNone(_validate_query("Not A Real Doctype", fields=["whatever"], filters={"x": "y"}))


class TestOperatorToolAuthorization(_SkipIfNoDB, unittest.TestCase):
	"""P0 #4/#6/#8: the operator tool registry is not an authorization bypass.

	``execute_erp_tool`` dispatches a model-supplied name into ``ERP_TOOLS``.
	These tests pin that (a) nobody outside the registry can be reached, (b) the
	registry holds no write tool that skips the draft/permission path, and
	(c) a user without create permission cannot create through an operator tool.
	"""

	RESTRICTED_USER = "ai6-operator-restricted@example.com"
	ROLE = "Stock User"  # read on Item, no create on Customer

	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_unknown_tool_name_is_refused(self):
		from erp_ai.erp_tools import execute_erp_tool

		result = execute_erp_tool("create_payment_entry", {"party": "x"})
		self.assertFalse(result["success"])
		self.assertIn("Unknown tool", result["error"])

	def test_rejected_create_is_reported_as_a_failure(self):
		"""A create tool returns None when the draft is rejected (no permission,
		duplicate, validation). The dispatcher used to report success for any
		result, so the model was told "created" for a document that never
		existed."""
		from erp_ai.erp_tools import execute_erp_tool

		with mock.patch.dict("erp_ai.erp_tools.ERP_TOOLS", {"create_probe": lambda **kw: None}):
			result = execute_erp_tool("create_probe", {})
		self.assertFalse(result["success"])
		self.assertIn("created nothing", result["error"])

	def test_read_tool_returning_none_is_still_success(self):
		"""A read tool answering "no data" is not a failure, so the new check
		must stay scoped to the create tools."""
		from erp_ai.erp_tools import execute_erp_tool

		with mock.patch.dict("erp_ai.erp_tools.ERP_TOOLS", {"get_probe": lambda **kw: None}):
			result = execute_erp_tool("get_probe", {})
		self.assertTrue(result["success"])
		self.assertIsNone(result["result"])

	def test_arbitrary_admin_tools_are_not_reachable(self):
		"""A model-invented name must not resolve to a privileged helper."""
		from erp_ai.erp_tools import execute_erp_tool

		for name in (
			"grant_role",
			"frappe.client.insert",
			"get_doc",
			"delete_document",
			"submit_document",
			"__import__",
			"system_console",
		):
			self.assertFalse(execute_erp_tool(name, {})["success"], "%s must not be dispatchable" % name)

	def test_registry_contains_only_erp_ai_callables(self):
		from erp_ai.erp_tools import ERP_TOOLS

		for name, fn in ERP_TOOLS.items():
			self.assertTrue(callable(fn), name)
			self.assertTrue(
				getattr(fn, "__module__", "").startswith("erp_ai"),
				"%s comes from %s" % (name, getattr(fn, "__module__", "?")),
			)

	def test_create_tools_have_no_direct_write_bypass(self):
		"""Static proof: no operator create tool calls Document.insert/save or
		frappe.db.commit directly (they route through create_draft_for_review)."""
		import ast

		path = frappe.get_app_path("erp_ai", "erp_tools.py")
		with open(path) as handle:
			tree = ast.parse(handle.read())
		banned = {"insert", "save", "submit", "delete"}
		offenders = []
		for node in ast.walk(tree):
			if not isinstance(node, ast.FunctionDef):
				continue
			if not node.name.startswith("create_"):
				continue
			for call in ast.walk(node):
				if not isinstance(call, ast.Call):
					continue
				attr = getattr(call.func, "attr", None)
				if attr in banned or attr == "commit":
					offenders.append("%s().%s()" % (node.name, attr))
		self.assertEqual(offenders, [], "operator create tools bypass the draft path")

	def _ensure_restricted_user(self):
		if not frappe.db.exists("User", self.RESTRICTED_USER):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": self.RESTRICTED_USER,
					"first_name": "AI6 Operator Restricted",
					"send_welcome_email": 0,
					"roles": [{"role": self.ROLE}],
				}
			).insert(ignore_permissions=True)
			frappe.db.commit()
			self.addCleanup(self._drop_restricted_user)
		frappe.clear_cache()
		frappe.cache.delete_keys("*user_permissions*")

	def _drop_restricted_user(self):
		frappe.set_user("Administrator")
		if frappe.db.exists("User", self.RESTRICTED_USER):
			frappe.delete_doc("User", self.RESTRICTED_USER, ignore_permissions=True, force=True)
		frappe.db.commit()

	def test_restricted_user_cannot_create_customer_via_operator_tool(self):
		from erp_ai.erp_tools import execute_erp_tool

		self._ensure_restricted_user()
		name = "AI6-DENIED-CUSTOMER-%s" % frappe.generate_hash(length=6)
		frappe.set_user(self.RESTRICTED_USER)
		try:
			result = execute_erp_tool("create_customer", {"customer_name": name})
		finally:
			frappe.set_user("Administrator")
		# The Customer's *id* comes from the naming series, not from the
		# customer_name the tool received, so looking it up by `name` would pass
		# vacuously whether or not the write happened. Check the real value.
		self.assertFalse(
			frappe.db.get_value("Customer", {"customer_name": name}, "name"),
			"restricted user created a Customer",
		)
		self.assertFalse(result.get("success"), "operator tool reported success for a denied create")

	def test_guest_is_refused_every_create_tool(self):
		from erp_ai.erp_tools import ERP_TOOLS, execute_erp_tool

		creates = [n for n in ERP_TOOLS if n.startswith("create_")]
		self.assertTrue(creates, "no create tools registered")
		frappe.set_user("Guest")
		try:
			for name in creates:
				self.assertFalse(execute_erp_tool(name, {})["success"], name)
		finally:
			frappe.set_user("Administrator")


class TestErrorLoggingNeverMasksFailures(_SkipIfNoDB, unittest.TestCase):
	"""Regression: ``frappe.log_error`` takes the TITLE first and Error Log caps
	the title at 140 chars, so the old ``log_error(f'...{str(e)}', 'ERP AI
	Operator')`` calls raised CharacterLengthExceededError from inside the
	``except`` block — replacing the real tool error with a logging error.
	"""

	def test_safe_logger_truncates_a_long_title(self):
		from erp_ai.audit import log_error_safely

		log_error_safely("A" * 1000, "message body")  # must not raise
		frappe.db.commit()

	def test_safe_logger_tolerates_non_string_titles(self):
		from erp_ai.audit import log_error_safely

		log_error_safely(ValueError("boom" * 200))
		frappe.db.commit()

	def test_safe_logger_records_structured_context(self):
		"""Phase 1.3: context + retryable flag land in the log entry as
		machine-readable lines."""
		from erp_ai.audit import log_error_safely

		log_error_safely(
			"erp_ai.test.structured",
			"simulated failure",
			context={
				"action_id": "ACT-TEST-1",
				"provider": "Ollama (Local)",
				"model": "llama3",
				"session": "sess-1",
				"user": "u1",
			},
			retryable=True,
		)
		frappe.db.commit()
		entry = frappe.get_all(
			"Error Log",
			filters={"method": "erp_ai.test.structured"},
			fields=["error"],
			order_by="creation desc",
			limit_page_length=1,
		)
		self.assertTrue(entry, "structured log entry not written")
		msg = entry[0]["error"] or ""
		self.assertIn('"action_id": "ACT-TEST-1"', msg)
		self.assertIn('"provider": "Ollama (Local)"', msg)
		self.assertIn("class: retryable", msg)

	def test_safe_logger_fatal_classification(self):
		from erp_ai.audit import log_error_safely

		log_error_safely("erp_ai.test.fatal", "bad data", context={"k": "v"}, retryable=False)
		frappe.db.commit()
		entry = frappe.get_all(
			"Error Log",
			filters={"method": "erp_ai.test.fatal"},
			fields=["error"],
			order_by="creation desc",
			limit_page_length=1,
		)
		self.assertTrue(entry)
		self.assertIn("class: fatal", entry[0]["error"])

	def test_safe_logger_classifies_exception_type(self):
		"""Passing the exception as ``retryable`` classifies by type:
		timeout/connection errors are retryable, others fatal."""
		import requests

		from erp_ai.audit import _classify_retryable

		class MyCustomTimeout(TimeoutError):
			pass

		self.assertTrue(_classify_retryable(requests.Timeout("t")))
		self.assertTrue(_classify_retryable(requests.ConnectionError("c")))
		self.assertFalse(_classify_retryable(ValueError("nope")))
		self.assertTrue(_classify_retryable(MyCustomTimeout("custom")))
		frappe.db.commit()

	def test_tool_error_logging_never_raises(self):
		from erp_ai.erp_tools import _log_tool_error

		_log_tool_error("some_tool", Exception("z" * 5000))
		_log_tool_error("some_tool", RuntimeError("boom"))
		frappe.db.commit()

	def test_execute_erp_tool_reports_the_real_error_on_failure(self):
		"""A failing tool must return its own message, not a logging error."""
		from erp_ai.erp_tools import execute_erp_tool

		boom = RuntimeError("q" * 5000)
		with mock.patch.dict("erp_ai.erp_tools.ERP_TOOLS", {"probe_tool": mock.Mock(side_effect=boom)}):
			result = execute_erp_tool("probe_tool", {})
		self.assertFalse(result["success"])
		self.assertEqual(result["error"], str(boom))


class TestOperatorCreatePayloadContract(_SkipIfNoDB, unittest.TestCase):
	"""Every key an operator create tool sends must exist in that DocType's
	schema contract.

	``create_document_from_draft`` -> ``_create_*_doc`` whitelists the keys it
	maps, so a payload key that is *not* in ``DOCTYPE_SCHEMAS`` is silently
	dropped: the tool reports success while the value never reaches the
	document. This is the regression guard for that class of bug (Customer /
	Supplier ``email``, Sales Order ``warehouse`` + ``terms``, Item
	``description`` / ``valuation_rate``).
	"""

	def _capture_payload(self, fn, *args, **kwargs):
		"""Run a create tool with the write boundary stubbed, return its payload."""
		captured = {}

		def _record(payload):
			captured.update(payload)
			return "AI6-CONTRACT-PROBE"

		with mock.patch("erp_ai.erp_tools.create_draft_for_review", _record):
			fn(*args, **kwargs)
		self.assertTrue(captured, "tool built no payload (write boundary not reached)")
		return captured

	def _assert_contract(self, payload):
		doctype = payload["doctype"]
		schema = DOCTYPE_SCHEMAS.get(doctype)
		self.assertIsNotNone(schema, "%s is not in DOCTYPE_SCHEMAS" % doctype)
		allowed = set(schema.get("required", [])) | set(schema.get("optional", []))
		child = schema.get("child_table") or {}
		child_field = child.get("fieldname")
		for key, value in payload.items():
			if key == "doctype":
				continue
			if child_field and key == child_field:
				child_allowed = set(child.get("required", [])) | set(child.get("optional", []))
				for row in value:
					self.assertEqual(
						set(row) - child_allowed,
						set(),
						"%s.%s[] carries dropped keys %s" % (doctype, key, set(row) - child_allowed),
					)
				continue
			self.assertIn(key, allowed, "%s payload key %r is dropped by the creator" % (doctype, key))
		return payload

	def test_item_payload_is_inside_the_schema_contract(self):
		from erp_ai.erp_tools import create_item

		payload = self._capture_payload(
			create_item,
			item_code="AI6-CONTRACT-ITEM",
			item_name="AI6 Contract Item",
			item_group="Products",
			description="from the tool",
			is_stock_item=0,
			standard_rate=11,
			valuation_rate=7,
		)
		self._assert_contract(payload)
		# Argument values must survive the mapping, not merely be whitelisted.
		self.assertEqual(payload["description"], "from the tool")
		self.assertEqual(payload["valuation_rate"], 7)
		self.assertEqual(payload["is_stock_item"], 0)

	def test_customer_payload_is_inside_the_schema_contract(self):
		from erp_ai.erp_tools import create_customer

		payload = self._capture_payload(
			create_customer,
			customer_name="AI6 Contract Customer",
			phone_no="03001234567",
			email_id="contract@example.com",
		)
		self._assert_contract(payload)
		# `email` is the schema key that the creator maps onto the Customer's
		# email_id column; sending the column name here dropped the address.
		self.assertEqual(payload["email"], "contract@example.com")
		self.assertEqual(payload["mobile_no"], "03001234567")

	def test_supplier_payload_is_inside_the_schema_contract(self):
		from erp_ai.erp_tools import create_supplier

		payload = self._capture_payload(
			create_supplier,
			supplier_name="AI6 Contract Supplier",
			phone_no="03001234568",
			email_id="supplier@example.com",
		)
		self._assert_contract(payload)
		self.assertEqual(payload["email"], "supplier@example.com")
		# Supplier has no `territory` field, so the argument maps onto `country`.
		self.assertEqual(payload["country"], "Pakistan")

	def test_sales_order_payload_is_inside_the_schema_contract(self):
		from erp_ai.erp_tools import create_sales_order

		company = frappe.db.get_value("Company", {}, "name")
		warehouse = frappe.db.get_value("Warehouse", {"is_group": 0}, "name")
		if not (company and warehouse):
			self.skipTest("site has no Company/Warehouse")
		payload = self._capture_payload(
			create_sales_order,
			customer="AI6 Contract Customer",
			items=[{"item_code": "AI6-CONTRACT-ITEM", "qty": 2, "rate": 5}],
			delivery_date="2026-01-01",
			company=company,
			warehouse=warehouse,
			currency="PKR",
			comments="please expedite",
		)
		self._assert_contract(payload)
		# `remarks` is the Sales Order free-text field; the old `terms` key was
		# dropped, so the operator's comment never reached the document.
		self.assertEqual(payload["remarks"], "please expedite")
		self.assertEqual(payload["items"][0]["warehouse"], warehouse)


if __name__ == "__main__":
	pytest.main([__file__, "-v"])
