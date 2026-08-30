"""CKAN portal adapters.

Most LatAm gov portals run CKAN. Country subclasses override only BASE_URL
and (optionally) PORTAL_URL. All API behaviour is inherited from CkanAdapter.
"""

from .argentina import ArgentinaCkanAdapter
from .base import CkanAdapter
from .chile import ChileCkanAdapter
from .dominican_republic import DominicanRepublicCkanAdapter
from .ecuador import EcuadorCkanAdapter
from .mexico import MexicoCkanAdapter
from .panama import PanamaCkanAdapter
from .uruguay import UruguayCkanAdapter

__all__ = [
    "ArgentinaCkanAdapter",
    "ChileCkanAdapter",
    "CkanAdapter",
    "DominicanRepublicCkanAdapter",
    "EcuadorCkanAdapter",
    "MexicoCkanAdapter",
    "PanamaCkanAdapter",
    "UruguayCkanAdapter",
]
