from unittest.mock import patch

import pytest

from authn.models.user import User
from models.zoom import UserWebinar, UserWebinarStatus, Webinar
from tasks.zoom import (
    follow_up_with_users_who_missed_zoom_webinar,
    follow_up_with_users_who_participated_in_zoom_webinar,
)


@pytest.fixture
def webinar(factories):
    return factories.DefaultWebinarFactory.create()


@pytest.fixture
def user_webinar(factories, webinar: Webinar, default_user: User):
    return factories.DefaultUserWebinarFactory.create(
        webinar_id=webinar.id, user_id=default_user.id
    )


@patch("tasks.zoom.zoom")
def test_follow_up_with_users_who_participated_in_zoom_webinar_no_webinars(mock_zoom):
    mock_zoom.get_webinars_since_days_ago.return_value = []

    follow_up_with_users_who_participated_in_zoom_webinar()

    assert len(UserWebinar.query.all()) == 0
    mock_zoom.get_webinars_since_days_ago.assert_called_once_with(1)


@patch("tasks.zoom.zoom")
def test_follow_up_with_users_who_participated_in_zoom_webinar_no_participants(
    mock_zoom,
    webinar: Webinar,
    user_webinar: UserWebinar,
):
    mock_zoom.get_webinars_since_days_ago.return_value = [webinar]
    mock_zoom.get_users_who_participated_in_webinar.return_value = []

    follow_up_with_users_who_participated_in_zoom_webinar()

    assert UserWebinar.query.all() == [user_webinar]
    mock_zoom.get_webinars_since_days_ago.assert_called_once_with(1)
    mock_zoom.get_users_who_participated_in_webinar.assert_called_once_with(webinar.id)


@patch("tasks.zoom.braze_events")
@patch("tasks.zoom.braze")
@patch("tasks.zoom.zoom")
def test_follow_up_with_users_who_participated_in_zoom_webinar_user_webinar_does_not_exist(
    mock_zoom,
    mock_braze,
    mock_braze_events,
    webinar: Webinar,
    default_user: User,
):
    mock_zoom.get_webinars_since_days_ago.return_value = [webinar]
    mock_zoom.get_users_who_participated_in_webinar.return_value = [default_user]

    follow_up_with_users_who_participated_in_zoom_webinar()

    assert len(UserWebinar.query.all()) == 0
    mock_zoom.get_webinars_since_days_ago.assert_called_once_with(1)
    mock_zoom.get_users_who_participated_in_webinar.assert_called_once_with(webinar.id)
    mock_braze.track_user_webinars.assert_called_once_with(default_user, webinar.topic)
    mock_braze_events.zoom_webinar_followup.assert_called_once_with(
        default_user, "zoom_webinar_attended", webinar
    )


@patch("tasks.zoom.braze_events")
@patch("tasks.zoom.braze")
@patch("tasks.zoom.zoom")
def test_follow_up_with_users_who_participated_in_zoom_webinar(
    mock_zoom,
    mock_braze,
    mock_braze_events,
    db,
    webinar: Webinar,
    default_user: User,
    user_webinar: UserWebinar,
):
    mock_zoom.get_webinars_since_days_ago.return_value = [webinar]
    mock_zoom.get_users_who_participated_in_webinar.return_value = [default_user]

    follow_up_with_users_who_participated_in_zoom_webinar()

    assert len(db.session.query(UserWebinar).all()) == 1
    assert UserWebinar.query.all()[0].status == UserWebinarStatus.ATTENDED
    mock_zoom.get_webinars_since_days_ago.assert_called_once_with(1)
    mock_zoom.get_users_who_participated_in_webinar.assert_called_once_with(webinar.id)
    mock_braze.track_user_webinars.assert_called_once_with(default_user, webinar.topic)
    mock_braze_events.zoom_webinar_followup.assert_called_once_with(
        default_user, "zoom_webinar_attended", webinar
    )


@patch("tasks.zoom.zoom")
def test_follow_up_with_users_who_missed_zoom_webinar_no_webinars(mock_zoom):
    mock_zoom.get_webinars_since_days_ago.return_value = []

    follow_up_with_users_who_missed_zoom_webinar()

    assert len(UserWebinar.query.all()) == 0
    mock_zoom.get_webinars_since_days_ago.assert_called_once_with(1)


@patch("tasks.zoom.zoom")
def test_follow_up_with_users_who_missed_zoom_webinar_no_users_who_missed(
    mock_zoom,
    webinar: Webinar,
    user_webinar: UserWebinar,
):
    mock_zoom.get_webinars_since_days_ago.return_value = [webinar]
    mock_zoom.get_users_who_missed_webinar.return_value = []

    follow_up_with_users_who_missed_zoom_webinar()

    assert UserWebinar.query.all() == [user_webinar]
    mock_zoom.get_webinars_since_days_ago.assert_called_once_with(1)
    mock_zoom.get_users_who_missed_webinar.assert_called_once_with(webinar.id)


@patch("tasks.zoom.braze_events")
@patch("tasks.zoom.braze")
@patch("tasks.zoom.zoom")
def test_follow_up_with_users_who_missed_zoom_webinar_user_webinar_does_not_exist(
    mock_zoom,
    mock_braze,
    mock_braze_events,
    webinar: Webinar,
    default_user: User,
):
    mock_zoom.get_webinars_since_days_ago.return_value = [webinar]
    mock_zoom.get_users_who_missed_webinar.return_value = [default_user]

    follow_up_with_users_who_missed_zoom_webinar()

    assert len(UserWebinar.query.all()) == 0
    mock_zoom.get_webinars_since_days_ago.assert_called_once_with(1)
    mock_zoom.get_users_who_missed_webinar.assert_called_once_with(webinar.id)
    mock_braze.track_user_webinars.assert_called_once_with(default_user, webinar.topic)
    mock_braze_events.zoom_webinar_followup.assert_called_once_with(
        default_user, "zoom_webinar_missed", webinar
    )


@patch("tasks.zoom.braze_events")
@patch("tasks.zoom.braze")
@patch("tasks.zoom.zoom")
def test_follow_up_with_users_who_missed_zoom_webinar(
    mock_zoom,
    mock_braze,
    mock_braze_events,
    db,
    webinar: Webinar,
    default_user: User,
    user_webinar: UserWebinar,
):
    mock_zoom.get_webinars_since_days_ago.return_value = [webinar]
    mock_zoom.get_users_who_missed_webinar.return_value = [default_user]

    follow_up_with_users_who_missed_zoom_webinar()

    assert len(db.session.query(UserWebinar).all()) == 1
    assert UserWebinar.query.all()[0].status == UserWebinarStatus.MISSED
    mock_zoom.get_webinars_since_days_ago.assert_called_once_with(1)
    mock_zoom.get_users_who_missed_webinar.assert_called_once_with(webinar.id)
    mock_braze.track_user_webinars.assert_called_once_with(default_user, webinar.topic)
    mock_braze_events.zoom_webinar_followup.assert_called_once_with(
        default_user, "zoom_webinar_missed", webinar
    )
