from maven.feature_flags import test_data


def test_get_by_country_code(country_repository):
    """
    When:
        - a valid ISO 3166-1 alpha-2 country code is passed
    Then:
        - the returned object should have an alpha_2 value for the corresponding country
    """
    assert country_repository.get(country_code="US").alpha_2 == "US"


def test_get_by_country_code__invalid_country_code(country_repository):
    """
    When:
        - an invalid ISO 3166-1 alpha-2 country code is passed
    Then:
        - we return None
    """
    assert country_repository.get(country_code="ZZ") is None


def test_get_by_country_code__no_country_code(country_repository):
    """
    When:
        - no alpha-2 country code is passed
    Then:
        - we return None
    """
    assert country_repository.get(country_code="") is None


def test_get_by_name__alpha_2(country_repository):
    """
    When:
        - a valid ISO 3166-1 alpha-2 country code is passed
    Then:
        - the returned object should have an alpha_2 value for the corresponding country
    """
    assert country_repository.get_by_name(name="US").alpha_2 == "US"


def test_get_by_name__alpha_3(country_repository):
    """
    When:
        - a valid ISO 3166-1 alpha-3 country code is passed
    Then:
        - the returned object should have an alpha_2 value for the corresponding country
    """
    assert country_repository.get_by_name(name="USA").alpha_2 == "US"


def test_get_by_name__official_name(country_repository):
    """
    When:
        - a valid ISO 3166-1 alpha-3 country name is passed
    Then:
        - the returned object should have an alpha_2 value for the corresponding country
    """
    assert (
        country_repository.get_by_name(name="United States of America").alpha_2 == "US"
    )


def test_get_by_name__no_country(country_repository):
    """
    When:
        - no country name is passed
    Then:
        - we return None
    """
    assert country_repository.get_by_name(name="") is None


def test_get_by_subdivision_code(country_repository):
    """
    When:
        - a valid ISO 3166-2 subdivision code is passed
    Then:
        - the returned object should have an alpha_2 value for the corresponding country
    """
    assert (
        country_repository.get_by_subdivision_code(subdivision_code="US-NY").alpha_2
        == "US"
    )


def test_get_by_subdivision_code__invalid_subdivision_code(country_repository):
    """
    When:
        - an invalid ISO 3166-2 subdivision code is passed
    Then:
        - we return None
    """
    assert country_repository.get_by_subdivision_code(subdivision_code="ZZ-ZZ") is None


def test_get_metadata(country_repository, factories):
    """
    Given:
        - a CountryMetadata entry exists
    When:
        - a valid ISO 3166-1 alpha-2 country code is passed
          that corresponds with an existing CountryMetadata entry's country_code
    Then:
        - we return the corresponding CountryMetadata entry
    """
    country_metadata = factories.CountryMetadataFactory.create(country_code="US")
    assert country_repository.get_metadata(country_code="US") == country_metadata


def test_get_metadata__invalid_country_code(country_repository, factories):
    """
    Given:
        - a CountryMetadata entry exists
    When:
        - a country code is passed that does not correspond with an existing CountryMetadata entry's country_code
    Then:
        - we return None
    """
    factories.CountryMetadataFactory.create(country_code="US")
    assert country_repository.get_metadata(country_code="ZZ") is None


def test_create_metadata(country_repository):
    """
    When:
        - Country metadata is passed
    Then:
        - we create a CountryMetadata instance with properies populated with the values provided to the create method
    """
    expected_values = {
        "country_code": "US",
        "summary": "summary",
        "ext_info_link": "ext_info_link",
        "emoji": "🇺🇸",
    }

    country_metadata = country_repository.create_metadata(
        country_code=expected_values["country_code"],
        summary=expected_values["summary"],
        ext_info_link=expected_values["ext_info_link"],
        emoji=expected_values["emoji"],
    )

    created_values = {
        f: v for f, v in vars(country_metadata).items() if f in expected_values
    }

    assert created_values == expected_values


def test_get_by_country_code_with_locale_outside_of_request(country_repository):
    """
    Confirms that default locale (en) is used when `gettext` is applied outside a Flask request context
    """
    with test_data() as td:
        td.update(td.flag("release-pycountry-localization").variation_for_all(True))
        assert country_repository.get(country_code="US").name == "United States"


def test_get_overriden_country(country_repository):
    assert country_repository.get(country_code="TW").name == "Taiwan"
