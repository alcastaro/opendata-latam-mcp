"""Shared pytest fixtures."""

from __future__ import annotations

import os

import pytest

from opendata_latam_mcp import netguard


def pytest_collection_modifyitems(config, items):
    """Auto-skip live network tests unless RUN_LIVE_TESTS=1."""
    if os.environ.get("RUN_LIVE_TESTS") == "1":
        return
    skipper = pytest.mark.skip(reason="set RUN_LIVE_TESTS=1 to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skipper)


@pytest.fixture(autouse=True)
def _no_dns_in_hermetic_tests(request, monkeypatch):
    """Hermetic means hermetic: no test may touch DNS.

    The SSRF guard runs as an httpx request hook, so it resolves the host of
    every request — including ones answered by a mock transport. Without this,
    the hermetic suite would silently depend on network and on a portal's DNS
    still existing, and would fail on a plane.

    The resolver is patched rather than the guard disabled, so the guard's own
    logic still runs on every mocked request: a test that accidentally builds a
    request to a private address still fails. Tests that exercise the guard's
    rejection path patch this again with their own addresses.
    """
    if "live" in request.keywords:
        return
    monkeypatch.setattr(netguard, "_resolve", lambda _host: ["93.184.216.34"])
