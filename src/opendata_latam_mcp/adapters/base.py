"""PortalAdapter abstract base — every country implements this surface.

The MCP tools (search_datasets, get_dataset, list_organizations, etc.)
dispatch on country code via the registry and call adapter methods. New
portals just implement a subclass and register themselves.

Three implementation paths:
1. CKAN family — subclass CkanAdapter, set BASE_URL only.
2. Socrata family — implement SocrataAdapter.
3. Custom family — implement from scratch.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class PortalAdapter(Protocol):
    """Surface every adapter must expose. Country-specific implementations
    fulfil these contracts using whatever native API the portal offers."""

    COUNTRY_CODE: str          # ISO 3166-1 alpha-2
    PORTAL_NAME: str           # Human-readable portal title
    PORTAL_URL: str            # Base URL of the portal (no trailing /api)
    PLATFORM: str              # "ckan", "socrata", "custom"

    async def search_datasets(
        self,
        query: str | None = None,
        organization: str | None = None,
        tag: str | None = None,
        group: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> dict[str, Any]: ...

    async def get_dataset(self, id: str) -> dict[str, Any]: ...

    async def list_recent_datasets(self, limit: int = 10) -> dict[str, Any]: ...

    async def get_resource(self, id: str) -> dict[str, Any]: ...

    async def search_resources(self, query: str, limit: int = 10) -> dict[str, Any]: ...

    async def list_organizations(self, limit: int = 50) -> list[dict[str, Any]]: ...

    async def get_organization(self, id: str) -> dict[str, Any]: ...

    async def list_groups(self) -> list[dict[str, Any]]: ...

    async def list_tags(self, query: str | None = None, limit: int = 20) -> list[str]: ...

    async def autocomplete(
        self, kind: str, query: str, limit: int = 10
    ) -> list[Any]: ...

    async def get_site_stats(self) -> dict[str, Any]: ...

    async def close(self) -> None: ...
