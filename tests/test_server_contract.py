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
