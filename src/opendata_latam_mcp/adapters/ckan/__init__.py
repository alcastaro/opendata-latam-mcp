"""CKAN portal adapters.

Most LatAm gov portals run CKAN. Country subclasses override only BASE_URL
and (optionally) PORTAL_URL. All API behaviour is inherited from CkanAdapter.
"""

from .base import CkanAdapter
from .argentina import ArgentinaCkanAdapter
from .chile import ChileCkanAdapter
from .dominican_republic import DominicanRepublicCkanAdapter
from .ecuador import EcuadorCkanAdapter
from .mexico import MexicoCkanAdapter
from .uruguay import UruguayCkanAdapter

__all__ = [
    "CkanAdapter",
    "ArgentinaCkanAdapter",
    "ChileCkanAdapter",
    "DominicanRepublicCkanAdapter",
    "EcuadorCkanAdapter",
    "MexicoCkanAdapter",
    "UruguayCkanAdapter",
]
