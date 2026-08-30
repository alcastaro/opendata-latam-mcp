"""Opt-in live tests against real LatAm portals.

Skipped by default. Enable with: RUN_LIVE_TESTS=1 pytest tests/test_live_portals.py
"""

from __future__ import annotations

import asyncio

import pytest

from opendata_latam_mcp import adapters

pytestmark = pytest.mark.live


# Every configured country, and the subset each adapter declares as answering.
# Driving the "must work" tests off STATUS rather than a literal list turns a
# permanently-red test into a meaningful one: a portal known to be down does not
# fail these, and the assertion that it is really down lives in its own test,
# which fails in BOTH directions — if Ecuador starts answering again, that test
# goes red and tells us to update the declared status.
SUPPORTED = ["AR", "CL", "DO", "EC", "MX", "PA", "UY"]
ANSWERING = [c for c in SUPPORTED if adapters.get_adapter(c).STATUS == "ok"]
UNREACHABLE = [c for c in SUPPORTED if adapters.get_adapter(c).STATUS != "ok"]


@pytest.fixture(autouse=True)
async def _close_adapters():
    """Adapters cache httpx clients. Close between tests so each test gets a
    fresh client bound to the test's event loop."""
    yield
    await adapters.registry.close_all()


@pytest.mark.parametrize("country", ANSWERING)
async def test_live_site_stats(country):
    a = adapters.get_adapter(country)
    s = await a.get_site_stats()
    assert s["country"] == country
    assert s["total_datasets"] is not None
    assert s["total_datasets"] > 100  # every gov portal we cover has > 100 datasets


@pytest.mark.parametrize("country", ANSWERING)
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
        for c in ANSWERING
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


# ─── Every registered tool, against every portal ──────────────────────────────

# Written after the Colombian MCP found three defects its 538 hermetic tests
# could not see. The worst of them, `query_dataset_soql`, had NEVER worked
# against a real portal: it sent the row cap in a way Socrata rejects with HTTP
# 400, so it failed 100% of the time in production and 0% in CI, because
# hermetic tests mock the HTTP layer. It was the only one of 24 tools without a
# live test.
#
# The lesson is not "add one more test". It is that a hermetic test proves the
# code does what its author expected the portal to accept, and only a live test
# proves the portal accepts it. From inside the process the two failures look
# identical.
#
# So: every tool, through the registered function a model would call, against
# every portal. Not the adapter underneath it — the tool layer adds validation,
# clamping and the error envelope, and those are what a portal rejects.


def _tool(name: str):
    from opendata_latam_mcp.server import mcp

    entry = mcp._tool_manager.get_tool(name)
    assert entry is not None, f"{name} is not registered on the server"
    return entry.fn


async def _first_dataset(country: str):
    """A real dataset id and resource id from this portal, or (None, None)."""
    found = await _tool("search_datasets")(country=country, limit=5)
    for ds in found.get("datasets") or []:
        ident = ds.get("id") or ds.get("name")
        if not ident:
            continue
        full = await _tool("get_dataset")(country=country, id=ident)
        for r in full.get("resources") or []:
            if r.get("id"):
                return ident, r["id"]
        return ident, None
    return None, None


@pytest.mark.parametrize("country", ANSWERING)
async def test_live_every_per_country_tool_answers(country):
    """Exercise all eleven per-country tools against one real portal.

    Asserts shape, not content: what is being checked is that the portal accepts
    the request this server actually builds. A tool that returns an empty list
    passes; a tool that raises, or comes back as something other than the shape
    its callers expect, does not.
    """
    dataset_id, resource_id = await _first_dataset(country)
    if dataset_id is None:
        pytest.skip(f"{country}: no dataset with an id in the first 5 results")

    org_slug = None
    orgs = await _tool("list_organizations")(country=country, limit=3)
    assert isinstance(orgs, dict) and "organizations" in orgs
    if orgs["organizations"]:
        first = orgs["organizations"][0]
        org_slug = first.get("name") or first.get("id")

    # Every tool returns a dict. That is a contract, not a coincidence: SDK v2
    # derives an output schema from the return annotation and validates against
    # it, so a tool annotated `-> list` cannot return the {"error","hint"}
    # envelope without raising. Uniform dicts are what make the envelope
    # possible, and each carries the key its payload lives under.
    checks = {
        "get_dataset": (_tool("get_dataset")(country=country, id=dataset_id), None),
        "list_recent_datasets": (_tool("list_recent_datasets")(country=country, limit=3), "datasets"),
        "search_resources": (_tool("search_resources")(country=country, query="csv", limit=3), "resources"),
        "list_groups": (_tool("list_groups")(country=country), "groups"),
        "list_tags": (_tool("list_tags")(country=country, limit=5), "tags"),
        "autocomplete": (
            _tool("autocomplete")(country=country, kind="dataset", query="salud", limit=3),
            "suggestions",
        ),
        "get_site_stats": (_tool("get_site_stats")(country=country), None),
    }
    if resource_id:
        checks["get_resource"] = (_tool("get_resource")(country=country, id=resource_id), None)
    if org_slug:
        checks["get_organization"] = (
            _tool("get_organization")(country=country, id=org_slug),
            None,
        )

    failures = []
    for name, (coro, payload_key) in checks.items():
        try:
            out = await coro
        except Exception as e:  # noqa: BLE001 — the point is to report every one
            failures.append(f"{name}: raised {type(e).__name__}: {e} — no tool may raise")
            continue
        if not isinstance(out, dict):
            failures.append(f"{name}: returned {type(out).__name__}, expected dict")
            continue
        if "error" in out:
            # An envelope is an acceptable answer, but it must be actionable.
            if not out.get("hint"):
                failures.append(f"{name}: returned an error with no hint")
            continue
        if payload_key and payload_key not in out:
            failures.append(f"{name}: dict without its `{payload_key}` key: {sorted(out)}")

    assert not failures, f"{country}: " + " | ".join(failures)


async def test_live_catalog_and_cross_country_tools_answer():
    supported = await _tool("list_supported_countries")()
    assert isinstance(supported, dict)
    assert supported["count"] == len(supported["countries"])
    # `status` is what lets a model route around a dead portal without spending
    # a turn on it, so it has to be present on every entry.
    assert all("status" in c for c in supported["countries"])

    search = await _tool("cross_country_search")(query="presupuesto", limit_per_country=2)
    assert set(search) >= {"query", "summary", "by_country", "grand_total_hits"}
    # A portal that is down must appear as its own error, not sink the call.
    assert search["grand_total_hits"] > 0
    working = [c for c, s in search["summary"].items() if s.get("portal_error") is None]
    assert len(working) >= 5, f"only {len(working)} portals answered: {search['summary']}"

    stats = await _tool("cross_country_stats")()
    assert isinstance(stats, dict) and stats


# ─── The declared status must match reality ───────────────────────────────────


@pytest.mark.parametrize("country", UNREACHABLE)
async def test_live_declared_unreachable_portal_is_really_unreachable(country):
    """A portal declared dead must actually be dead — and come back loudly.

    `STATUS = "unreachable"` is a claim this server makes to the model, so it
    needs the same standard as a coverage figure: measured, not remembered. This
    test fails in both directions. If the portal is still refusing, it passes and
    the declaration stands. If it starts answering, this goes red and says so,
    which is the only reliable way anyone will notice — the "must work" tests
    skip these countries by design, so nothing else would.
    """
    a = adapters.get_adapter(country)
    assert a.STATUS_NOTE, f"{country}: declared unreachable without saying why"
    with pytest.raises(RuntimeError) as excinfo:
        await a.search_datasets(query="presupuesto", limit=1)
    assert country in str(excinfo.value)


@pytest.mark.parametrize("country", UNREACHABLE)
async def test_live_unreachable_portal_still_returns_an_actionable_envelope(country):
    """Down is not an excuse for an unhelpful answer.

    The tool layer must still hand the model an error it can act on, rather than
    an exception or a row of nulls. Ecuador answering 403 is exactly the case
    that made `get_site_stats` return four `None`s and no error at all.
    """
    from opendata_latam_mcp.server import mcp

    for name, args in [
        ("search_datasets", {"country": country, "query": "presupuesto"}),
        ("get_site_stats", {"country": country}),
    ]:
        out = await mcp._tool_manager.get_tool(name).fn(**args)
        assert isinstance(out, dict), f"{name} must return a dict even when down"
        assert out.get("error"), f"{name} must report the failure, not hide it"
        assert out.get("hint"), f"{name} must say what to try next"
        assert "null" not in str(out.get("total_datasets", "")).lower()
