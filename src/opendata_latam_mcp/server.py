"""opendata-latam-mcp — MCP server over Latin American open-data portals.

Every tool takes a `country` parameter (ISO 3166-1 alpha-2) so the model always
knows which portal it is hitting. `cross_country_search` fans out to every
selected portal in parallel — the one thing a single-country MCP cannot do.

**What this server does, and does not, do.** Fourteen of the fifteen tools are
CATALOGUE-level: they search datasets, return metadata, and list organizations,
groups and tags. The fifteenth, `read_resource_rows`, returns actual rows
through the CKAN DataStore where a portal has built one. There is still no file
download and no CSV/XLSX parsing here: reading files is what the dedicated
country packages do (`dominican-open-data-mcp`, `colombian-open-data-mcp`), and
it will arrive here through them rather than being reimplemented. Saying so in
the tool descriptions is deliberate: a server that claims a depth it does not
have costs the model a turn to discover.

`read_resource_rows` does not aggregate: the CKAN action that would run a GROUP
BY server-side answers on Uruguay alone out of the six portals measured, so
aggregation belongs in a local layer above these rows.

Portals, measured 2026-08-30 by exercising the registered tools:
AR 1,273 · CL 3,188 · DO 1,062 · MX 1,736 · PA 5,667 · UY 2,702 — 15,628 live.
EC is configured but has answered HTTP 403 to every request, from the site root
as well as the API, since 2026-08-30. Kept in the list rather than removed,
because a single vantage point is not enough to tell a portal that closed
programmatic access from one that blocks this address.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from . import __version__, adapters
from .countries import COUNTRIES, all_codes, normalize_country_code
from .errors import build_error, tool_envelope

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("opendata-latam-mcp")

# `version` is a real constructor argument in SDK v2. Under v1 it was not, so the
# low-level server fell back to the installed SDK's version and every client's
# `initialize` handshake reported the SDK version as ours. Passing it here is the
# fix, and it is invisible from inside the server — hence the test that asserts it.
mcp = MCPServer("opendata-latam-mcp", version=__version__)


def _ro(title: str) -> ToolAnnotations:
    """Annotations for a read-only tool that talks to a public portal.

    Every tool in this server reads; none writes anything anywhere. The Claude
    connectors directory requires a title and `readOnlyHint` on every tool, and
    the hint is what lets a client skip a confirmation prompt it does not need.
    """
    return ToolAnnotations(title=title, read_only_hint=True, open_world_hint=True)


# ─── Catalog / discovery ──────────────────────────────────────────────────────


@mcp.tool(annotations=_ro("Países soportados"))
@tool_envelope
async def list_supported_countries() -> dict[str, Any]:
    """Return the LatAm open-data portals this MCP currently supports.

    Each entry carries the ISO country code, portal name, URL, platform and a
    `status`. Call this before any other tool to learn which country codes are
    valid and which portals are currently answering — `status` is what tells
    you a country is configured but unreachable, so you can route around it
    instead of spending a turn discovering it.
    """
    portals = adapters.list_supported()
    return {
        "count": len(portals),
        "answering": sum(1 for p in portals if p.get("status") == "ok"),
        "countries": portals,
    }


# ─── Per-country tools ────────────────────────────────────────────────────────


def _country_arg_description() -> str:
    """Built from the registry so it cannot go stale.

    The hand-written version had to be edited by hand every time a country was
    added or a portal changed status, and its twin in the README omitted Panama
    for two weeks after Panama was added — the same lie-by-staleness this
    project measures other people's portals for. Every declared-unreachable
    portal is named with its note, so the model knows before its first call.
    """
    portals = adapters.list_supported()
    ok = [
        f"{p['country']} ({COUNTRIES[p['country']].name_en})"
        for p in portals
        if p["status"] == "ok"
    ]
    down = [
        f"{p['country']} ({COUNTRIES[p['country']].name_en}) is configured but "
        f"{p.get('status_note') or 'currently unreachable'}"
        for p in portals
        if p["status"] != "ok"
    ]
    text = "ISO 3166-1 alpha-2 country code. Supported: " + ", ".join(ok) + ". "
    if down:
        text += " ".join(down) + " "
    text += (
        "Every tool here reads CATALOGUE metadata — it finds datasets and describes "
        "them; only read_resource_rows returns rows. "
        "Use list_supported_countries to verify before passing other codes."
    )
    return text


CountryArg = Annotated[str, Field(description=_country_arg_description())]


@mcp.tool(annotations=_ro("Buscar datasets"))
@tool_envelope
async def search_datasets(
    country: CountryArg,
    query: Annotated[
        str | None,
        Field(
            description=(
                "Free-text search term. Omit to list all datasets sorted by "
                "relevance score."
            )
        ),
    ] = None,
    organization: Annotated[
        str | None,
        Field(description="Organization slug (use `autocomplete` to resolve names)."),
    ] = None,
    tag: Annotated[str | None, Field(description="Tag name.")] = None,
    group: Annotated[str | None, Field(description="Thematic group slug.")] = None,
    limit: Annotated[int, Field(description="Results (1-50)", ge=1, le=50)] = 10,
    offset: Annotated[int, Field(description="Offset for pagination.", ge=0)] = 0,
) -> dict[str, Any]:
    """Search datasets in a specific LatAm country's open-data portal.

    Returns summary metadata (title, organization, formats, URL) for matching
    datasets. Combinable filters; pagination via `offset`.
    """
    adapter = adapters.get_adapter(country)
    return await adapter.search_datasets(
        query=query,
        organization=organization,
        tag=tag,
        group=group,
        limit=limit,
        offset=offset,
    )


@mcp.tool(annotations=_ro("Metadatos de dataset"))
@tool_envelope
async def get_dataset(
    country: CountryArg,
    id: Annotated[str, Field(description="Dataset UUID or slug.")],
) -> dict[str, Any]:
    """Return full metadata for a dataset in a specific country's portal.

    Includes title, description, license, author, and full resource list with
    direct download URLs.
    """
    adapter = adapters.get_adapter(country)
    return await adapter.get_dataset(id)


@mcp.tool(annotations=_ro("Datasets recientes"))
@tool_envelope
async def list_recent_datasets(
    country: CountryArg,
    limit: Annotated[int, Field(description="Count (1-30)", ge=1, le=30)] = 10,
) -> dict[str, Any]:
    """Most recently modified datasets in a country's portal. Hydrated, not
    raw activity events."""
    adapter = adapters.get_adapter(country)
    return await adapter.list_recent_datasets(limit=limit)


@mcp.tool(annotations=_ro("Metadatos de recurso"))
@tool_envelope
async def get_resource(
    country: CountryArg,
    id: Annotated[str, Field(description="Resource UUID.")],
) -> dict[str, Any]:
    """Metadata for a single resource (file) — download URL, format, size, date."""
    adapter = adapters.get_adapter(country)
    return await adapter.get_resource(id)


@mcp.tool(annotations=_ro("Buscar recursos"))
@tool_envelope
async def search_resources(
    country: CountryArg,
    query: Annotated[str, Field(description="Resource name (full or partial).")],
    limit: Annotated[int, Field(description="Results (1-50)", ge=1, le=50)] = 10,
) -> dict[str, Any]:
    """Search resources (files) by name within a country's portal."""
    adapter = adapters.get_adapter(country)
    return await adapter.search_resources(query=query, limit=limit)


@mcp.tool(annotations=_ro("Entidades publicadoras"))
@tool_envelope
async def list_organizations(
    country: CountryArg,
    limit: Annotated[int, Field(description="Max (1-200)", ge=1, le=200)] = 50,
) -> dict[str, Any]:
    """Government institutions publishing data in a country's portal, with
    per-institution dataset counts."""
    adapter = adapters.get_adapter(country)
    orgs = await adapter.list_organizations(limit=limit)
    return {
        "country": adapter.COUNTRY_CODE,
        "portal": adapter.PORTAL_NAME,
        "returned": len(orgs),
        "organizations": orgs,
    }


@mcp.tool(annotations=_ro("Detalle de entidad"))
@tool_envelope
async def get_organization(
    country: CountryArg,
    id: Annotated[str, Field(description="Organization slug or UUID.")],
) -> dict[str, Any]:
    """Detailed info on a single publishing institution in a country."""
    adapter = adapters.get_adapter(country)
    return await adapter.get_organization(id)


@mcp.tool(annotations=_ro("Categorías temáticas"))
@tool_envelope
async def list_groups(country: CountryArg) -> dict[str, Any]:
    """Thematic categories (economy, health, education, etc.) in a country's portal."""
    adapter = adapters.get_adapter(country)
    groups = await adapter.list_groups()
    return {
        "country": adapter.COUNTRY_CODE,
        "portal": adapter.PORTAL_NAME,
        "returned": len(groups),
        "groups": groups,
    }


@mcp.tool(annotations=_ro("Etiquetas"))
@tool_envelope
async def list_tags(
    country: CountryArg,
    query: Annotated[str | None, Field(description="Optional prefix.")] = None,
    limit: Annotated[int, Field(description="Max (1-100)", ge=1, le=100)] = 20,
) -> dict[str, Any]:
    """List tags available in a country's portal, optionally prefix-filtered."""
    adapter = adapters.get_adapter(country)
    tags = await adapter.list_tags(query=query, limit=limit)
    return {
        "country": adapter.COUNTRY_CODE,
        "portal": adapter.PORTAL_NAME,
        "returned": len(tags),
        "tags": tags,
    }


@mcp.tool(annotations=_ro("Autocompletar"))
@tool_envelope
async def autocomplete(
    country: CountryArg,
    kind: Annotated[
        Literal["dataset", "organization", "group", "tag"],
        Field(description="What to complete: dataset, organization, group or tag."),
    ],
    query: Annotated[str, Field(description="Partial text to complete.")],
    limit: Annotated[int, Field(description="Suggestions (1-30)", ge=1, le=30)] = 10,
) -> dict[str, Any]:
    """Autocomplete dataset / organization / group / tag names within a country.

    `kind` is a closed set enforced by the schema, so an invalid value is
    rejected by the client before a request is ever made — cheaper than a
    round-trip that ends in an error.
    """
    adapter = adapters.get_adapter(country)
    suggestions = await adapter.autocomplete(kind=kind, query=query, limit=limit)
    return {
        "country": adapter.COUNTRY_CODE,
        "portal": adapter.PORTAL_NAME,
        "kind": kind,
        "returned": len(suggestions),
        "suggestions": suggestions,
    }


@mcp.tool(annotations=_ro("Estadísticas del portal"))
@tool_envelope
async def get_site_stats(country: CountryArg) -> dict[str, Any]:
    """Portal-wide stats for one country: datasets, organizations, groups, tags."""
    adapter = adapters.get_adapter(country)
    return await adapter.get_site_stats()


# ─── Reading rows ─────────────────────────────────────────────────────────────


@mcp.tool(annotations=_ro("Leer filas de un recurso"))
@tool_envelope
async def read_resource_rows(
    country: CountryArg,
    resource_id: Annotated[
        str,
        Field(
            description=(
                "Resource identifier (a CKAN UUID) from `search_resources` or "
                "`get_dataset`. This is an ID, never a URL."
            )
        ),
    ],
    limit: Annotated[int, Field(description="Rows to return (1-100).", ge=1, le=100)] = 20,
    offset: Annotated[int, Field(description="Row offset for pagination.", ge=0)] = 0,
    q: Annotated[
        str | None,
        Field(description="Free-text filter applied across the resource's columns."),
    ] = None,
) -> dict[str, Any]:
    """Read the actual rows of one resource, through the portal's CKAN DataStore.

    This is the only tool here that returns data rather than metadata, and it
    works only where the portal has built a DataStore table for that resource.
    Many resources are published as a plain file instead; for those this returns
    an error saying so, with what to try next.

    It does not aggregate. `datastore_search_sql` — the CKAN action that would
    run a GROUP BY on the portal — answers on Uruguay alone out of the six
    national portals measured on 2026-08-30, so minimum, maximum, average and
    GROUP BY have to be computed locally rather than pushed to the portal.
    """
    adapter = adapters.get_adapter(country)
    return await adapter.read_resource_rows(
        resource_id, limit=limit, offset=offset, q=q
    )


# ─── Cross-country (the unique value-add of this MCP) ─────────────────────────


@mcp.tool(annotations=_ro("Búsqueda multi-país"))
@tool_envelope
async def cross_country_search(
    query: Annotated[
        str,
        Field(description="Free-text search term applied to every selected country."),
    ],
    countries: Annotated[
        list[str] | None,
        Field(
            description=(
                "List of ISO alpha-2 codes to search. Defaults to ALL supported "
                "countries when None. Example: ['DO','CL','MX']."
            )
        ),
    ] = None,
    limit_per_country: Annotated[
        int,
        Field(description="Max results per portal (1-20)", ge=1, le=20),
    ] = 5,
) -> dict[str, Any]:
    """Search the same term across every LatAm portal in parallel. THE unique
    feature of this MCP — impossible with single-country MCPs.

    Returns a dict keyed by country code with each portal's matches and a
    rolled-up `summary` showing total hits per country.
    """
    # Normalize and de-duplicate at the entry, not per country. Measured
    # 2026-09-12 with ["mx", "MX"]: Mexico was queried twice, the results came
    # back under two keys, and the summary named the lowercase one "mx" because
    # the COUNTRIES lookup below is case-sensitive. An unknown code is not a
    # reason to fail the whole fan-out: it gets its own error entry, the same
    # way a dead portal does.
    target_codes: list[str] = []
    rejected: dict[str, dict] = {}
    for raw in all_codes() if countries is None else countries:
        try:
            code = normalize_country_code(raw)
        except ValueError as e:
            rejected[str(raw)] = build_error(e, tool="cross_country_search", country=str(raw))
            continue
        if code not in target_codes:
            target_codes.append(code)

    async def _one(code: str):
        try:
            adapter = adapters.get_adapter(code)
            r = await adapter.search_datasets(query=query, limit=limit_per_country)
            return code, r
        except Exception as e:  # noqa: BLE001 — one dead portal must not sink the fan-out
            # Same taxonomy as the per-country tools. Without this the fan-out
            # would report a bare str(e) with no hint, so the identical failure
            # would be actionable through search_datasets and opaque here.
            return code, build_error(e, tool="cross_country_search", country=code)

    results = await asyncio.gather(*[_one(c) for c in target_codes])

    by_country: dict[str, dict] = dict(results)
    by_country.update(rejected)
    summary = {
        code: {
            "country_name": COUNTRIES[code].name_es if code in COUNTRIES else code,
            "total_hits": data.get("total", 0) if "error" not in data else None,
            "returned": data.get("returned", 0) if "error" not in data else 0,
            "portal_error": data.get("error"),
        }
        for code, data in by_country.items()
    }
    grand_total = sum(
        s["total_hits"] or 0 for s in summary.values() if s["total_hits"] is not None
    )

    return {
        "query": query,
        "countries_queried": target_codes,
        "grand_total_hits": grand_total,
        "summary": summary,
        "by_country": by_country,
    }


@mcp.tool(annotations=_ro("Estadísticas multi-país"))
@tool_envelope
async def cross_country_stats() -> dict[str, Any]:
    """Run get_site_stats against every supported country in parallel. Quick
    health check + comparative portal sizes."""

    async def _one(code: str):
        try:
            adapter = adapters.get_adapter(code)
            r = await adapter.get_site_stats()
            return code, r
        except Exception as e:  # noqa: BLE001 — one dead portal must not sink the fan-out
            return code, build_error(e, tool="cross_country_stats", country=code)

    results = await asyncio.gather(*[_one(c) for c in all_codes()])
    return dict(results)


# ─── Entry point ──────────────────────────────────────────────────────────────


def _tool_count() -> int | None:
    """Best-effort, for the startup log only.

    Reaches into a private attribute, so it must never be the reason a server
    fails to start: if a future SDK renames it, the log line goes quiet and
    everything else keeps working.
    """
    try:
        return len(mcp._tool_manager._tools)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 — a log line is not worth failing startup
        return None


def main() -> None:
    logger.info("opendata-latam-mcp starting (supported countries: %s)", all_codes())
    count = _tool_count()
    if count is not None:
        logger.info("Registered %d tools", count)
    try:
        mcp.run()
    except Exception:
        logger.exception("Fatal error in MCP server")
        raise
    finally:
        try:
            asyncio.run(adapters.registry.close_all())
        except RuntimeError:
            pass
        logger.info("opendata-latam-mcp shut down")


if __name__ == "__main__":
    main()
