from .base import CkanAdapter


class ChileCkanAdapter(CkanAdapter):
    COUNTRY_CODE = "CL"
    PORTAL_NAME = "Portal de Datos Abiertos de Chile"
    PORTAL_URL = "https://datos.gob.cl"
    BASE_URL = "https://datos.gob.cl/api/3/action"
