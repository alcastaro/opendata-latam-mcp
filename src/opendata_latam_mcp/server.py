"""opendata-latam-mcp — FastMCP server.

Unifies LatAm gov open-data portals under one MCP. Every tool takes a
`country` parameter (ISO alpha-2 code) so the model knows which portal it
hits. cross_country_search fans out to every supported portal in parallel.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from . import adapters
from .countries import COUNTRIES, all_codes

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("opendata-latam-mcp")

mcp = FastMCP("opendata-latam-mcp")


# ─── Catalog / discovery ──────────────────────────────────────────────────────


@mcp.tool()
def list_supported_countries() -> list[dict]:
    """Return the list of LatAm open-data portals this MCP currently supports.

    Each entry includes ISO country code, portal name, URL, and platform
    (ckan, socrata, custom). Use this before any other tool to know which
    country codes are valid.
    """
    return adapters.list_supported()


# ─── Per-country tools ────────────────────────────────────────────────────────


CountryArg = Annotated[
    str,
    Field(
        description=(
            "ISO 3166-1 alpha-2 country code. Supported: "
            "AR (Argentina), CL (Chile), DO (Dominican Republic), "
            "EC (Ecuador), MX (Mexico), UY (Uruguay). "
            "Use list_supported_countries to verify before passing other codes."
        )
    ),
]


@mcp.tool()
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
) -> dict:
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


@mcp.tool()
async def get_dataset(
    country: CountryArg,
    id: Annotated[str, Field(description="Dataset UUID or slug.")],
) -> dict:
    """Return full metadata for a dataset in a specific country's portal.

    Includes title, description, license, author, and full resource list with
    direct download URLs.
    """
    adapter = adapters.get_adapter(country)
    return await adapter.get_dataset(id)


@mcp.tool()
async def list_recent_datasets(
    country: CountryArg,
    limit: Annotated[int, Field(description="Count (1-30)", ge=1, le=30)] = 10,
) -> dict:
    """Most recently modified datasets in a country's portal. Hydrated, not
    raw activity events."""
    adapter = adapters.get_adapter(country)
    return await adapter.list_recent_datasets(limit=limit)


@mcp.tool()
async def get_resource(
    country: CountryArg,
    id: Annotated[str, Field(description="Resource UUID.")],
) -> dict:
    """Metadata for a single resource (file) — download URL, format, size, date."""
    adapter = adapters.get_adapter(country)
    return await adapter.get_resource(id)


@mcp.tool()
async def search_resources(
    country: CountryArg,
    query: Annotated[str, Field(description="Resource name (full or partial).")],
    limit: Annotated[int, Field(description="Results (1-50)", ge=1, le=50)] = 10,
) -> dict:
    """Search resources (files) by name within a country's portal."""
    adapter = adapters.get_adapter(country)
    return await adapter.search_resources(query=query, limit=limit)


@mcp.tool()
async def list_organizations(
    country: CountryArg,
    limit: Annotated[int, Field(description="Max (1-200)", ge=1, le=200)] = 50,
) -> list[dict]:
    """Government institutions publishing data in a country's portal, with
    per-institution dataset counts."""
    adapter = adapters.get_adapter(country)
    return await adapter.list_organizations(limit=limit)


@mcp.tool()
async def get_organization(
    country: CountryArg,
    id: Annotated[str, Field(description="Organization slug or UUID.")],
) -> dict:
    """Detailed info on a single publishing institution in a country."""
    adapter = adapters.get_adapter(country)
    return await adapter.get_organization(id)


@mcp.tool()
async def list_groups(country: CountryArg) -> list[dict]:
    """Thematic categories (economy, health, education, etc.) in a country's portal."""
    adapter = adapters.get_adapter(country)
    return await adapter.list_groups()


@mcp.tool()
async def list_tags(
    country: CountryArg,
    query: Annotated[str | None, Field(description="Optional prefix.")] = None,
    limit: Annotated[int, Field(description="Max (1-100)", ge=1, le=100)] = 20,
) -> list[str]:
    """List tags available in a country's portal, optionally prefix-filtered."""
    adapter = adapters.get_adapter(country)
    return await adapter.list_tags(query=query, limit=limit)


@mcp.tool()
async def autocomplete(
    country: CountryArg,
    kind: Annotated[
        str,
        Field(description="One of: dataset, organization, group, tag."),
    ],
    query: Annotated[str, Field(description="Partial text to complete.")],
    limit: Annotated[int, Field(description="Suggestions (1-30)", ge=1, le=30)] = 10,
) -> list:
    """Autocomplete dataset / organization / group / tag names within a country."""
    adapter = adapters.get_adapter(country)
    return await adapter.autocomplete(kind=kind, query=query, limit=limit)


@mcp.tool()
async def get_site_stats(country: CountryArg) -> dict:
    """Portal-wide stats for one country: datasets, organizations, groups, tags."""
    adapter = adapters.get_adapter(country)
    return await adapter.get_site_stats()


# ─── Cross-country (the unique value-add of this MCP) ─────────────────────────


@mcp.tool()
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
) -> dict:
    """Search the same term across every LatAm portal in parallel. THE unique
    feature of this MCP — impossible with single-country MCPs.

    Returns a dict keyed by country code with each portal's matches and a
    rolled-up `summary` showing total hits per country.
    """
    if countries is None:
        target_codes = all_codes()
    else:
        target_codes = countries

    async def _one(code: str):
        try:
            adapter = adapters.get_adapter(code)
            r = await adapter.search_datasets(query=query, limit=limit_per_country)
            return code, r
        except Exception as e:
            return code, {"error": str(e), "country": code}

    results = await asyncio.gather(*[_one(c) for c in target_codes])

    by_country: dict[str, dict] = {code: data for code, data in results}
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


@mcp.tool()
async def cross_country_stats() -> dict:
    """Run get_site_stats against every supported country in parallel. Quick
    health check + comparative portal sizes."""

    async def _one(code: str):
        try:
            adapter = adapters.get_adapter(code)
            r = await adapter.get_site_stats()
            return code, r
        except Exception as e:
            return code, {"error": str(e), "country": code}

    results = await asyncio.gather(*[_one(c) for c in all_codes()])
    return {code: data for code, data in results}


# ─── Entry point ──────────────────────────────────────────────────────────────


def _tool_count() -> int | None:
    try:
        return len(mcp._tool_manager._tools)  # type: ignore[attr-defined]
    except Exception:
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
