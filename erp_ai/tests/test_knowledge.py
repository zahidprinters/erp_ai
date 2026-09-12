# ---------------------------------------------------------------------------
# Knowledge source tests — citations, freshness, doctype mapping.
# ---------------------------------------------------------------------------
from erp_ai.knowledge.sources import (
    SOURCES,
    KnowledgeSource,
    check_freshness,
    find_sources_by_doctype,
    find_sources_by_tag,
    get_citation_for_doctype,
    get_source,
)


def test_sources_populated():
    """Sources registry should have entries."""
    assert len(SOURCES) >= 5


def test_get_source_exists():
    """Should retrieve a known source."""
    source = get_source("erpnext_selling")
    assert source is not None
    assert source.title == "ERPNext Selling Workflow"


def test_get_source_missing():
    """Should return None for unknown source."""
    assert get_source("nonexistent") is None


def test_find_by_tag():
    """Should find sources by tag."""
    results = find_sources_by_tag("selling")
    assert len(results) >= 1
    assert any("selling" in s.tags for s in results)


def test_find_by_doctype_sales():
    """Should find sources for Sales Invoice."""
    results = find_sources_by_doctype("Sales Invoice")
    assert len(results) >= 1


def test_find_by_doctype_bom():
    """Should find manufacturing sources for BOM."""
    results = find_sources_by_doctype("BOM")
    assert len(results) >= 1


def test_find_by_doctype_quality():
    """Should find quality sources for Quality Inspection."""
    results = find_sources_by_doctype("Quality Inspection")
    assert len(results) >= 1


def test_find_by_doctype_asset():
    """Should find maintenance sources for Asset."""
    results = find_sources_by_doctype("Asset")
    assert len(results) >= 1


def test_citation_format():
    """Citation should include title and type."""
    citation = get_citation_for_doctype("Sales Invoice")
    assert "Selling" in citation or "ERPNext" in citation


def test_citation_unknown_doctype():
    """Unknown doctype should return generic citation."""
    citation = get_citation_for_doctype("UnknownXYZ")
    assert "ERPNext" in citation


def test_source_freshness():
    """Source freshness check should work."""
    source = get_source("erpnext_selling")
    assert source is not None
    assert isinstance(source.is_fresh(), bool)


def test_source_freshness_old():
    """Very old source should be stale."""
    old_source = KnowledgeSource(
        id="old", title="Old Source", source_type="kb_article",
        last_updated="2020-01-01")
    assert old_source.is_fresh(max_days=90) is False


def test_source_freshness_recent():
    """Recent source should be fresh."""
    source = KnowledgeSource(
        id="recent", title="Recent", source_type="kb_article",
        last_updated="2026-09-01")
    assert source.is_fresh(max_days=90) is True


def test_source_citation_format():
    """Citation should include version and date."""
    source = KnowledgeSource(
        id="test", title="Test Source", source_type="company_sop",
        version="2.0", last_updated="2026-06-01")
    citation = source.citation()
    assert "Test Source" in citation
    assert "v2.0" in citation


def test_check_freshness_all():
    """Freshness check should return all sources."""
    result = check_freshness()
    assert "stale_sources" in result
    assert "total" in result
    assert result["total"] == len(SOURCES)


def test_doctype_mapping_employee():
    """Employee should map to HR sources."""
    results = find_sources_by_doctype("Employee")
    assert len(results) >= 1


def test_doctype_mapping_work_order():
    """Work Order should map to manufacturing sources."""
    results = find_sources_by_doctype("Work Order")
    assert len(results) >= 1
