import random
import string
from unittest import mock

import pytest

from authn.domain import model
from preferences import models, repository
from preferences.pytests.factories import MemberPreferenceFactory, PreferenceFactory


@pytest.fixture
def created_member(factories) -> model.User:
    user: model.User = factories.EnterpriseUserFactory.create()
    return user


@pytest.fixture
def preference_repository(session) -> repository.PreferenceRepository:
    return repository.PreferenceRepository(session=session)


@pytest.fixture
def created_preference(
    preference_repository: repository.PreferenceRepository,
) -> models.Preference:
    random_suffix = "".join(random.choices(string.ascii_letters + string.digits, k=9))
    created: models.Preference = preference_repository.create(
        instance=models.Preference(
            name="PREFERENCE" + random_suffix,
            default_value="DEFAULT",
            type="str",
        )
    )
    return created


@pytest.fixture
def member_preferences_repository(session) -> repository.MemberPreferencesRepository:
    return repository.MemberPreferencesRepository(session=session)


@pytest.fixture
def created_member_preference(
    member_preferences_repository: repository.MemberPreferencesRepository,
    created_member: model.User,
    created_preference: models.Preference,
) -> models.MemberPreference:
    created: models.MemberPreference = member_preferences_repository.create(
        instance=models.MemberPreference(
            value="VALUE",
            member_id=created_member.id,
            preference_id=created_preference.id,
        )
    )
    return created


@pytest.fixture
def mock_preference_service():
    with mock.patch(
        "preferences.service.PreferenceService", autospec=True, spec_set=True
    ) as m:
        yield m.return_value


@pytest.fixture
def preference():
    return PreferenceFactory.create()


@pytest.fixture
def member_preference_true(preference):
    return MemberPreferenceFactory.create_with_preference(preference, value=str(True))


@pytest.fixture
def member_preference_false(preference):
    return MemberPreferenceFactory.create_with_preference(preference, value=str(False))


@pytest.fixture
def mock_preference_service_with_preference(mock_preference_service, preference):
    mock_preference_service.get_by_name.return_value = preference
    return mock_preference_service


@pytest.fixture
def mock_preference_service_without_preference(mock_preference_service):
    mock_preference_service.get_by_name.return_value = None
    mock_preference_service.create.return_value = PreferenceFactory.create()
    return mock_preference_service


@pytest.fixture
def mock_member_preferences_service():
    with mock.patch(
        "preferences.service.MemberPreferencesService", autospec=True, spec_set=True
    ) as m:
        yield m.return_value


@pytest.fixture
def mock_member_preference_service_with_true_preference(
    mock_member_preferences_service, member_preference_true
):
    mock_member_preferences_service.get_by_preference_name.return_value = (
        member_preference_true
    )
    mock_member_preferences_service.get_value.return_value = True
    return mock_member_preferences_service


@pytest.fixture
def mock_member_preference_service_with_false_preference(
    mock_member_preferences_service, member_preference_false
):
    mock_member_preferences_service.get_by_preference_name.return_value = (
        member_preference_false
    )
    mock_member_preferences_service.get_value.return_value = False
    return mock_member_preferences_service


@pytest.fixture
def mock_member_preference_service_without_preference(
    mock_member_preferences_service, member_preference_false
):
    mock_member_preferences_service.get_by_preference_name.return_value = None
    return mock_member_preferences_service
