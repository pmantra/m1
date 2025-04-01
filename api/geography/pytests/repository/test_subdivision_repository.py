import pytest
from maven.feature_flags import test_data

from l10n.config import CUSTOM_LOCALE_HEADER


def test_get(subdivision_repository):
    """
    When:
        - a valid ISO 3166-2 subdivision code is passed
    Then:
        - the returned object should have the subdivision code for the corresponding country
    """
    assert subdivision_repository.get(subdivision_code="US-NY").code == "US-NY"


def test_get__invalid_subdivision_code(subdivision_repository):
    """
    When:
        - an invalid subdivision code is passed
    Then:
        - we return None
    """
    assert subdivision_repository.get(subdivision_code="ZZ-ZZ") is None


def test_get_by_country_code_and_state(subdivision_repository):
    """
    When:
        - a valid ISO 3166-1 alpha-2 country code is passed
        - a valid ISO 3166-2 subdivision code suffix is passed
    Then:
        - the returned object should have the subdivision code for the corresponding country
    """
    assert (
        subdivision_repository.get_by_country_code_and_state(
            country_code="US", state="NY"
        ).code
        == "US-NY"
    )


def test_get_by_country_code_and_state__invalid_country_code(subdivision_repository):
    """
    When:
        - an invalid country code is passed
        - a valid ISO 3166-2 subdivision code suffix is passed
    Then:
        - we return None
    """
    assert (
        subdivision_repository.get_by_country_code_and_state(
            country_code="ZZ", state="NY"
        )
        is None
    )


def test_get_by_country_code_and_state__invalid_state(subdivision_repository):
    """
    When:
        - a valid ISO 3166-1 alpha-2 country code is passed
        - an invalid subdivision code suffix is passed
    Then:
        - we return None
    """
    assert (
        subdivision_repository.get_by_country_code_and_state(
            country_code="US", state="11"
        )
        is None
    )


def test_get_subdivisions_by_country_code(subdivision_repository):
    """
    When:
        - a valid ISO 3166-1 alpha-2 country code is passed
    Then:
        - we return a list of Subdivision objects, each of which correspond to the provided country code
    """
    country_code = "US"
    subdivisions = subdivision_repository.get_subdivisions_by_country_code(
        country_code=country_code
    )

    assert subdivisions

    for subdivision in subdivisions:
        assert subdivision.country_code == country_code


def test_get_subdivisions_by_country_code__no_subdivisions(subdivision_repository):
    """
    When:
        - a valid ISO 3166-1 alpha-2 country code is passed
        - the country does not have any subdivisions
    Then:
        - we return an empty list
    """
    assert (
        len(subdivision_repository.get_subdivisions_by_country_code(country_code="AQ"))
        == 0
    )


def test_get_subdivisions_by_country_code__invalid_country_code(subdivision_repository):
    """
    When:
        - an invalid country code is passed
    Then:
        - we return None
    """
    assert (
        subdivision_repository.get_subdivisions_by_country_code(country_code="ZZ")
        is None
    )


def test_get_child_subdivisions(subdivision_repository):
    """
    When:
        - a valid ISO 3166-2 subdivision code is passed
        - there exist other subdivisions that have a parent_code equal to the passed subdivision_code
    Then:
        - we return a list of Subdivision objects,
          each of which have a parent_code equal to the originally passed subdivision_code
    """
    subdivision_code = "AZ-NX"
    child_subdivisions = subdivision_repository.get_child_subdivisions(
        subdivision_code=subdivision_code
    )

    assert child_subdivisions

    for child_subdivision in child_subdivisions:
        assert child_subdivision.parent_code == subdivision_code


def test_get_child_subdivisions__no_children(subdivision_repository):
    """
    When:
        - a valid ISO 3166-2 subdivision code is passed
        - there are no other subdivisions that have a parent_code equal to the passed subdivision_code
    Then:
        - we return an empty list
    """
    assert (
        len(subdivision_repository.get_child_subdivisions(subdivision_code="US-NY"))
        == 0
    )


def test_get_child_subdivisions__invalid_subdivision_code(subdivision_repository):
    """
    When:
        - an invalid subdivision code is passed
    Then:
        - we return None
    """
    assert (
        subdivision_repository.get_child_subdivisions(subdivision_code="ZZ-ZZ") is None
    )


@pytest.mark.parametrize(
    "subdivision_code, locale, expected",
    [
        ("NZ-HKB", "en", "Hawke's Bay"),
        ("NZ-HKB", "fr", "Baie de Hawke"),
    ],
)
def test_get_with_locale(
    app, subdivision_repository, subdivision_code, locale, expected
):
    headers = {
        CUSTOM_LOCALE_HEADER: locale,
    }
    with app.test_request_context("/test", headers=headers), test_data() as td:
        td.update(td.flag("release-mono-api-localization").variation_for_all(True))
        td.update(td.flag("release-pycountry-localization").variation_for_all(True))
        assert (
            subdivision_repository.get(subdivision_code=subdivision_code).name
            == expected
        )
