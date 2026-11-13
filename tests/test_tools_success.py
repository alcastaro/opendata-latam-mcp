"""One offline success-path test per tool, against a faked CKAN portal."""

from __future__ import annotations

import re

import httpx

from opendata_latam_mcp.server import mcp

PA = "https://www.datosabiertos.gob.pa/api/3/action"

DATASET = {
    "id": "d1",
    "name": "agua",
    "title": "Agua potable",
    "notes": "Cobertura",
    "organization": {"name": "idaan", "title": "IDAAN"},
    "tags": [{"name": "agua"}],
    "groups": [{"name": "ambiente", "title": "Ambiente"}],
    "resources": [{"id": "r1", "name": "datos.csv", "format": "CSV", "url": "http://x/datos.csv"}],
    "metadata_modified": "2026-01-01",
}
RESOURCE = DATASET["resources"][0]
ORG = {"id": "o1", "name": "idaan", "title": "IDAAN", "package_count": 4}
GROUP = {"id": "g1", "name": "ambiente", "title": "Ambiente", "package_count": 2}


def _tool(name: str):
    return mcp._tool_manager.get_tool(name).fn


def _portal(httpx_mock, action: str, result):
    httpx_mock.add_response(
        url=re.compile(rf"{re.escape(PA)}/{action}(\?.*)?$"),
        json={"success": True, "result": result},
        is_reusable=True,
    )


async def test_list_supported_countries():
    out = await _tool("list_supported_countries")()
    assert out["count"] == 7 and {c["country"] for c in out["countries"]} >= {"PA", "DO"}


async def test_search_datasets(httpx_mock):
    _portal(httpx_mock, "package_search", {"count": 1, "results": [DATASET]})
    out = await _tool("search_datasets")(country="PA", query="agua")
    assert (out["total"], out["returned"]) == (1, 1)
    assert out["datasets"][0]["title"] == "Agua potable"


async def test_get_dataset(httpx_mock):
    _portal(httpx_mock, "package_show", DATASET)
    out = await _tool("get_dataset")(country="PA", id="agua")
    assert out["title"] == "Agua potable"
    assert out["resources"][0]["format"] == "CSV"


async def test_list_recent_datasets(httpx_mock):
    _portal(httpx_mock, "package_search", {"count": 1, "results": [DATASET]})
    out = await _tool("list_recent_datasets")(country="PA", limit=5)
    assert out["returned"] == 1 and out["datasets"][0]["name"] == "agua"


async def test_get_resource(httpx_mock):
    _portal(httpx_mock, "resource_show", RESOURCE)
    out = await _tool("get_resource")(country="PA", id="r1")
    assert out["id"] == "r1" and out["url"] == "http://x/datos.csv"


async def test_search_resources(httpx_mock):
    _portal(httpx_mock, "resource_search", {"count": 1, "results": [RESOURCE]})
    out = await _tool("search_resources")(country="PA", query="datos")
    assert out["total"] == 1 and out["resources"][0]["name"] == "datos.csv"


async def test_get_organization(httpx_mock):
    _portal(httpx_mock, "organization_show", ORG)
    out = await _tool("get_organization")(country="PA", id="idaan")
    assert out["name"] == "idaan" and out["dataset_count"] == 4


async def test_list_groups(httpx_mock):
    _portal(httpx_mock, "group_list", [GROUP])
    out = await _tool("list_groups")(country="PA")
    assert (out["returned"], out["total"], out["complete"]) == (1, 1, True)
    assert out["groups"][0]["name"] == "ambiente"


async def test_list_tags(httpx_mock):
    _portal(httpx_mock, "tag_list", ["agua", "salud"])
    out = await _tool("list_tags")(country="PA")
    assert out["tags"] == ["agua", "salud"]


async def test_autocomplete(httpx_mock):
    _portal(httpx_mock, "tag_autocomplete", [{"name": "agua"}])
    out = await _tool("autocomplete")(country="PA", kind="tag", query="ag")
    assert out["kind"] == "tag" and out["returned"] == 1


async def test_get_site_stats(httpx_mock):
    def answer(request: httpx.Request) -> httpx.Response:
        action = request.url.path.rsplit("/", 1)[-1]
        result = {"package_search": {"count": 9}}.get(action, ["a", "b"])
        return httpx.Response(200, json={"success": True, "result": result})

    httpx_mock.add_callback(answer, is_reusable=True)
    out = await _tool("get_site_stats")(country="PA")
    assert out["total_datasets"] == 9 and out["total_tags"] == 2
    assert "partial" not in out


async def test_cross_country_stats(httpx_mock):
    httpx_mock.add_response(
        json={"success": True, "result": {"count": 3}}, is_reusable=True
    )
    out = await _tool("cross_country_stats")()
    assert set(out) == {"AR", "CL", "DO", "EC", "MX", "PA", "UY"}
    assert out["PA"]["total_datasets"] == 3
