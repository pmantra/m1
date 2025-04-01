import pytest

from geography.models.country_metadata import CountryMetadata


def test_valid_country_code():
    country_metadata = CountryMetadata(country_code="US")
    assert country_metadata.country_code == "US"


def test_invalid_country_code():
    with pytest.raises(ValueError) as err:
        CountryMetadata(country_code="00")

    assert str(err.value) == "'00' is not a valid ISO 3166-1 alpha-2 country code"
