from unittest import mock

import pytest
from babel import Locale

from l10n.utils import locale_to_alpha_3, request_locale_str


@pytest.mark.parametrize(
    "locale_str, expected_alpha_3",
    [
        ("fr", "fra"),
        ("fr-CA", "fra"),
        ("es", "spa"),
    ],
)
def test_locale_to_alpha_3(locale_str, expected_alpha_3):
    _locale = Locale.parse(locale_str, sep="-")
    actual_alpha_3 = locale_to_alpha_3(_locale)
    assert actual_alpha_3 == expected_alpha_3


@mock.patch("l10n.utils.get_locale")
@pytest.mark.parametrize(
    argnames=["locale", "expected_locale_str"],
    argvalues=[
        (Locale("fr"), "fr"),
        (Locale("es"), "es"),
        (Locale("en", "US"), "en-US"),
        (Locale("fr", "CA"), "fr-CA"),
    ],
)
def test_request_locale_str(get_locale, locale, expected_locale_str):
    get_locale.return_value = locale
    actual_locale_str = request_locale_str()
    assert actual_locale_str == expected_locale_str
