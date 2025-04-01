from unittest import mock

from preferences import models, service
from preferences.pytests import factories


def test_create(
    mock_preference_repository,
    preference_service: service.PreferenceService,
    preference: models.Preference,
):
    # Given
    expected_call = mock.call(instance=preference)
    # When
    preference_service.create(
        name=preference.name,
        default_value=preference.default_value,
        type=preference.type,
    )
    # Then
    assert mock_preference_repository.create.call_args == expected_call


def test_get(
    mock_preference_repository,
    preference_service: service.PreferenceService,
    preference: models.Preference,
):
    # Given
    mock_preference_repository.get.return_value = preference
    # When
    fetched_preference = preference_service.get(id=preference.id)
    # Then
    assert fetched_preference == preference


def test_get_not_found(
    mock_preference_repository,
    preference_service: service.PreferenceService,
    preference: models.Preference,
):
    # Given
    mock_preference_repository.get.return_value = None
    # When
    fetched_preference = preference_service.get(id=preference.id)
    # Then
    assert fetched_preference is None


def test_get_by_name(
    mock_preference_repository,
    preference_service: service.PreferenceService,
    preference: models.Preference,
):
    # Given
    mock_preference_repository.get_by_name.return_value = preference
    # When
    fetched_preference = preference_service.get_by_name(name=preference.name)
    # Then
    assert fetched_preference == preference


def test_get_by_name_not_found(
    mock_preference_repository,
    preference_service: service.PreferenceService,
    preference: models.Preference,
):
    # Given
    mock_preference_repository.get_by_name.return_value = None
    # When
    fetched_preference = preference_service.get_by_name(name=preference.name)
    # Then
    assert fetched_preference is None


def test_get_value_no_type(
    mock_preference_repository,
    preference_service: service.PreferenceService,
):
    # Given
    preference = factories.PreferenceFactory.create(type=None, default_value="true")
    mock_preference_repository.get.return_value = preference
    # When
    fetched_value = preference_service.get_value(id=preference.id, value=None)
    # Then
    assert fetched_value == "true"


def test_get_value_no_default_value(
    mock_preference_repository,
    preference_service: service.PreferenceService,
):
    # Given
    preference = factories.PreferenceFactory.create(type="str", default_value=None)
    mock_preference_repository.get.return_value = preference
    # When
    fetched_value = preference_service.get_value(id=preference.id, value=None)
    # Then
    assert fetched_value is None


def test_get_value_bool_default_value(
    mock_preference_repository,
    preference_service: service.PreferenceService,
):
    # Given
    preference = factories.PreferenceFactory.create(type="bool", default_value="true")
    mock_preference_repository.get.return_value = preference
    # When
    fetched_value = preference_service.get_value(id=preference.id, value=None)
    # Then
    assert fetched_value is True


def test_get_value_bool_given_value(
    mock_preference_repository,
    preference_service: service.PreferenceService,
):
    # Given
    preference = factories.PreferenceFactory.create(type="bool", default_value="false")
    mock_preference_repository.get.return_value = preference
    # When
    fetched_value = preference_service.get_value(id=preference.id, value="true")
    # Then
    assert fetched_value is True


def test_get_value_str_default_value(
    mock_preference_repository,
    preference_service: service.PreferenceService,
):
    # Given
    preference = factories.PreferenceFactory.create(type="str", default_value="true")
    mock_preference_repository.get.return_value = preference
    # When
    fetched_value = preference_service.get_value(id=preference.id, value=None)
    # Then
    assert fetched_value == "true"


def test_get_value_str_given_value(
    mock_preference_repository,
    preference_service: service.PreferenceService,
):
    # Given
    preference = factories.PreferenceFactory.create(type="str", default_value="true")
    mock_preference_repository.get.return_value = preference
    # When
    fetched_value = preference_service.get_value(id=preference.id, value="foo")
    # Then
    assert fetched_value == "foo"


def test_get_value_int_default_value(
    mock_preference_repository,
    preference_service: service.PreferenceService,
):
    # Given
    preference = factories.PreferenceFactory.create(type="int", default_value="42")
    mock_preference_repository.get.return_value = preference
    # When
    fetched_value = preference_service.get_value(id=preference.id, value=None)
    # Then
    assert fetched_value == 42


def test_get_value_int_given_value(
    mock_preference_repository,
    preference_service: service.PreferenceService,
):
    # Given
    preference = factories.PreferenceFactory.create(type="int", default_value="42")
    mock_preference_repository.get.return_value = preference
    # When
    fetched_value = preference_service.get_value(id=preference.id, value="24")
    # Then
    assert fetched_value == 24


def test_get_value_unknown_type_default_value(
    mock_preference_repository,
    preference_service: service.PreferenceService,
):
    # Given
    preference = factories.PreferenceFactory.create(type="foo", default_value="42")
    mock_preference_repository.get.return_value = preference
    # When
    fetched_value = preference_service.get_value(id=preference.id, value=None)
    # Then
    assert fetched_value == "42"


def test_get_value_unknown_type_given_value(
    mock_preference_repository,
    preference_service: service.PreferenceService,
):
    # Given
    preference = factories.PreferenceFactory.create(type="foo", default_value="42")
    mock_preference_repository.get.return_value = preference
    # When
    fetched_value = preference_service.get_value(id=preference.id, value="24")
    # Then
    assert fetched_value == "24"
