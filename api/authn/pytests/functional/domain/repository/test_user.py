import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from authn.domain import model, repository
from authn.pytests import factories


class TestUserRepository:
    def test_fetch(self, user_repository: repository.UserRepository, created_user):
        # Given
        expected_users = [created_user]
        # When
        fetched = user_repository.fetch()
        # Then
        assert fetched == expected_users

    def test_fetch_with_time_range(
        self, user_repository: repository.UserRepository, created_user
    ):
        # Given
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        # When
        fetched = user_repository.get_all_by_time_range(end=tomorrow, start=yesterday)
        # Then
        assert fetched[0] == created_user

    def test_fetch_with_email(
        self, user_repository: repository.UserRepository, created_user
    ):
        # Given
        expected_users = [created_user]
        # When
        fetched = user_repository.fetch(filters={"email": created_user.email})
        # Then
        assert fetched == expected_users

    def test_fetch_with_email_none(
        self, user_repository: repository.UserRepository, created_user
    ):
        # Given
        missing_email = f"{created_user.email}999999"
        # When
        fetched = user_repository.fetch(filters={"email": missing_email})
        # Then
        assert fetched == []

    def test_fetch_with_email_like(
        self, user_repository: repository.UserRepository, created_user
    ):
        # Given
        expected_users = [created_user]
        partial_email = created_user.email[:3]
        # When
        fetched = user_repository.fetch(filters={"email_like": f"{partial_email}%"})
        # Then
        assert fetched == expected_users

    def test_fetch_with_email_like_none(
        self, user_repository: repository.UserRepository, created_user
    ):
        # Given
        missing_email = f"99999999{created_user.email}"
        # When
        fetched = user_repository.fetch(filters={"email_like": f"{missing_email}%"})
        # Then
        assert fetched == []

    def test_fetch_with_unavailable_filter(self, user_repository):
        with pytest.raises(repository.user.UserRepositoryError):
            user_repository.fetch(filters={"zzzzz": "aaaa"})

    def test_create(self, user_repository: repository.UserRepository):
        # Given
        user: model.User = factories.UserFactory.create()
        input = dict(
            email=user.email,
            password=user.password,
            first_name=user.first_name,
            last_name=user.last_name,
            username=user.username,
            email_confirmed=user.email_confirmed,
            active=user.active,
        )
        # When
        created: model.User = user_repository.create(instance=user)
        output = {f: getattr(created, f) for f in input}
        # Then
        assert created.id and created.created_at and created.modified_at
        assert created.first_name and created.last_name
        assert output == input

    def test_update(
        self,
        user_repository: repository.UserRepository,
        created_user: model.User,
        faker,
    ):
        # Given
        new_email = faker.email()
        user = dataclasses.replace(created_user, email=new_email)
        # When
        updated = user_repository.update(instance=user)
        # Then
        assert updated.email == new_email

    def test_get(
        self, user_repository: repository.UserRepository, created_user: model.User
    ):
        # NOTE: this is implicitly tested by the mutation tests above, but we're going to explicitly test it.
        # Given
        user_id = created_user.id
        # When
        fetched = user_repository.get(id=user_id)
        # Then
        assert fetched == created_user

    def test_get_not_found(self, user_repository: repository.UserRepository):
        # Given
        user_id = 1
        # When
        fetched = user_repository.get(id=user_id)
        # Then
        assert fetched is None

    def test_delete(
        self, user_repository: repository.UserRepository, created_user: model.User
    ):
        # Given
        user_id = created_user.id
        # When
        count = user_repository.delete(id=user_id)
        fetched = user_repository.get(id=user_id)
        # Then
        assert count == 1 and fetched is None

    def test_get_by_email(
        self, user_repository: repository.UserRepository, created_user
    ):
        # Given
        email = created_user.email
        # When
        fetched = user_repository.get_by_email(email=email)
        # Then
        assert fetched == created_user

    def test_get_by_email_not_found(
        self, user_repository: repository.UserRepository, faker
    ):
        # Given
        email = faker.email()
        # When
        fetched = user_repository.get_by_email(email=email)
        # Then
        assert fetched is None

    def test_get_all_by_ids(
        self, user_repository: repository.UserRepository, created_user
    ):
        # Given
        user_id = created_user.id
        # When
        fetched = user_repository.get_all_by_ids(ids=[user_id])
        # Then
        assert fetched[0] == created_user

    def test_get_all_by_ids_not_found(self, user_repository: repository.UserRepository):
        # Given
        out_of_range_id = 999999999999
        # When
        fetched = user_repository.get_all_by_ids(ids=[out_of_range_id])
        # Then
        assert fetched == []

    def test_get_all_without_auth(
        self, user_repository: repository.UserRepository, created_user
    ):
        # Given
        user_ids = [created_user.id]
        # When
        fetched = user_repository.get_all_without_auth(user_ids=user_ids)
        # Then
        assert fetched == [created_user.id]

    def test_get_all_without_auth_none_found(
        self,
        user_repository: repository.UserRepository,
        created_user_auth,
    ):
        # Given
        user_ids = [created_user_auth.user_id]
        # When
        fetched = user_repository.get_all_without_auth(user_ids=user_ids)
        # Then
        assert fetched == []
