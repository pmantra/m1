from __future__ import annotations

from babel import Locale
from flask import abort

from authn.models.user import User
from storage.connection import db
from user_locale.models.user_locale_preference import UserLocalePreference
from utils import braze
from utils.log import logger

log = logger(__name__)


SUPPORTED_LOCALES_SET = {
    "en",
    "en-US",
    "es",
    "fr",
    "fr-CA",
}


def is_locale_supported(locale_str: str) -> bool:
    return locale_str in SUPPORTED_LOCALES_SET


class LocalePreferenceService:
    @staticmethod
    def get_preferred_locale_for_user(user: User) -> Locale | None:
        locale_preference = (
            db.session.query(UserLocalePreference)
            .filter(UserLocalePreference.user_id == user.id)
            .one_or_none()
        )
        if locale_preference == None:
            return None
        locale_string: str = locale_preference.locale
        try:
            locale = Locale.parse(locale_string, "-")
        except Exception as e:
            log.exception("Error fetching locale", exception=e)
            locale = None
        log.info(f"User locale fetched: user_id={user.id}, locale={locale}")
        return locale

    @staticmethod
    def update_preferred_locale_for_user(user: User, locale_str: str) -> str:
        if not is_locale_supported(locale_str):
            abort(400, f"Locale {locale_str} not supported.")
        try:
            current_locale_preference = (
                db.session.query(UserLocalePreference)
                .filter(UserLocalePreference.user_id == user.id)
                .one_or_none()
            )
            if current_locale_preference:
                # Update existing locale
                current_locale_preference.locale = locale_str
            else:
                # Create a new locale preference
                new_locale_preference = UserLocalePreference(
                    user_id=user.id, locale=locale_str
                )
                db.session.add(new_locale_preference)

            db.session.commit()
            braze.track_user_locale(user, locale_str)
        except Exception as e:
            log.exception("Error parsing locale", exception=e)
            abort(400, "Something went wrong, please try again.")
        log.info(f"User locale updated: user_id={user.id}, locale={locale_str}")
        return locale_str
