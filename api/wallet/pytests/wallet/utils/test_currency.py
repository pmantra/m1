from decimal import Decimal

import pytest

from wallet.models.currency import Money
from wallet.utils import currency


class TestFormatDisplayAmount:
    @staticmethod
    @pytest.mark.parametrize(
        argnames=("money", "expected"),
        argvalues=[
            (Money(amount=Decimal("1.12"), currency_code="USD"), "$1.12"),
            (Money(amount=Decimal("1000.00"), currency_code="USD"), "$1,000.00"),
            (Money(amount=Decimal("1.12"), currency_code="AUD"), "$1.12"),
            (Money(amount=Decimal("1000.00"), currency_code="AUD"), "$1,000.00"),
            (Money(amount=Decimal("1.12"), currency_code="CAD"), "$1.12"),
            (Money(amount=Decimal("1000.00"), currency_code="CAD"), "$1,000.00"),
            (Money(amount=Decimal("1.12"), currency_code="CHF"), "CHF\xa01.12"),
            (Money(amount=Decimal("1000.00"), currency_code="CHF"), "CHF\xa01’000.00"),
            (Money(amount=Decimal("1.12"), currency_code="NZD"), "$1.12"),
            (Money(amount=Decimal("1000.00"), currency_code="NZD"), "$1,000.00"),
            (Money(amount=Decimal("1.12"), currency_code="GBP"), "£1.12"),
            (Money(amount=Decimal("1000.00"), currency_code="GBP"), "£1,000.00"),
            (Money(amount=Decimal("1.12"), currency_code="BRL"), "R$\xa01,12"),
            (Money(amount=Decimal("1000.00"), currency_code="BRL"), "R$\xa01.000,00"),
            (Money(amount=Decimal("1.12"), currency_code="EUR"), "1,12\xa0€"),
            (Money(amount=Decimal("1000.00"), currency_code="EUR"), "1.000,00\xa0€"),
            (Money(amount=Decimal("1.12"), currency_code="INR"), "₹1.12"),
            (Money(amount=Decimal("1000.00"), currency_code="INR"), "₹1,000.00"),
            (
                Money(amount=Decimal("10000000.00"), currency_code="INR"),
                "₹1,00,00,000.00",
            ),
        ],
        ids=[
            "USD-under-a-thousand",
            "USD-over-a-thousand",
            "AUD-under-a-thousand",
            "AUD-over-a-thousand",
            "CAD-under-a-thousand",
            "CAD-over-a-thousand",
            "CHF-under-a-thousand",
            "CHF-over-a-thousand",
            "NZD-under-a-thousand",
            "NZD-over-a-thousand",
            "GBP-under-a-thousand",
            "GBP-over-a-thousand",
            "BRL-under-a-thousand",
            "BRL-over-a-thousand",
            "EUR-under-a-thousand",
            "EUR-over-a-thousand",
            "INR-under-a-thousand",
            "INR-over-a-thousand",
            "INR-over-a-million",
        ],
    )
    def test_format_display_amount(money: Money, expected: str):
        # Given a Money instance

        # When
        formatted: str = currency.format_display_amount(money=money)

        # Then
        assert formatted == expected


class TestFormatTruncatedAmount:
    @staticmethod
    @pytest.mark.parametrize(
        argnames=("money", "expected"),
        argvalues=[
            (Money(amount=Decimal("1.12"), currency_code="USD"), "$1"),
            (Money(amount=Decimal("1000.00"), currency_code="USD"), "$1,000"),
            (Money(amount=Decimal("1000.12"), currency_code="USD"), "$1,000"),
            (Money(amount=Decimal("1999.99"), currency_code="USD"), "$1,999"),
            (Money(amount=Decimal("1.12"), currency_code="AUD"), "$1"),
            (Money(amount=Decimal("1000.00"), currency_code="AUD"), "$1,000"),
            (Money(amount=Decimal("1000.12"), currency_code="AUD"), "$1,000"),
            (Money(amount=Decimal("1.12"), currency_code="CAD"), "$1"),
            (Money(amount=Decimal("1000.00"), currency_code="CAD"), "$1,000"),
            (Money(amount=Decimal("1000.12"), currency_code="CAD"), "$1,000"),
            (Money(amount=Decimal("1.12"), currency_code="CHF"), "CHF\xa01"),
            (Money(amount=Decimal("1000.00"), currency_code="CHF"), "CHF\xa01’000"),
            (Money(amount=Decimal("1000.12"), currency_code="CHF"), "CHF\xa01’000"),
            (Money(amount=Decimal("1.12"), currency_code="NZD"), "$1"),
            (Money(amount=Decimal("1000.00"), currency_code="NZD"), "$1,000"),
            (Money(amount=Decimal("1000.12"), currency_code="NZD"), "$1,000"),
            (Money(amount=Decimal("1.12"), currency_code="GBP"), "£1"),
            (Money(amount=Decimal("1000.00"), currency_code="GBP"), "£1,000"),
            (Money(amount=Decimal("1000.12"), currency_code="GBP"), "£1,000"),
            (Money(amount=Decimal("1.12"), currency_code="BRL"), "R$\xa01"),
            (Money(amount=Decimal("1000.00"), currency_code="BRL"), "R$\xa01.000"),
            (Money(amount=Decimal("1000.12"), currency_code="BRL"), "R$\xa01.000"),
            (Money(amount=Decimal("1.12"), currency_code="EUR"), "1\xa0€"),
            (Money(amount=Decimal("1000.00"), currency_code="EUR"), "1.000\xa0€"),
            (Money(amount=Decimal("1000.12"), currency_code="EUR"), "1.000\xa0€"),
            (Money(amount=Decimal("1.12"), currency_code="INR"), "₹1"),
            (Money(amount=Decimal("1000.00"), currency_code="INR"), "₹1,000"),
            (Money(amount=Decimal("1000.12"), currency_code="INR"), "₹1,000"),
            (Money(amount=Decimal("10000000.00"), currency_code="INR"), "₹1,00,00,000"),
        ],
        ids=[
            "USD-under-a-thousand",
            "USD-over-a-thousand",
            "USD-over-a-thousand-with-cents",
            "USD-a-cent-under-2k",
            "AUD-under-a-thousand",
            "AUD-over-a-thousand",
            "AUD-over-a-thousand-with-cents",
            "CAD-under-a-thousand",
            "CAD-over-a-thousand",
            "CAD-over-a-thousand-with-cents",
            "CHF-under-a-thousand",
            "CHF-over-a-thousand",
            "CHF-over-a-thousand-with-cents",
            "NZD-under-a-thousand",
            "NZD-over-a-thousand",
            "NZD-over-a-thousand-with-cents",
            "GBP-under-a-thousand",
            "GBP-over-a-thousand",
            "GBP-over-a-thousand-with-cents",
            "BRL-under-a-thousand",
            "BRL-over-a-thousand",
            "BRL-over-a-thousand-with-cents",
            "EUR-under-a-thousand",
            "EUR-over-a-thousand",
            "EUR-over-a-thousand-with-cents",
            "INR-under-a-thousand",
            "INR-over-a-thousand",
            "INR-over-a-thousand-with-cents",
            "INR-over-a-million",
        ],
    )
    def test_format_truncated_format(money: Money, expected: str):
        # Given a Decimal amount, ISO 4217 currency_code

        # When
        formatted: str = currency.format_truncated_amount(money=money)

        # Then
        assert formatted == expected


class TestFormatRawAmount:
    @staticmethod
    @pytest.mark.parametrize(
        argnames=("money", "expected"),
        argvalues=[
            (Money(amount=Decimal("1.12"), currency_code="USD"), "1.12"),
            (Money(amount=Decimal("1000.00"), currency_code="USD"), "1000.00"),
            (Money(amount=Decimal("1.12"), currency_code="AUD"), "1.12"),
            (Money(amount=Decimal("1000.00"), currency_code="AUD"), "1000.00"),
            (Money(amount=Decimal("1.12"), currency_code="CAD"), "1.12"),
            (Money(amount=Decimal("1000.00"), currency_code="CAD"), "1000.00"),
            (Money(amount=Decimal("1.12"), currency_code="CHF"), "1.12"),
            (Money(amount=Decimal("1000.00"), currency_code="CHF"), "1000.00"),
            (Money(amount=Decimal("10000000.00"), currency_code="CHF"), "10000000.00"),
            (Money(amount=Decimal("1.12"), currency_code="NZD"), "1.12"),
            (Money(amount=Decimal("1000.00"), currency_code="NZD"), "1000.00"),
            (Money(amount=Decimal("1.12"), currency_code="GBP"), "1.12"),
            (Money(amount=Decimal("1000.00"), currency_code="GBP"), "1000.00"),
            (Money(amount=Decimal("1.12"), currency_code="BRL"), "1.12"),
            (Money(amount=Decimal("1000.00"), currency_code="BRL"), "1000.00"),
            (Money(amount=Decimal("1.12"), currency_code="EUR"), "1.12"),
            (Money(amount=Decimal("1000.00"), currency_code="EUR"), "1000.00"),
            (Money(amount=Decimal("1.12"), currency_code="INR"), "1.12"),
            (Money(amount=Decimal("1000.00"), currency_code="INR"), "1000.00"),
            (Money(amount=Decimal("10000000.00"), currency_code="INR"), "10000000.00"),
        ],
        ids=[
            "USD-under-a-thousand",
            "USD-over-a-thousand",
            "AUD-under-a-thousand",
            "AUD-over-a-thousand",
            "CAD-under-a-thousand",
            "CAD-over-a-thousand",
            "CHF-under-a-thousand",
            "CHF-over-a-thousand",
            "CHF-over-a-million",
            "NZD-under-a-thousand",
            "NZD-over-a-thousand",
            "GBP-under-a-thousand",
            "GBP-over-a-thousand",
            "BRL-under-a-thousand",
            "BRL-over-a-thousand",
            "EUR-under-a-thousand",
            "EUR-over-a-thousand",
            "INR-under-a-thousand",
            "INR-over-a-thousand",
            "INR-over-a-million",
        ],
    )
    def test_format_raw_amount(money: Money, expected: str):
        # Given a Decimal amount, ISO 4217 currency_code

        # When
        formatted: str = currency.format_raw_amount(money=money)

        # Then
        assert formatted == expected


class TestFormatDisplayAmountWithCurrencyCode:
    @staticmethod
    @pytest.mark.parametrize(
        argnames=("money", "expected"),
        argvalues=[
            (Money(amount=Decimal("1.12"), currency_code="USD"), "$1.12"),
            (Money(amount=Decimal("1000.00"), currency_code="USD"), "$1,000.00"),
            (Money(amount=Decimal("1.12"), currency_code="AUD"), "A$1.12"),
            (Money(amount=Decimal("1000.00"), currency_code="AUD"), "A$1,000.00"),
            (Money(amount=Decimal("1.12"), currency_code="CAD"), "CA$1.12"),
            (Money(amount=Decimal("1000.00"), currency_code="CAD"), "CA$1,000.00"),
            (Money(amount=Decimal("1.12"), currency_code="CHF"), "CHF1.12"),
            (Money(amount=Decimal("1000.00"), currency_code="CHF"), "CHF1,000.00"),
            (Money(amount=Decimal("1.12"), currency_code="NZD"), "NZ$1.12"),
            (Money(amount=Decimal("1000.00"), currency_code="NZD"), "NZ$1,000.00"),
            (Money(amount=Decimal("1.12"), currency_code="GBP"), "£1.12"),
            (Money(amount=Decimal("1000.00"), currency_code="GBP"), "£1,000.00"),
            (Money(amount=Decimal("1.12"), currency_code="BRL"), "R$1.12"),
            (Money(amount=Decimal("1000.00"), currency_code="BRL"), "R$1,000.00"),
            (Money(amount=Decimal("1.12"), currency_code="EUR"), "€1.12"),
            (Money(amount=Decimal("1000.00"), currency_code="EUR"), "€1,000.00"),
            (Money(amount=Decimal("1.12"), currency_code="INR"), "₹1.12"),
            (Money(amount=Decimal("1000.00"), currency_code="INR"), "₹1,000.00"),
            (
                Money(amount=Decimal("10000000.00"), currency_code="INR"),
                "₹10,000,000.00",
            ),
        ],
        ids=[
            "USD-under-a-thousand",
            "USD-over-a-thousand",
            "AUD-under-a-thousand",
            "AUD-over-a-thousand",
            "CAD-under-a-thousand",
            "CAD-over-a-thousand",
            "CHF-under-a-thousand",
            "CHF-over-a-thousand",
            "NZD-under-a-thousand",
            "NZD-over-a-thousand",
            "GBP-under-a-thousand",
            "GBP-over-a-thousand",
            "BRL-under-a-thousand",
            "BRL-over-a-thousand",
            "EUR-under-a-thousand",
            "EUR-over-a-thousand",
            "INR-under-a-thousand",
            "INR-over-a-thousand",
            "INR-over-a-million",
        ],
    )
    def test_format_display_amount_with_currency_code(money: Money, expected: str):
        # Given a Decimal amount, ISO 4217 currency_code

        # When
        formatted: str = currency.format_display_amount_with_currency_code(money=money)

        # Then
        assert formatted == expected


class TestFormatDisplayAmountWithFullCurrencyName:
    @staticmethod
    @pytest.mark.parametrize(
        argnames=("money", "expected"),
        argvalues=[
            (Money(amount=Decimal("1.12"), currency_code="USD"), "1.12 US dollars"),
            (
                Money(amount=Decimal("1000.00"), currency_code="USD"),
                "1,000.00 US dollars",
            ),
            (
                Money(amount=Decimal("1.12"), currency_code="AUD"),
                "1.12 Australian dollars",
            ),
            (
                Money(amount=Decimal("1000.00"), currency_code="AUD"),
                "1,000.00 Australian dollars",
            ),
            (
                Money(amount=Decimal("1.12"), currency_code="CAD"),
                "1.12 Canadian dollars",
            ),
            (
                Money(amount=Decimal("1000.00"), currency_code="CAD"),
                "1,000.00 Canadian dollars",
            ),
            (
                Money(amount=Decimal("1.12"), currency_code="CHF"),
                "1.12 Swiss francs",
            ),
            (
                Money(amount=Decimal("1000.00"), currency_code="CHF"),
                "1,000.00 Swiss francs",
            ),
            (
                Money(amount=Decimal("1.12"), currency_code="NZD"),
                "1.12 New Zealand dollars",
            ),
            (
                Money(amount=Decimal("1000.00"), currency_code="NZD"),
                "1,000.00 New Zealand dollars",
            ),
            (
                Money(amount=Decimal("1.12"), currency_code="GBP"),
                "1.12 British pounds",
            ),
            (
                Money(amount=Decimal("1000.00"), currency_code="GBP"),
                "1,000.00 British pounds",
            ),
            (
                Money(amount=Decimal("1.12"), currency_code="BRL"),
                "1.12 Brazilian reals",
            ),
            (
                Money(amount=Decimal("1000.00"), currency_code="BRL"),
                "1,000.00 Brazilian reals",
            ),
            (
                Money(amount=Decimal("1.12"), currency_code="EUR"),
                "1.12 euros",
            ),
            (
                Money(amount=Decimal("1000.00"), currency_code="EUR"),
                "1,000.00 euros",
            ),
            (
                Money(amount=Decimal("1.12"), currency_code="INR"),
                "1.12 Indian rupees",
            ),
            (
                Money(amount=Decimal("1000.00"), currency_code="INR"),
                "1,000.00 Indian rupees",
            ),
            (
                Money(amount=Decimal("10000000.00"), currency_code="INR"),
                "10,000,000.00 Indian rupees",
            ),
        ],
        ids=[
            "USD-under-a-thousand",
            "USD-over-a-thousand",
            "AUD-under-a-thousand",
            "AUD-over-a-thousand",
            "CAD-under-a-thousand",
            "CAD-over-a-thousand",
            "CHF-under-a-thousand",
            "CHF-over-a-thousand",
            "NZD-under-a-thousand",
            "NZD-over-a-thousand",
            "GBP-under-a-thousand",
            "GBP-over-a-thousand",
            "BRL-under-a-thousand",
            "BRL-over-a-thousand",
            "EUR-under-a-thousand",
            "EUR-over-a-thousand",
            "INR-under-a-thousand",
            "INR-over-a-thousand",
            "INR-over-a-million",
        ],
    )
    def test_format_display_amount_with_full_currency_name(money: Money, expected: str):
        # Given a Decimal amount, ISO 4217 currency_code

        # When
        formatted: str = currency.format_display_amount_with_full_currency_name(
            money=money
        )

        # Then
        assert formatted == expected
