from .base import CkanAdapter


class MexicoCkanAdapter(CkanAdapter):
    COUNTRY_CODE = "MX"
    PORTAL_NAME = "Plataforma Nacional de Datos Abiertos de México"
    PORTAL_URL = "https://www.datos.gob.mx"
    BASE_URL = "https://www.datos.gob.mx/api/3/action"
