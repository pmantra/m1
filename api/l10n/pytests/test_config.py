from unittest import mock

import pytest
from babel import Locale, support
from maven.feature_flags import test_data

from l10n.config import (
    CUSTOM_LOCALE_HEADER,
    DEFAULT_LOCALE,
    DEFAULT_LOCALE_FLAG_OFF,
    _negotiate_locale_wrapper,
    negotiate_locale,
    register_babel,
)


@pytest.mark.parametrize(
    "x_maven_user_locale_header, accept_languages_header, expected",
    [
        (None, None, DEFAULT_LOCALE),
        ("en-US", None, "en-US"),
        (None, "en-GB", "en"),
        (None, "en-US", "en-US"),
        (None, "es", "es"),
        (None, "fr-CH", "fr"),
        (None, "fr-CA", "fr-CA"),
        (None, "fr-CH, fr;q=0.9, es;q=0.8", "fr"),
        # Equally weighted values in the Accept-Languages header will resolve
        # to the first match found in SUPPORTED_LOCALES ("es" is defined before "fr")
        (None, "fr, es", "es"),
        (None, "fr;q=0.2, es;q=0.1", "fr"),
        ("fr", "es", "fr"),
        ("de", "fr", "fr"),
        ("de", "de", DEFAULT_LOCALE),
        ("en-US", "en", "en-US"),
    ],
)
def test_negotiate_locale(
    app, x_maven_user_locale_header, accept_languages_header, expected
):
    headers = {
        CUSTOM_LOCALE_HEADER: x_maven_user_locale_header,
        "Accept-Language": accept_languages_header,
    }
    with app.test_request_context("/test", headers=headers):
        result = negotiate_locale()

    assert result == expected


def test_negotiate_locale_wrapper_returns_default_when_flag_disabled():
    with test_data() as td:
        td.update(td.flag("release-mono-api-localization").variation_for_all(False))

        result = _negotiate_locale_wrapper()

    assert result == Locale.parse(DEFAULT_LOCALE_FLAG_OFF, sep="-")


def test_negotiate_locale_wrapper_returns_negotiate_locale_when_flag_enabled():
    negotiated_locale = "fr"

    with test_data() as td, mock.patch(
        "l10n.config.negotiate_locale", return_value=negotiated_locale
    ):
        td.update(td.flag("release-mono-api-localization").variation_for_all(True))

        result = _negotiate_locale_wrapper()

    assert result == Locale.parse(negotiated_locale)


def test_negotiate_locale_wrapper_returns_default_on_exception():
    with test_data() as td, mock.patch(
        "l10n.config.negotiate_locale"
    ) as mock_negotiate_locale:
        td.update(td.flag("release-mono-api-localization").variation_for_all(True))
        mock_negotiate_locale.side_effect = Exception

        result = _negotiate_locale_wrapper()

    assert result == Locale.parse(DEFAULT_LOCALE)


@pytest.mark.parametrize(
    "negotiated_locale, expected",
    [
        ("en", Locale.parse("en")),
        ("es", Locale.parse("es")),
        ("fr", Locale.parse("fr")),
        ("fr-CA", Locale.parse("fr_CA")),
    ],
)
def test_negotiate_locale_wrapper_returns_valid_locale(negotiated_locale, expected):
    with test_data() as td, mock.patch(
        "l10n.config.negotiate_locale", return_value=negotiated_locale
    ):
        td.update(td.flag("release-mono-api-localization").variation_for_all(True))

        result = _negotiate_locale_wrapper()

    assert result == expected


def test_negotiate_locale_returns_default_outside_of_request():
    assert negotiate_locale() == DEFAULT_LOCALE


def test_unique_translation_keys(app):
    babel = register_babel(app)

    all_keys = []
    for index, dirname in enumerate(babel.domain_instance.translation_directories):
        domain = babel.domain_instance.domain[index]

        catalog = support.Translations.load(dirname, ["en"], domain)

        all_keys.extend(list(catalog._catalog.keys()))

    duplicate_keys = [
        (key, all_keys.count(key))
        for key in set(all_keys)
        if all_keys.count(key) > 1 and key != ""
    ]

    assert (
        duplicate_keys == []
    ), f"Found duplicate keys, which could lead to nondeterministic translations: {duplicate_keys}"


def test_en_and_en_us_always_equal(app):
    babel = register_babel(app)
    for index, dirname in enumerate(babel.domain_instance.translation_directories):
        domain = babel.domain_instance.domain[index]

        en_catalog = support.Translations.load(dirname, [Locale.parse("en")], domain)
        en_us_catalog = support.Translations.load(
            dirname, [Locale.parse("en-US", "-")], domain
        )

        for key in [key for key in en_catalog._catalog.keys()]:
            assert en_catalog._catalog[key] == en_us_catalog._catalog[key]
