"""ISO 3166-1 alpha-2 country codes for Latin American open-data portals.

Used as the primary key for portal lookup. Country code is required in every
tool call so the model knows exactly which portal it's hitting.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Country:
    code: str        # ISO 3166-1 alpha-2
    name_es: str
    name_en: str


# Currently supported. Add more here as adapters are implemented, and ONLY once
# the adapter exists in adapters/registry._ADAPTER_CLASSES.
#
# Measured 2026-08-30 against the live portals (do not edit these notes from
# memory — probe the portal, that is the whole lesson):
#   PA Panamá  — CKAN 2.11.2 WITH DataStore. All seven actions this adapter
#                calls answer; 5,667 datasets. Drop-in: needs only a descriptor.
#   PE Perú    — NOT "CloudWAF-protected", that earlier note was wrong. It is
#                DKAN (Drupal 7) serving a PARTIAL CKAN action API: package_list
#                (4,670), package_show and group_list work; package_search,
#                organization_list, tag_list and resource_search all 404. No
#                server-side search at all.
#   PY Paraguay— DKAN too, and thinner: only package_list (434) and group_list.
#   CO Colombia— two platforms (Socrata national + CKAN municipal); comes from
#                the colombian-open-data-mcp package, not from here.
#   CR Costa Rica — `datos.go.cr` is CKAN 2.11.3 and all seven actions answer.
#                A drop-in like Panama, but nearly empty: 13 datasets. (The old
#                host datosabiertos.presidencia.go.cr no longer resolves — a DNS
#                miss is not proof a country has no portal.)
#   BR Brasil  — `/api/3/action/package_list` answers HTTP 401 with
#                `www-authenticate: Bearer`. So it IS the CKAN API, not a custom
#                one: this adapter plus an Authorization header, not a new client.
#   BO, GT     — HTTP 403 to everything, same shape as Ecuador. Not forced.
#   CU, SV, HT, HN, NI, VE — no national portal found at the usual host names.
#                Not probed exhaustively; needs a candidate sweep before writing
#                any of them off. Full survey: internal/plan/COBERTURA_REGIONAL.md
COUNTRIES: dict[str, Country] = {
    "AR": Country("AR", "Argentina", "Argentina"),
    "CL": Country("CL", "Chile", "Chile"),
    "DO": Country("DO", "República Dominicana", "Dominican Republic"),
    "EC": Country("EC", "Ecuador", "Ecuador"),
    "MX": Country("MX", "México", "Mexico"),
    "PA": Country("PA", "Panamá", "Panama"),
    "UY": Country("UY", "Uruguay", "Uruguay"),
}


def normalize_country_code(raw: str) -> str:
    """Accept lowercase, names, or codes and return canonical 2-letter uppercase code.

    Raises ValueError if unknown.
    """
    if not raw:
        raise ValueError("country code required")
    s = raw.strip().upper()
    if s in COUNTRIES:
        return s
    # Try by name (Spanish or English).
    s_lower = raw.strip().lower()
    for c in COUNTRIES.values():
        if s_lower in (c.name_es.lower(), c.name_en.lower()):
            return c.code
    raise ValueError(
        f"Unknown country: {raw!r}. Supported: {sorted(COUNTRIES.keys())}"
    )


def all_codes() -> list[str]:
    return sorted(COUNTRIES.keys())
