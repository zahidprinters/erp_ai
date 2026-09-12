# ---------------------------------------------------------------------------
# Knowledge source metadata — citations, freshness, versioning.
#
# Tracks where each piece of knowledge came from, when it was last updated,
# and its confidence level. Enables the AI to cite sources and flag stale info.
# ---------------------------------------------------------------------------
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class KnowledgeSource:
    """A single knowledge source with metadata."""
    id: str
    title: str
    source_type: str  # "official_docs", "company_sop", "kb_article"
    url: Optional[str] = None
    version: str = "1.0"
    last_updated: str = ""
    confidence: str = "high"  # "high", "medium", "low"
    tags: List[str] = field(default_factory=list)

    def is_fresh(self, max_days: int = 90) -> bool:
        """Check if the source is fresh (updated within max_days)."""
        if not self.last_updated:
            return True
        try:
            updated = datetime.fromisoformat(self.last_updated)
            return (datetime.now() - updated).days < max_days
        except (ValueError, TypeError):
            return True

    def citation(self) -> str:
        """Return a human-readable citation."""
        parts = [self.title]
        if self.source_type == "official_docs":
            parts.append("(Official ERPNext Docs)")
        elif self.source_type == "company_sop":
            parts.append("(Company SOP)")
        if self.version:
            parts.append("v%s" % self.version)
        if self.last_updated:
            parts.append("updated %s" % self.last_updated)
        return " ".join(parts)


SOURCES: Dict[str, KnowledgeSource] = {
    "erpnext_selling": KnowledgeSource(
        id="erpnext_selling", title="ERPNext Selling Workflow",
        source_type="official_docs", url="https://docs.frappe.io/erpnext/user/en/selling",
        version="15.0", last_updated="2026-01-01", confidence="high",
        tags=["selling", "sales_order", "sales_invoice", "customer"]),
    "erpnext_buying": KnowledgeSource(
        id="erpnext_buying", title="ERPNext Buying Workflow",
        source_type="official_docs", url="https://docs.frappe.io/erpnext/user/en/buying",
        version="15.0", last_updated="2026-01-01", confidence="high",
        tags=["buying", "purchase_order", "purchase_invoice", "supplier"]),
    "erpnext_stock": KnowledgeSource(
        id="erpnext_stock", title="ERPNext Stock Management",
        source_type="official_docs", url="https://docs.frappe.io/erpnext/user/en/stock",
        version="15.0", last_updated="2026-01-01", confidence="high",
        tags=["stock", "warehouse", "item", "stock_entry"]),
    "erpnext_manufacturing": KnowledgeSource(
        id="erpnext_manufacturing", title="ERPNext Manufacturing",
        source_type="official_docs", url="https://docs.frappe.io/erpnext/user/en/manufacturing",
        version="15.0", last_updated="2026-01-01", confidence="high",
        tags=["manufacturing", "bom", "work_order", "job_card"]),
    "erpnext_quality": KnowledgeSource(
        id="erpnext_quality", title="ERPNext Quality Management",
        source_type="official_docs", url="https://docs.frappe.io/erpnext/user/en/quality-management",
        version="15.0", last_updated="2026-01-01", confidence="high",
        tags=["quality", "inspection", "nonconformance"]),
    "erpnext_hr": KnowledgeSource(
        id="erpnext_hr", title="ERPNext HR & Payroll",
        source_type="official_docs", url="https://docs.frappe.io/erpnext/user/en/human-resources",
        version="15.0", last_updated="2026-01-01", confidence="high",
        tags=["hr", "employee", "leave", "payroll", "expense"]),
    "erpnext_accounting": KnowledgeSource(
        id="erpnext_accounting", title="ERPNext Accounting",
        source_type="official_docs", url="https://docs.frappe.io/erpnext/user/en/accounting",
        version="15.0", last_updated="2026-01-01", confidence="high",
        tags=["accounting", "journal_entry", "payment_entry"]),
    "erpnext_maintenance": KnowledgeSource(
        id="erpnext_maintenance", title="ERPNext Asset & Maintenance",
        source_type="official_docs", url="https://docs.frappe.io/erpnext/user/en/asset",
        version="15.0", last_updated="2026-01-01", confidence="high",
        tags=["asset", "maintenance", "repair"]),
    "spi_sop_stores": KnowledgeSource(
        id="spi_sop_stores", title="SPI Stores SOP",
        source_type="company_sop", version="2.0", last_updated="2026-06-01",
        confidence="high", tags=["stores", "receipt", "issue", "transfer"]),
    "spi_sop_quality": KnowledgeSource(
        id="spi_sop_quality", title="SPI Quality Inspection Procedure",
        source_type="company_sop", version="1.5", last_updated="2026-05-15",
        confidence="high", tags=["quality", "inspection", "quarantine"]),
}


def get_source(source_id: str) -> Optional[KnowledgeSource]:
    """Return a knowledge source by ID."""
    return SOURCES.get(source_id)


def find_sources_by_tag(tag: str) -> List[KnowledgeSource]:
    """Find all sources matching a tag."""
    return [s for s in SOURCES.values() if tag in s.tags]


def find_sources_by_doctype(doctype: str) -> List[KnowledgeSource]:
    """Map a doctype to relevant knowledge sources."""
    doctype_tag_map = {
        "Sales Invoice": ["selling"], "Sales Order": ["selling"],
        "Quotation": ["selling"], "Customer": ["selling"],
        "Purchase Invoice": ["buying"], "Purchase Order": ["buying"],
        "Purchase Receipt": ["buying"], "Supplier": ["buying"],
        "Item": ["stock"], "Warehouse": ["stock"], "Stock Entry": ["stock"],
        "BOM": ["manufacturing"], "Work Order": ["manufacturing"],
        "Job Card": ["manufacturing"],
        "Quality Inspection": ["quality"],
        "Employee": ["hr"], "Leave Application": ["hr"],
        "Expense Claim": ["hr"],
        "Journal Entry": ["accounting"], "Payment Entry": ["accounting"],
        "Asset": ["asset"], "Asset Maintenance": ["maintenance"],
        "Asset Repair": ["maintenance"],
    }
    tags = doctype_tag_map.get(doctype, [])
    results = []
    for tag in tags:
        results.extend(find_sources_by_tag(tag))
    return results


def get_citation_for_doctype(doctype: str) -> str:
    """Get a citation string for a doctype."""
    sources = find_sources_by_doctype(doctype)
    if sources:
        return sources[0].citation()
    return "ERPNext v15 documentation"


def check_freshness() -> Dict[str, list]:
    """Check all sources for freshness."""
    stale = []
    for source in SOURCES.values():
        if not source.is_fresh():
            stale.append(source.id)
    return {"stale_sources": stale, "total": len(SOURCES)}
