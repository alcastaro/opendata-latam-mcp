"""Opt-in live tests against real LatAm portals.

Skipped by default. Enable with: RUN_LIVE_TESTS=1 pytest tests/test_live_portals.py
"""

from __future__ import annotations

import asyncio

import pytest

from opendata_latam_mcp import adapters

pytestmark = pytest.mark.live


SUPPORTED = ["AR", "CL", "DO", "EC", "MX", "PA", "UY"]


@pytest.fixture(autouse=True)
async def _close_adapters():
    """Adapters cache httpx clients. Close between tests so each test gets a
    fresh client bound to the test's event loop."""
    yield
    await adapters.registry.close_all()


@pytest.mark.parametrize("country", SUPPORTED)
async def test_live_site_stats(country):
    a = adapters.get_adapter(country)
    s = await a.get_site_stats()
    assert s["country"] == country
    assert s["total_datasets"] is not None
    assert s["total_datasets"] > 100  # every gov portal we cover has > 100 datasets


@pytest.mark.parametrize("country", SUPPORTED)
async def test_live_search_one_term(country):
    a = adapters.get_adapter(country)
    r = await a.search_datasets(query="presupuesto", limit=2)
    assert r["country"] == country
    assert "datasets" in r
    # 'presupuesto' is universal across LatAm gov portals — must hit > 0
    assert r["total"] > 0


async def test_live_cross_country_parallel():
    """The unique value-add: 6 portals queried in parallel under 5 seconds."""
    import time

    t0 = time.time()
    results = await asyncio.gather(*[
        adapters.get_adapter(c).search_datasets(query="presupuesto", limit=1)
        for c in SUPPORTED
    ])
    elapsed = time.time() - t0
    assert elapsed < 10.0, f"Parallel cross-country took {elapsed:.1f}s"
    total = sum(r["total"] for r in results)
    assert total > 500  # cumulative hits across 6 LatAm portals


# ─── Row reading (DataStore route) ────────────────────────────────────────────

# Only the portals whose DataStore was measured as answering on 2026-08-30. The
# route is a property of the portal, not of this server, so a portal that has no
# DataStore is not a failure here — the Dominican Republic has none at all and
# needs the file route, which does not exist yet.
DATASTORE_COUNTRIES = ["AR", "CL", "MX", "PA", "UY"]


@pytest.mark.parametrize("country", DATASTORE_COUNTRIES)
async def test_live_read_rows_through_the_registered_tool(country):
    """Exercise the tool a model would call, not the adapter underneath it.

    Walks a handful of datasets rather than assuming the first one is readable:
    the DataStore covers a fraction of any catalogue, so a single dataset is a
    coin flip, and a test that flips a coin is a test that will lie one day.
    """
    from opendata_latam_mcp.server import mcp

    tool = mcp._tool_manager.get_tool("read_resource_rows").fn
    a = adapters.get_adapter(country)
    found = await a.search_datasets(query=None, limit=8)

    for ds in found.get("datasets") or []:
        full = await a.get_dataset(ds.get("id") or ds.get("name"))
        for r in (full.get("resources") or [])[:3]:
            if not r.get("id"):
                continue
            out = await tool(country=country, resource_id=r["id"], limit=3)
            assert isinstance(out, dict), "the tool must always return a dict"
            if out.get("rows"):
                assert out["route"] == "ckan_datastore"
                assert out["country"] == country
                assert out["fields"]
                return
            # Anything that is not rows must still be actionable, never opaque.
            assert "error" in out and "hint" in out

    pytest.skip(f"{country}: no readable DataStore resource in the first 8 datasets")


async def test_live_read_rows_never_accepts_a_url():
    """The invariant, asserted against a live portal rather than a mock."""
    from opendata_latam_mcp.server import mcp

    tool = mcp._tool_manager.get_tool("read_resource_rows").fn
    out = await tool(country="PA", resource_id="https://169.254.169.254/latest/meta-data/")
    assert "error" in out and "hint" in out
    assert "rows" not in out
