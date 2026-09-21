# ---------------------------------------------------------------------------
# RBAC tests — approval limits, supervisor rules, department restrictions.
# ---------------------------------------------------------------------------
from erp_ai.rbac import (
	can,
	check_amount_limit,
	get_approval_limit,
	get_department_restrictions,
	get_doctype_category,
	requires_supervisor,
)


def test_approval_limit_admin():
	"""Administrator has no limit."""
	# Mock-free: verify the data structure
	from erp_ai.rbac import APPROVAL_LIMITS

	assert APPROVAL_LIMITS["Administrator"] is None
	assert APPROVAL_LIMITS["System Manager"] is None


def test_approval_limit_stock_user():
	"""Stock User has a limit."""
	from erp_ai.rbac import APPROVAL_LIMITS

	assert APPROVAL_LIMITS["Stock User"] == 10000


def test_approval_limit_auditor():
	"""Auditor has zero limit (read-only)."""
	from erp_ai.rbac import APPROVAL_LIMITS

	assert APPROVAL_LIMITS["Auditor"] == 0


def test_requires_supervisor_data():
	"""Verify supervisor requirement data."""
	from erp_ai.rbac import REQUIRES_SUPERVISOR

	assert "submit" in REQUIRES_SUPERVISOR["Stock User"]
	assert "cancel" in REQUIRES_SUPERVISOR["Stock User"]
	assert "delete" in REQUIRES_SUPERVISOR["Purchase User"]


def test_department_restrictions_data():
	"""Verify department restriction data."""
	from erp_ai.rbac import DEPARTMENT_RESTRICTIONS

	rest = DEPARTMENT_RESTRICTIONS["Stock User"]
	assert rest is not None
	assert "Stores - SPI" in rest["warehouses"]
	assert "Sheikh Plastic Industries" in rest["companies"]


def test_department_restrictions_admin():
	"""Admin has no restrictions."""
	from erp_ai.rbac import DEPARTMENT_RESTRICTIONS

	assert "Administrator" not in DEPARTMENT_RESTRICTIONS


def test_approval_limits_structure():
	"""Approval limits data should be well-formed."""
	from erp_ai.rbac import APPROVAL_LIMITS

	for role, limit in APPROVAL_LIMITS.items():
		assert isinstance(role, str)
		assert limit is None or (isinstance(limit, (int, float)) and limit >= 0)


def test_doctype_category_manufacturing():
	"""Manufacturing doctypes have correct category."""
	assert get_doctype_category("BOM") == "production"
	assert get_doctype_category("Work Order") == "production"
	assert get_doctype_category("Job Card") == "production"


def test_doctype_category_quality():
	"""Quality doctypes have correct category."""
	assert get_doctype_category("Quality Inspection") == "quality"


def test_doctype_category_maintenance():
	"""Maintenance doctypes have correct category."""
	assert get_doctype_category("Asset") == "maintenance"
	assert get_doctype_category("Asset Maintenance") == "maintenance"
	assert get_doctype_category("Asset Repair") == "maintenance"


def test_doctype_category_hr():
	"""HR doctypes have correct category."""
	assert get_doctype_category("Employee") == "hr"
	assert get_doctype_category("Leave Application") == "hr"
	assert get_doctype_category("Expense Claim") == "hr"


def test_doctype_category_unknown():
	"""Unknown doctype returns 'other'."""
	assert get_doctype_category("UnknownDocType") == "other"


# --- Department-scope enforcement (audit point 19) ---
class _Meta:
	def __init__(self, fields):
		self._fields = set(fields)

	def has_field(self, name):
		return name in self._fields


class _Doc:
	def __init__(self, **values):
		self._values = values

	def get(self, key):
		return self._values.get(key)


def _stub_frappe(monkeypatch, roles, meta_fields):
	import sys
	import types

	meta = _Meta(meta_fields)
	monkeypatch.setitem(
		sys.modules,
		"frappe",
		types.SimpleNamespace(
			session=types.SimpleNamespace(user="tester"),
			get_meta=lambda doctype: meta,
		),
	)
	import erp_ai.rbac as rbac

	monkeypatch.setattr(rbac, "get_user_roles", lambda user=None: roles)
	return rbac


def test_apply_department_filters_scopes_bin_warehouse(monkeypatch):
	# Real Bin meta has `warehouse` but no `company` field.
	rbac = _stub_frappe(monkeypatch, ["Stock User"], {"warehouse"})

	filters = rbac.apply_department_filters("tester", "Bin", {"item_code": "X"})
	# The restricted user only sees their own warehouse...
	assert filters["warehouse"] == ["in", ["Stores - SPI"]]
	# ...and Bin has no company field, so none was invented.
	assert "company" not in filters
	assert filters["item_code"] == "X"


def test_apply_department_filters_cannot_be_widened_by_caller(monkeypatch):
	rbac = _stub_frappe(monkeypatch, ["Sales User"], {"company"})

	# The user asks for another company's invoices: the intersection is empty,
	# which must produce a no-match filter, not the user's requested company.
	filters = rbac.apply_department_filters("tester", "Sales Invoice", {"company": "Demo FBR Company"})
	assert filters["company"][1] == rbac._SCOPE_EMPTY


def test_apply_department_filters_list_form_is_anded(monkeypatch):
	rbac = _stub_frappe(monkeypatch, ["Stock Manager"], {"warehouse"})

	filters = rbac.apply_department_filters(
		"tester", "SomeWarehouseScopedDoc", [["posting_date", ">=", "2026-01-01"]]
	)
	assert ["warehouse", "in", ["Finished Goods - SPI", "Stores - SPI", "Work In Progress - SPI"]] in filters
	assert ["posting_date", ">=", "2026-01-01"] in filters


def test_apply_department_filters_passthrough_for_unrestricted(monkeypatch):
	rbac = _stub_frappe(monkeypatch, ["Accounts Manager"], {"company"})

	filters = {"company": "Anything"}
	assert rbac.apply_department_filters("tester", "Sales Invoice", filters) is filters


def test_record_outside_department_scope(monkeypatch):
	rbac = _stub_frappe(monkeypatch, ["Stock User"], {"warehouse", "company"})

	outside = _Doc(company="Demo FBR Company")
	inside = _Doc(company="Sheikh Plastic Industries", warehouse="Stores - SPI")
	assert rbac.record_outside_department_scope("tester", "Sales Invoice", outside) is True
	assert rbac.record_outside_department_scope("tester", "Sales Invoice", inside) is False
