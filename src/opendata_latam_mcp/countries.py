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


# Currently supported. Add more here as adapters are implemented.
COUNTRIES: dict[str, Country] = {
    "AR": Country("AR", "Argentina", "Argentina"),
    "CL": Country("CL", "Chile", "Chile"),
    "CO": Country("CO", "Colombia", "Colombia"),
    "DO": Country("DO", "República Dominicana", "Dominican Republic"),
    "EC": Country("EC", "Ecuador", "Ecuador"),
    "MX": Country("MX", "México", "Mexico"),
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
