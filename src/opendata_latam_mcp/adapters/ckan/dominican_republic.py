from .base import CkanAdapter


class DominicanRepublicCkanAdapter(CkanAdapter):
    COUNTRY_CODE = "DO"
    PORTAL_NAME = "Portal de Datos Abiertos de la República Dominicana"
    PORTAL_URL = "https://datos.gob.do"
    BASE_URL = "https://datos.gob.do/api/3/action"
