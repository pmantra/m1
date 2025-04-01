import dataclasses

from activity import models, repository
from activity.pytests import factories
from authn.domain import model


class TestUserActivityRepository:
    def test_create(
        self,
        user_activity_repository: repository.UserActivityRepository,
        created_user: model.User,
    ):
        # Given
        user_activity: models.UserActivity = factories.UserActivityFactory.create(
            user_id=created_user.id
        )

        input_ = dict(
            user_id=user_activity.user_id,
            activity_type=user_activity.activity_type,
        )

        # When
        created: models.UserActivity = user_activity_repository.create(
            instance=user_activity
        )
        output = {f: getattr(created, f) for f in input_}

        # Then
        assert output == input_

    def test_update(
        self,
        user_activity_repository: repository.UserActivityRepository,
        created_user_activity: models.UserActivity,
        faker,
    ):
        # Given
        new_date = faker.date_time()
        update = dataclasses.replace(created_user_activity, activity_date=new_date)

        # When
        updated_user_activity: models.UserActivity = user_activity_repository.update(
            instance=update
        )

        # Then
        assert updated_user_activity.activity_date == new_date

    def test_get(
        self,
        user_activity_repository: repository.UserActivityRepository,
        created_user_activity: models.UserActivity,
    ):
        # Given
        user_activity_id = created_user_activity.id

        # When
        fetched = user_activity_repository.get(id=user_activity_id)

        # Then
        assert fetched == created_user_activity

    def test_get__not_found(
        self,
        user_activity_repository: repository.UserActivityRepository,
    ):
        # Given
        user_activity_id = 1

        # When
        fetched = user_activity_repository.get(id=user_activity_id)

        # Then
        assert fetched is None

    def test_get_by_user_id(
        self,
        user_activity_repository: repository.UserActivityRepository,
        created_user_activity: models.UserActivity,
    ):
        # Given
        user_id = created_user_activity.user_id

        # When
        fetched = user_activity_repository.get_by_user_id(user_id=user_id)

        # Then
        assert len(fetched) == 1
        assert fetched[0] == created_user_activity

    def test_get_by_user_id__not_found(
        self,
        user_activity_repository: repository.UserActivityRepository,
        created_user_activity: models.UserActivity,
    ):
        # Given
        user_id = created_user_activity.user_id + 1

        # When
        fetched = user_activity_repository.get_by_user_id(user_id=user_id)

        # Then
        assert len(fetched) == 0

    def test_get_by_activity_type(
        self,
        user_activity_repository: repository.UserActivityRepository,
        created_user_activity: models.UserActivity,
    ):
        # Given
        user_id = created_user_activity.user_id
        activity_type = created_user_activity.activity_type

        # When
        fetched = user_activity_repository.get_by_activity_type(
            user_id=user_id, activity_type=activity_type
        )

        # Then
        assert len(fetched) == 1
        assert fetched[0] == created_user_activity

    def test_get_by_activity_type__not_found(
        self,
        user_activity_repository: repository.UserActivityRepository,
        created_user_activity: models.UserActivity,
    ):
        # Given
        user_id = created_user_activity.user_id + 1
        activity_type = f"{created_user_activity.activity_type}_NOT_FOUND"

        # When
        fetched = user_activity_repository.get_by_activity_type(
            user_id=user_id, activity_type=activity_type
        )

        # Then
        assert len(fetched) == 0

    def test_delete(
        self,
        user_activity_repository: repository.UserActivityRepository,
        created_user_activity: models.UserActivity,
    ):
        # Given
        activity_id = created_user_activity.id

        # When
        count = user_activity_repository.delete(id=activity_id)
        fetched = user_activity_repository.get(id=activity_id)

        # Then
        assert count == 1
        assert fetched is None

    def test_delete__not_found(
        self,
        user_activity_repository: repository.UserActivityRepository,
        created_user_activity: models.UserActivity,
    ):
        # Given
        activity_id = created_user_activity.id + 1

        # When
        count = user_activity_repository.delete(id=activity_id)

        # Then
        assert count == 0

    def test_delete_by_user_id(
        self,
        user_activity_repository: repository.UserActivityRepository,
        created_user_activity: models.UserActivity,
    ):
        # Given
        activity_id = created_user_activity.id
        user_id = created_user_activity.user_id

        # When
        count = user_activity_repository.delete_by_user_id(user_id=user_id)
        fetched = user_activity_repository.get(id=activity_id)

        # Then
        assert count == 1
        assert fetched is None

    def test_delete_by_user_id__not_found(
        self,
        user_activity_repository: repository.UserActivityRepository,
        created_user_activity: models.UserActivity,
    ):
        # Given
        user_id = created_user_activity.user_id + 1

        # When
        count = user_activity_repository.delete_by_user_id(user_id=user_id)

        # Then
        assert count == 0
