from unittest import mock

import pytest

from activity import models, repository, service
from activity.pytests import factories
from authn.domain import model
from authn.domain import repository as authn_repository
from authn.pytests import factories as authn_factories


@pytest.fixture
def user_repository(session) -> authn_repository.UserRepository:
    return authn_repository.UserRepository(session=session, is_in_uow=True)


@pytest.fixture
def user_activity_repository(session) -> repository.UserActivityRepository:
    return repository.UserActivityRepository(session=session, is_in_uow=True)


@pytest.fixture
def created_user(user_repository) -> model.User:
    user: model.User = authn_factories.UserFactory.create()
    created: model.User = user_repository.create(instance=user)
    return created


@pytest.fixture
def created_user_activity(
    user_activity_repository, created_user
) -> models.UserActivity:
    user_activity: models.UserActivity = factories.UserActivityFactory.create(
        user_id=created_user.id
    )
    created: models.UserActivity = user_activity_repository.create(
        instance=user_activity
    )
    return created


@pytest.fixture
def mock_user_activity_repository():
    with mock.patch(
        "activity.repository.user_activity.UserActivityRepository",
        autospec=True,
        spec_set=True,
    ) as mock_repo, mock.patch(
        "activity.service.user_activity.repository.UserActivityRepository",
        new=mock_repo,
    ):
        yield mock_repo.return_value


@pytest.fixture
def user_activity_service() -> service.UserActivityService:
    return service.UserActivityService()


@pytest.fixture
def user_activity(created_user) -> models.UserActivity:
    return factories.UserActivityFactory.create(user_id=created_user.id)
