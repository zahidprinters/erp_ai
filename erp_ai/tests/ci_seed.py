"""Seed the minimal ERPNext masters the Frappe-backed test suite assumes.

A bare ``bench new-site`` only installs the apps' fixtures — masters like the
"Nos" UOM, "Individual" customer group and a default Company are normally
created by ERPNext's interactive setup wizard, so a fresh CI site lacks them
and ~14 tests fail with LinkValidationError / "Missing required fields".

Run from CI right after site creation (idempotent — safe to re-run):

    bench --site test_site execute erp_ai.tests.ci_seed.seed
"""
import frappe

COMPANY = "Test CI Company"
CURRENCY = "INR"


def _insert_if_missing(doctype, lookup, values):
    """Insert when absent; return the existing/created document name."""
    existing = frappe.db.exists(doctype, lookup)
    if existing:
        return existing
    doc = frappe.get_doc(dict(values, doctype=doctype))
    doc.insert(ignore_permissions=True)
    return doc.name


def _root_group(doctype, group_field, fallback):
    name = frappe.db.get_value(doctype, {"is_group": 1}, group_field)
    if name:
        return name
    return _insert_if_missing(doctype, fallback, {
        group_field: fallback,
        "is_group": 1,
    })


def seed():
    # 1. UOM used by every test Item (created by the ERPNext setup wizard)
    _insert_if_missing("UOM", "Nos", {
        "uom_name": "Nos", "enabled": 1, "must_be_whole_number": 1,
    })

    # 2. Item Group "Products" the tests hardcode (guard, though install
    #    usually seeds it already)
    root_ig = _root_group("Item Group", "item_group_name", "All Item Groups")
    _insert_if_missing("Item Group", "Products", {
        "item_group_name": "Products",
        "parent_item_group": root_ig,
        "is_group": 0,
    })

    # 3. Customer Group "Individual" the tests hardcode
    root_cg = _root_group("Customer Group", "customer_group_name", "All Customer Groups")
    _insert_if_missing("Customer Group", "Individual", {
        "customer_group_name": "Individual",
        "parent_customer_group": root_cg,
        "is_group": 0,
    })

    # 4. Currency for the Company's default_currency
    _insert_if_missing("Currency", CURRENCY, {
        "currency_name": CURRENCY, "enabled": 1,
        "number_format": "#,##.##", "symbol": "Rs",
    })

    # 5. Country (Company.validate requires one) + Company + global defaults.
    #    draft_workflow resolves "company" via
    #    frappe.defaults.get_global_default("company") — i.e. Global Defaults.
    _insert_if_missing("Country", "Pakistan", {
        "country_name": "Pakistan", "code": "PK",
        "date_format": "dd-mm-yyyy", "time_format": "HH:mm:ss",
        "number_format": "#,##.##",
    })
    _insert_if_missing("Company", COMPANY, {
        "company_name": COMPANY, "abbr": "TCI",
        "default_currency": CURRENCY, "country": "Pakistan",
    })
    frappe.db.set_single_value("Global Defaults", "default_company", COMPANY)
    frappe.db.set_single_value("Global Defaults", "default_currency", CURRENCY)
    if not frappe.db.get_single_value("Global Defaults", "country"):
        frappe.db.set_single_value("Global Defaults", "country", "Pakistan")

    # 6. Warehouses: a group plus the leaf names the tests resolve against
    #    ("Raw Materials" in the receipt flow; any leaf for stock tests).
    wh_group = _insert_if_missing("Warehouse", {"warehouse_name": "All Warehouses", "company": COMPANY}, {
        "warehouse_name": "All Warehouses", "company": COMPANY, "is_group": 1,
    })
    for leaf in ("Raw Materials", "Stores"):
        _insert_if_missing("Warehouse", {"warehouse_name": leaf, "company": COMPANY}, {
            "warehouse_name": leaf, "company": COMPANY,
            "parent_warehouse": wh_group, "is_group": 0,
        })

    # 7. Supplier used by the shipment-receipt confirm test
    sg = _insert_if_missing("Supplier Group", "All Supplier Groups", {
        "supplier_group_name": "All Supplier Groups", "is_group": 1,
    })
    _insert_if_missing("Supplier", "Ship Test Ltd", {
        "supplier_name": "Ship Test Ltd", "supplier_group": sg,
        "country": "Pakistan",
    })

    # 8. Item the receipt confirm test consumes (its own setUp may create it
    #    too — the guard keeps this harmless)
    _insert_if_missing("Item", "TST-CONF-ITEM", {
        "item_code": "TST-CONF-ITEM", "item_name": "TST-CONF-ITEM",
        "item_group": "Products", "stock_uom": "Nos",
        "standard_rate": 10, "valuation_rate": 10,
    })

    frappe.db.commit()
