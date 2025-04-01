from datetime import datetime, timedelta, timezone

from authn.domain import model, repository
from authn.pytests import factories


class TestUserAuthRepository:
    def test_create(
        self, user_auth_repository: repository.UserAuthRepository, created_user
    ):
        # Given
        user_id = created_user.id
        external_id = "auth0|abcd1234"
        user_auth: model.UserAuth = factories.UserAuthFactory.create(
            user_id=user_id, external_id=external_id
        )
        # When
        created = user_auth_repository.create(instance=user_auth)
        # Then
        assert created.user_id == user_id
        assert created.external_id == external_id

    def test_get(
        self,
        user_auth_repository: repository.UserAuthRepository,
        created_user_auth: model.UserAuth,
    ):
        # Given
        auth_id = created_user_auth.id
        # When
        fetched = user_auth_repository.get(id=auth_id)
        # Then
        assert fetched == created_user_auth

    def test_get_by_range(
        self,
        user_auth_repository: repository.UserAuthRepository,
        created_user_auth: model.UserAuth,
    ):
        # Given
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        # When
        fetched = user_auth_repository.get_all_by_time_range(
            end=tomorrow, start=yesterday
        )
        # Then
        assert fetched[0] == created_user_auth

    def test_get_not_found(self, user_auth_repository: repository.UserAuthRepository):
        # Given
        user_id = 1
        # When
        fetched = user_auth_repository.get(id=user_id)
        # Then
        assert fetched is None

    def test_delete_by_user_id(
        self,
        user_auth_repository: repository.UserAuthRepository,
        created_user_auth: model.UserAuth,
    ):
        # Given
        user_id = created_user_auth.user_id
        # When
        count = user_auth_repository.delete_by_user_id(user_id=user_id)
        fetched = user_auth_repository.get_by_user_id(user_id=user_id)
        # Then
        assert count == 1 and fetched is None

    def test_bulk_insert_user_auth(
        self,
        user_repository: repository.UserRepository,
        user_auth_repository: repository.UserAuthRepository,
        created_user,
    ):
        # Given
        # Commit the created_user so that the bulk insert can succeed
        user_auth_repository.session.commit()
        user_ids = [created_user.id]
        # When
        insert_count = user_auth_repository.bulk_insert_user_auth(user_ids=user_ids)
        # Then
        assert insert_count == len(user_ids)
        # Cleanup: Remove user and user auth from test database
        user_repository.delete(id=created_user.id)
        user_repository.session.commit()

    def test_bulk_insert_user_auth_no_ids(
        self, user_auth_repository: repository.UserAuthRepository, created_user
    ):
        # Given
        user_ids = []
        # When
        insert_count = user_auth_repository.bulk_insert_user_auth(user_ids=user_ids)
        # Then
        assert insert_count == 0

    def test_set_refresh_token(
        self, user_auth_repository: repository.UserAuthRepository, created_user_auth
    ):
        # Given
        refresh_token = "refresh.abcd.1234"
        user_id = created_user_auth.user_id
        # When
        updated = user_auth_repository.set_refresh_token(
            user_id=user_id, refresh_token=refresh_token
        )
        # Then
        assert updated.refresh_token == refresh_token
