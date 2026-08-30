"""The SSRF guard, including the case that motivated it: the redirect.

This server already had the strong half of the defence — no tool accepts a URL,
so every address is built from a portal's own configured base, and that is
asserted elsewhere. What it did not have was any validation of where a redirect
goes. `follow_redirects=True` meant a portal answering
`302 Location: http://169.254.169.254/latest/meta-data/` would be followed to a
cloud metadata endpoint, and nothing checked.

The distinction these tests encode: a check that runs once before the first
request validates the address we chose. A request *event hook* runs on every
hop. Only the second closes the redirect.
"""

from __future__ import annotations

import httpx
import pytest

from opendata_latam_mcp import netguard
from opendata_latam_mcp.adapters.ckan import PanamaCkanAdapter
from opendata_latam_mcp.netguard import NetGuardError, assert_public_url, check_address

# Captured before conftest's autouse fixture swaps it out. The fixture keeps the
# hermetic suite off DNS; the tests below that exercise resolution itself put the
# real implementation back for their own duration.
_REAL_RESOLVE = netguard._resolve


# ─── The address rules ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "addr,what",
    [
        ("127.0.0.1", "loopback"),
        ("::1", "IPv6 loopback"),
        ("10.0.0.5", "RFC-1918 private"),
        ("172.16.0.1", "RFC-1918 private"),
        ("192.168.1.1", "RFC-1918 private"),
        ("169.254.169.254", "cloud metadata endpoint"),
        ("100.64.0.1", "CGNAT"),
        ("fd00::1", "IPv6 unique-local"),
        ("0.0.0.0", "unspecified"),  # noqa: S104 — an address under test, not a bind
    ],
)
def test_non_public_addresses_are_refused(addr, what):
    """`is_global` is the single control, on purpose.

    It already covers every range below. Enumerating them by hand is how one
    gets missed — 169.254.169.254 is not special-cased here, it is refused
    because link-local is not global.
    """
    with pytest.raises(NetGuardError):
        check_address(addr, host=what)


@pytest.mark.parametrize("addr", ["93.184.216.34", "8.8.8.8", "2606:2800:220:1:248:1893:25c8:1946"])
def test_public_addresses_are_allowed(addr):
    check_address(addr)


def test_an_unparseable_address_is_refused_rather_than_ignored():
    with pytest.raises(NetGuardError):
        check_address("not-an-address")


def test_a_non_http_scheme_is_refused(monkeypatch):
    monkeypatch.setattr(netguard, "_resolve", lambda _host: ["93.184.216.34"])
    with pytest.raises(NetGuardError):
        assert_public_url("file:///etc/passwd")


def test_a_host_that_does_not_resolve_fails_closed(monkeypatch):
    """A name that will not resolve must refuse, never fall through.

    Puts the real resolver back first: the autouse fixture that keeps the
    hermetic suite off DNS would otherwise make this test pass without
    exercising anything.
    """
    import socket

    def boom(_host, *_a, **_k):
        raise socket.gaierror("no such host")

    monkeypatch.setattr(netguard, "_resolve", _REAL_RESOLVE)
    monkeypatch.setattr(netguard.socket, "getaddrinfo", boom)
    with pytest.raises(NetGuardError):
        assert_public_url("https://nonexistent.invalid/api")


def test_every_resolved_address_is_checked_not_just_the_first(monkeypatch):
    """A host resolving to one public and one private address must be refused.

    Checking only the first resolved address is a real bypass: an attacker who
    controls DNS can order the answers so the public one leads.
    """
    monkeypatch.setattr(netguard, "_resolve", lambda _host: ["93.184.216.34", "127.0.0.1"])
    with pytest.raises(NetGuardError):
        assert_public_url("https://example.test/api")


# ─── The case the guard exists for ────────────────────────────────────────────


async def test_a_redirect_to_the_metadata_endpoint_is_refused(httpx_mock, monkeypatch):
    """The whole point: the hook runs on the hop, not only on the first call.

    A compromised or misbehaving government portal answers 302 pointing at the
    cloud metadata address. Without the hook this is followed and the response
    is handed back. With it, the redirect fails closed.
    """
    real_hosts = {
        "datosabiertos.gob.pa": ["93.184.216.34"],
        "169.254.169.254": ["169.254.169.254"],
    }
    monkeypatch.setattr(netguard, "_resolve", lambda h: real_hosts.get(h, ["93.184.216.34"]))

    httpx_mock.add_response(
        url="https://datosabiertos.gob.pa/api/3/action/package_search?q=%2A%3A%2A&rows=10&start=0",
        status_code=302,
        headers={"Location": "http://169.254.169.254/latest/meta-data/"},
    )

    adapter = PanamaCkanAdapter()
    with pytest.raises(Exception) as excinfo:
        await adapter.search_datasets()
    # The guard's message must survive whatever wraps it, or nobody debugging
    # this in six months learns why the call died.
    assert "169.254.169.254" in str(excinfo.value) or "non-public" in str(excinfo.value)
    await adapter.close()


async def test_the_guard_is_installed_on_the_client_not_called_once_by_hand():
    """Asserts the mechanism, not just the behaviour.

    A one-shot call before the first request would pass the behavioural test
    above only by accident. What makes redirects safe is that the guard is an
    httpx *request* event hook, so this asserts it is registered as one.
    """
    adapter = PanamaCkanAdapter()
    client = await adapter._get_client()
    hooks = client.event_hooks.get("request", [])
    assert netguard.guard_request_hook in hooks, "the guard is not a request hook"
    assert client.follow_redirects is True, (
        "if redirects are ever disabled, revisit this file — the guard's main "
        "reason to exist is the redirect hop"
    )
    await adapter.close()


async def test_normal_traffic_is_unaffected(httpx_mock, monkeypatch):
    monkeypatch.setattr(netguard, "_resolve", lambda _host: ["93.184.216.34"])
    httpx_mock.add_response(json={"success": True, "result": {"count": 0, "results": []}})
    out = await PanamaCkanAdapter().search_datasets(query="agua")
    assert out["total"] == 0


def test_the_guard_uses_httpx_url_parsing_not_a_regex():
    """Hand-rolled URL parsing is how these guards get bypassed.

    Tricks like an embedded credential (`http://public@127.0.0.1/`) fool a naive
    split on `@` or `/`; httpx.URL resolves the real host.
    """
    parsed = httpx.URL("http://evil.example@127.0.0.1/admin")
    assert parsed.host == "127.0.0.1"
