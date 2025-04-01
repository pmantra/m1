from typing import List, Tuple

import pytest

from wallet.pytests.factories import CountryCurrencyCodeFactory
from wallet.repository.currency_code import CurrencyCodeRepository, MissingCurrencyCode


@pytest.fixture(scope="function", autouse=True)
def supported_currency_codes():
    # override the autouse fixture so we can have a clean slate for these tests
    return


@pytest.fixture
def currency_code_repository(session):
    return CurrencyCodeRepository(session)


class TestCurrencyCodeRepository:
    @staticmethod
    def test_get_minor_unit(currency_code_repository):
        """Test that we can fetch a minor unit when given a currency"""
        # Given
        currency_code: str = "USD"
        expected_minor_unit: int = 2

        CountryCurrencyCodeFactory.create(
            country_alpha_2=currency_code,
            currency_code=currency_code,
            minor_unit=expected_minor_unit,
        )

        # When
        minor_unit = currency_code_repository.get_minor_unit(
            currency_code=currency_code
        )

        # Then
        assert expected_minor_unit == minor_unit

    @staticmethod
    def test_get_minor_unit_multiple(currency_code_repository):
        """
        Test that we can fetch a minor unit when given a currency
        if there are multiple in DB
        """
        # Given
        currencies: List[Tuple[str, int]] = [
            ("USD", 2),
            ("JPY", 0),
            ("AUD", 2),
            ("NZD", 2),
        ]

        for code, minor_unit in currencies:
            CountryCurrencyCodeFactory.create(
                country_alpha_2=code,
                currency_code=code,
                minor_unit=minor_unit,
            )

        # When
        minor_unit = currency_code_repository.get_minor_unit(currency_code="USD")

        # Then
        assert minor_unit == 2

    @staticmethod
    def test_get_minor_unit_missing(currency_code_repository):
        """Test that we raise an exception when the currency code is missing"""
        # Given
        currency_code: str = "USD"
        expected_minor_unit: int = 2

        CountryCurrencyCodeFactory.create(
            country_alpha_2=currency_code,
            currency_code=currency_code,
            minor_unit=expected_minor_unit,
        )

        # When
        with pytest.raises(MissingCurrencyCode):
            currency_code_repository.get_minor_unit(currency_code="JPY")

    @staticmethod
    def test_get_minor_unit_is_null(currency_code_repository):
        """Test that we raise an exception when the currency code's minor unit is null"""
        # Given
        currency_code: str = "USD"

        CountryCurrencyCodeFactory.create(
            country_alpha_2=currency_code,
            currency_code=currency_code,
            minor_unit=None,
        )

        # When
        with pytest.raises(MissingCurrencyCode):
            currency_code_repository.get_minor_unit(currency_code="JPY")

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("currency_code", "exception_string"),
        argvalues=[
            ("", "currency_code can't be empty string"),
            ("    ", "currency_code can't be empty string"),
            (None, "currency_code can't be None"),
        ],
    )
    def test_get_minor_unit_invalid_currency_code(
        currency_code_repository, currency_code, exception_string
    ):
        """Test that we raise an exception when the input is empty string or null"""
        # When - Then
        with pytest.raises(ValueError, match=exception_string):
            currency_code_repository.get_minor_unit(currency_code=currency_code)
