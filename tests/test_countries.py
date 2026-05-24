"""Unit tests for country code normalization."""

from __future__ import annotations

import pytest

from opendata_latam_mcp.countries import COUNTRIES, all_codes, normalize_country_code


def test_all_codes_returns_sorted_supported():
    codes = all_codes()
    assert codes == sorted(codes)
    assert "DO" in codes
    assert "AR" in codes


def test_normalize_uppercase_passes_through():
    assert normalize_country_code("DO") == "DO"


def test_normalize_lowercase_uppercases():
    assert normalize_country_code("do") == "DO"


def test_normalize_mixed_case():
    assert normalize_country_code("Do") == "DO"


def test_normalize_by_spanish_name():
    assert normalize_country_code("México") == "MX"
    assert normalize_country_code("república dominicana") == "DO"


def test_normalize_by_english_name():
    assert normalize_country_code("Mexico") == "MX"
    assert normalize_country_code("Dominican Republic") == "DO"


def test_normalize_unknown_raises():
    with pytest.raises(ValueError, match="Unknown country"):
        normalize_country_code("ZZ")


def test_normalize_empty_raises():
    with pytest.raises(ValueError, match="required"):
        normalize_country_code("")


def test_countries_metadata_consistent():
    for code, c in COUNTRIES.items():
        assert c.code == code
        assert c.name_es
        assert c.name_en
