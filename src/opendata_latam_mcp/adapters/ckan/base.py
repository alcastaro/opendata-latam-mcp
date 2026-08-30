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
import ssl
from typing import Any, ClassVar

import httpx

from ... import __version__

# Some LatAm gov portals (e.g. datos.gob.mx) ship an incomplete TLS cert chain.
# curl works because it reads the macOS / Windows / Linux system trust store.
# Python's httpx defaults to certifi which is narrower. Build a context backed
# by the OS trust store via `truststore`; fall back to default if unavailable.
try:
    import truststore as _truststore  # type: ignore[import-not-found]

    _SSL_CTX: ssl.SSLContext | None = _truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
except Exception:
    _SSL_CTX = None

# No URL in the User-Agent. Measured 2026-08-29: datos.gob.mx answers 403 to any
# UA containing a URL and to the default "curl/..." and "python-httpx/...", but
# 200 to "opendata-latam-mcp/0.1 (MCP Server)". We still identify ourselves
# honestly and by name — this is not browser impersonation, which this project
# does not do. Keep the project URL out of this string or Mexico breaks again.
USER_AGENT = f"opendata-latam-mcp/{__version__} (MCP Server)"
DEFAULT_TIMEOUT = 15.0

# Output trimming so a single call never blows the LLM's context window.
NOTES_TRUNC = 300
DESC_TRUNC = 300
CELL_TRUNC = 200
MAX_ROWS = 100

# A resource identifier goes straight into the URL we build, so it is validated
# strictly rather than by a blacklist. That inversion is deliberate: the loose
# blacklist belongs on COLUMN NAMES, where real portals publish spaces, accents
# and punctuation that a whitelist wrongly rejects. An identifier has no such
# excuse — CKAN's are UUIDs — and validating it is the defense against injecting
# anything into the request path.
_RESOURCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")


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
            kwargs: dict[str, Any] = dict(
                base_url=self.BASE_URL,
                headers={"User-Agent": USER_AGENT},
                timeout=DEFAULT_TIMEOUT,
                follow_redirects=True,
            )
            if _SSL_CTX is not None:
                kwargs["verify"] = _SSL_CTX
            self._client = httpx.AsyncClient(**kwargs)
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

    # ─── Reading rows (DataStore route) ──────────────────────────────────

    async def read_resource_rows(
        self,
        resource_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
        q: str | None = None,
    ) -> dict[str, Any]:
        """Read rows of one resource through the CKAN DataStore.

        This is the cheap, polite route: the portal has already built the table,
        so it filters and paginates server-side and nothing is downloaded. It is
        also only *one* of the routes a catalogue offers — many resources are
        published only as a file, and those need the download route, which this
        adapter does not have yet. Callers get told which case they hit.

        Aggregation is deliberately absent. `datastore_search_sql`, the action
        that would run a GROUP BY on the portal, was measured on 2026-08-30
        across six national portals and answers only on Uruguay; everywhere else
        it is HTTP 400. So min/max/avg/GROUP BY cannot be pushed to the portal
        and belong in a local layer on top of these rows, not here.

        Takes a resource **identifier**, never a URL. The address is built from
        this portal's own BASE_URL, so the set of hosts this can reach is bounded
        by what a government catalogue publishes rather than by what an argument
        can express.

        Returns `{"error": ..., "hint": ...}` rather than raising: an exception
        reaches the model as an opaque protocol error it cannot act on, while a
        hint tells it what to try instead.
        """
        if not _RESOURCE_ID.match(resource_id or ""):
            return {
                "error": f"[{self.COUNTRY_CODE}] not a valid resource identifier: {resource_id!r}",
                "hint": (
                    "Pass the resource `id` from search_resources or get_dataset — "
                    "a CKAN UUID, not a URL and not a dataset name."
                ),
            }

        rows = min(max(int(limit), 1), MAX_ROWS)
        params: dict[str, Any] = {
            "resource_id": resource_id,
            "limit": rows,
            "offset": max(int(offset), 0),
        }
        if q:
            params["q"] = q

        try:
            result = await self._ckan("datastore_search", params)
        except RuntimeError as e:
            msg = str(e)
            # The catalogue's `datastore_active` flag lies: in a sibling project
            # 37 of 59 resources marked queryable answered 404 because the table
            # was never built. Say so, or the model assumes it asked wrongly.
            if "404" in msg or "not found" in msg.lower():
                return {
                    "error": (
                        f"[{self.COUNTRY_CODE}] this resource has no DataStore table, "
                        f"even if the catalogue says it is queryable."
                    ),
                    "hint": (
                        "The catalogue was wrong, not the request. Use get_resource to "
                        "find the resource's published file URL and read it by hand, or "
                        "try another resource of the same dataset."
                    ),
                    "resource_id": resource_id,
                }
            return {"error": msg, "hint": "Portal-side failure. Retry or try another resource."}

        records = result.get("records") or []
        fields = [
            {"id": f.get("id"), "type": f.get("type")}
            for f in (result.get("fields") or [])
            if f.get("id") != "_id"
        ]
        trimmed = []
        for rec in records:
            trimmed.append(
                {
                    k: (self._truncate(v, CELL_TRUNC) if isinstance(v, str) else v)
                    for k, v in rec.items()
                    if k != "_id"
                }
            )
        return {
            "country": self.COUNTRY_CODE,
            "portal": self.PORTAL_NAME,
            "resource_id": resource_id,
            "route": "ckan_datastore",
            "total_rows": result.get("total"),
            "returned": len(trimmed),
            "fields": fields,
            "rows": trimmed,
        }

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
