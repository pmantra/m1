from unittest import mock

import pytest

from authn.domain import service
from authn.pytests import factories


def test_get_user(user_service):
    # Given
    user = factories.UserFactory.create()
    user_service.users.get.return_value = user
    # When
    user_from_user_service = user_service.get_user(user_id=user.id)
    # Then
    assert user == user_from_user_service


def test_get_user_by_email(user_service):
    # Given
    user = factories.UserFactory.create()
    user_service.users.get_by_email.return_value = user
    # When
    user_from_user_service = user_service.get_by_email(email=user.email)
    # Then
    assert user == user_from_user_service


def test_fetch_users(user_service):
    # Given
    user = factories.UserFactory.create()
    user_service.users.fetch.return_value = [user]
    # When
    users = user_service.fetch_users()
    # Then
    assert users == [user]


def test_get_identities(user_service):
    # When
    identities = user_service.get_identities(user_id=99)
    # Then
    assert identities == ["member"]


def test_user_create(user_service):
    # Given
    user = factories.UserFactory.create()
    # When
    with mock.patch(
        "authn.domain.service.user.UserService.notify_user_created"
    ) as notify_user_created_mock:
        user_service.create_user(email=user.email)
    # Then
    call_args = user_service.users.create.call_args.kwargs["instance"]
    assert call_args.email == user.email
    assert notify_user_created_mock.called


def test_user_update(user_service):
    # Given
    user = factories.UserFactory.create()
    user_service.users.get.return_value = user
    # When
    args = {"email": "new_email@test.com", "is_active": False}
    user = user_service.update_user(user_id=user.id, **args)
    # Then
    call_args = user_service.users.update.call_args.kwargs["instance"]
    assert call_args.email == args["email"]
    assert call_args.active == args["is_active"]


def test_user_migration_create(user_service):
    # Given
    user = factories.UserMigrationFactory.create()
    user_dict: dict = user.__dict__
    user_dict["updated_at"] = user_dict["modified_at"]
    user_dict.pop("modified_at")
    # user_dict is the original data, it simulates the raw data from the authn-api
    # When
    user_service.insert_user_data_from_authn_api(data=user_dict)
    # Then
    ret = user_service.get_user(user_id=user.id)
    assert ret is not None


def test_user_migration_update(user_service):
    # Given
    user = factories.UserMigrationFactory.create()
    user_dict: dict = user.__dict__
    user_dict["updated_at"] = user_dict["modified_at"]
    user_dict.pop("modified_at")
    # user_dict is the original data, it simulates the raw data from the authn-api
    user_service.insert_user_data_from_authn_api(data=user_dict)
    update_data = user_dict
    update_data["username"] = "test_update"
    user_dict["updated_at"] = user_dict["modified_at"]
    user_dict.pop("modified_at")
    # When
    user_service.update_user_data_from_authn_api(data=update_data)
    # Then
    ret = user_service.get_user(user_id=user.id)
    assert ret is not None


class TestNotifyUserCreated:
    @staticmethod
    def test_success(user_service):
        # Given
        user = factories.UserFactory.create(id=10, email_confirmed=False)

        # When
        # Mock database dependent functions
        with mock.patch("sqlalchemy.orm.Query.first") as query_first_mock, mock.patch(
            "health.domain.add_profile.add_profile_to_user"
        ) as add_profile_mock, mock.patch(
            "authn.resources.user.post_user_create_steps"
        ) as post_user_create_mock, mock.patch(
            "authn.resources.user.create_idp_user"
        ) as create_idp_user_mock:
            query_first_mock.return_value = {}
            user_service.notify_user_created(user_id=user.id)

        # Then
        assert add_profile_mock.called
        assert post_user_create_mock.called
        assert create_idp_user_mock.called

    @staticmethod
    def test_no_user_found(user_service):
        # Given
        # Mock database dependent functions
        with pytest.raises(service.NoUserFound), mock.patch(
            "sqlalchemy.orm.Query.first"
        ) as query_first_mock:
            query_first_mock.return_value = None

            # When/Then
            user_service.notify_user_created(user_id=10)
