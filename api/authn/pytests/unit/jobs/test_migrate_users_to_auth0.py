from unittest import mock

from authn.jobs.migrate_users_to_auth0 import (
    MIGRATION_JOB_KEY,
    MIGRATION_JOB_TTL,
    enqueue_all,
    migrate_users_to_auth0,
)
from authn.pytests import factories
from pytests import factories as legacy_factories


class TestMigrateUsersToAuth0:
    @staticmethod
    def test_enqueue_all(user_service, mock_migrate_job):
        # Given
        user = factories.UserFactory.create(id=12345)
        user_service.users.get_all_without_auth.return_value = [user.id]

        # When
        enqueue_all(batch_size=10)

        # Then
        assert mock_migrate_job.delay.call_args.kwargs["user_ids"] == [user.id]

    @staticmethod
    def test_enqueue_all_no_op(user_service, mock_migrate_job):
        # Given
        user = factories.UserFactory.create()
        user_service.users.get_all_without_auth.return_value = []

        # When
        enqueue_all(batch_size=10, user_ids=[user.id])

        # Then
        assert mock_migrate_job.delay.call_count == 0

    @staticmethod
    def test_migrate_users(
        mock_import_helper,
        mock_idp_management_client,
        mock_redis,
        mock_user_repository,
        mock_user_auth_repository,
    ):
        # Given
        user = legacy_factories.DefaultUserFactory.create(id=1)
        user_ids = [user.id]
        job_id = "job123"
        mock_payload_data = {"value": "password"}
        # "None" values are filtered out of the payload
        mock_import_helper.build_payload.side_effect = [mock_payload_data, None]
        mock_user_repository.get_all_by_ids.return_value = [user]
        mock_idp_management_client.import_users.return_value = {"id": job_id}
        mock_redis.get.return_value = None

        # When
        migrate_users_to_auth0(user_ids=user_ids)

        # Then
        assert mock_idp_management_client.import_users.call_args.kwargs["payload"] == [
            mock_payload_data
        ]
        assert mock_redis.setex.call_args.args == (
            MIGRATION_JOB_KEY,
            MIGRATION_JOB_TTL,
            job_id,
        )

    @staticmethod
    def test_migrate_users_blocking_job_finished(
        mock_idp_management_client, mock_import_helper, mock_redis, mock_user_repository
    ):
        # Given
        user = legacy_factories.DefaultUserFactory.create(id=1)
        user_ids = [user.id]
        blocking_job_id = "job123"
        new_job_id = "job456"
        mock_redis.get.return_value = blocking_job_id
        mock_import_helper.build_payload.return_value = []
        mock_user_repository.get_all_by_ids.return_value = [user]
        mock_idp_management_client.import_users.return_value = {
            "status": "pending",
            "id": new_job_id,
        }
        mock_idp_management_client.get_job.return_value = {"status": "completed"}

        # When
        migrate_users_to_auth0(user_ids=user_ids)

        # Then
        assert mock_redis.setex.call_args.args == (
            MIGRATION_JOB_KEY,
            MIGRATION_JOB_TTL,
            new_job_id,
        )

    @staticmethod
    def test_migrate_users_blocking_job_exhausted(
        mock_idp_management_client, mock_redis
    ):
        # Given
        user_ids = [1]
        blocking_job_id = "job123"
        mock_redis.get.return_value = blocking_job_id
        mock_idp_management_client.get_job.return_value = {"status": "pending"}

        # When
        with mock.patch("authn.jobs.migrate_users_to_auth0.sleep", return_value=None):
            migrate_users_to_auth0(user_ids=user_ids)

        # Then
        assert mock_redis.setex.call_count == 0
