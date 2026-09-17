
"""
ERP Operator Tools - Comprehensive ERPNext interaction for AI

This module provides tools that allow the AI to:
1. Query ERPNext data (items, customers, suppliers, companies, etc.)
2. Execute ERP operations (create documents, update records)
3. Analyze business data (stock levels, orders, transactions)

All tools are designed to be called by the AI assistant based on user queries.
Every read goes through frappe.get_list() (permission-aware) and every write
through Document.insert()/save(), so the caller's own roles and User Permission
row filters always apply - nothing here bypasses frappe.has_permission().
"""

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import frappe

from erp_ai.rbac import apply_department_filters

# ---------------------------------------------------------------------------
# Query validation (audit points 14-17). The model supplies `filters`, `fields`,
# `order_by` and (through `limit`) the row count in operator/chat questions. An
# invented field name would otherwise reach frappe.get_list and come back as an
# opaque SQL error, a malformed filter value would be mis-applied, and an
# oversized limit would turn a list read into a full-table scan. All three are
# rejected up front with a diagnosable message instead of being silently
# dropped or trusted.
# ---------------------------------------------------------------------------
_MAX_LIMIT = 500
_MAX_FILTERS = 25
_FILTER_OPS = frozenset({
    "=", "!=", ">", "<", ">=", "<=", "like", "not like", "in", "not in",
    "is", "is not", "between", "timespan",
})
# Columns frappe.get_list exposes on every DocType, regardless of metadata.
_STANDARD_FIELDS = frozenset({
    "name", "owner", "creation", "modified", "modified_by", "docstatus", "idx",
    "_user_tags", "_comments", "_assign", "_liked_by",
})
_AGGREGATE_RE = re.compile(
    r"^(count|sum|avg|min|max|group_concat)\(\s*(\w+)\s*\)\s+as\s+(\w+)$", re.I
)


def _column_of(field: str) -> str:
    """Return the underlying column name: 'count(name) as total' -> 'name'."""
    match = _AGGREGATE_RE.match(field.strip())
    return match.group(2) if match else field.strip()


def _validate_filter_dict(doctype: str, filters: Dict, valid: set) -> Optional[str]:
    """Reject an unknown filter field or an unsupported operator, else None."""
    if not isinstance(filters, dict):
        return f"filters must be a dict, got {type(filters).__name__}"
    if len(filters) > _MAX_FILTERS:
        return f"Too many filters ({len(filters)} > {_MAX_FILTERS})"
    for key, value in filters.items():
        if key in ("or_filters", "and_filters"):
            return f"'{key}' must be a keyword argument, not a key inside filters"
        if key not in valid:
            return f"Unknown field '{key}' on {doctype}"
        if isinstance(value, (list, tuple)):
            if not value:
                return f"Empty filter condition for '{key}' on {doctype}"
            op = value[0]
            if not isinstance(op, str) or op.lower() not in _FILTER_OPS:
                return f"Unsupported filter operator {op!r} for '{key}' on {doctype}"
    return None


def _validate_query(doctype, fields=None, filters=None, order_by=None,
                    or_filters=None, and_filters=None) -> Optional[str]:
    """Return an error message if the query names something invalid, else None.

    Validation is skipped when the DocType has no metadata (ERPNext not
    installed on the site): in that case every field name would look invalid and
    rejecting the query would break the degraded-but-useful empty answer.
    """

    try:
        meta = frappe.get_meta(doctype)
    except frappe.DoesNotExistError:
        # The DocType has no metadata at all (ERPNext not installed on the site,
        # or a bogus name): there is nothing to validate field names against, so
        # skip instead of rejecting every field and breaking the degraded-but-
        # useful empty answer. Without this, frappe.get_meta *throws* and the
        # documented skip path above was unreachable dead code.
        return None
    known = {f.fieldname for f in meta.fields}
    if not known:
        return None
    valid = known | _STANDARD_FIELDS
    if fields:
        for field in fields:
            if not isinstance(field, str) or _column_of(field) not in valid:
                return f"Unknown field '{field}' on {doctype}"
    if order_by:
        for token in str(order_by).split(","):
            column = token.strip().split(" ")[0]
            if column and column not in valid:
                return f"Unknown order_by field '{column}' on {doctype}"
    for candidate in (filters, and_filters):
        if candidate:
            err = _validate_filter_dict(doctype, candidate, valid)
            if err:
                return err
    if or_filters:
        if not isinstance(or_filters, (list, tuple)):
            return "or_filters must be a list of filter dicts"
        for clause in or_filters:
            err = _validate_filter_dict(doctype, clause, valid)
            if err:
                return err
    return None


def _fetch(doctype: str, *args, **kwargs) -> List[Dict]:
    """Permission-aware, validated list read.

    ``frappe.get_all`` forces ``ignore_permissions=True`` (frappe/__init__.py),
    which skips both the role check and the row-level filters coming from User
    Permissions (company, warehouse, item, ...). These tools answer live
    operator/chat questions, so every read goes through ``frappe.get_list``.
    A DocType the current user may not read yields an empty list, so one
    forbidden module degrades the answer instead of failing the whole tool.

    An invalid field/filter/order_by raises rather than being dropped (audit
    point 14) and an oversized limit is rejected rather than silently clamped
    (audit points 15-16: the model supplies these values, so a rejected query
    is diagnosable where a silently narrowed one is not).

    ``limit_page_length=0`` (frappe's "no limit") is deliberately allowed: it is
    only used by the internal aggregate helpers below, where truncating the row
    set would silently produce a wrong SUM/COUNT.
    """
    limit = kwargs.get("limit_page_length")
    if limit and int(limit) > _MAX_LIMIT:
        raise ValueError(
            f"Invalid query for {doctype}: limit_page_length {limit} exceeds "
            f"the maximum of {_MAX_LIMIT}"
        )
    err = _validate_query(
        doctype,
        fields=kwargs.get("fields"),
        filters=kwargs.get("filters"),
        order_by=kwargs.get("order_by"),
        or_filters=kwargs.get("or_filters"),
        and_filters=kwargs.get("and_filters"),
    )
    if err:
        raise ValueError(f"Invalid query for {doctype}: {err}")
    # Department scope enforcement (audit point 19): the app's warehouse/
    # company restrictions are ANDed into every read here — the one path all
    # list tools, counts, sums and API aggregates funnel through — so a
    # restricted role can never aggregate rows outside their scope.
    kwargs["filters"] = apply_department_filters(
        frappe.session.user, doctype, kwargs.get("filters"))
    try:
        return frappe.get_list(doctype, *args, **kwargs)
    except frappe.PermissionError:
        return []


def _count(doctype: str, filters: Optional[Dict] = None) -> int:
    """Permission-aware COUNT (``frappe.db.count`` applies no permissions)."""
    rows = _fetch(doctype, filters=filters or {}, fields=["count(name) as total"], limit_page_length=0)
    if not rows:
        return 0
    return int(rows[0].get("total") or 0)


def _first(doctype: str, filters: Dict, fields: List[str]) -> Optional[Dict]:
    """Permission-aware single-row read (``frappe.db.get_value`` ignores perms)."""
    rows = _fetch(doctype, filters=filters, fields=fields, limit_page_length=1)
    return rows[0] if rows else None


def _sum(doctype: str, filters: Dict, field: str) -> float:
    """Permission-aware SUM (``frappe.db.get_sum`` ignores permissions)."""
    rows = _fetch(doctype, filters=filters, fields=["sum(%s) as total" % field], limit_page_length=0)
    if not rows:
        return 0
    return rows[0].get("total") or 0


def _log_tool_error(tool_name: str, error) -> None:
    """Log a tool failure without letting logging mask the original error.

    ``frappe.log_error`` takes the TITLE first and Error Log caps that title at
    140 characters, so the previous ``frappe.log_error(f'...{str(e)}', 'ERP AI
    Operator')`` calls passed the full message as the title and raised
    CharacterLengthExceededError from inside the except block — replacing the
    real tool error with a logging error. erp_ai.audit.log_error_safely
    truncates and can never raise.
    """
    from erp_ai.audit import log_error_safely

    log_error_safely(f'ERP AI Operator [{tool_name}]', str(error))


def get_system_overview() -> Dict[str, Any]:
    """
    Get comprehensive overview of the entire ERP system.
    Returns counts and key data for all major modules.
    """
    overview = {
        "timestamp": datetime.now().isoformat(),
        "companies": [],
        "customers": [],
        "suppliers": [],
        "items_summary": {},
        "warehouses": [],
        "open_orders": {"sales": 0, "purchase": 0},
        "recent_transactions": []
    }

        # Companies
    companies = _fetch(
        'Company',
        fields=['name', 'company_name', 'default_currency', 'country', 'phone_no', 'email', 'website'],
        order_by='name'
    )
    overview['companies'] = [
        {
            'name': c['name'],
            'company_name': c.get('company_name', ''),
            'currency': c['default_currency'],
            'country': c['country'],
            'phone': c['phone_no'],
            'email': c['email'],
            'website': c.get('website', '')
        }
        for c in companies
    ]

    # Customers
    customers = _fetch(
        'Customer',
        fields=['name', 'customer_name', 'customer_group', 'territory', 'customer_type', 'default_currency'],
        order_by='customer_name'
    )
    overview['customers'] = [
        {
            'name': c['name'],
            'customer_name': c['customer_name'],
            'group': c['customer_group'],
            'territory': c['territory'],
            'type': c['customer_type'],
            'currency': c['default_currency']
        }
        for c in customers
    ]

        # Suppliers
    suppliers = _fetch(
        'Supplier',
        fields=['name', 'supplier_name', 'supplier_group', 'country', 'default_currency', 'website'],
        order_by='supplier_name'
    )
    overview['suppliers'] = [
        {
            'name': s['name'],
            'supplier_name': s['supplier_name'],
            'group': s['supplier_group'],
            'country': s.get('country', ''),
            'currency': s['default_currency'],
            'website': s.get('website', '')
        }
        for s in suppliers
    ]

    # Items by group
    item_groups = _fetch(
        'Item Group',
        fields=['name'],
        order_by='name'
    )
    for ig in item_groups:
        count = _count('Item', {'item_group': ig['name']})
        overview['items_summary'][ig['name']] = count
    overview['items_summary']['TOTAL'] = _count('Item')

        # Warehouses
    warehouses = _fetch(
        'Warehouse',
        fields=['name', 'warehouse_name', 'is_group', 'company'],
        order_by='warehouse_name'
    )
    overview['warehouses'] = [
        {
            'name': w['name'],
            'warehouse_name': w['warehouse_name'],
            'company': w.get('company', ''),
            'is_group': w['is_group']
        }
        for w in warehouses
    ]

    # Open orders count
    overview['open_orders']['sales'] = _count(
        'Sales Order',
        {'status': ['in', ['Draft', 'Quotation', 'On Hold', 'Pending']]}
    )
    overview['open_orders']['purchase'] = _count(
        'Purchase Order',
        {'status': ['in', ['Draft', 'On Hold', 'Pending']]}
    )

    # Recent transactions (last 10)
    recent_sales = _fetch(
        'Sales Invoice',
        fields=['name', 'customer', 'customer_name', 'posting_date', 'grand_total', 'status'],
        order_by='posting_date desc',
        limit_page_length=5
    )
    recent_purchases = _fetch(
        'Purchase Invoice',
        fields=['name', 'supplier', 'supplier_name', 'posting_date', 'grand_total', 'status'],
        order_by='posting_date desc',
        limit_page_length=5
    )

    overview['recent_transactions'] = {
        'sales_invoices': [
            {
                'name': inv['name'],
                'customer': inv['customer_name'],
                'date': str(inv['posting_date']),
                'amount': inv['grand_total'],
                'status': inv['status']
            }
            for inv in recent_sales
        ],
        'purchase_invoices': [
            {
                'name': inv['name'],
                'supplier': inv['supplier_name'],
                'date': str(inv['posting_date']),
                'amount': inv['grand_total'],
                'status': inv['status']
            }
            for inv in recent_purchases
        ]
    }

    return overview


def get_items(filters: Optional[Dict] = None, limit: int = 50, fields: Optional[List] = None) -> List[Dict]:
    """
    Get items from ERP with optional filters.

    Args:
        filters: Dict of filters (e.g., {'item_group': 'Products', 'is_stock_item': 1})
        limit: Max number of items to return (default 50)
        fields: List of fields to return (default: common fields)

    Returns:
        List of item dictionaries
    """
    if fields is None:
        fields = [
            'item_code', 'item_name', 'item_group', 'description',
            'stock_uom', 'is_stock_item', 'valuation_rate', 'standard_rate'
        ]

    item_filters = filters or {}
    items = _fetch('Item', filters=item_filters, fields=fields, limit_page_length=limit)

    return items


def get_item_details(item_code: str) -> Optional[Dict]:
    """
    Get detailed information about a specific item.

    Args:
        item_code: The item code to look up

    Returns:
        Full item document or None if not found
    """
    try:
        item = frappe.get_doc('Item', item_code)
        return item.as_dict()
    except (frappe.DoesNotExistError, frappe.PermissionError):
        # frappe.get_doc enforces the document-level check and raises; return
        # None so an out-of-scope document is indistinguishable from a missing
        # one (audit point 19: no by-name existence probing).
        return None


def search_items(query: str, limit: int = 20) -> List[Dict]:
    """
    Search items by name, code, or description.

    Args:
        query: Search term
        limit: Max results (default 20)

    Returns:
        List of matching items
    """
    # `or_filters` is a keyword argument of frappe.get_list; nesting it inside
    # `filters` made frappe treat it as a column filter, so this tool answered
    # an error/empty instead of matching on name, code or description.
    items = _fetch(
        'Item',
        filters=[],
        or_filters=[
            {'item_name': ['like', f'%{query}%']},
            {'item_code': ['like', f'%{query}%']},
            {'description': ['like', f'%{query}%']}
        ],
        fields=['item_code', 'item_name', 'item_group', 'description', 'stock_uom', 'standard_rate'],
        limit_page_length=limit
    )
    return items


def get_customers(filters: Optional[Dict] = None, limit: int = 50) -> List[Dict]:
    """
    Get customers from ERP.

    Args:
        filters: Optional filters (e.g., {'customer_group': 'Spare Parts'})
        limit: Max customers to return

    Returns:
        List of customer dictionaries
    """
    fields = [
        'name', 'customer_name', 'customer_group', 'territory',
        'customer_type', 'default_currency', 'website', 'tax_id'
    ]

    cust_filters = filters or {}
    customers = _fetch('Customer', filters=cust_filters, fields=fields, limit_page_length=limit)

    return customers


def get_customer_details(customer_code: str) -> Optional[Dict]:
    """
    Get detailed information about a specific customer.

    Args:
        customer_code: Customer name or document name

    Returns:
        Full customer document or None
    """
    try:
        customer = frappe.get_doc('Customer', customer_code)
        return customer.as_dict()
    except (frappe.DoesNotExistError, frappe.PermissionError):
        return None


def get_suppliers(filters: Optional[Dict] = None, limit: int = 50) -> List[Dict]:
    """
    Get suppliers from ERP.

    Args:
        filters: Optional filters
        limit: Max suppliers to return

    Returns:
        List of supplier dictionaries
    """
    fields = [
        'name', 'supplier_name', 'supplier_group',
        'country', 'website', 'tax_id'
    ]

    supp_filters = filters or {}
    suppliers = _fetch('Supplier', filters=supp_filters, fields=fields, limit_page_length=limit)

    return suppliers


def get_supplier_details(supplier_code: str) -> Optional[Dict]:
    """
    Get detailed information about a specific supplier.

    Args:
        supplier_code: Supplier name or document name

    Returns:
        Full supplier document or None
    """
    try:
        supplier = frappe.get_doc('Supplier', supplier_code)
        return supplier.as_dict()
    except (frappe.DoesNotExistError, frappe.PermissionError):
        return None


def get_companies() -> List[Dict]:
    """
    Get all companies in the ERP system.

    Returns:
        List of company dictionaries with key details
    """
    fields = [
        'name', 'company_name', 'default_currency', 'country',
        'tax_id', 'website', 'email', 'phone_no'
    ]

    companies = _fetch('Company', fields=fields, order_by='company_name')

    return companies


def get_company_details(company_name: str) -> Optional[Dict]:
    """
    Get detailed information about a specific company.

    Args:
        company_name: Company document name

    Returns:
        Full company document or None
    """
    try:
        company = frappe.get_doc('Company', company_name)
        return company.as_dict()
    except (frappe.DoesNotExistError, frappe.PermissionError):
        return None


def get_warehouses(filters: Optional[Dict] = None) -> List[Dict]:
    """
    Get all warehouses or filter by group.

    Args:
        filters: Optional filters (e.g., {'is_group': 1} or {'company': 'SPI Pharma'})

    Returns:
        List of warehouse dictionaries
    """
    fields = ['name', 'warehouse_name', 'is_group', 'company', 'parent_warehouse']

    wh_filters = filters or {}
    warehouses = _fetch('Warehouse', filters=wh_filters, fields=fields, order_by='warehouse_name')

    return warehouses


def get_stock_levels(item_code: str, warehouse: Optional[str] = None) -> List[Dict]:
    """
    Get current stock levels for an item.

    Args:
        item_code: The item code to check
        warehouse: Optional specific warehouse (if None, checks all)

    Returns:
        List of stock entries with actual quantities
    """
    # 'Bin' is ERPNext's own current-stock aggregate: one row per item/warehouse
    # carrying the running totals. The previous version summed the newest 100
    # Stock Ledger Entry rows, which is not "current" stock once an item has more
    # than 100 movements - and it raised UnboundLocalError whenever `warehouse`
    # was omitted, because the fetch sat inside the `if warehouse:` block while
    # the aggregation loop below always ran.
    filters = {'item_code': item_code}
    if warehouse:
        filters['warehouse'] = warehouse

    return _fetch(
        'Bin',
        filters=filters,
        fields=['warehouse', 'actual_qty', 'valuation_rate', 'stock_value', 'projected_qty'],
        order_by='warehouse',
        limit_page_length=100,
    )


def get_open_sales_orders(filters: Optional[Dict] = None, limit: int = 20) -> List[Dict]:
    """
    Get open sales orders.

    Args:
        filters: Optional filters (e.g., {'customer': 'SPI Traders'})
        limit: Max orders to return

    Returns:
        List of sales order dictionaries
    """
    fields = [
        'name', 'customer', 'customer_name', 'transaction_date', 'delivery_date',
        'status', 'grand_total', 'base_grand_total', 'terms'
    ]

    so_filters = filters or {'status': ['in', ['Draft', 'Quotation', 'On Hold', 'Pending', 'Partially Delivered']]}
    orders = _fetch('Sales Order', filters=so_filters, fields=fields, limit_page_length=limit, order_by='transaction_date desc')

    return orders


def get_open_purchase_orders(filters: Optional[Dict] = None, limit: int = 20) -> List[Dict]:
    """
    Get open purchase orders.

    Args:
        filters: Optional filters (e.g., {'supplier': 'SPIPHARMA'})
        limit: Max orders to return

    Returns:
        List of purchase order dictionaries
    """
    fields = [
        'name', 'supplier', 'supplier_name', 'transaction_date', 'schedule_date',
        'status', 'grand_total', 'base_grand_total', 'terms'
    ]

    po_filters = filters or {'status': ['in', ['Draft', 'On Hold', 'Pending']]}
    orders = _fetch('Purchase Order', filters=po_filters, fields=fields, limit_page_length=limit, order_by='transaction_date desc')

    return orders


def get_sales_invoices(filters: Optional[Dict] = None, limit: int = 20) -> List[Dict]:
    """
    Get sales invoices.

    Args:
        filters: Optional filters
        limit: Max invoices to return

    Returns:
        List of sales invoice dictionaries
    """
    fields = [
        'name', 'customer', 'customer_name', 'posting_date', 'due_date',
        'status', 'grand_total', 'base_grand_total', 'outstanding_amount',
        'paid_amount'
    ]

    inv_filters = filters or {}
    invoices = _fetch('Sales Invoice', filters=inv_filters, fields=fields, limit_page_length=limit, order_by='posting_date desc')

    return invoices


def get_purchase_invoices(filters: Optional[Dict] = None, limit: int = 20) -> List[Dict]:
    """
    Get purchase invoices.

    Args:
        filters: Optional filters
        limit: Max invoices to return

    Returns:
        List of purchase invoice dictionaries
    """
    fields = [
        'name', 'supplier', 'supplier_name', 'posting_date', 'due_date',
        'status', 'grand_total', 'base_grand_total', 'outstanding_amount',
        'paid_amount'
    ]

    inv_filters = filters or {}
    invoices = _fetch('Purchase Invoice', filters=inv_filters, fields=fields, limit_page_length=limit, order_by='posting_date desc')

    return invoices


def get_item_price(item_code: str, price_list: str = 'Standard Selling') -> Optional[Dict]:
    """
    Get price list entry for an item.

    Args:
        item_code: The item code
        price_list: Price list name (default: Standard Selling)

    Returns:
        Price list entry or None
    """
    price_list_entry = _first(
        'Item Price',
        {'item_code': item_code, 'price_list': price_list},
        ['price_list_rate', 'currency', 'valid_from'],
    )

    return price_list_entry


def get_low_stock_items(threshold: int = 10) -> List[Dict]:
    """
    Get items with stock below threshold.

    Args:
        threshold: Minimum quantity to consider as "low stock"

    Returns:
        List of items with low stock
    """
    items = _fetch(
        'Item',
        filters={'is_stock_item': 1},
        fields=['item_code', 'item_name', 'item_group', 'valuation_rate', 'opening_stock'],
        limit_page_length=100
    )

    # Check actual stock from stock ledger
    low_stock = []
    for item in items:
        actual_stock = _sum(
            'Stock Ledger Entry',
            {'item_code': item['item_code']},
            'actual_qty'
        ) or 0

        if actual_stock < threshold:
            low_stock.append({
                'item_code': item['item_code'],
                'item_name': item['item_name'],
                'item_group': item['item_group'],
                'actual_stock': actual_stock,
                'valuation_rate': item['valuation_rate']
            })

    return low_stock


def get_transaction_summary(days: int = 30) -> Dict[str, Any]:
    """
    Get transaction summary for recent period.

    Args:
        days: Number of days to look back (default 30)

    Returns:
        Summary statistics
    """
    from_date = datetime.now() - timedelta(days=days)

    summary = {
        'period': f'Last {days} days',
        'from_date': from_date.isoformat(),
        'sales_invoices': {
            'count': 0,
            'total_amount': 0,
            'outstanding': 0
        },
        'purchase_invoices': {
            'count': 0,
            'total_amount': 0,
            'outstanding': 0
        },
        'sales_orders': {
            'count': 0,
            'total_amount': 0
        },
        'purchase_orders': {
            'count': 0,
            'total_amount': 0
        }
    }

    # Sales invoices
    sales_invs = _fetch(
        'Sales Invoice',
        filters={'posting_date': ['>=', from_date]},
        fields=['grand_total', 'outstanding_amount']
    )
    summary['sales_invoices']['count'] = len(sales_invs)
    summary['sales_invoices']['total_amount'] = sum(inv['grand_total'] or 0 for inv in sales_invs)
    summary['sales_invoices']['outstanding'] = sum(inv['outstanding_amount'] or 0 for inv in sales_invs)

    # Purchase invoices
    purch_invs = _fetch(
        'Purchase Invoice',
        filters={'posting_date': ['>=', from_date]},
        fields=['grand_total', 'outstanding_amount']
    )
    summary['purchase_invoices']['count'] = len(purch_invs)
    summary['purchase_invoices']['total_amount'] = sum(inv['grand_total'] or 0 for inv in purch_invs)
    summary['purchase_invoices']['outstanding'] = sum(inv['outstanding_amount'] or 0 for inv in purch_invs)

    # Sales orders
    sales_orders = _fetch(
        'Sales Order',
        filters={'transaction_date': ['>=', from_date]},
        fields=['grand_total']
    )
    summary['sales_orders']['count'] = len(sales_orders)
    summary['sales_orders']['total_amount'] = sum(so['grand_total'] or 0 for so in sales_orders)

    # Purchase orders
    purch_orders = _fetch(
        'Purchase Order',
        filters={'transaction_date': ['>=', from_date]},
        fields=['grand_total']
    )
    summary['purchase_orders']['count'] = len(purch_orders)
    summary['purchase_orders']['total_amount'] = sum(po['grand_total'] or 0 for po in purch_orders)

    return summary


def create_draft_for_review(payload: Dict) -> Optional[str]:
    """Route an operator create-draft payload through the controlled-write boundary.

    Operator create tools must not call ``Document.insert()``/``.save()`` or
    ``frappe.db.commit()`` directly — those bypasses skip confirmation,
    idempotency, audit and the single workflow commit boundary. Instead they
    build a payload dict (carrying its own ``doctype``) and hand it here.

    This helper extracts the doctype, builds a permission-checked ``FrappeMCP``
    client, and delegates to ``erp_ai.draft_workflow.create_document_from_draft``
    — the one materialisation path that ends in MCP ``create_document`` (single
    commit at the workflow boundary). Returns the created document's name, or
    ``None`` when the draft was rejected (duplicate, permission, etc.).
    """
    doctype = payload.get('doctype')
    if not doctype:
        return None
    from erp_ai.draft_workflow import create_document_from_draft
    from erp_ai.mcp.server import FrappeMCP

    mcp = FrappeMCP()
    result = create_document_from_draft(doctype, payload, mcp)
    if isinstance(result, dict) and result.get('name'):
        return result['name']
    return None


def create_sales_order(
    customer: str,
    items: List[Dict],
    delivery_date: str,
    company: Optional[str] = None,
    warehouse: Optional[str] = None,
    currency: Optional[str] = None,
    comments: Optional[str] = None
) -> Optional[str]:
    """
    Create a new sales order.

    Args:
        customer: Customer document name
        items: List of item dicts with {'item_code': str, 'qty': float, 'rate': float}
        delivery_date: Delivery date (YYYY-MM-DD)
        company: Company name (default: first company)
        warehouse: Warehouse name (default: from item or first warehouse)
        currency: Currency (default: from customer)
        comments: Order notes (stored in the 'terms' field)

    Returns:
        Sales Order name if successful, None otherwise
    """
    # Build a draft payload, then hand it to the controlled workflow boundary.
    # The operator tool no longer calls Document.insert() or
    # frappe.db.commit() directly - that now happens only at the workflow
    # commit boundary (draft_workflow.commit_document), which is the single
    # place operator writes are materialised.
    try:
        # Resolve defaults through permission-aware reads (the caller's roles
        # and User Permission row filters apply here as well).
        #
        # The filter dict must be passed as `filters=`; frappe.get_list forwards
        # positional arguments to DatabaseQuery.execute(), where the second
        # parameter is `fields`, so a positional dict collided with the `fields`
        # keyword ("got multiple values for argument 'fields'") and the whole
        # tool failed.
        if not company:
            _companies = _fetch('Company', limit_page_length=1)
            company = _companies[0].name if _companies else None

        currency = currency
        if not currency:
            _customer_doc = _fetch('Customer', filters={'name': customer}, fields=['default_currency'], limit_page_length=1)
            if _customer_doc:
                currency = _customer_doc[0].get('default_currency') or currency
            if not currency and company:
                _company_doc = _fetch('Company', filters={'name': company}, fields=['default_currency'], limit_page_length=1)
                if _company_doc:
                    currency = _company_doc[0].get('default_currency') or currency

        if not warehouse:
            _warehouses = _fetch('Warehouse', filters={'is_group': 0}, limit_page_length=1)
            warehouse = _warehouses[0].name if _warehouses else None

        if not company:
            return None

        so_payload = {
            'doctype': 'Sales Order',
            'customer': customer,
            'company': company,
            'currency': currency or 'PKR',
            'delivery_date': delivery_date,
            # The Sales Order schema contract carries the free-text field as
            # `remarks`; `terms` is not a Sales Order field, so the previous key
            # was dropped and the operator's comment never reached the document.
            'remarks': comments or '',
            # Warehouse goes on each child row: the top-level `warehouse` key this
            # payload used to send is not in the Sales Order schema, so it was
            # dropped and every order line lost its delivery warehouse.
            'items': [],
            # No hardcoded 'taxes_and_charges': the previous literal 'No Tax' is
            # not a Taxes and Charges Template on this site (real names are e.g.
            # 'Pakistan Tax -SPI'), so the link field failed validation on every
            # insert. Left unset; the operator/confirm step can pick a live
            # template (audit point 83: no hardcoded tax defaults).
        }

        for item_data in items:
            so_payload.setdefault('items', []).append({
                'item_code': item_data['item_code'],
                'qty': item_data.get('qty', 1),
                'rate': item_data.get('rate', 0),
                'warehouse': warehouse,
            })

        # Route through the controlled draft path; operator tools never call
        # Document.insert()/frappe.db.commit() directly.
        created_name = create_draft_for_review(so_payload)
        return created_name
    except Exception as e:
        _log_tool_error('create_sales_order', e)
        return None


def create_item(
    item_code: str,
    item_name: str,
    item_group: str,
    description: Optional[str] = None,
    is_stock_item: int = 1,
    uom: str = 'Nos',
    standard_rate: float = 0,
    valuation_rate: float = 0,
) -> Optional[str]:
    """
    Create a new item.

    Args:
        item_code: Unique item code
        item_name: Item name
        item_group: Item group
        description: Item description
        is_stock_item: 1 if stock item, 0 if non-stock
        uom: Unit of measure
        standard_rate: Standard selling rate
        valuation_rate: Valuation rate
        opening_stock: Opening stock quantity
        default_warehouse: Default warehouse

    Returns:
        Item code if successful, None otherwise
    """
    try:
        item_payload = {
            'doctype': 'Item',
            'item_name': item_name or item_code,
            'item_group': item_group,
            'stock_uom': uom,
            'standard_rate': standard_rate,
            'valuation_rate': valuation_rate,
            'is_stock_item': is_stock_item,
            'description': description or '',
        }
        # Route through the controlled draft path (single commit at boundary);
        # operator tools never call Document.insert()/frappe.db.commit() directly.
        return create_draft_for_review(item_payload)
    except Exception as e:
        _log_tool_error('create_item', e)
        return None


def create_customer(
    customer_name: str,
    customer_group: str = 'Spare Parts',
    territory: str = 'Pakistan',
    customer_type: str = 'Individual',
    default_currency: str = 'PKR',
    phone_no: Optional[str] = None,
    email_id: Optional[str] = None,
    website: Optional[str] = None
) -> Optional[str]:
    """
    Create a new customer.

    Args:
        customer_name: Customer name
        customer_group: Customer group
        territory: Territory
        customer_type: Customer type (Individual/Company)
        default_currency: Default currency
        phone_no: Phone number
        email_id: Email address
        website: Website

    Returns:
        Customer name if successful, None otherwise
    """
    try:
        # Keys must match the Customer schema contract (erp_ai/schema/__init__.py):
        # the shared creator `_create_customer_doc` whitelists them and maps
        # `email` onto the Customer's `email_id` column. Sending the raw column
        # name (`email_id`) here would be dropped instead of mapped.
        customer_payload = {
            'doctype': 'Customer',
            'customer_name': customer_name,
            'customer_group': customer_group,
            'territory': territory,
            'customer_type': customer_type,
            'default_currency': default_currency,
            'mobile_no': phone_no or '',
            'email': email_id or '',
            'website': website or '',
        }
        # Route through the controlled draft path (single commit at boundary);
        # operator tools never call Document.insert()/frappe.db.commit() directly.
        return create_draft_for_review(customer_payload)
    except Exception as e:
        _log_tool_error('create_customer', e)
        return None


def create_supplier(
    supplier_name: str,
    supplier_group: str = 'SPI Pharma',
    territory: str = 'Pakistan',
    default_currency: str = 'PKR',
    phone_no: Optional[str] = None,
    email_id: Optional[str] = None,
    website: Optional[str] = None
) -> Optional[str]:
    """
    Create a new supplier.

    Args:
        supplier_name: Supplier name
        supplier_group: Supplier group
        territory: Territory
        default_currency: Default currency
        phone_no: Phone number
        email_id: Email address
        website: Website

    Returns:
        Supplier name if successful, None otherwise
    """
    try:
        # Supplier's schema contract uses `email` (mapped to the `email_id`
        # column by `_create_supplier_doc`) and `country` — Supplier has no
        # `territory` field, so the tool's `territory` argument lands in `country`.
        supplier_payload = {
            'doctype': 'Supplier',
            'supplier_name': supplier_name,
            'supplier_group': supplier_group,
            'country': territory,
            'default_currency': default_currency,
            'mobile_no': phone_no or '',
            'email': email_id or '',
            'website': website or '',
        }
        # Route through the controlled draft path (single commit at boundary);
        # operator tools never call Document.insert()/frappe.db.commit() directly.
        return create_draft_for_review(supplier_payload)
    except Exception as e:
        _log_tool_error('create_supplier', e)
        return None


# Tool registry - maps tool names to functions
ERP_TOOLS = {
    # System overview
    'get_system_overview': get_system_overview,

    # Items
    'get_items': get_items,
    'get_item_details': get_item_details,
    'search_items': search_items,
    'get_item_price': get_item_price,

    # Customers
    'get_customers': get_customers,
    'get_customer_details': get_customer_details,

    # Suppliers
    'get_suppliers': get_suppliers,
    'get_supplier_details': get_supplier_details,

    # Companies
    'get_companies': get_companies,
    'get_company_details': get_company_details,

    # Warehouses & Stock
    'get_warehouses': get_warehouses,
    'get_stock_levels': get_stock_levels,
    'get_low_stock_items': get_low_stock_items,

    # Orders
    'get_open_sales_orders': get_open_sales_orders,
    'get_open_purchase_orders': get_open_purchase_orders,

    # Invoices
    'get_sales_invoices': get_sales_invoices,
    'get_purchase_invoices': get_purchase_invoices,

    # Transactions
    'get_transaction_summary': get_transaction_summary,

    # Create operations
    'create_sales_order': create_sales_order,
    'create_item': create_item,
    'create_customer': create_customer,
    'create_supplier': create_supplier,
}


def get_available_tools() -> List[Dict]:
    """
    Get list of all available ERP tools with descriptions.

    Returns:
        List of tool definitions
    """
    return [
        {
            'name': 'get_system_overview',
            'description': 'Get comprehensive overview of entire ERP system including companies, customers, suppliers, items, warehouses, and recent transactions',
            'parameters': {}
        },
        {
            'name': 'get_items',
            'description': 'Get list of items with optional filters (item_group, is_stock_item, etc.)',
            'parameters': {
                'filters': 'Optional dict of filters',
                'limit': 'Max items to return (default 50)',
                'fields': 'List of fields to return'
            }
        },
        {
            'name': 'get_item_details',
            'description': 'Get detailed information about a specific item by item code',
            'parameters': {
                'item_code': 'The item code to look up (required)'
            }
        },
        {
            'name': 'search_items',
            'description': 'Search items by name, code, description, or barcode',
            'parameters': {
                'query': 'Search term (required)',
                'limit': 'Max results (default 20)'
            }
        },
        {
            'name': 'get_customers',
            'description': 'Get list of all customers with details',
            'parameters': {
                'filters': 'Optional filters',
                'limit': 'Max customers to return (default 50)'
            }
        },
        {
            'name': 'get_customer_details',
            'description': 'Get detailed information about a specific customer',
            'parameters': {
                'customer_code': 'Customer document name (required)'
            }
        },
        {
            'name': 'get_suppliers',
            'description': 'Get list of all suppliers with details',
            'parameters': {
                'filters': 'Optional filters',
                'limit': 'Max suppliers to return (default 50)'
            }
        },
        {
            'name': 'get_supplier_details',
            'description': 'Get detailed information about a specific supplier',
            'parameters': {
                'supplier_code': 'Supplier document name (required)'
            }
        },
        {
            'name': 'get_companies',
            'description': 'Get all companies in the ERP system',
            'parameters': {}
        },
        {
            'name': 'get_company_details',
            'description': 'Get detailed information about a specific company',
            'parameters': {
                'company_name': 'Company document name (required)'
            }
        },
        {
            'name': 'get_warehouses',
            'description': 'Get all warehouses or filter by group',
            'parameters': {
                'filters': 'Optional filters (e.g., company or is_group)'
            }
        },
        {
            'name': 'get_stock_levels',
            'description': 'Get current stock levels for an item across warehouses',
            'parameters': {
                'item_code': 'The item code (required)',
                'warehouse': 'Specific warehouse (optional, checks all if not provided)'
            }
        },
        {
            'name': 'get_open_sales_orders',
            'description': 'Get open/draft sales orders',
            'parameters': {
                'filters': 'Optional filters (e.g., customer)',
                'limit': 'Max orders to return (default 20)'
            }
        },
        {
            'name': 'get_open_purchase_orders',
            'description': 'Get open/draft purchase orders',
            'parameters': {
                'filters': 'Optional filters (e.g., supplier)',
                'limit': 'Max orders to return (default 20)'
            }
        },
        {
            'name': 'get_sales_invoices',
            'description': 'Get sales invoices with optional filters',
            'parameters': {
                'filters': 'Optional filters (e.g., customer, status)',
                'limit': 'Max invoices to return (default 20)'
            }
        },
        {
            'name': 'get_purchase_invoices',
            'description': 'Get purchase invoices with optional filters',
            'parameters': {
                'filters': 'Optional filters (e.g., supplier, status)',
                'limit': 'Max invoices to return (default 20)'
            }
        },
        {
            'name': 'get_item_price',
            'description': 'Get price list entry for an item',
            'parameters': {
                'item_code': 'The item code (required)',
                'price_list': 'Price list name (default: Standard Selling)'
            }
        },
        {
            'name': 'get_low_stock_items',
            'description': 'Get items with stock below threshold',
            'parameters': {
                'threshold': 'Minimum quantity to consider low stock (default 10)'
            }
        },
        {
            'name': 'get_transaction_summary',
            'description': 'Get transaction summary for recent period',
            'parameters': {
                'days': 'Number of days to look back (default 30)'
            }
        },
        {
            'name': 'create_sales_order',
            'description': 'Create a new sales order',
            'parameters': {
                'customer': 'Customer document name (required)',
                'items': 'List of item dicts with item_code, qty, rate (required)',
                'delivery_date': 'Delivery date YYYY-MM-DD (required)',
                'company': 'Company name (optional)',
                'warehouse': 'Warehouse name (optional)',
                'currency': 'Currency (optional)',
                'comments': 'Order comments (optional)'
            }
        },
        {
            'name': 'create_item',
            'description': 'Create a new item master record',
            'parameters': {
                'item_code': 'Unique item code (required)',
                'item_name': 'Item name (required)',
                'item_group': 'Item group (required)',
                'description': 'Item description (optional)',
                'is_stock_item': '1 if stock item, 0 if non-stock (default 1)',
                'uom': 'Unit of measure (default Nos)',
                'standard_rate': 'Standard selling rate (default 0)',
                'valuation_rate': 'Valuation rate (default 0)'
            }
        },
        {
            'name': 'create_customer',
            'description': 'Create a new customer master record',
            'parameters': {
                'customer_name': 'Customer name (required)',
                'customer_group': 'Customer group (default Spare Parts)',
                'territory': 'Territory (default Pakistan)',
                'customer_type': 'Customer type (default Individual)',
                'default_currency': 'Default currency (default PKR)',
                'phone_no': 'Phone number (optional)',
                'email_id': 'Email address (optional)',
                'website': 'Website (optional)'
            }
        },
        {
            'name': 'create_supplier',
            'description': 'Create a new supplier master record',
            'parameters': {
                'supplier_name': 'Supplier name (required)',
                'supplier_group': 'Supplier group (default SPI Pharma)',
                'territory': 'Territory (default Pakistan)',
                'default_currency': 'Default currency (default PKR)',
                'phone_no': 'Phone number (optional)',
                'email_id': 'Email address (optional)',
                'website': 'Website (optional)'
            }
        }
    ]


def execute_erp_tool(tool_name: str, parameters: Dict) -> Dict:
    """
    Execute an ERP tool by name with given parameters.

    Args:
        tool_name: Name of the tool to execute
        parameters: Dictionary of parameters for the tool

    Returns:
        Dictionary with 'success' boolean and 'result' or 'error'
    """
    if tool_name not in ERP_TOOLS:
        return {
            'success': False,
            'error': f'Unknown tool: {tool_name}. Available tools: {list(ERP_TOOLS.keys())}'
        }

    try:
        tool_func = ERP_TOOLS[tool_name]
        result = tool_func(**parameters)

        # Create tools return the new document's name, or a falsy value when the
        # write was rejected (no create permission, duplicate, validation error,
        # unsupported doctype). Reporting success unconditionally here told the
        # model "created" for a document that does not exist.
        if tool_name.startswith('create_') and not result:
            return {
                'success': False,
                'error': (
                    f'{tool_name} created nothing: the draft was rejected '
                    f'(missing permission, duplicate, or validation error)'
                ),
            }
        return {
            'success': True,
            'result': result
        }
    except Exception as e:
        _log_tool_error(tool_name, e)
        return {
            'success': False,
            'error': str(e)
        }


# For backward compatibility
def get_erp_tools_list():
    """Return list of available ERP tools."""
    return get_available_tools()


def call_erp_tool(tool_name: str, params: Dict = None):
    """Execute an ERP tool and return result."""
    if params is None:
        params = {}
    return execute_erp_tool(tool_name, params)


if __name__ == '__main__':
    # Test the tools
    print('Testing ERP Operator Tools...')
    print()

    # System overview
    print('=== System Overview ===')
    overview = get_system_overview()
    print(f"Companies: {len(overview['companies'])}")
    print(f"Customers: {len(overview['customers'])}")
    print(f"Suppliers: {len(overview['suppliers'])}")
    print(f"Total Items: {overview['items_summary'].get('TOTAL', 0)}")
    print(f"Warehouses: {len(overview['warehouses'])}")
    print()

    # Items
    print('=== Sample Items ===')
    items = get_items(limit=5)
    for item in items:
        print(f"  {item['item_code']}: {item['item_name']} ({item['item_group']})")
    print()

    # Customers
    print('=== Customers ===')
    customers = get_customers()
    for cust in customers:
        print(f"  {cust['customer_name']} ({cust['customer_group']})")
    print()

    # Suppliers
    print('=== Suppliers ===')
    suppliers = get_suppliers()
    for supp in suppliers:
        print(f"  {supp['supplier_name']} ({supp['supplier_group']})")
    print()

    print('=== Available Tools ===')
    tools = get_available_tools()
    print(f'Total tools: {len(tools)}')
    for tool in tools:
        print(f"  - {tool['name']}: {tool['description'][:60]}...")
