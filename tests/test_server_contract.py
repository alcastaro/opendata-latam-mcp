"""Contract the server owes its clients, and the directory review.

These assertions all cover things that are invisible from inside a running
server: a wrong version in the `initialize` handshake, a tool missing the
annotations a connector directory requires, a tool name too long for a client
to accept. Every one of them was a real defect in a sibling project, found by
a client or a reviewer rather than by the code.
"""

from __future__ import annotations

import asyncio

import pytest

from opendata_latam_mcp import __version__
from opendata_latam_mcp.server import mcp

# The Claude connectors directory caps tool names here.
MAX_TOOL_NAME = 64


@pytest.fixture(scope="module")
def tools():
    return asyncio.run(mcp.list_tools())


def test_handshake_reports_this_package_version():
    """The `initialize` handshake must report our version, not the SDK's.

    Under SDK v1 `FastMCP` took no `version` argument, so the low-level server
    fell back to the installed SDK's version and every client saw "1.27.1" as
    this server's version. Nothing inside the server could tell. In v2 `version`
    is a real constructor argument; this test is what keeps it passed.
    """
    opts = mcp._lowlevel_server.create_initialization_options()
    assert opts.server_version == __version__


def test_every_tool_is_annotated_read_only(tools):
    """Title plus `readOnlyHint` on every tool.

    The directory requires both. The hint is also what lets a client skip a
    confirmation prompt it does not need — this server never writes anything.
    """
    assert tools, "server registered no tools"
    for tool in tools:
        assert tool.annotations is not None, f"{tool.name}: no annotations"
        assert tool.annotations.title, f"{tool.name}: no title"
        assert tool.annotations.read_only_hint is True, f"{tool.name}: not read-only"


def test_annotations_serialize_as_camel_case(tools):
    """Python is snake_case, the wire is camelCase.

    SDK v2 renamed the annotation fields in Python (`read_only_hint`) while
    pydantic keeps serializing the camelCase the protocol specifies. A client
    reads `readOnlyHint`, so that is what has to come out.
    """
    wire = tools[0].annotations.model_dump(by_alias=True, exclude_none=True)
    assert wire["readOnlyHint"] is True
    assert "title" in wire


def test_every_tool_has_a_description(tools):
    """A tool with no description is a tool the model has to guess about."""
    for tool in tools:
        assert tool.description, f"{tool.name}: no description"


def test_tool_names_fit_the_directory_limit(tools):
    for tool in tools:
        assert len(tool.name) <= MAX_TOOL_NAME, f"{tool.name}: {len(tool.name)} chars"


def test_no_write_tools_are_registered(tools):
    """This server reads public catalogues. Nothing here writes anywhere."""
    writes = [t for t in tools if t.annotations and t.annotations.read_only_hint is not True]
    assert writes == []


def test_every_tool_advertises_an_object_output_schema(tools):
    """Bare `-> dict` produces NO output schema in SDK v2, and therefore no
    `structuredContent` on the wire — measured 2026-09-12 through a real client
    session: fifteen tools, fifteen `None`s. `dict[str, Any]` produces an object
    schema, and with it structured output. The existing test that no tool
    advertises an ARRAY schema passed vacuously the whole time."""
    for tool in tools:
        assert tool.output_schema, f"{tool.name}: no output schema"
        assert tool.output_schema.get("type") == "object", f"{tool.name}: not an object"


def test_server_json_agrees_with_the_package():
    """Three files carry the version: pyproject, __init__ and server.json. The
    first two are checked by the build; this one was not, and the registry also
    caps `description` at 100 characters — `mcp-publisher validate` returned 422
    on 2026-09-12 for a 158-character one that a checklist had called valid."""
    import json
    from pathlib import Path

    spec = json.loads((Path(__file__).parent.parent / "server.json").read_text("utf-8"))
    assert spec["version"] == __version__
    assert all(p["version"] == __version__ for p in spec["packages"])
    assert len(spec["description"]) <= 100, len(spec["description"])
    assert spec["name"] == "io.github.alcastaro/opendata-latam-mcp"


async def test_over_the_wire_an_envelope_is_a_result_not_a_protocol_error():
    """A real client session, in memory. What the model receives for a bad
    country is an ordinary result with structured content — not `isError`, not
    'Error executing tool'. The unit tests call the function; this is the one
    place the whole SDK path is exercised."""
    import anyio
    from mcp.client.session import ClientSession
    from mcp.shared.memory import create_client_server_memory_streams

    server = mcp._lowlevel_server
    async with create_client_server_memory_streams() as (client_streams, server_streams):
        client_read, client_write = client_streams
        server_read, server_write = server_streams
        async with anyio.create_task_group() as tg:
            tg.start_soon(
                server.run, server_read, server_write, server.create_initialization_options()
            )
            async with ClientSession(client_read, client_write) as session:
                init = await session.initialize()
                assert init.server_info.version == __version__
                listed = await session.list_tools()
                assert len(listed.tools) == 15
                r = await session.call_tool("search_datasets", {"country": "XX", "query": "agua"})
                assert r.is_error is False
                assert r.structured_content is not None
                assert r.structured_content["error"].startswith("Unknown country")
                assert "list_supported_countries" in r.structured_content["hint"]
            await client_write.aclose()
            await server_write.aclose()
            tg.cancel_scope.cancel()
