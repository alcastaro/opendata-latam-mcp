"""list_organizations and list_groups must page past CKAN's 25-item ceiling."""

from __future__ import annotations

import re

import httpx

from opendata_latam_mcp import server
from opendata_latam_mcp.adapters.ckan import PanamaCkanAdapter

API = "https://www.datosabiertos.gob.pa/api/3/action"
TOTAL = 60


def _portal(httpx_mock, action: str, prefix: str):
    """Fake a CKAN that answers at most 25 full records per call, silently."""
    names = [f"{prefix}{i:03d}" for i in range(TOTAL)]

    def answer(request: httpx.Request) -> httpx.Response:
        q = request.url.params
        if q.get("all_fields"):
            off = int(q.get("offset", 0))
            lim = min(int(q.get("limit", 25)), 25)
            result = [{"name": n, "title": n, "package_count": 1} for n in names[off : off + lim]]
        else:
            result = names
        return httpx.Response(200, json={"success": True, "result": result})

    httpx_mock.add_callback(answer, url=re.compile(rf"{re.escape(API)}/{action}(\?.*)?$"), is_reusable=True)


async def test_list_organizations_pages_past_the_ckan_ceiling(httpx_mock):
    _portal(httpx_mock, "organization_list", "org")
    orgs = await PanamaCkanAdapter().list_organizations(limit=50)
    assert len(orgs) == 50


async def test_list_groups_returns_every_group(httpx_mock):
    _portal(httpx_mock, "group_list", "grp")
    groups = await PanamaCkanAdapter().list_groups()
    assert len(groups) == TOTAL


async def test_organizations_reply_states_total_and_completeness(httpx_mock):
    _portal(httpx_mock, "organization_list", "org")
    part = await server.list_organizations("PA", limit=50)
    assert (part["returned"], part["total"], part["complete"]) == (50, TOTAL, False)
    full = await server.list_organizations("PA", limit=200)
    assert (full["returned"], full["total"], full["complete"]) == (TOTAL, TOTAL, True)
