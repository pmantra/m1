from unittest.mock import patch

from authn.domain import model
from preferences import models
from preferences.pytests.factories import PreferenceFactory
from preferences.tasks.sync_email_preferences import get_rows_with_unsubscribe_email


def test_no_update_if_email_does_not_match_user(faker):
    with patch("braze.client.BrazeClient.get_unsubscribes") as mock_braze:
        mock_braze.return_value = [faker.email()]

        preference = PreferenceFactory.create()
        rows = get_rows_with_unsubscribe_email(preference)

        assert len(rows) == 0


def test_get_correct_update_data(
    created_member: model.User,
    created_preference: models.Preference,
    created_member_preference: models.MemberPreference,
):
    with patch("braze.client.BrazeClient.get_unsubscribes") as mock_braze, patch(
        "preferences.service.MemberPreferencesService.get_by_preference_name"
    ) as mock_member_preference_get, patch(
        "authn.domain.repository.UserRepository.get_by_email"
    ) as mock_user_repo:
        mock_braze.return_value = [
            created_member.email,
        ]

        mock_user_repo.return_value = created_member
        mock_member_preference_get.return_value = created_member_preference
        rows = get_rows_with_unsubscribe_email(created_preference)

        assert len(rows) == 1
        assert mock_member_preference_get.called
        assert (created_member_preference.id, created_member.email) == (
            rows[0].member_preference_id,
            rows[0].email,
        )
