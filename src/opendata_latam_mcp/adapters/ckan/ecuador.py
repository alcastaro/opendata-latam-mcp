from .base import CkanAdapter


class EcuadorCkanAdapter(CkanAdapter):
    """Configured, and not answering.

    Measured 2026-08-30: HTTP 403 to every request — with the adapter's
    User-Agent, with a short one, with none at all, and on the site root as well
    as the API. Header is a bare `Server: Apache` with no commercial WAF
    signature, so it is not a User-Agent rule the way Mexico's was.

    Kept in COUNTRIES rather than removed because a single vantage point cannot
    distinguish a portal that closed programmatic access from one that blocks
    this address; that needs a check from another network. If it turns out to
    answer only through a VPN, the correct response is to declare it
    unavailable, not to ship the detour — the same line held at Cali's WAF.
    """

    COUNTRY_CODE = "EC"
    STATUS = "unreachable"
    STATUS_NOTE = (
        "HTTP 403 to every request since 2026-08-30, site root included. "
        "Calls will return an error, not results."
    )
    PORTAL_NAME = "Plataforma de Datos Abiertos de Ecuador (PDAE)"
    PORTAL_URL = "https://www.datosabiertos.gob.ec"
    BASE_URL = "https://www.datosabiertos.gob.ec/api/3/action"
