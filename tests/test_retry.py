"""The CKAN client retries what the network broke, briefly, and nothing else."""

from __future__ import annotations

import httpx
import pytest

from opendata_latam_mcp.adapters.ckan import PanamaCkanAdapter

URL = "https://www.datosabiertos.gob.pa/api/3/action/tag_list"
OK = {"success": True, "result": ["salud"]}


async def test_a_dropped_connection_is_retried(httpx_mock, sleeps):
    httpx_mock.add_exception(httpx.RemoteProtocolError("Server disconnected"), url=URL)
    httpx_mock.add_response(url=URL, json=OK)
    assert await PanamaCkanAdapter().list_tags() == ["salud"]
    assert len(sleeps) == 1


async def test_a_timeout_is_retried(httpx_mock, sleeps):
    httpx_mock.add_exception(httpx.ReadTimeout("slow"), url=URL)
    httpx_mock.add_response(url=URL, json=OK)
    assert await PanamaCkanAdapter().list_tags() == ["salud"]


@pytest.mark.parametrize("status", [429, 502, 503, 504])
async def test_transient_statuses_are_retried(status, httpx_mock, sleeps):
    httpx_mock.add_response(url=URL, status_code=status)
    httpx_mock.add_response(url=URL, json=OK)
    assert await PanamaCkanAdapter().list_tags() == ["salud"]


async def test_retry_after_is_honoured(httpx_mock, sleeps):
    httpx_mock.add_response(url=URL, status_code=429, headers={"Retry-After": "3"})
    httpx_mock.add_response(url=URL, json=OK)
    await PanamaCkanAdapter().list_tags()
    assert sleeps == [3.0]


async def test_retries_are_bounded(httpx_mock, sleeps):
    httpx_mock.add_response(url=URL, status_code=503, is_reusable=True)
    with pytest.raises(RuntimeError, match="HTTP 503"):
        await PanamaCkanAdapter().list_tags()
    assert len(httpx_mock.get_requests()) == 3
    assert len(sleeps) == 2


async def test_a_404_is_not_retried(httpx_mock, sleeps):
    httpx_mock.add_response(url=URL, status_code=404)
    with pytest.raises(RuntimeError, match="HTTP 404"):
        await PanamaCkanAdapter().list_tags()
    assert len(httpx_mock.get_requests()) == 1
    assert sleeps == []
