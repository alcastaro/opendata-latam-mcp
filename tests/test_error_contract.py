"""The error contract: return, never raise — asserted at the tool layer.

Before this contract existed, a real client session calling `search_datasets`
with an unsupported country received, over the wire, `is_error=True` and the
text `'Error executing tool search_datasets'`. Nothing else. The underlying
message named the bad argument and listed the valid ones, and the SDK discarded
it.

These tests are written against the **registered tool functions**, not the
adapters underneath, because the envelope lives at the tool layer and the
adapters still raise by design — that separation is deliberate and asserted
below.
"""

from __future__ import annotations

import asyncio
import re

import httpx
import pytest

from opendata_latam_mcp.errors import build_error, tool_envelope
from opendata_latam_mcp.server import mcp

TOOL_NAMES = [
    "list_supported_countries", "search_datasets", "get_dataset",
    "list_recent_datasets", "get_resource", "search_resources",
    "list_organizations", "get_organization", "list_groups", "list_tags",
    "autocomplete", "get_site_stats", "read_resource_rows",
    "cross_country_search", "cross_country_stats",
]


def _tool(name: str):
    entry = mcp._tool_manager.get_tool(name)
    assert entry is not None, f"{name} is not registered"
    return entry.fn


# ─── The shape contract that makes the envelope possible ──────────────────────


@pytest.fixture(scope="module")
def tools():
    return asyncio.run(mcp.list_tools())


def test_every_tool_returns_an_object_never_a_bare_list():
    """Uniform dicts are a hard requirement, not a style choice.

    SDK v2 derives an output schema from the return annotation and validates
    against it. A tool annotated `-> list[str]` that returns the error envelope
    raises `UnexpectedToolError`, which is precisely the opaque failure the
    envelope exists to remove. Measured, not assumed.
    """
    import inspect

    for name in TOOL_NAMES:
        ann = inspect.signature(_tool(name)).return_annotation
        # `dict[str, Any]`, not bare `dict`: only the parametrized form makes SDK
        # v2 emit an output schema — and with it structured content on the wire.
        # Measured 2026-09-12: bare `dict` gave fifteen tools with no schema.
        assert str(ann).replace("typing.", "") == "dict[str, Any]", (
            f"{name} returns {ann!r}, must be dict[str, Any]"
        )


def test_no_tool_advertises_an_array_output_schema(tools):
    for tool in tools:
        schema = getattr(tool, "output_schema", None)
        if not schema:
            continue
        result = schema.get("properties", {}).get("result", {})
        assert result.get("type") != "array", (
            f"{tool.name} advertises an array result; the envelope cannot satisfy it"
        )


# ─── No tool raises ───────────────────────────────────────────────────────────


async def test_unknown_country_returns_a_hint_instead_of_raising():
    out = await _tool("search_datasets")(country="XX", query="agua")
    assert out["error"].startswith("Unknown country")
    # The original message is preserved: it lists the valid codes, which is the
    # difference between a model that can fix its call and one that guesses.
    assert "'AR'" in out["error"]
    assert "list_supported_countries" in out["hint"]
    assert out["tool"] == "search_datasets"
    assert out["country"] == "XX"


async def test_portal_failure_returns_a_hint_instead_of_raising(httpx_mock):
    httpx_mock.add_response(status_code=403)
    out = await _tool("search_datasets")(country="PA", query="agua")
    assert "403" in out["error"]
    assert "refusing programmatic access" in out["hint"]


async def test_network_failure_returns_a_hint_instead_of_raising(httpx_mock):
    httpx_mock.add_exception(httpx.ConnectError("no route"))
    out = await _tool("get_dataset")(country="PA", id="whatever")
    assert out["error"]
    assert out["hint"]


@pytest.mark.parametrize(
    "name,args",
    [
        ("search_datasets", {"country": "XX"}),
        ("get_dataset", {"country": "XX", "id": "x"}),
        ("list_recent_datasets", {"country": "XX"}),
        ("get_resource", {"country": "XX", "id": "x"}),
        ("search_resources", {"country": "XX", "query": "x"}),
        ("list_organizations", {"country": "XX"}),
        ("get_organization", {"country": "XX", "id": "x"}),
        ("list_groups", {"country": "XX"}),
        ("list_tags", {"country": "XX"}),
        ("autocomplete", {"country": "XX", "kind": "dataset", "query": "x"}),
        ("get_site_stats", {"country": "XX"}),
        ("read_resource_rows", {"country": "XX", "resource_id": "x"}),
    ],
)
async def test_no_per_country_tool_raises_on_a_bad_country(name, args):
    out = await _tool(name)(**args)
    assert isinstance(out, dict)
    assert out.get("error") and out.get("hint"), f"{name} gave no actionable error"


# ─── The hint taxonomy earns its keep ─────────────────────────────────────────


@pytest.mark.parametrize(
    "message,expected",
    [
        ("Unknown country: 'ZZ'", "list_supported_countries"),
        ("[PA] portal package_search HTTP 403 Forbidden", "refusing programmatic access"),
        ("[PA] portal package_show HTTP 404 NOT FOUND", "not shared between countries"),
        ("[MX] timeout in package_search (>15.0s)", "lower `limit`"),
        ("[CL] network error in package_search: boom", "unreachable"),
        ("[UY] CKAN error in package_search: bad param", "rejected its contents"),
        ("[AR] portal package_search HTTP 429 Too Many Requests", "rate-limiting"),
        ("something nobody predicted", "original message is in `error`"),
    ],
)
def test_each_failure_class_gets_its_own_action(message, expected):
    """A hint names an action, not a diagnosis.

    "The portal is refusing" tells a model nothing it can do; "try another
    country, or use cross_country_search" does.
    """
    out = build_error(RuntimeError(message), tool="t")
    assert expected in out["hint"], f"{message!r} got: {out['hint']}"


def test_an_ambiguous_message_goes_to_the_most_specific_branch():
    """Pins the branch ORDER, which is where a string taxonomy rots.

    Portals forward things like "database connection failed" inside a CKAN
    error. A bare "connect" test would claim that for the network hint and send
    the model to retry a call the portal rejected on its contents. If anyone
    reorders `_hint_for`, this fails instead of silently degrading.
    """
    out = build_error(
        RuntimeError("[DO] CKAN error in package_show: database connection failed"),
        tool="t",
    )
    assert "rejected its contents" in out["hint"]
    assert "unreachable" not in out["hint"]


def test_the_original_message_is_never_swallowed():
    out = build_error(ValueError("the specific thing that went wrong"), tool="t")
    assert "the specific thing that went wrong" in out["error"]


def test_a_flood_of_error_text_is_capped():
    """A portal that answers with an HTML error page must not fill the context."""
    out = build_error(RuntimeError("x" * 5000), tool="t")
    assert len(out["error"]) <= 401


async def test_the_envelope_preserves_the_wrapped_signature():
    """`functools.wraps` is load-bearing: the SDK reads the wrapper's signature
    and docstring to build the tool schema."""

    @tool_envelope
    async def sample(country: str) -> dict:
        """A docstring the SDK will publish."""
        return {"ok": True, "country": country}

    assert sample.__name__ == "sample"
    assert sample.__doc__ == "A docstring the SDK will publish."
    assert await sample(country="PA") == {"ok": True, "country": "PA"}


# ─── The layer boundary is deliberate ─────────────────────────────────────────


async def test_adapters_still_raise_so_callers_can_choose(httpx_mock):
    """The envelope belongs to the tool layer, not the adapter.

    Internal callers — the sweep harness, cross_country_search — need to
    distinguish failures and handle them per country. If the adapter swallowed
    them, `cross_country_search` could not report which portal failed.
    """
    from opendata_latam_mcp.adapters.ckan import PanamaCkanAdapter

    httpx_mock.add_response(status_code=500)
    with pytest.raises(RuntimeError):
        await PanamaCkanAdapter().search_datasets(query="x")


async def test_cross_country_search_reports_a_dead_portal_without_failing(httpx_mock):
    """One portal down must not sink the fan-out — that is the whole value-add."""
    httpx_mock.add_response(
        url=re.compile(r".*datosabiertos\.gob\.pa.*"),
        json={"success": True, "result": {"count": 3, "results": []}},
        is_reusable=True,
    )
    httpx_mock.add_response(status_code=403, is_reusable=True)

    out = await _tool("cross_country_search")(query="agua", countries=["PA", "EC"])
    assert out["summary"]["EC"]["portal_error"], "a dead portal must be named"
    assert out["summary"]["PA"]["portal_error"] is None


# ─── Failures found on 2026-09-12, each with the hint it now gets ─────────────


async def test_a_dns_failure_is_a_network_error_not_an_unexpected_one(monkeypatch):
    """The SSRF guard resolves every host before httpx does, and it raises its
    own exception type from inside the request hook. Measured on a machine with
    no DNS: that exception escaped the adapter as itself, so the envelope filed
    "cannot resolve host" under "Unexpected failure" and told the model to check
    its arguments — for a connectivity fault. The adapter's contract of raising
    RuntimeError, which the fan-out and the live suite depend on, stopped holding
    at the same time."""
    from opendata_latam_mcp import netguard
    from opendata_latam_mcp.adapters import get_adapter

    def _no_dns(host):
        raise netguard.NetGuardError(f"cannot resolve host {host!r}: nodename not known")

    monkeypatch.setattr(netguard, "_resolve", _no_dns)
    await get_adapter("PA").close()  # a fresh client, so the hook runs

    with pytest.raises(RuntimeError) as excinfo:
        await get_adapter("PA").search_datasets(query="agua")
    assert "network error" in str(excinfo.value)

    out = await _tool("search_datasets")(country="PA", query="agua")
    assert "cannot resolve host" in out["error"]
    assert "unreachable" in out["hint"]
    assert "Unexpected" not in out["hint"]


async def test_a_web_page_where_json_was_expected_names_the_portal_not_the_parser(httpx_mock):
    """Panama's `status_show` answers HTTP 200 with an HTML page. Before this,
    the model received 'Expecting value: line 1 column 1 (char 0)' — a JSON
    parser's complaint, with nothing about what the portal did."""
    httpx_mock.add_response(status_code=200, text="<html><body>Access denied</body></html>")
    out = await _tool("get_dataset")(country="PA", id="whatever")
    assert "non-JSON body" in out["error"]
    assert "Access denied" in out["error"]
    assert "web page" in out["hint"]
    assert "Expecting value" not in out["error"]


async def test_cross_country_search_normalizes_and_deduplicates_codes(httpx_mock):
    """Measured with ["mx", "MX"]: Mexico was queried twice, answered under two
    keys, and the summary called the lowercase one "mx" because the COUNTRIES
    lookup is case-sensitive. An unknown code gets its own error entry rather
    than sinking the fan-out — the same treatment a dead portal gets."""
    httpx_mock.add_response(json={"success": True, "result": {"count": 1, "results": []}})
    out = await _tool("cross_country_search")(query="agua", countries=["mx", "MX", "Mexico", "XX"])
    assert set(out["by_country"]) == {"MX", "XX"}
    assert out["countries_queried"] == ["MX"]
    assert out["summary"]["MX"]["country_name"] == "México"
    assert out["summary"]["MX"]["total_hits"] == 1
    assert out["by_country"]["XX"]["error"].startswith("Unknown country")
    assert out["summary"]["XX"]["portal_error"]
    # One request for one country, not three.
    assert len(httpx_mock.get_requests()) == 1
