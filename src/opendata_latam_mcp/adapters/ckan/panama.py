from .base import CkanAdapter


class PanamaCkanAdapter(CkanAdapter):
    """Panama's national portal — the largest catalogue this server reaches.

    Measured 2026-08-30 against the live portal: 5,667 datasets, and every
    action this adapter calls answers (package_search with and without a query,
    package_show, organization_list, group_list, tag_list, resource_search).

    Two things worth knowing:

    * It runs CKAN 2.11.2 **with the DataStore extension** — `datastore_search`
      answers `success: true` against a real resource. It is the first portal
      here where rows could be read server-side without downloading a file.
      Nothing in this server does that yet; the capability belongs to the CKAN
      family, not to Panama, so when it lands it lands in `base.py`.
    * `status_show` never returns JSON on either host — HTML on the bare one, a
      WAF rejection page on www. It does not matter: `get_site_stats` composes
      its answer from `package_search` plus the three `*_list` actions, all of
      which answer. Do not add a `status_show` call to this adapter.

    BASE_URL uses the **www** host on purpose. Measured 2026-08-30: the bare
    `datosabiertos.gob.pa` answers 301 to www on every API action, so the
    non-www form cost two round trips for every single call — against the
    largest catalogue this server reaches. The redirect was invisible because
    the client follows redirects; it showed up only in request logs. PORTAL_URL
    stays on the bare host because that is the address a person should be given
    for the site itself.
    """

    COUNTRY_CODE = "PA"
    PORTAL_NAME = "Portal Nacional de Datos Abiertos de Panamá"
    PORTAL_URL = "https://datosabiertos.gob.pa"
    BASE_URL = "https://www.datosabiertos.gob.pa/api/3/action"
