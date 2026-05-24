from .base import CkanAdapter


class UruguayCkanAdapter(CkanAdapter):
    COUNTRY_CODE = "UY"
    PORTAL_NAME = "Catálogo de Datos Abiertos de Uruguay (AGESIC)"
    PORTAL_URL = "https://catalogodatos.gub.uy"
    BASE_URL = "https://catalogodatos.gub.uy/api/3/action"
