"""Portal adapters.

Each LatAm country has a portal adapter implementing the PortalAdapter
protocol. Most are CKAN-backed (subclass CkanAdapter, override BASE_URL).
Colombia uses Socrata. Brazil eventually will use a custom adapter.

Adapter lookup happens in registry.get_adapter(country_code).
"""

from .base import PortalAdapter
from .registry import get_adapter, list_supported

__all__ = ["PortalAdapter", "get_adapter", "list_supported"]
