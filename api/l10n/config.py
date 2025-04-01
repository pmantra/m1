import pycountry
from babel import Locale
from flask import Flask, has_request_context, request
from flask_babel import Babel
from maven import feature_flags
from werkzeug.datastructures import LanguageAccept
from werkzeug.http import parse_accept_header

from utils.log import logger

log = logger(__name__)

CUSTOM_LOCALE_HEADER = "X-Maven-User-Locale"
DEFAULT_LOCALE = "en"
DEFAULT_LOCALE_FLAG_OFF = "en-US"
SUPPORTED_LOCALES = ["en", "en-US", "es", "fr", "fr-CA"]
TRANSLATION_SOURCES = [
    {"directory": "geography/translations", "domain": "messages"},
    {"directory": "messaging/translations", "domain": "messages"},
    {"directory": "models/tracks/translations", "domain": "messages"},
    {"directory": "models/translations", "domain": "messages"},
    {"directory": "utils/translations", "domain": "messages"},
    {"directory": pycountry.LOCALES_DIR, "domain": "iso3166-1"},
    {"directory": pycountry.LOCALES_DIR, "domain": "iso3166-2"},
    {"directory": "appointments/translations", "domain": "messages"},
    {"directory": "l10n/db_strings/translations", "domain": "answers"},
    {"directory": "l10n/db_strings/translations", "domain": "languages"},
    {"directory": "l10n/db_strings/translations", "domain": "need_categories"},
    {"directory": "l10n/db_strings/translations", "domain": "needs"},
    {"directory": "l10n/db_strings/translations", "domain": "providers"},
    {"directory": "l10n/db_strings/translations", "domain": "questionnaires"},
    {"directory": "l10n/db_strings/translations", "domain": "questions"},
    {"directory": "l10n/db_strings/translations", "domain": "specialties"},
    {"directory": "l10n/db_strings/translations", "domain": "verticals"},
    {"directory": "direct_payment/payments/translations", "domain": "messages"},
    {"directory": "wallet/translations", "domain": "messages"},
    {"directory": "tasks/translations", "domain": "messages"},
    {"directory": "views/translations", "domain": "messages"},
]


def negotiate_locale() -> str:
    if not has_request_context():
        log.info("Attempt to negotiate locale outside of request context")
        return DEFAULT_LOCALE

    custom_header_locale = parse_accept_header(
        request.headers.get(CUSTOM_LOCALE_HEADER), LanguageAccept
    ).best_match(matches=SUPPORTED_LOCALES)

    if custom_header_locale:
        return custom_header_locale

    accept_languages_locale = request.accept_languages.best_match(
        matches=SUPPORTED_LOCALES, default=DEFAULT_LOCALE
    )

    return accept_languages_locale


def _negotiate_locale_wrapper() -> Locale:
    """Use flask_babel.get_locale() to get the locale that this function determined"""
    localization_enabled = feature_flags.bool_variation(
        "release-mono-api-localization",
        default=False,
    )

    locale = DEFAULT_LOCALE if localization_enabled else DEFAULT_LOCALE_FLAG_OFF

    if localization_enabled:
        try:
            locale = negotiate_locale()
        except Exception as e:
            log.exception("Error negotiating locale for locale", exception=e)

    return Locale.parse(locale, sep="-")


def register_babel(app: Flask) -> Babel:
    return Babel(
        app,
        locale_selector=_negotiate_locale_wrapper,
        default_translation_directories=";".join(
            [t["directory"] for t in TRANSLATION_SOURCES]
        ),
        default_domain=";".join([t["domain"] for t in TRANSLATION_SOURCES]),
    )
