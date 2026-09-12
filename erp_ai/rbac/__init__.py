# ---------------------------------------------------------------------------
# Role-Based Access Control (RBAC) — AI-specific permission layer.
#
# This module provides an AI-specific permission map that supplements
# (does NOT replace) Frappe's native permission system. Every AI operation
# should ALSO call frappe.has_permission() before performing ERP actions.
#
# Frappe's native permissions (roles, DocType perms, User Permissions,
# permission levels, workflow rules, ownership) remain authoritative.
# This module adds AI-category-based policy on top.
#
# Permission levels:
#   "none"   — cannot access this at all
#   "read"   — can view/query only
#   "create" — can create drafts
#   "submit" — can create + submit
#   "all"    — full access (create/submit/cancel/amend)
# ---------------------------------------------------------------------------
from typing import Dict, List, Optional

# Role → permission level for each doctype category
ROLE_PERMISSIONS: Dict[str, Dict[str, str]] = {
    "Administrator": {"*": "all"},
    "System Manager": {"*": "all"},
    "Accounts Manager": {
        "accounting": "all", "sales": "all", "purchase": "all",
        "stock": "read", "reports": "all",
    },
    "Accounts User": {
        "accounting": "create", "sales": "create", "purchase": "create",
        "stock": "read", "reports": "read",
    },
    "Sales Manager": {
        "sales": "all", "stock": "read", "reports": "all", "accounting": "read",
    },
    "Sales User": {
        "sales": "create", "stock": "read", "reports": "read",
    },
    "Purchase Manager": {
        "purchase": "all", "stock": "read", "reports": "all", "accounting": "read",
    },
    "Purchase User": {
        "purchase": "create", "stock": "read", "reports": "read",
    },
    "Stock Manager": {
        "stock": "all", "sales": "read", "purchase": "read", "reports": "all",
    },
    "Stock User": {
        "stock": "create", "sales": "read", "purchase": "read", "reports": "read",
    },
    "Manufacturing Manager": {
        "production": "all", "stock": "all", "reports": "all",
    },
    "Manufacturing User": {
        "production": "create", "stock": "create", "reports": "read",
    },
    "HR Manager": {"hr": "all", "reports": "all"},
    "HR User": {"hr": "create", "reports": "read"},
    "Auditor": {"*": "read"},
}

# Doctype → category mapping
DOCTYPE_CATEGORIES: Dict[str, str] = {
    "Sales Invoice": "accounting", "Purchase Invoice": "accounting",
    "Payment Entry": "accounting", "Journal Entry": "accounting",
    "Account": "accounting", "Cost Center": "accounting",
    "Tax Rule": "accounting", "Item Tax Template": "accounting",
    "Sales Order": "sales", "Delivery Note": "sales",
    "Quotation": "sales", "Customer": "sales",
    "Customer Group": "sales", "Lead": "sales", "Opportunity": "sales",
    "Purchase Order": "purchase", "Purchase Receipt": "purchase",
    "Supplier": "purchase", "Supplier Group": "purchase",
    "Material Request": "purchase",
    "Item": "stock", "Item Group": "stock", "Stock Entry": "stock",
    "Warehouse": "stock", "Price List": "stock",
    "UOM": "stock", "UoM": "stock",
    "Stock Reconciliation": "stock", "Batch": "stock", "Serial No": "stock",
    "BOM": "production", "Work Order": "production",
    "Job Card": "production", "Production Plan": "production",
    "Quality Inspection": "quality",
    "Asset": "maintenance", "Asset Maintenance": "maintenance",
    "Asset Repair": "maintenance", "Asset Movement": "maintenance",
    "Employee": "hr", "Leave Application": "hr",
    "Attendance": "hr", "Payroll Entry": "hr", "Salary Structure": "hr",
    "Expense Claim": "hr",
    "Project": "projects", "Task": "projects",
    "Request for Quotation": "purchase", "Supplier Quotation": "purchase",
}

# Approval limits per role (max transaction amount in company currency).
# None means no limit. Set to 0 to require supervisor approval for everything.
APPROVAL_LIMITS: Dict[str, Optional[float]] = {
    "Administrator": None,
    "System Manager": None,
    "Accounts Manager": None,
    "Accounts User": 50000,
    "Sales Manager": None,
    "Sales User": 25000,
    "Purchase Manager": None,
    "Purchase User": 50000,
    "Stock Manager": None,
    "Stock User": 10000,
    "Manufacturing Manager": None,
    "Manufacturing User": 10000,
    "HR Manager": None,
    "HR User": 5000,
    "Auditor": 0,
}

# Which actions require supervisor confirmation regardless of amount.
REQUIRES_SUPERVISOR: Dict[str, List[str]] = {
    "Accounts User": ["submit", "cancel"],
    "Sales User": ["submit", "cancel", "delete"],
    "Purchase User": ["submit", "cancel", "delete"],
    "Stock User": ["submit", "cancel"],
    "Manufacturing User": ["submit", "cancel"],
    "HR User": ["submit", "cancel", "delete"],
}

# Department-specific warehouse/company restrictions.
# Each entry: role -> { "warehouses": [...], "companies": [...] }
# None means no restriction (all accessible).
DEPARTMENT_RESTRICTIONS: Dict[str, Optional[Dict[str, List[str]]]] = {
    "Stock Manager": {"warehouses": ["Stores - SPI", "Work In Progress - SPI", "Finished Goods - SPI"], "companies": ["SPI"]},
    "Stock User": {"warehouses": ["Stores - SPI"], "companies": ["SPI"]},
    "Manufacturing User": {"warehouses": ["Work In Progress - SPI", "Stores - SPI"], "companies": ["SPI"]},
    "Sales User": {"companies": ["SPI"]},
    "Purchase User": {"companies": ["SPI"]},
}

# Permission hierarchy
PERMISSION_LEVELS = {"none": 0, "read": 1, "create": 2, "submit": 3, "all": 4}


def get_user_roles(user=None):
    """Return the list of roles for a user."""
    import frappe
    user = user or frappe.session.user
    return frappe.get_roles(user)


def get_user_categories(user=None):
    """Return the best permission level per category for a user."""
    roles = get_user_roles(user)
    best = {}
    for role in roles:
        role_perms = ROLE_PERMISSIONS.get(role, {})
        for category, level in role_perms.items():
            if category == "*":
                for cat in set(DOCTYPE_CATEGORIES.values()):
                    current = best.get(cat, "none")
                    if PERMISSION_LEVELS.get(level, 0) > PERMISSION_LEVELS.get(current, 0):
                        best[cat] = level
                continue
            current = best.get(category, "none")
            if PERMISSION_LEVELS.get(level, 0) > PERMISSION_LEVELS.get(current, 0):
                best[category] = level
    return best


def get_doctype_category(doctype):
    """Return the category for a doctype."""
    return DOCTYPE_CATEGORIES.get(doctype, "other")


def can(user, doctype, action):
    """Check if a user can perform an action on a doctype.

    For unmapped doctypes (category "other"), only wildcard ("*") roles
    like Administrator/System Manager are allowed. This prevents silent
    permission grants for unknown doctypes.
    """
    action_level = _action_to_level(action)
    if action_level == 0:
        return False
    categories = get_user_categories(user)
    cat = get_doctype_category(doctype)
    user_level = PERMISSION_LEVELS.get(categories.get(cat, "none"), 0)
    wildcard_level = PERMISSION_LEVELS.get(categories.get("*", "none"), 0)
    # For unknown doctypes, only wildcard roles are permitted
    if cat == "other" and wildcard_level == 0:
        return False
    return max(user_level, wildcard_level) >= action_level


def can_create(user, doctype):
    return can(user, doctype, "create")


def can_submit(user, doctype):
    return can(user, doctype, "submit")


def can_read(user, doctype):
    return can(user, doctype, "read")


def can_cancel(user, doctype):
    return can(user, doctype, "cancel")


def get_allowed_doctypes(user=None, action="read"):
    """Return all doctypes a user can perform an action on."""
    action_level = _action_to_level(action)
    categories = get_user_categories(user)
    allowed = []
    for doctype, cat in DOCTYPE_CATEGORIES.items():
        user_level = PERMISSION_LEVELS.get(categories.get(cat, "none"), 0)
        wildcard_level = PERMISSION_LEVELS.get(categories.get("*", "none"), 0)
        if max(user_level, wildcard_level) >= action_level:
            allowed.append(doctype)
    return sorted(allowed)


def check_permission(user, doctype, action):
    """Check permission. Returns error message if denied, None if allowed."""
    if not can(user, doctype, action):
        cat = get_doctype_category(doctype)
        roles = get_user_roles(user)
        return (
            "Access denied: your role does not allow %s on %s (%s). Your roles: %s."
        ) % (action, doctype, cat, ", ".join(roles))
    return None


def get_approval_limit(user=None):
    """Return the max transaction amount for a user (None = no limit)."""
    import frappe
    user = user or frappe.session.user
    roles = get_user_roles(user)
    best = None
    for role in roles:
        limit = APPROVAL_LIMITS.get(role)
        if limit is None:
            return None  # No limit at all
        if best is None or limit > best:
            best = limit
    return best


def requires_supervisor(user, action):
    """Check if an action requires supervisor confirmation for this user."""
    import frappe
    user = user or frappe.session.user
    roles = get_user_roles(user)
    for role in roles:
        if action in REQUIRES_SUPERVISOR.get(role, []):
            return True
    return False


def get_department_restrictions(user=None):
    """Return warehouse/company restrictions for a user."""
    import frappe
    user = user or frappe.session.user
    roles = get_user_roles(user)
    warehouses = set()
    companies = set()
    has_restriction = False
    for role in roles:
        rest = DEPARTMENT_RESTRICTIONS.get(role)
        if rest is None:
            continue
        has_restriction = True
        warehouses.update(rest.get("warehouses") or [])
        companies.update(rest.get("companies") or [])
    if not has_restriction:
        return None
    return {"warehouses": sorted(warehouses), "companies": sorted(companies)}


def check_amount_limit(user, amount):
    """Check if amount is within the user's approval limit. Returns (ok, limit)."""
    limit = get_approval_limit(user)
    if limit is None:
        return True, None
    return float(amount) <= limit, limit


def _action_to_level(action):
    """Convert an action name to its permission level number."""
    mapping = {
        "read": "read", "view": "read", "query": "read",
        "create": "create", "write": "create",
        "submit": "submit", "cancel": "all", "amend": "all", "delete": "all",
    }
    return PERMISSION_LEVELS.get(mapping.get(action, "none"), 0)
