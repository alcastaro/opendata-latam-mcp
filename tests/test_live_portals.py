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
