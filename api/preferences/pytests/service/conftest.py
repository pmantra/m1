from unittest import mock

import pytest

from preferences import service
from preferences.pytests import factories


@pytest.fixture
def mock_preference_repository():
    with mock.patch(
        "preferences.repository.preference.PreferenceRepository",
        autospec=True,
        spec_set=True,
    ) as mock_repo, mock.patch(
        "preferences.service.preference.repository.PreferenceRepository",
        new=mock_repo,
    ):
        yield mock_repo.return_value


@pytest.fixture
def mock_member_preferences_repository():
    with mock.patch(
        "preferences.repository.member_preference.MemberPreferencesRepository",
        autospec=True,
        spec_set=True,
    ) as mock_repo, mock.patch(
        "preferences.service.member_preference.repository.MemberPreferencesRepository",
        new=mock_repo,
    ):
        yield mock_repo.return_value


@pytest.fixture
def member_preferences_service():
    return service.MemberPreferencesService()


@pytest.fixture
def preference_service():
    return service.PreferenceService()


@pytest.fixture
def preference():
    return factories.PreferenceFactory.create()


@pytest.fixture
def member_preference():
    preference = factories.PreferenceFactory.create()
    return factories.MemberPreferenceFactory.create_with_preference(
        preference=preference,
    )
