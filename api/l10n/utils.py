from __future__ import annotations

import flask_babel
import pycountry
from babel import Locale, get_locale_identifier
from flask_babel import get_locale
from maven import feature_flags

from authn.models.user import User
from l10n.config import DEFAULT_LOCALE
from user_locale.services.locale_preference_service import LocalePreferenceService
from utils.log import logger

log = logger(__name__)


def localization_is_enabled() -> bool:
    return feature_flags.bool_variation(
        "release-mono-api-localization",
        default=False,
    )


def get_locale_from_member_preference(user: User) -> Locale | None:
    return LocalePreferenceService.get_preferred_locale_for_user(user)


def generate_locale(user: User) -> str:
    if localization_is_enabled() and user:
        member_locale = get_locale_from_member_preference(user)
        return member_locale if member_locale else DEFAULT_LOCALE

    return DEFAULT_LOCALE


def message_with_enforced_locale(user: User, text_key: str) -> str:
    locale = generate_locale(user)
    with flask_babel.force_locale(locale):
        return flask_babel.gettext(text_key)


def locale_to_alpha_3(_locale: Locale) -> str:
    """
    Transforms a given locale into an alpha3 abbreviation

    NOTE: alpha3 abbreviations can also be used for iso-639-3, as they are roughly
    equivalent. Source: https://en.wikipedia.org/wiki/ISO_639-3 - "ISO 639-3 extends
    the ISO 639-2 alpha-3 codes"

    Raises:
        LookupError: if there is an error looking up the locale in pycountry
    """
    try:
        alpha_2 = _locale.language
        alpha_3: str = pycountry.languages.get(alpha_2=alpha_2).alpha_3
    except LookupError as e:
        log.error(
            "Error looking up locale",
            alpha_2=alpha_2,
        )
        raise e

    return alpha_3


def is_default_langauge() -> bool:
    """Whether the app is running in the default language (irrespective of region)"""
    return get_locale().language == Locale.parse(DEFAULT_LOCALE, sep="-").language


def request_locale_str() -> str:
    """The string representation of the current locale, to be used for passing in headers, cache keys, or logs"""
    locale = get_locale()
    return get_locale_identifier((locale.language, locale.territory), sep="-")
