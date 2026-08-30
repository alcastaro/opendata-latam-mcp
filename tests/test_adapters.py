"""Unit tests for adapter base + registry (no network)."""

from __future__ import annotations

import pytest

from opendata_latam_mcp import adapters
from opendata_latam_mcp.adapters.ckan import (
    ArgentinaCkanAdapter,
    ChileCkanAdapter,
    CkanAdapter,
    DominicanRepublicCkanAdapter,
    EcuadorCkanAdapter,
    MexicoCkanAdapter,
    PanamaCkanAdapter,
    UruguayCkanAdapter,
)

# ─── Registry ─────────────────────────────────────────────────────────────────


def test_list_supported_returns_all_countries():
    supported = adapters.list_supported()
    codes = {s["country"] for s in supported}
    assert codes == {"AR", "CL", "DO", "EC", "MX", "PA", "UY"}


def test_get_adapter_by_code():
    a = adapters.get_adapter("DO")
    assert a.COUNTRY_CODE == "DO"


def test_get_adapter_lowercase_works():
    a = adapters.get_adapter("do")
    assert a.COUNTRY_CODE == "DO"


def test_get_adapter_by_name():
    a = adapters.get_adapter("Mexico")
    assert a.COUNTRY_CODE == "MX"


def test_get_adapter_unknown_raises():
    with pytest.raises(ValueError):
        adapters.get_adapter("ZZ")


def test_adapters_are_singletons():
    a1 = adapters.get_adapter("CL")
    a2 = adapters.get_adapter("CL")
    assert a1 is a2


# ─── Adapter classes ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "cls,expected_code,expected_url_contains",
    [
        (ArgentinaCkanAdapter, "AR", "datos.gob.ar"),
        (ChileCkanAdapter, "CL", "datos.gob.cl"),
        (DominicanRepublicCkanAdapter, "DO", "datos.gob.do"),
        (EcuadorCkanAdapter, "EC", "datosabiertos.gob.ec"),
        (MexicoCkanAdapter, "MX", "datos.gob.mx"),
        (PanamaCkanAdapter, "PA", "datosabiertos.gob.pa"),
        (UruguayCkanAdapter, "UY", "catalogodatos.gub.uy"),
    ],
)
def test_country_adapter_metadata(cls, expected_code, expected_url_contains):
    assert cls.COUNTRY_CODE == expected_code
    assert expected_url_contains in cls.BASE_URL
    assert expected_url_contains in cls.PORTAL_URL
    assert cls.PLATFORM == "ckan"


# ─── Solr escape (shared with RD MCP, must stay consistent) ───────────────────


def test_escape_solr_basic():
    assert CkanAdapter._escape_solr("simple") == "simple"


def test_escape_solr_quote():
    assert r'\"' in CkanAdapter._escape_solr('has "quote"')


def test_escape_solr_colon():
    assert r"\:" in CkanAdapter._escape_solr("a:b")


def test_fq_term_no_spaces_no_quotes():
    out = CkanAdapter._fq_term("organization", "ministerio-de-salud")
    assert '"' not in out
    assert out.startswith("organization:")


def test_fq_term_with_spaces_uses_quotes():
    out = CkanAdapter._fq_term("organization", "ministerio de salud")
    assert out.startswith('organization:"')
    assert out.endswith('"')


# ─── Formatters ───────────────────────────────────────────────────────────────


def test_truncate_short_unchanged():
    assert CkanAdapter._truncate("hi", 10) == "hi"


def test_truncate_long_ellipsis():
    out = CkanAdapter._truncate("x" * 500, 50)
    assert out and out.endswith("…")
    assert len(out) <= 51


def test_truncate_none():
    assert CkanAdapter._truncate(None, 10) is None


def test_format_dataset_carries_country_code():
    a = DominicanRepublicCkanAdapter()
    raw = {
        "id": "abc",
        "name": "presupuesto",
        "title": "Presupuesto",
        "organization": {"name": "minhac", "title": "Min. Hacienda"},
        "notes": "x" * 500,
        "tags": [{"name": "finanzas"}],
        "groups": [{"title": "Economía"}],
        "resources": [{"format": "CSV"}],
        "metadata_modified": "2026-01-01",
    }
    d = a.format_dataset(raw)
    assert d["country"] == "DO"
    assert d["url"] == "https://datos.gob.do/dataset/presupuesto"
    assert len(d["notes"]) <= 301


def test_format_dataset_chile_url():
    a = ChileCkanAdapter()
    raw = {"id": "x", "name": "abc", "title": "T", "organization": None,
           "tags": [], "groups": [], "resources": []}
    d = a.format_dataset(raw)
    assert d["url"] == "https://datos.gob.cl/dataset/abc"
    assert d["country"] == "CL"
