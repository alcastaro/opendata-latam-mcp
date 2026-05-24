from .base import CkanAdapter


class ArgentinaCkanAdapter(CkanAdapter):
    COUNTRY_CODE = "AR"
    PORTAL_NAME = "Portal Nacional de Datos Abiertos de Argentina"
    PORTAL_URL = "https://datos.gob.ar"
    BASE_URL = "https://datos.gob.ar/api/3/action"
