import datetime

import pytest

from tracks import repository


@pytest.fixture
def member_track_repository(session) -> repository.MemberTrackRepository:
    return repository.MemberTrackRepository(session=session, is_in_uow=True)


def test_get_by_user_id(
    member_track_repository: repository.MemberTrackRepository,
    factories,
    default_user,
):
    created_member_track = factories.MemberTrackFactory.create(
        user_id=default_user.id,
        name="pregnancy",
    )
    user_id = created_member_track.user_id

    fetched = member_track_repository.get_by_user_id(user_id=user_id)

    assert len(fetched) == 1
    assert fetched[0] == created_member_track


def test_get_by_user_id__not_found(
    member_track_repository: repository.MemberTrackRepository,
    factories,
    default_user,
):
    created_member_track = factories.MemberTrackFactory.create(
        user_id=default_user.id,
        name="pregnancy",
    )
    user_id = created_member_track.user_id + 1

    fetched = member_track_repository.get_by_user_id(user_id=user_id)

    assert len(fetched) == 0


def test_get_by_user_id__no_user_id(
    member_track_repository: repository.MemberTrackRepository,
    factories,
    default_user,
):
    factories.MemberTrackFactory.create(
        user_id=default_user.id,
        name="pregnancy",
    )

    fetched = member_track_repository.get_by_user_id(user_id=None)

    assert fetched is None


def test_get_active_tracks(
    member_track_repository: repository.MemberTrackRepository,
    factories,
    default_user,
):
    created_member_track = factories.MemberTrackFactory.create(
        user_id=default_user.id,
        name="pregnancy",
    )
    user_id = created_member_track.user_id

    fetched = member_track_repository.get_active_tracks(user_id=user_id)

    assert len(fetched) == 1
    assert fetched[0] == created_member_track


def test_get_active_tracks__no_active_tracks(
    member_track_repository: repository.MemberTrackRepository,
    factories,
    default_user,
):
    created_member_track = factories.MemberTrackFactory.create(
        user_id=default_user.id,
        name="pregnancy",
        start_date=datetime.datetime.utcnow().date() - datetime.timedelta(weeks=3),
        ended_at=datetime.datetime.utcnow() - datetime.timedelta(weeks=2),
    )
    user_id = created_member_track.user_id

    fetched = member_track_repository.get_active_tracks(user_id=user_id)

    assert len(fetched) == 0


def test_get_active_tracks__not_found(
    member_track_repository: repository.MemberTrackRepository,
    factories,
    default_user,
):
    created_member_track = factories.MemberTrackFactory.create(
        user_id=default_user.id,
        name="pregnancy",
    )
    user_id = created_member_track.user_id + 1

    fetched = member_track_repository.get_active_tracks(user_id=user_id)

    assert len(fetched) == 0


def test_get_active_tracks__no_user_id(
    member_track_repository: repository.MemberTrackRepository,
    factories,
    default_user,
):
    factories.MemberTrackFactory.create(
        user_id=default_user.id,
        name="pregnancy",
    )

    fetched = member_track_repository.get_active_tracks(user_id=None)

    assert fetched is None


def test_get_inactive_tracks(
    member_track_repository: repository.MemberTrackRepository,
    factories,
    default_user,
):
    created_member_track = factories.MemberTrackFactory.create(
        user_id=default_user.id,
        name="pregnancy",
        start_date=datetime.datetime.utcnow().date() - datetime.timedelta(weeks=3),
        ended_at=datetime.datetime.utcnow() - datetime.timedelta(weeks=2),
    )
    user_id = created_member_track.user_id

    fetched = member_track_repository.get_inactive_tracks(user_id=user_id)

    assert len(fetched) == 1
    assert fetched[0] == created_member_track


def test_get_inactive_tracks__no_inactive_tracks(
    member_track_repository: repository.MemberTrackRepository,
    factories,
    default_user,
):
    created_member_track = factories.MemberTrackFactory.create(
        user_id=default_user.id,
        name="pregnancy",
    )
    user_id = created_member_track.user_id

    fetched = member_track_repository.get_inactive_tracks(user_id=user_id)

    assert len(fetched) == 0


def test_get_inactive_tracks__not_found(
    member_track_repository: repository.MemberTrackRepository,
    factories,
    default_user,
):
    created_member_track = factories.MemberTrackFactory.create(
        user_id=default_user.id,
        name="pregnancy",
        start_date=datetime.datetime.utcnow().date() - datetime.timedelta(weeks=3),
        ended_at=datetime.datetime.utcnow() - datetime.timedelta(weeks=2),
    )
    user_id = created_member_track.user_id + 1

    fetched = member_track_repository.get_inactive_tracks(user_id=user_id)

    assert len(fetched) == 0


def test_get_inactive_tracks__no_user_id(
    member_track_repository: repository.MemberTrackRepository,
    factories,
    default_user,
):
    factories.MemberTrackFactory.create(
        user_id=default_user.id,
        name="pregnancy",
        start_date=datetime.datetime.utcnow().date() - datetime.timedelta(weeks=3),
        ended_at=datetime.datetime.utcnow() - datetime.timedelta(weeks=2),
    )

    fetched = member_track_repository.get_inactive_tracks(user_id=None)

    assert fetched is None


def test_get_scheduled_tracks(
    member_track_repository: repository.MemberTrackRepository,
    factories,
    default_user,
):
    created_member_track = factories.MemberTrackFactory.create(
        user_id=default_user.id,
        name="pregnancy",
        start_date=datetime.datetime.utcnow().date() + datetime.timedelta(weeks=3),
    )
    created_member_track.activated_at = None

    user_id = created_member_track.user_id

    fetched = member_track_repository.get_scheduled_tracks(user_id=user_id)

    assert len(fetched) == 1
    assert fetched[0] == created_member_track


def test_get_scheduled_tracks__no_scheduled_tracks(
    member_track_repository: repository.MemberTrackRepository,
    factories,
    default_user,
):
    created_member_track = factories.MemberTrackFactory.create(
        user_id=default_user.id,
        name="pregnancy",
    )
    user_id = created_member_track.user_id

    fetched = member_track_repository.get_scheduled_tracks(user_id=user_id)

    assert len(fetched) == 0


def test_get_scheduled_tracks__not_found(
    member_track_repository: repository.MemberTrackRepository,
    factories,
    default_user,
):
    created_member_track = factories.MemberTrackFactory.create(
        user_id=default_user.id,
        name="pregnancy",
        start_date=datetime.datetime.utcnow().date() + datetime.timedelta(weeks=3),
    )
    user_id = created_member_track.user_id + 1

    fetched = member_track_repository.get_scheduled_tracks(user_id=user_id)

    assert len(fetched) == 0


def test_get_scheduled_tracks__no_user_id(
    member_track_repository: repository.MemberTrackRepository,
    factories,
    default_user,
):
    factories.MemberTrackFactory.create(
        user_id=default_user.id,
        name="pregnancy",
        start_date=datetime.datetime.utcnow().date() + datetime.timedelta(weeks=3),
    )

    fetched = member_track_repository.get_scheduled_tracks(user_id=None)

    assert fetched is None
