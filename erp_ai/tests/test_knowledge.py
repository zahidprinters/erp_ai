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


# ---------------------------------------------------------------------------
# Phase 1.2 — verifiable citations + real freshness
# ---------------------------------------------------------------------------

def test_citation_metadata_is_verifiable():
    """A citation returned for a doctype must point at a source that actually
    exists in the registry and carry enough metadata to verify it."""
    from erp_ai.knowledge.sources import get_citation_metadata_for_doctype

    metadata = get_citation_metadata_for_doctype("Sales Invoice")
    assert metadata is not None, "Sales Invoice must have a real cited source"
    # The cited source must exist in the registry (no invented references).
    source = get_source(metadata["source_id"])
    assert source is not None
    assert source.title == metadata["title"]
    # Verification essentials present.
    assert metadata["url"], "official docs citation must carry a url"
    assert isinstance(metadata["fresh"], bool)
    assert metadata["doctype"] == "Sales Invoice"


def test_citation_metadata_unknown_doctype_is_none():
    """Unknown doctypes get no citation — never an invented one."""
    from erp_ai.knowledge.sources import get_citation_metadata_for_doctype
    assert get_citation_metadata_for_doctype("UnknownXYZ") is None


def test_stale_source_flagged_in_citation():
    """A stale source's human citation must carry the stale warning."""
    stale_source = KnowledgeSource(
        id="stale", title="Stale SOP", source_type="company_sop",
        last_updated="2020-01-01")
    assert stale_source.is_fresh() is False
    assert "STALE" in stale_source.citation()


def test_check_freshness_reports_reindex_trigger():
    """check_freshness must expose a machine-readable reindex trigger."""
    result = check_freshness()
    assert "reindex_required" in result
    assert "fresh_sources" in result
    assert result["stale_count"] == len(result["stale_sources"])
    # Every stale source is also flagged for reindexing.
    assert set(result["stale_sources"]) == set(result["reindex_required"])
    # Partition is complete: fresh + stale == total.
    assert len(result["fresh_sources"]) + result["stale_count"] == result["total"]


def test_check_freshness_threshold_respected():
    """A custom max_days threshold must change what counts as stale."""
    result_strict = check_freshness(max_days=1)
    # With a 1-day window, everything with a last_updated date is stale.
    assert result_strict["stale_count"] >= 1
    assert "erpnext_selling" in result_strict["stale_sources"]


def test_citation_excerpt_truncated():
    """Excerpts in verifiable citations are capped at 200 chars."""
    long_source = KnowledgeSource(
        id="long", title="Long", source_type="kb_article",
        excerpt="x" * 500)
    assert len(long_source.citation_dict()["excerpt"]) == 200
