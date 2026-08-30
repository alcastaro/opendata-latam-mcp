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

DS = "https://datosabiertos.gob.pa/api/3/action/datastore_search"


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
