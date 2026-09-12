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
    assert "SPI" in rest["companies"]


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
