from unittest import mock

from activity import models, service
from activity.pytests import factories


def test_create(
    mock_user_activity_repository,
    user_activity_service: service.UserActivityService,
    user_activity: models.UserActivity,
):
    # Given
    expected_call = mock.call(instance=user_activity)
    # When
    user_activity_service.create(
        user_id=user_activity.user_id,
        activity_type=user_activity.activity_type,
        activity_date=user_activity.activity_date,
    )
    # Then
    assert mock_user_activity_repository.create.call_args == expected_call


def test_create__deletes_old_entries(
    mock_user_activity_repository,
    user_activity_service: service.UserActivityService,
    user_activity: models.UserActivity,
):
    # Given
    existing: models.UserActivity = factories.UserActivityFactory.create(
        user_id=user_activity.user_id
    )
    mock_user_activity_repository.get_by_activity_type.return_value = [existing]

    expected_call = mock.call(instance=user_activity)
    expected_delete_call = mock.call(id=existing.id)
    # When
    user_activity_service.create(
        user_id=user_activity.user_id,
        activity_type=user_activity.activity_type,
        activity_date=user_activity.activity_date,
    )
    # Then
    assert mock_user_activity_repository.create.call_args == expected_call
    assert mock_user_activity_repository.delete.call_args == expected_delete_call


def test_get(
    mock_user_activity_repository,
    user_activity_service: service.UserActivityService,
    user_activity: models.UserActivity,
):
    # Given
    mock_user_activity_repository.get.return_value = user_activity
    # When
    fetched = user_activity_service.get(id=user_activity.id)
    # Then
    assert fetched == user_activity


def test_get__not_found(
    mock_user_activity_repository,
    user_activity_service: service.UserActivityService,
    user_activity: models.UserActivity,
):
    # Given
    mock_user_activity_repository.get.return_value = None
    # When
    fetched = user_activity_service.get(id=user_activity.id)
    # Then
    assert fetched is None


def test_get_by_activity_type(
    mock_user_activity_repository,
    user_activity_service: service.UserActivityService,
    user_activity: models.UserActivity,
):
    # Given
    mock_user_activity_repository.get_by_activity_type.return_value = [user_activity]
    # When
    fetched = user_activity_service.get_by_activity_type(
        user_id=user_activity.user_id,
        activity_type=user_activity.activity_type,
    )
    # Then
    assert len(fetched) == 1
    assert fetched[0] == user_activity


def test_get_by_activity_type__not_found(
    mock_user_activity_repository,
    user_activity_service: service.UserActivityService,
    user_activity: models.UserActivity,
):
    # Given
    mock_user_activity_repository.get_by_activity_type.return_value = None
    # When
    fetched = user_activity_service.get_by_activity_type(
        user_id=user_activity.user_id,
        activity_type=user_activity.activity_type,
    )

    assert fetched is None


def test_delete_by_user_id(
    user_activity_service: service.UserActivityService,
    created_user_activity: models.UserActivity,
):
    # Given
    # When
    rows_affected = user_activity_service.delete_by_user_id(
        user_id=created_user_activity.user_id,
    )
    # Then
    assert rows_affected == 1


def test_delete_by_user_id__not_found(
    user_activity_service: service.UserActivityService,
    created_user_activity: models.UserActivity,
):
    # Given
    # When
    rows_affected = user_activity_service.delete_by_user_id(
        user_id=created_user_activity.user_id + 1,
    )
    # Then
    assert rows_affected == 0


def test_get_last_login_date(
    mock_user_activity_repository,
    user_activity_service: service.UserActivityService,
    user_activity: models.UserActivity,
):
    # Given
    mock_user_activity_repository.get_by_activity_type.return_value = [user_activity]
    # When
    last_login_date = user_activity_service.get_last_login_date(
        user_id=user_activity.user_id,
    )
    # Then
    assert last_login_date == user_activity.activity_date.date()


def test_get_last_login_date__no_last_login(
    mock_user_activity_repository,
    user_activity_service: service.UserActivityService,
    user_activity: models.UserActivity,
):
    # Given
    mock_user_activity_repository.get_by_activity_type.return_value = None
    # When
    last_login_date = user_activity_service.get_last_login_date(
        user_id=user_activity.user_id,
    )
    # Then
    assert last_login_date is None
