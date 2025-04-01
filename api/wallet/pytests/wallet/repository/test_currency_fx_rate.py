import datetime
from datetime import date
from decimal import Decimal

import pytest

from wallet.pytests.factories import ReimbursementRequestExchangeRatesFactory
from wallet.repository.currency_fx_rate import (
    CurrencyFxRateRepository,
    InvalidExchangeRate,
    MissingExchangeRate,
)


@pytest.fixture
def fx_rate_repository(session):
    return CurrencyFxRateRepository(session)


class TestCurrencyFxRateRepository:
    @staticmethod
    def test_get_direct_rate(fx_rate_repository):
        """Test that we can fetch a rate from source currency to target currency"""
        # Given
        source_currency: str = "USD"
        target_currency: str = "JPY"
        expected_rate: Decimal = Decimal("2.06")
        trading_date: date = date(2024, 1, 1)

        ReimbursementRequestExchangeRatesFactory.create(
            source_currency=source_currency,
            target_currency=target_currency,
            exchange_rate=expected_rate,
            trading_date=trading_date,
        )

        # When
        rate = fx_rate_repository.get_direct_rate(
            source_currency_code=source_currency,
            target_currency_code=target_currency,
            as_of_date=trading_date,
        )

        # Then
        assert rate == expected_rate

    @staticmethod
    def test_get_direct_rate_same_source_and_target(fx_rate_repository):
        """Test that when the source and target are the same, we return Decimal("1.0")"""
        # Given
        currency: str = "USD"
        expected_rate: Decimal = Decimal("1.00")
        trading_date: date = date(2024, 1, 1)

        # When
        rate = fx_rate_repository.get_direct_rate(
            source_currency_code=currency,
            target_currency_code=currency,
            as_of_date=trading_date,
        )

        # Then
        assert rate == expected_rate

    @staticmethod
    def test_get_direct_rate_only_inverse(fx_rate_repository):
        """
        Test that we can fetch a rate from source currency to target currency using
        a fallback to the inverse rate of target currency to source currency
        """
        # Given
        source_currency: str = "USD"
        target_currency: str = "JPY"
        inverse_rate: Decimal = Decimal(".66")
        expected_rate: Decimal = 1 / inverse_rate
        trading_date: date = date(2024, 1, 1)

        ReimbursementRequestExchangeRatesFactory.create(
            source_currency=target_currency,
            target_currency=source_currency,
            exchange_rate=inverse_rate,
            trading_date=trading_date,
        )

        # When
        rate = fx_rate_repository.get_direct_rate(
            source_currency_code=source_currency,
            target_currency_code=target_currency,
            as_of_date=trading_date,
        )

        # Then
        assert rate == expected_rate

    @staticmethod
    @pytest.mark.parametrize(
        argnames="rate",
        argvalues=[Decimal("0"), Decimal("-1.0")],
        ids=["rate-is-zero", "rate-is-negative"],
    )
    def test_get_direct_rate_invalid_rate(fx_rate_repository, rate):
        """
        Test that when we try to calculate an inverse rate with a 0 rate
        we get a InvalidExchangeRate
        """
        # Given
        source_currency: str = "USD"
        target_currency: str = "JPY"
        trading_date: date = date(2024, 1, 1)

        ReimbursementRequestExchangeRatesFactory.create(
            source_currency=source_currency,
            target_currency=target_currency,
            exchange_rate=rate,
            trading_date=trading_date,
        )

        # When
        with pytest.raises(InvalidExchangeRate):
            fx_rate_repository.get_direct_rate(
                source_currency_code=source_currency,
                target_currency_code=target_currency,
                as_of_date=trading_date,
            )

    @staticmethod
    def test_get_direct_rate_missing_rate(fx_rate_repository):
        """Test that an exception is raised when we can't find the rate using any method"""
        # Given
        source_currency: str = "USD"
        target_currency: str = "JPY"
        trading_date: date = date(2024, 1, 1)

        # When - Then
        with pytest.raises(MissingExchangeRate):
            fx_rate_repository.get_direct_rate(
                source_currency_code=source_currency,
                target_currency_code=target_currency,
                as_of_date=trading_date,
            )

    @staticmethod
    def test_get_rate(fx_rate_repository):
        """Test that we can fetch a rate from source currency to target currency using a direct rate"""
        # Given
        source_currency: str = "USD"
        target_currency: str = "JPY"
        expected_rate: Decimal = Decimal("2.06")
        trading_date: date = date(2024, 1, 1)

        ReimbursementRequestExchangeRatesFactory.create(
            source_currency=source_currency,
            target_currency=target_currency,
            exchange_rate=expected_rate,
            trading_date=trading_date,
        )

        # When
        rate = fx_rate_repository.get_rate(
            source_currency_code=source_currency,
            target_currency_code=target_currency,
            as_of_date=trading_date,
        )

        # Then
        assert rate == expected_rate

    @staticmethod
    def test_get_direct_rate_uses_latest_rate(fx_rate_repository):
        """
        Test that the latest rate is fetched when there are multiple rates that match the criteria
        """
        # Given
        source_currency: str = "USD"
        target_currency: str = "JPY"
        older_rate: Decimal = Decimal("1.04")
        expected_rate: Decimal = Decimal("2.06")
        trading_date: date = date(2023, 1, 1)

        ReimbursementRequestExchangeRatesFactory.create(
            source_currency=source_currency,
            target_currency=target_currency,
            exchange_rate=older_rate,
            # A rate that is older
            trading_date=trading_date - datetime.timedelta(weeks=4),
        )

        ReimbursementRequestExchangeRatesFactory.create(
            source_currency=source_currency,
            target_currency=target_currency,
            exchange_rate=expected_rate,
            trading_date=trading_date,
        )

        # When
        rate = fx_rate_repository.get_direct_rate(
            source_currency_code=source_currency,
            target_currency_code=target_currency,
            as_of_date=date(2024, 1, 1),
        )

        # Then
        assert rate == expected_rate

    @staticmethod
    def test_get_direct_rate_uses_earlier_rate(fx_rate_repository):
        """
        Test that the correct rate is fetched when there are multiple rates that match the criteria based on as_of_date
        """
        # Given
        source_currency: str = "USD"
        target_currency: str = "JPY"
        expected_rate: Decimal = Decimal("1.04")
        newer_rate: Decimal = Decimal("2.06")

        ReimbursementRequestExchangeRatesFactory.create(
            source_currency=source_currency,
            target_currency=target_currency,
            exchange_rate=expected_rate,
            # A rate that is older
            trading_date=date(2023, 1, 1),
        )

        ReimbursementRequestExchangeRatesFactory.create(
            source_currency=source_currency,
            target_currency=target_currency,
            exchange_rate=newer_rate,
            trading_date=date(2024, 1, 1),
        )

        # When
        rate = fx_rate_repository.get_direct_rate(
            source_currency_code=source_currency,
            target_currency_code=target_currency,
            as_of_date=date(2023, 2, 1),
        )

        # Then
        assert rate == expected_rate

    @staticmethod
    def test_get_rate_with_intermediate_rate(fx_rate_repository):
        """
        Test that we can fall back to using an intermediate rate to calculate a rate
        if we don't have a direct rate to use
        """
        # Given
        USD_GBP_rate: Decimal = Decimal("0.05")
        USD_JPY_rate: Decimal = Decimal("0.38")
        source_currency: str = "GBP"
        target_currency: str = "JPY"
        expected_rate: Decimal = (1 / USD_GBP_rate) * USD_JPY_rate
        trading_date: date = date(2024, 1, 1)

        ReimbursementRequestExchangeRatesFactory.create(
            source_currency="USD",
            target_currency="GBP",
            exchange_rate=USD_GBP_rate,
            trading_date=trading_date,
        )
        ReimbursementRequestExchangeRatesFactory.create(
            source_currency="USD",
            target_currency="JPY",
            exchange_rate=USD_JPY_rate,
            trading_date=trading_date,
        )

        # When
        rate = fx_rate_repository.get_rate(
            source_currency_code=source_currency,
            target_currency_code=target_currency,
            as_of_date=trading_date,
        )

        # Then
        assert rate == expected_rate

    @staticmethod
    def test_get_rate_missing_rate(fx_rate_repository):
        """
        Test that an exception is raised because we don't have the rates even
        while using an intermediate rate
        """
        # Given
        USD_GBP_rate: Decimal = Decimal("0.05")
        source_currency: str = "GBP"
        target_currency: str = "JPY"
        trading_date: date = date(2024, 1, 1)

        ReimbursementRequestExchangeRatesFactory.create(
            source_currency="USD",
            target_currency="GBP",
            exchange_rate=USD_GBP_rate,
            trading_date=trading_date,
        )

        # When - Then
        with pytest.raises(MissingExchangeRate):
            fx_rate_repository.get_rate(
                source_currency_code=source_currency,
                target_currency_code=target_currency,
                as_of_date=trading_date,
            )

    @staticmethod
    def test_get_available_currencies(fx_rate_repository):
        # Given
        exchange_rates = [
            ("USD", "JPY"),
            ("USD", "GBP"),
            ("USD", "AUD"),
        ]
        currency_code_to_minor_unit = {"USD": 2, "JPY": 0, "AUD": 2, "GBP": 2}
        expected_currencies = set()

        for source, target in exchange_rates:
            ReimbursementRequestExchangeRatesFactory.create(
                source_currency=source,
                target_currency=target,
                exchange_rate=Decimal("0.05"),
                trading_date=date(2024, 1, 1),
            )
            expected_currencies.add((source, currency_code_to_minor_unit[source]))
            expected_currencies.add((target, currency_code_to_minor_unit[target]))

        # When
        currencies = fx_rate_repository.get_available_currency_and_minor_units()

        # Then
        assert (
            set(
                [
                    (currency["currency_code"], currency["minor_unit"])
                    for currency in currencies
                ]
            )
            == expected_currencies
        )
