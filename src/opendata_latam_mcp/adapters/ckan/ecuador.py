from .base import CkanAdapter


class EcuadorCkanAdapter(CkanAdapter):
    COUNTRY_CODE = "EC"
    PORTAL_NAME = "Plataforma de Datos Abiertos de Ecuador (PDAE)"
    PORTAL_URL = "https://www.datosabiertos.gob.ec"
    BASE_URL = "https://www.datosabiertos.gob.ec/api/3/action"
