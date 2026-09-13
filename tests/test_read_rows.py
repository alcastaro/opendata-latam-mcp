"""Row reading through the CKAN DataStore, and the coverage harness.

Two properties here are not conveniences, they are the reason the tool is shaped
the way it is:

* **No tool accepts a URL.** `read_resource_rows` takes a resource identifier and
  builds the address from the portal's own BASE_URL, so the set of hosts this
  server can reach is bounded by what a government catalogue publishes rather
  than by what an argument can express. With seven countries that matters more,
  not less, and it is asserted rather than documented.
* **Return, never raise.** An exception reaches the model as an opaque protocol
  error it cannot act on; a dict with a `hint` tells it what to try instead.
"""

from __future__ import annotations

import httpx
import pytest

from opendata_latam_mcp.adapters.ckan import PanamaCkanAdapter

DS = "https://www.datosabiertos.gob.pa/api/3/action/datastore_search"


# ─── The no-URL invariant ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "bad",
    [
        "https://evil.example/steal",
        "http://127.0.0.1:8080/admin",
        "http://169.254.169.254/latest/meta-data/",
        "../../../etc/passwd",
        "abc/../../other",
        "id with spaces",
        "",
    ],
)
async def test_read_rows_rejects_anything_that_is_not_an_identifier(bad, httpx_mock):
    """A URL, a traversal or a loopback address must never reach the network."""
    a = PanamaCkanAdapter()
    out = await a.read_resource_rows(bad)
    assert "error" in out and "hint" in out
    assert not httpx_mock.get_requests(), "a rejected identifier still hit the network"


async def test_read_rows_accepts_a_uuid(httpx_mock):
    rid = "3f2a1b4c-5d6e-4f80-9a1b-2c3d4e5f6071"
    httpx_mock.add_response(
        url=f"{DS}?resource_id={rid}&limit=5&offset=0",
        json={
            "success": True,
            "result": {
                "total": 12,
                "fields": [{"id": "_id", "type": "int"}, {"id": "monto", "type": "numeric"}],
                "records": [{"_id": 1, "monto": 100}, {"_id": 2, "monto": 250}],
            },
        },
    )
    out = await PanamaCkanAdapter().read_resource_rows(rid, limit=5)
    assert out["route"] == "ckan_datastore"
    assert out["country"] == "PA"
    assert out["total_rows"] == 12
    assert out["returned"] == 2
    # _id is CKAN's own row counter; it is noise to a model, so it is dropped
    # from both the rows and the field list.
    assert all("_id" not in r for r in out["rows"])
    assert [f["id"] for f in out["fields"]] == ["monto"]


# ─── Return, never raise ──────────────────────────────────────────────────────


async def test_missing_datastore_table_blames_the_catalogue_not_the_caller(httpx_mock):
    """CKAN's `datastore_active` flag lies; the message has to say so.

    A sibling project measured 37 of 59 resources marked queryable answering 404.
    If the tool just forwards "404", the model concludes it asked wrongly and
    retries the same call. Naming the catalogue as the wrong party is what makes
    it try another route instead.
    """
    rid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    httpx_mock.add_response(
        url=f"{DS}?resource_id={rid}&limit=20&offset=0", status_code=404
    )
    out = await PanamaCkanAdapter().read_resource_rows(rid)
    assert "error" in out and "hint" in out
    assert "catalogue says it is queryable" in out["error"]
    assert "get_resource" in out["hint"]


async def test_portal_failure_returns_a_dict_rather_than_raising(httpx_mock):
    rid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    httpx_mock.add_response(
        url=f"{DS}?resource_id={rid}&limit=20&offset=0", status_code=500
    )
    out = await PanamaCkanAdapter().read_resource_rows(rid)
    assert "error" in out and "hint" in out


async def test_network_error_returns_a_dict_rather_than_raising(httpx_mock):
    rid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    httpx_mock.add_exception(httpx.ConnectError("boom"))
    out = await PanamaCkanAdapter().read_resource_rows(rid)
    assert "error" in out and "hint" in out


# ─── Output bounds ────────────────────────────────────────────────────────────


async def test_long_cells_are_truncated_so_one_call_cannot_flood_the_context(httpx_mock):
    rid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    httpx_mock.add_response(
        url=f"{DS}?resource_id={rid}&limit=20&offset=0",
        json={
            "success": True,
            "result": {"total": 1, "fields": [{"id": "nota", "type": "text"}],
                       "records": [{"nota": "x" * 5000}]},
        },
    )
    out = await PanamaCkanAdapter().read_resource_rows(rid)
    assert len(out["rows"][0]["nota"]) <= 201


async def test_limit_is_capped_at_the_documented_maximum(httpx_mock):
    rid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    httpx_mock.add_response(
        url=f"{DS}?resource_id={rid}&limit=100&offset=0",
        json={"success": True, "result": {"total": 0, "fields": [], "records": []}},
    )
    out = await PanamaCkanAdapter().read_resource_rows(rid, limit=99999)
    assert out["returned"] == 0  # the mock only matches when limit was clamped to 100


# ─── The sweep harness ────────────────────────────────────────────────────────


def test_sweep_measures_the_registered_tool_not_the_http_client():
    """The rule that made four coverage figures wrong: measure the real tool.

    If the sweep talked to the adapter directly it could report a number the
    model can never reproduce, because the tool layer adds validation, clamping
    and the error envelope. Resolving through the tool manager makes the sweep
    break when the tool breaks, which is the point.
    """
    from opendata_latam_mcp.server import mcp
    from opendata_latam_mcp.sweep import _resolve_tool

    fn = _resolve_tool()
    assert fn is mcp._tool_manager.get_tool("read_resource_rows").fn


def test_sweep_reports_zero_coverage_without_dividing_by_zero():
    from opendata_latam_mcp.sweep import CountryResult

    assert CountryResult(country="XX").coverage == 0.0


def test_sweep_counts_datasets_not_resources():
    """A dataset with twenty unreadable layers and one CSV counts once, not 1/21."""
    from opendata_latam_mcp.sweep import CountryResult

    r = CountryResult(country="PA", datasets_sampled=40, datasets_with_rows=11)
    assert r.coverage == pytest.approx(27.5)
    assert "with_rows=11" in r.line()


# ─── Robustness bounds (audit R3) ─────────────────────────────────────────────


async def test_a_nested_cell_is_truncated_too(httpx_mock):
    """The per-cell cap used to apply only to strings.

    CKAN JSONB columns hold objects and arrays. Those came back whole, so a
    resource with large nested cells flooded the model's context despite the
    cap being "in place". Non-scalars are serialized before being measured,
    because the serialized size is what actually costs context.
    """
    rid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    httpx_mock.add_response(
        url=f"{DS}?resource_id={rid}&limit=20&offset=0",
        json={
            "success": True,
            "result": {
                "total": 1,
                "fields": [{"id": "payload", "type": "json"}],
                "records": [{"payload": {"items": ["x" * 400 for _ in range(20)]}}],
            },
        },
    )
    out = await PanamaCkanAdapter().read_resource_rows(rid)
    assert len(str(out["rows"][0]["payload"])) <= 201


async def test_an_oversized_response_is_refused_not_truncated(httpx_mock, monkeypatch):
    """A body over the cap must fail loudly rather than be cut.

    Truncating changes what a parse failure means: a JSON body cut at the byte
    limit fails with "invalid JSON" at exactly that offset, and the message
    blames the publisher for a cut we made. The sibling project lost hours to
    that. Refusing names the real cause and says what to do.
    """
    from opendata_latam_mcp.adapters.ckan import base as ckan_base

    monkeypatch.setattr(ckan_base, "MAX_RESPONSE_BYTES", 1024)
    httpx_mock.add_response(
        json={"success": True, "result": {"count": 0, "results": [{"pad": "x" * 5000}]}}
    )
    out = await PanamaCkanAdapter().read_resource_rows(
        "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    )
    assert "exceeded" in out["error"]
    assert "fewer rows" in out["error"] or "fewer rows" in out["hint"]


async def test_concurrent_calls_share_one_client():
    """cross_country_search fans out; without a lock each call could build its
    own client and leak all but one.

    No HTTP mock here on purpose: this asserts client construction, and
    registering an unused response would fail the suite for the wrong reason.
    """
    import asyncio as _asyncio

    adapter = PanamaCkanAdapter()
    clients = await _asyncio.gather(*[adapter._get_client() for _ in range(8)])
    assert len({id(c) for c in clients}) == 1
    await adapter.close()


def test_the_timeout_is_configurable_and_bounded(monkeypatch):
    """Fixed at 15s it was measured too short for real aggregation, and an
    unbounded value could hang a stdio server forever."""
    import importlib

    from opendata_latam_mcp.adapters.ckan import base as ckan_base

    monkeypatch.setenv("OPENDATA_LATAM_TIMEOUT", "90")
    importlib.reload(ckan_base)
    assert ckan_base.DEFAULT_TIMEOUT == 90.0

    monkeypatch.setenv("OPENDATA_LATAM_TIMEOUT", "99999")
    importlib.reload(ckan_base)
    assert ckan_base.DEFAULT_TIMEOUT == 300.0

    monkeypatch.delenv("OPENDATA_LATAM_TIMEOUT")
    importlib.reload(ckan_base)
    assert ckan_base.DEFAULT_TIMEOUT == 15.0


def test_the_response_cap_is_bounded_and_survives_a_typo(monkeypatch):
    """Its sibling above was bounded and this one was not — measured 2026-09-13.

    Two failures, both from the same missing parse. A non-numeric value raised
    ValueError at IMPORT time, so the server never started and a stdio client
    saw a dead process with a traceback; a typo in an environment variable must
    not cost you the whole server. And an unbounded value was accepted, so
    999999 gave a ~1 TB ceiling that silently disabled the memory protection
    this constant exists to provide.
    """
    import importlib

    from opendata_latam_mcp.adapters.ckan import base as ckan_base

    monkeypatch.setenv("OPENDATA_LATAM_MAX_RESPONSE_MB", "50")
    importlib.reload(ckan_base)
    assert ckan_base.MAX_RESPONSE_MB == 50

    # Garbage falls back to the default rather than killing the process.
    monkeypatch.setenv("OPENDATA_LATAM_MAX_RESPONSE_MB", "abc")
    importlib.reload(ckan_base)
    assert ckan_base.MAX_RESPONSE_MB == 25

    # Clamped at both ends, so neither a huge value nor a zero disables the cap.
    monkeypatch.setenv("OPENDATA_LATAM_MAX_RESPONSE_MB", "999999")
    importlib.reload(ckan_base)
    assert ckan_base.MAX_RESPONSE_MB == 512

    monkeypatch.setenv("OPENDATA_LATAM_MAX_RESPONSE_MB", "0")
    importlib.reload(ckan_base)
    assert ckan_base.MAX_RESPONSE_MB == 1

    monkeypatch.delenv("OPENDATA_LATAM_MAX_RESPONSE_MB")
    importlib.reload(ckan_base)
    assert ckan_base.MAX_RESPONSE_MB == 25
    assert ckan_base.MAX_RESPONSE_BYTES == 25 * 1024 * 1024
