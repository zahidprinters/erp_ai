# ---------------------------------------------------------------------------
# ERP AI install / migrate hooks.
# ---------------------------------------------------------------------------

import frappe


def after_install():
    """Seed help articles and sync workspace after app install."""
    _ensure_schema()
    _seed_help_articles()
    _seed_number_cards()
    _sync_workspace()


def after_migrate():
    """Re-seed help articles and re-sync workspace after every migrate.

    Also creates the schema the app's runtime invites rely on (the idempotency
    unique index) — doing it here instead of per-request keeps DDL off the
    request path. Idempotent: safe to run multiple times.
    """
    _ensure_schema()
    _seed_help_articles()
    _seed_number_cards()
    _sync_workspace()


def _ensure_schema():
    """Create/repair indexes that runtime correctness depends on."""
    from erp_ai.idempotency import ensure_unique_index
    ensure_unique_index()


NUMBER_CARDS = (
    {
        "label": "Active Items",
        "document_type": "Item",
        "filters_json": '{"disabled": 0}',
        "color": "#2563eb",
    },
    {
        "label": "Customers",
        "document_type": "Customer",
        "color": "#059669",
    },
    {
        "label": "Suppliers",
        "document_type": "Supplier",
        "color": "#d97706",
    },
    {
        "label": "Open Sales Orders",
        "document_type": "Sales Order",
        "filters_json": '{"docstatus": 1, "status": ["not in", ["Completed", "Closed", "Cancelled"]]}',
        "color": "#7c3aed",
    },
)


def _seed_number_cards():
    """Create the public, read-only count cards used by the AI workspace."""
    for card_data in NUMBER_CARDS:
        try:
            if frappe.db.exists("Number Card", card_data["label"]):
                card = frappe.get_doc("Number Card", card_data["label"])
                for field, value in card_data.items():
                    setattr(card, field, value)
                card.save(ignore_permissions=True)
                continue
            card = frappe.get_doc({
                "doctype": "Number Card",
                "label": card_data["label"],
                "type": "Document Type",
                "function": "Count",
                "is_public": 1,
                **card_data,
            })
            card.insert(ignore_permissions=True)
        except Exception as e:
            frappe.log_error("erp_ai: seed number card failed", str(e))


def _seed_help_articles():
    from erp_ai.help.seed_articles import seed_all
    try:
        seed_all()
    except Exception as e:
        frappe.log_error("erp_ai: seed help articles failed", str(e))


def _sync_workspace():
    from erp_ai.api import setup_workspace
    try:
        setup_workspace()
    except Exception as e:
        frappe.log_error("erp_ai: sync workspace failed", str(e))


def sync_workspace(**kwargs):
    """Bench-execute entrypoint: bench --site <site> execute erp_ai.install.sync_workspace"""
    _seed_number_cards()
    return _sync_workspace()
