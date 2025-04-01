from __future__ import annotations

from dataclasses import asdict, dataclass

from babel import get_locale_identifier
from flask import request

from common.services.api import AuthenticatedResource
from user_locale.services.locale_preference_service import LocalePreferenceService


@dataclass
class UserLocaleResponse:
    locale: str | None


class UserLocaleResource(AuthenticatedResource):
    def get(self, user_id: int) -> dict[str, str | None]:
        locale = LocalePreferenceService.get_preferred_locale_for_user(user=self.user)
        locale_str = (
            get_locale_identifier((locale.language, locale.territory), "-")
            if locale
            else None
        )
        return asdict(UserLocaleResponse(locale=locale_str))

    def put(self, user_id: int) -> dict[str, str | None]:
        args = request.json if request.is_json else {}
        locale_str = args.get("locale")
        locale_stored = LocalePreferenceService.update_preferred_locale_for_user(
            user=self.user, locale_str=locale_str
        )
        return asdict(UserLocaleResponse(locale=locale_stored))
