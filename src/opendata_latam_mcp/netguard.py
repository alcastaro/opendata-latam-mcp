"""SSRF guard — every hop of every outbound request must be publicly routable.

**This is an interim module and is meant to be deleted.** The sibling packages
already have a measured `netguard` (48 tests in the Colombian one), and the
project's standing decision is to IMPORT that rather than keep a third copy: the
two existing copies already drifted apart, which is the whole argument. This
file exists only because importing it today would mean adding a path dependency
on a package that is not on PyPI yet, and a path dependency cannot ship. When
the shared module lands, delete this and switch the import — do not let a third
copy grow features.

**What it defends.** SSRF (*Server-Side Request Forgery*) is making the server
issue a request to an address the caller could not reach directly — the loopback
interface, the private network, or a cloud metadata endpoint holding
credentials. This server already has the strong half of that defence: **no tool
accepts a URL**, so every address is built from a portal's own configured base.
What that does NOT cover is redirects. `follow_redirects=True` means a portal
answering `302 Location: http://169.254.169.254/latest/meta-data/` gets followed,
and the destination was never validated by anything.

That needs a compromised or misbehaving *government portal* to trigger, so it is
not an open door. But the reachable set grows with every country added, each one
a third party whose redirects we follow, and the fix costs twenty lines.

**Why a request hook and not a check before the first call.** A one-shot check
validates the address we chose and nothing else. Installed as an httpx request
event hook, this runs on **every hop**, which is exactly what makes the redirect
case fail closed.

**Known limit, stated rather than hidden:** a DNS rebinding window remains
between our resolution here and httpx's own. Same limit the sibling modules
document; closing it needs a pinned-address transport.
"""

from __future__ import annotations

import ipaddress
import socket

import httpx


class NetGuardError(Exception):
    """Raised when a request targets an address that is not publicly routable."""


def _resolve(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise NetGuardError(f"cannot resolve host {host!r}: {e}") from e
    return sorted({info[4][0] for info in infos})


def check_address(addr: str, *, host: str = "") -> None:
    """Reject anything `ipaddress` does not consider globally routable.

    `is_global` is the single control, deliberately: it already covers loopback,
    RFC-1918 private ranges, link-local — which is where the cloud metadata
    address 169.254.169.254 lives — CGNAT, and IPv6 unique-local. Enumerating
    those by hand is how a range gets missed.
    """
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError as e:
        raise NetGuardError(f"unparseable address {addr!r} for host {host!r}") from e
    if not ip.is_global:
        raise NetGuardError(
            f"refusing request to non-public address {addr} "
            f"(host {host!r}): loopback, private, link-local, CGNAT and IPv6 "
            f"unique-local destinations are never valid for a public data portal"
        )


def assert_public_url(url: str | httpx.URL) -> None:
    """Validate every address a URL's host resolves to."""
    parsed = httpx.URL(str(url))
    host = parsed.host
    if not host:
        raise NetGuardError(f"no host in URL {url!r}")
    if parsed.scheme not in ("http", "https"):
        raise NetGuardError(f"refusing non-HTTP scheme {parsed.scheme!r} in {url!r}")
    for addr in _resolve(host):
        check_address(addr, host=host)


async def guard_request_hook(request: httpx.Request) -> None:
    """httpx request event hook — runs on the initial call AND every redirect."""
    assert_public_url(request.url)
