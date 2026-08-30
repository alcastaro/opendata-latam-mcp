"""Adapter registry — map country code → adapter instance.

Singleton per country: one httpx client per portal, reused across tool calls.
"""

from __future__ import annotations

import logging
from typing import Any

from ..countries import normalize_country_code
from .base import PortalAdapter
from .ckan import (
    ArgentinaCkanAdapter,
    ChileCkanAdapter,
    DominicanRepublicCkanAdapter,
    EcuadorCkanAdapter,
    MexicoCkanAdapter,
    PanamaCkanAdapter,
    UruguayCkanAdapter,
)

logger = logging.getLogger("opendata-latam-mcp")

# Country code → adapter class
_ADAPTER_CLASSES: dict[str, type] = {
    "AR": ArgentinaCkanAdapter,
    "CL": ChileCkanAdapter,
    "DO": DominicanRepublicCkanAdapter,
    "EC": EcuadorCkanAdapter,
    "MX": MexicoCkanAdapter,
    "PA": PanamaCkanAdapter,
    "UY": UruguayCkanAdapter,
}

# Lazy-instantiated singletons. Each adapter holds its own httpx client.
_INSTANCES: dict[str, PortalAdapter] = {}


def get_adapter(country: str) -> PortalAdapter:
    """Return the adapter for `country` (case-insensitive code or name)."""
    code = normalize_country_code(country)
    if code not in _ADAPTER_CLASSES:
        raise ValueError(
            f"No adapter registered for {code!r}. "
            f"Supported: {sorted(_ADAPTER_CLASSES.keys())}"
        )
    if code not in _INSTANCES:
        _INSTANCES[code] = _ADAPTER_CLASSES[code]()
    return _INSTANCES[code]


def list_supported() -> list[dict[str, Any]]:
    """Return list of supported portals (without hitting them)."""
    out = []
    for code, cls in sorted(_ADAPTER_CLASSES.items()):
        entry = {
            "country": code,
            "portal_name": cls.PORTAL_NAME,
            "portal_url": cls.PORTAL_URL,
            "platform": cls.PLATFORM,
            "status": getattr(cls, "STATUS", "ok"),
        }
        note = getattr(cls, "STATUS_NOTE", "")
        if note:
            entry["status_note"] = note
        out.append(entry)
    return out


async def close_all() -> None:
    """Close every cached adapter (httpx clients). Call on shutdown.

    One adapter failing to close must not prevent the others from closing, so
    each is attempted independently — but the failure is logged rather than
    discarded. A silently swallowed close is how a leaked connection stays
    invisible.
    """
    for code, adapter in list(_INSTANCES.items()):
        try:
            await adapter.close()
        except Exception as e:  # noqa: BLE001 — shutdown continues regardless
            logger.warning("closing the %s adapter failed: %s", code, e)
    _INSTANCES.clear()
