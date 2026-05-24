"""Generic CKAN adapter — covers every CKAN portal that follows the standard
API at /api/3/action/*.

Country-specific subclasses override:
    - COUNTRY_CODE (ISO alpha-2)
    - PORTAL_NAME (human title)
    - BASE_URL (everything before /api/3/action)

This adapter is platform-aware but country-agnostic. Each instance is bound
to a single portal via constructor; reuse the httpx client per instance.
"""

from __future__ import annotations

import re
from typing import Any, ClassVar

import httpx

USER_AGENT = "opendata-latam-mcp/0.1 (MCP Server; +https://github.com/alcastaro/opendata-latam-mcp)"
DEFAULT_TIMEOUT = 15.0

# Output trimming so a single call never blows the LLM's context window.
NOTES_TRUNC = 300
DESC_TRUNC = 300


class CkanAdapter:
    """Generic CKAN client. Subclass per country."""

    COUNTRY_CODE: ClassVar[str] = ""
    PORTAL_NAME: ClassVar[str] = ""
    PORTAL_URL: ClassVar[str] = ""
    PLATFORM: ClassVar[str] = "ckan"

    # Subclasses override at minimum BASE_URL.
    BASE_URL: ClassVar[str] = ""  # e.g. "https://datos.gob.do/api/3/action"

    # Operational caps. Override per portal if a national portal has limits.
    MAX_ROWS_PER_PAGE: ClassVar[int] = 50
    MAX_RECENT: ClassVar[int] = 30
    MAX_AUTOCOMPLETE: ClassVar[int] = 30
    MAX_ORGS: ClassVar[int] = 200

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    # ─── HTTP layer ──────────────────────────────────────────────────────

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers={"User-Agent": USER_AGENT},
                timeout=DEFAULT_TIMEOUT,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    @staticmethod
    def _clean(params: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in params.items() if v is not None}

    async def _ckan(self, action: str, params: dict[str, Any] | None = None) -> Any:
        client = await self._get_client()
        try:
            r = await client.get(f"/{action}", params=self._clean(params or {}))
        except httpx.TimeoutException as e:
            raise RuntimeError(
                f"[{self.COUNTRY_CODE}] timeout in {action} (>{DEFAULT_TIMEOUT}s)"
            ) from e
        except httpx.HTTPError as e:
            raise RuntimeError(
                f"[{self.COUNTRY_CODE}] network error in {action}: {e}"
            ) from e
        if r.status_code >= 400:
            raise RuntimeError(
                f"[{self.COUNTRY_CODE}] {self.PORTAL_NAME} {action} "
                f"HTTP {r.status_code} {r.reason_phrase}"
            )
        data = r.json()
        if not data.get("success"):
            err = data.get("error", {})
            msg = err.get("message") if isinstance(err, dict) else str(err)
            raise RuntimeError(
                f"[{self.COUNTRY_CODE}] CKAN error in {action}: {msg}"
            )
        return data["result"]

    # ─── Solr escaping (shared) ──────────────────────────────────────────

    _SOLR_SPECIAL = re.compile(r'([+\-&|!(){}\[\]^"~*?:\\/])')

    @classmethod
    def _escape_solr(cls, value: str) -> str:
        return cls._SOLR_SPECIAL.sub(r"\\\1", value)

    @classmethod
    def _fq_term(cls, field: str, value: str) -> str:
        escaped = cls._escape_solr(value)
        if " " in value or '"' in value:
            return f'{field}:"{escaped}"'
        return f"{field}:{escaped}"

    # ─── Formatters ──────────────────────────────────────────────────────

    @staticmethod
    def _truncate(s: str | None, n: int) -> str | None:
        if s is None:
            return None
        s = s.strip()
        return s if len(s) <= n else s[:n].rstrip() + "…"

    def _portal_dataset_url(self, name: str | None) -> str | None:
        if not name or not self.PORTAL_URL:
            return None
        return f"{self.PORTAL_URL.rstrip('/')}/dataset/{name}"

    def _portal_org_url(self, name: str | None) -> str | None:
        if not name or not self.PORTAL_URL:
            return None
        return f"{self.PORTAL_URL.rstrip('/')}/organization/{name}"

    def format_resource(self, r: dict) -> dict:
        return {
            "id": r.get("id"),
            "name": r.get("name"),
            "description": self._truncate(r.get("description"), DESC_TRUNC),
            "format": r.get("format"),
            "url": r.get("url"),
            "size": r.get("size"),
            "mimetype": r.get("mimetype") or r.get("mimetype_inner"),
            "created": r.get("created"),
            "last_modified": r.get("last_modified") or r.get("metadata_modified"),
        }

    def format_dataset(self, d: dict) -> dict:
        org = d.get("organization") or {}
        resources = d.get("resources") or []
        return {
            "country": self.COUNTRY_CODE,
            "id": d.get("id"),
            "name": d.get("name"),
            "title": d.get("title"),
            "organization": org.get("title") or org.get("name"),
            "organization_slug": org.get("name"),
            "notes": self._truncate(d.get("notes"), NOTES_TRUNC),
            "tags": [t.get("name") for t in (d.get("tags") or []) if t.get("name")],
            "groups": [
                g.get("title") or g.get("name") for g in (d.get("groups") or [])
            ],
            "resource_count": len(resources),
            "formats": sorted({r.get("format") for r in resources if r.get("format")}),
            "last_modified": d.get("metadata_modified"),
            "license": d.get("license_title") or d.get("license_id"),
            "url": self._portal_dataset_url(d.get("name")),
        }

    def format_dataset_full(self, d: dict) -> dict:
        base = self.format_dataset(d)
        base["resources"] = [self.format_resource(r) for r in (d.get("resources") or [])]
        base["author"] = d.get("author")
        base["maintainer"] = d.get("maintainer")
        extras = d.get("extras") or []
        if extras:
            base["extras"] = [{"key": e.get("key"), "value": e.get("value")} for e in extras]
        return base

    def format_organization(self, o: dict, *, short: bool = False) -> dict:
        out = {
            "country": self.COUNTRY_CODE,
            "id": o.get("id"),
            "name": o.get("name"),
            "title": o.get("title") or o.get("display_name") or o.get("name"),
            "dataset_count": o.get("package_count"),
            "url": self._portal_org_url(o.get("name")),
        }
        if not short:
            out["description"] = self._truncate(o.get("description"), DESC_TRUNC)
        return out

    def format_group(self, g: dict) -> dict:
        return {
            "country": self.COUNTRY_CODE,
            "id": g.get("id"),
            "name": g.get("name"),
            "title": g.get("title") or g.get("display_name") or g.get("name"),
            "description": self._truncate(g.get("description"), DESC_TRUNC),
            "dataset_count": g.get("package_count"),
        }

    # ─── Public CKAN operations ──────────────────────────────────────────

    async def search_datasets(
        self,
        query: str | None = None,
        organization: str | None = None,
        tag: str | None = None,
        group: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> dict[str, Any]:
        fq_parts: list[str] = []
        if organization:
            fq_parts.append(self._fq_term("organization", organization))
        if tag:
            fq_parts.append(self._fq_term("tags", tag))
        if group:
            fq_parts.append(self._fq_term("groups", group))

        params: dict[str, Any] = {
            "q": query or "*:*",
            "rows": min(max(int(limit), 1), self.MAX_ROWS_PER_PAGE),
            "start": max(int(offset), 0),
        }
        if fq_parts:
            params["fq"] = " AND ".join(fq_parts)

        result = await self._ckan("package_search", params)
        return {
            "country": self.COUNTRY_CODE,
            "portal": self.PORTAL_NAME,
            "total": result.get("count", 0),
            "returned": len(result.get("results", [])),
            "offset": params["start"],
            "datasets": [self.format_dataset(d) for d in result.get("results", [])],
        }

    async def get_dataset(self, id: str) -> dict[str, Any]:
        result = await self._ckan("package_show", {"id": id})
        return self.format_dataset_full(result)

    async def list_recent_datasets(self, limit: int = 10) -> dict[str, Any]:
        params = {
            "q": "*:*",
            "rows": min(max(int(limit), 1), self.MAX_RECENT),
            "sort": "metadata_modified desc",
        }
        result = await self._ckan("package_search", params)
        return {
            "country": self.COUNTRY_CODE,
            "portal": self.PORTAL_NAME,
            "total": result.get("count", 0),
            "returned": len(result.get("results", [])),
            "datasets": [self.format_dataset(d) for d in result.get("results", [])],
        }

    async def get_resource(self, id: str) -> dict[str, Any]:
        result = await self._ckan("resource_show", {"id": id})
        return self.format_resource(result)

    async def search_resources(self, query: str, limit: int = 10) -> dict[str, Any]:
        result = await self._ckan(
            "resource_search",
            {
                "query": f"name:{query}",
                "limit": min(max(int(limit), 1), self.MAX_ROWS_PER_PAGE),
            },
        )
        return {
            "country": self.COUNTRY_CODE,
            "portal": self.PORTAL_NAME,
            "total": result.get("count", 0),
            "resources": [self.format_resource(r) for r in (result.get("results") or [])],
        }

    async def list_organizations(self, limit: int = 50) -> list[dict[str, Any]]:
        result = await self._ckan(
            "organization_list",
            {"all_fields": True, "include_dataset_count": True, "include_extras": False},
        )
        if not isinstance(result, list):
            return []
        orgs = [self.format_organization(o, short=True) for o in result]
        return orgs[: min(max(int(limit), 1), self.MAX_ORGS)]

    async def get_organization(self, id: str) -> dict[str, Any]:
        result = await self._ckan(
            "organization_show",
            {
                "id": id,
                "include_datasets": False,
                "include_dataset_count": True,
                "include_extras": True,
            },
        )
        out = self.format_organization(result)
        extras = result.get("extras") or []
        if extras:
            out["extras"] = [{"key": e.get("key"), "value": e.get("value")} for e in extras]
        return out

    async def list_groups(self) -> list[dict[str, Any]]:
        result = await self._ckan(
            "group_list",
            {"all_fields": True, "include_dataset_count": True, "include_extras": False},
        )
        if not isinstance(result, list):
            return []
        return [self.format_group(g) for g in result]

    async def list_tags(self, query: str | None = None, limit: int = 20) -> list[str]:
        params: dict[str, Any] = {}
        if query:
            params["query"] = query
        result = await self._ckan("tag_list", params)
        if not isinstance(result, list):
            return []
        tags = [
            t if isinstance(t, str) else (t.get("name") or t.get("display_name"))
            for t in result
        ]
        tags = [t for t in tags if t]
        return tags[: max(int(limit), 1)]

    async def autocomplete(
        self, kind: str, query: str, limit: int = 10
    ) -> list[Any]:
        action_map = {
            "dataset": "package_autocomplete",
            "organization": "organization_autocomplete",
            "group": "group_autocomplete",
            "tag": "tag_autocomplete",
        }
        if kind not in action_map:
            raise ValueError(f"kind must be one of: {list(action_map)}")
        params = {
            "q": query,
            "limit": min(max(int(limit), 1), self.MAX_AUTOCOMPLETE),
        }
        result = await self._ckan(action_map[kind], params)
        return result if isinstance(result, list) else []

    async def get_site_stats(self) -> dict[str, Any]:
        import asyncio

        async def _safe(action: str, params: dict, *, count_key: str = "count") -> int | None:
            try:
                r = await self._ckan(action, params)
                if isinstance(r, dict):
                    return r.get(count_key)
                if isinstance(r, list):
                    return len(r)
                return None
            except Exception:
                return None

        datasets, orgs, groups, tags = await asyncio.gather(
            _safe("package_search", {"rows": 0, "q": "*:*"}),
            _safe("organization_list", {}),
            _safe("group_list", {}),
            _safe("tag_list", {}),
        )

        return {
            "country": self.COUNTRY_CODE,
            "portal": self.PORTAL_NAME,
            "portal_url": self.PORTAL_URL,
            "platform": self.PLATFORM,
            "total_datasets": datasets,
            "total_organizations": orgs,
            "total_groups": groups,
            "total_tags": tags,
        }
