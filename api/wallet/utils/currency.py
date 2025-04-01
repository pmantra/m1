from __future__ import annotations

from math import trunc

from babel import Locale
from babel.numbers import format_currency

from wallet.constants import CURRENCY_TO_LOCALE_MAP
from wallet.models.currency import Money

RAW_FORMAT: str = "###0.00"  # ex. "1000.00"
STANDARD_FORMAT: str = "¤#,##0.00"  # ex. "$1,000.00"
FULL_NAME_FORMAT: str = "#,##0.00 ¤¤¤"  # ex. "1,000.00 US dollars"


def format_display_amount(money: Money) -> str:
    """
    Format a decimal amount with the correct currency symbol and separators.
    ex. $1,000.00

    Args:
        money: instance of Money

    Returns:
        Formatted currency string
    """
    # Default locale to en_US, this could be dynamic in the future
    locale: str = CURRENCY_TO_LOCALE_MAP.get(money.currency_code, "en_US")
    return format_currency(
        number=money.amount, currency=money.currency_code, locale=locale
    )


def format_truncated_amount(money: Money) -> str:
    """
    Format a decimal amount with the correct currency symbol and separators,
    but no decimals, no rounding, just omitted after decimals.
    ex. $1,000

    Args:
        money: instance of Money

    Returns:
        Formatted currency string
    """
    locale_string: str = CURRENCY_TO_LOCALE_MAP.get(money.currency_code, "en_US")
    locale = Locale.parse(locale_string)
    pattern = locale.currency_formats["standard"]
    # A hack to utilize standard locale specific formatting but still removing decimals
    pattern.frac_prec = (0, 0)
    return pattern.apply(
        trunc(money.amount), locale, currency_digits=False, currency=money.currency_code
    )


def format_raw_amount(money: Money) -> str:
    """
    Format a decimal amount with no currency symbol in decimal format with correct number of decimal digits.
    ex. 1000.00

    Args:
        money: instance of Money

    Returns:
        Formatted currency string
    """
    return format_currency(
        number=money.amount, currency=money.currency_code, format=RAW_FORMAT
    )


def format_display_amount_with_currency_code(money: Money) -> str:
    """
    Format a display amount with the currency code
    ex. $1000.00 USD

    Args:
        money: instance of Money

    Returns:
        Formatted currency string
    """
    return format_currency(
        number=money.amount, currency=money.currency_code, format=STANDARD_FORMAT
    )


def format_display_amount_with_full_currency_name(money: Money) -> str:
    """
    Format a display amount with the currency code
    ex. 1000.00 US Dollars

    Args:
        money: instance of Money

    Returns:
        Formatted currency string
    """
    return format_currency(
        number=money.amount, currency=money.currency_code, format=FULL_NAME_FORMAT
    )
