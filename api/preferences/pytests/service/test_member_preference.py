import dataclasses
from unittest import mock

import pytest

from preferences import models, service
from preferences.pytests import factories


def test_create(
    mock_member_preferences_repository,
    member_preferences_service: service.MemberPreferencesService,
    member_preference: models.MemberPreference,
):
    # Given
    expected_call = mock.call(instance=member_preference)
    # When
    member_preferences_service.create(
        member_id=member_preference.member_id,
        preference_id=member_preference.preference_id,
        value=member_preference.value,
    )
    # Then
    assert mock_member_preferences_repository.create.call_args == expected_call


def test_get(
    mock_member_preferences_repository,
    member_preferences_service: service.MemberPreferencesService,
    member_preference: models.MemberPreference,
):
    # Given
    mock_member_preferences_repository.get.return_value = member_preference
    # When
    fetched = member_preferences_service.get(id=member_preference.id)
    # Then
    assert fetched == member_preference


def test_get_not_found(
    mock_member_preferences_repository,
    member_preferences_service: service.MemberPreferencesService,
    member_preference: models.MemberPreference,
):
    # Given
    mock_member_preferences_repository.get.return_value = None
    # When
    fetched = member_preferences_service.get(id=member_preference.id)
    # Then
    assert fetched is None


def test_get_member_preferences(
    mock_member_preferences_repository,
    member_preferences_service: service.MemberPreferencesService,
    member_preference: models.MemberPreference,
):
    # Given
    mock_member_preferences_repository.get_by_member_id.return_value = [
        member_preference
    ]
    # When
    fetched = member_preferences_service.get_member_preferences(
        member_id=member_preference.member_id
    )
    # Then
    assert fetched == [member_preference]


def test_get_by_preference_name(
    mock_member_preferences_repository,
    member_preferences_service: service.MemberPreferencesService,
):
    # Given
    preference = factories.PreferenceFactory.create()
    member_preference = factories.MemberPreferenceFactory.create_with_preference(
        preference=preference,
    )
    mock_member_preferences_repository.get_by_preference_name.return_value = (
        member_preference
    )
    # When
    fetched = member_preferences_service.get_by_preference_name(
        member_id=member_preference.member_id,
        preference_name=preference.name,
    )
    # Then
    assert fetched == member_preference


def test_get_by_preference_name_not_found(
    mock_member_preferences_repository,
    member_preferences_service: service.MemberPreferencesService,
):
    # Given
    preference = factories.PreferenceFactory.create()
    member_preference = factories.MemberPreferenceFactory.create_with_preference(
        preference=preference,
    )
    mock_member_preferences_repository.get_by_preference_name.return_value = None
    # When
    member_pref = member_preferences_service.get_by_preference_name(
        member_id=member_preference.member_id,
        preference_name=preference.name,
    )

    assert member_pref is None


def test_update_value(
    mock_member_preferences_repository,
    member_preferences_service: service.MemberPreferencesService,
    member_preference: models.MemberPreference,
    faker,
):
    # Given
    new_value = faker.word()
    mock_member_preferences_repository.get.return_value = member_preference
    expected_instance = dataclasses.replace(member_preference, value=new_value)
    expected_call = mock.call(instance=expected_instance)
    # When
    member_preferences_service.update_value(
        id=member_preference.id,
        value=new_value,
    )
    # Then
    assert mock_member_preferences_repository.update.call_args == expected_call


def test_update_value_not_found(
    mock_member_preferences_repository,
    member_preferences_service: service.MemberPreferencesService,
    member_preference: models.MemberPreference,
    faker,
):
    # Given
    new_value = faker.word()
    mock_member_preferences_repository.get.return_value = None
    # When/Then
    with pytest.raises(service.MemberPreferenceNotFoundError):
        member_preferences_service.update_value(
            id=member_preference.id,
            value=new_value,
        )


def test_get_value(
    mock_member_preferences_repository,
    mock_preference_repository,
    member_preferences_service: service.MemberPreferencesService,
):
    # Given
    preference = factories.PreferenceFactory.create(type="str", default_value="DEFAULT")
    member_preference = factories.MemberPreferenceFactory.create_with_preference(
        preference=preference,
        value="VALUE",
    )
    mock_member_preferences_repository.get.return_value = member_preference
    mock_preference_repository.get.return_value = preference

    # When
    fetched_value = member_preferences_service.get_value(id=member_preference.id)

    # Then
    assert fetched_value == "VALUE"


def test_get_value_not_found(
    mock_member_preferences_repository,
    member_preferences_service: service.MemberPreferencesService,
):
    # Given
    preference = factories.PreferenceFactory.create()
    member_preference = factories.MemberPreferenceFactory.create_with_preference(
        preference=preference,
    )
    mock_member_preferences_repository.get.return_value = None

    # When
    fetched_value = member_preferences_service.get_value(id=member_preference.id)

    # Then
    assert fetched_value is None
