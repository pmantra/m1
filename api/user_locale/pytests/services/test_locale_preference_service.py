from unittest.mock import patch

from babel import Locale

from pytests import factories
from user_locale.services.locale_preference_service import LocalePreferenceService


class TestLocalePreferenceService:
    def test_get_preferred_locale_for_user_en(self):
        user = factories.DefaultUserFactory.create(id=123)
        factories.UserLocalePreferenceFactory.create(user_id=user.id, locale="en")
        locale = LocalePreferenceService.get_preferred_locale_for_user(user=user)
        assert locale == Locale("en")

    def test_get_preferred_locale_for_user_en_US(self):
        user = factories.DefaultUserFactory.create(id=123)
        factories.UserLocalePreferenceFactory.create(user_id=user.id, locale="en-US")
        locale = LocalePreferenceService.get_preferred_locale_for_user(user=user)
        assert locale == Locale("en", "US")

    def test_get_preferred_locale_for_user_fr(self):
        user = factories.DefaultUserFactory.create(id=123)
        factories.UserLocalePreferenceFactory.create(user_id=user.id, locale="fr")
        locale = LocalePreferenceService.get_preferred_locale_for_user(user=user)
        assert locale == Locale("fr")

    def test_get_preferred_locale_for_user_not_found(self):
        user = factories.DefaultUserFactory.create(id=123)
        locale = LocalePreferenceService.get_preferred_locale_for_user(user=user)
        assert locale == None

    @patch("utils.braze.track_user_locale")
    def test_update_preferred_locale_for_user_insert(
        self, mock_braze_track_user_locale
    ):
        user = factories.DefaultUserFactory.create(id=123)
        factories.UserLocalePreferenceFactory.create(user_id=user.id, locale="en")
        initial_locale = LocalePreferenceService.get_preferred_locale_for_user(
            user=user
        )
        assert initial_locale == Locale("en")
        LocalePreferenceService.update_preferred_locale_for_user(
            user=user, locale_str="es"
        )
        updated_locale = LocalePreferenceService.get_preferred_locale_for_user(
            user=user
        )
        assert updated_locale == Locale("es")
        # then braze.track_user is called
        mock_braze_track_user_locale.assert_called_once_with(user, "es")

    @patch("utils.braze.track_user_locale")
    def test_update_preferred_locale_for_user_update(
        self, mock_braze_track_user_locale
    ):
        user = factories.DefaultUserFactory.create(id=123)
        initial_locale = LocalePreferenceService.get_preferred_locale_for_user(
            user=user
        )
        assert initial_locale == None
        LocalePreferenceService.update_preferred_locale_for_user(
            user=user, locale_str="es"
        )
        updated_locale = LocalePreferenceService.get_preferred_locale_for_user(
            user=user
        )
        assert updated_locale == Locale("es")
        # then braze.track_user is called
        mock_braze_track_user_locale.assert_called_once_with(user, "es")
