import datetime
from unittest.mock import patch

import requests

from authn.models.user import User
from models import virtual_events
from views.tracks import get_user_active_track
from views.virtual_events import VirtualEventSchema


def test_virtual_events(client, api_helpers, factories):
    user = factories.EnterpriseUserFactory(tracks__name="pregnancy")
    track_id = user.active_tracks[0].id

    stress_category = factories.VirtualEventCategoryFactory(name="stress-and-anxiety")
    factories.VirtualEventCategoryTrackFactory(
        category=stress_category, track_name="pregnancy"
    )
    factories.VirtualEventFactory(
        scheduled_start=datetime.datetime.now() + datetime.timedelta(days=1),
        title="Don't be stressed!",
        virtual_event_category=stress_category,
    )

    preg_102_category = factories.VirtualEventCategoryFactory(name="pregnancy-102")
    factories.VirtualEventCategoryTrackFactory(
        category=preg_102_category, track_name="pregnancy"
    )
    factories.VirtualEventFactory(
        scheduled_start=datetime.datetime.now() + datetime.timedelta(days=2),
        virtual_event_category=preg_102_category,
    )
    factories.VirtualEventFactory(
        scheduled_start=datetime.datetime.now() + datetime.timedelta(days=3),
        virtual_event_category=preg_102_category,
    )

    # should not be included because it's not a valid category for the track
    factories.VirtualEventFactory(
        scheduled_start=datetime.datetime.now() + datetime.timedelta(days=4),
        title="Parenting!",
    )

    # should not be included because class is not active
    factories.VirtualEventFactory(
        scheduled_start=datetime.datetime.now() + datetime.timedelta(days=7),
        title="Learn about pregnancy",
        active=False,
        virtual_event_category=preg_102_category,
    )

    # should not be included because class has already happened
    factories.VirtualEventFactory(
        scheduled_start=datetime.datetime.now() - datetime.timedelta(days=2),
        title="For the pregnant ones",
        virtual_event_category=preg_102_category,
    )

    res = client.get(
        f"/api/v1/library/virtual_events/{track_id}",
        headers=api_helpers.json_headers(user=user),
    )
    data = api_helpers.load_json(res)
    assert len(data["virtual_events"]) == 3


def test_virtual_events_host_image_url_present(client, api_helpers, factories):
    user = factories.EnterpriseUserFactory.create(tracks__name="pregnancy")
    track_id = user.active_tracks[0].id

    stress_category = factories.VirtualEventCategoryFactory(name="stress-and-anxiety")
    factories.VirtualEventCategoryTrackFactory(
        category=stress_category, track_name="pregnancy"
    )
    factories.VirtualEventFactory(
        scheduled_start=datetime.datetime.now() + datetime.timedelta(days=1),
        host_image_url="https://hostimages.net/host.png",
        virtual_event_category=stress_category,
    )

    preg_102_category = factories.VirtualEventCategoryFactory(name="pregnancy-102")
    factories.VirtualEventCategoryTrackFactory(
        category=preg_102_category, track_name="pregnancy"
    )
    factories.VirtualEventFactory(
        scheduled_start=datetime.datetime.now() + datetime.timedelta(days=2),
        virtual_event_category=preg_102_category,
    )

    res = client.get(
        f"/api/v1/library/virtual_events/{track_id}",
        headers=api_helpers.json_headers(user=user),
    )
    data = api_helpers.load_json(res)
    assert (
        data["virtual_events"][0]["host_image_url"] == "https://hostimages.net/host.png"
    )
    assert data["virtual_events"][1]["host_image_url"] is None


def test_virtual_events_limit(client, api_helpers, factories):
    user = factories.EnterpriseUserFactory.create(tracks__name="pregnancy")
    track_id = user.active_tracks[0].id
    stress_category = factories.VirtualEventCategoryFactory(name="stress-and-anxiety")
    factories.VirtualEventCategoryTrackFactory(
        category=stress_category, track_name="pregnancy"
    )
    factories.VirtualEventFactory(
        scheduled_start=datetime.datetime.now() + datetime.timedelta(days=1),
        title="Don't be stressed!",
        virtual_event_category=stress_category,
    )
    preg_102_category = factories.VirtualEventCategoryFactory(name="pregnancy-102")
    factories.VirtualEventCategoryTrackFactory(
        category=preg_102_category, track_name="pregnancy"
    )
    factories.VirtualEventFactory(
        scheduled_start=datetime.datetime.now() + datetime.timedelta(days=2),
        virtual_event_category=preg_102_category,
    )
    factories.VirtualEventFactory(
        scheduled_start=datetime.datetime.now() + datetime.timedelta(days=3),
        virtual_event_category=preg_102_category,
    )

    res = client.get(
        f"/api/v1/library/virtual_events/{track_id}?limit=1",
        headers=api_helpers.json_headers(user=user),
    )
    data = api_helpers.load_json(res)
    assert len(data["virtual_events"]) == 1


def test_virtual_events_week_availability_start(client, api_helpers, factories):
    week_5_track = factories.MemberTrackFactory(
        name="pregnancy", current_phase="week-5"
    )
    week_26_track = factories.MemberTrackFactory(
        name="pregnancy", current_phase="week-26"
    )

    # Only users in week 13 or later should see this event
    preg_102_category = factories.VirtualEventCategoryFactory(name="pregnancy-102")
    factories.VirtualEventCategoryTrackFactory(
        category=preg_102_category, track_name="pregnancy", availability_start_week=13
    )
    factories.VirtualEventFactory(
        scheduled_start=datetime.datetime.now() + datetime.timedelta(days=2),
        virtual_event_category=preg_102_category,
    )

    week_5_res = client.get(
        f"/api/v1/library/virtual_events/{week_5_track.id}?limit=1",
        headers=api_helpers.json_headers(user=week_5_track.user),
    )
    data = api_helpers.load_json(week_5_res)
    assert len(data["virtual_events"]) == 0

    week_26_res = client.get(
        f"/api/v1/library/virtual_events/{week_26_track.id}?limit=1",
        headers=api_helpers.json_headers(user=week_26_track.user),
    )
    data = api_helpers.load_json(week_26_res)
    assert len(data["virtual_events"]) == 1


def test_virtual_events_week_availability_end(client, api_helpers, factories):
    week_5_track = factories.MemberTrackFactory(
        name="pregnancy", current_phase="week-5"
    )
    week_26_track = factories.MemberTrackFactory(
        name="pregnancy", current_phase="week-26"
    )

    # Only users in week 13 or earlier should see this event
    preg_102_category = factories.VirtualEventCategoryFactory(name="pregnancy-102")
    factories.VirtualEventCategoryTrackFactory(
        category=preg_102_category, track_name="pregnancy", availability_end_week=13
    )
    factories.VirtualEventFactory(
        scheduled_start=datetime.datetime.now() + datetime.timedelta(days=2),
        virtual_event_category=preg_102_category,
    )

    week_5_res = client.get(
        f"/api/v1/library/virtual_events/{week_5_track.id}?limit=1",
        headers=api_helpers.json_headers(user=week_5_track.user),
    )
    data = api_helpers.load_json(week_5_res)
    assert len(data["virtual_events"]) == 1

    week_26_res = client.get(
        f"/api/v1/library/virtual_events/{week_26_track.id}?limit=1",
        headers=api_helpers.json_headers(user=week_26_track.user),
    )
    data = api_helpers.load_json(week_26_res)
    assert len(data["virtual_events"]) == 0


def test_virtual_events_no_category_assoc_for_track(client, api_helpers, factories):
    user = factories.EnterpriseUserFactory.create(tracks__name="generic")
    track_id = user.active_tracks[0].id

    res = client.get(
        f"/api/v1/library/virtual_events/{track_id}",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200
    data = api_helpers.load_json(res)
    assert len(data["virtual_events"]) == 0


def test_virtual_events_on_end_phase_no_error(db, client, api_helpers, factories):
    user = factories.EnterpriseUserFactory.create(tracks__name="egg_freezing")
    track = user.active_tracks[0]
    track.anchor_date = datetime.date.today() - track.length()

    stress_category = factories.VirtualEventCategoryFactory(name="stress-and-anxiety")
    factories.VirtualEventCategoryTrackFactory(
        category=stress_category, track_name="egg_freezing", availability_start_week=3
    )
    res = client.get(
        f"/api/v1/library/virtual_events/{track.id}",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    # WeeklyMemberTrackMixin.initial_phase is a property value which we cache
    # after first access. Sqlalchemy expunges the session context at the end of
    # a request, so we provide similar behavior before reevaluating the track
    # phase.
    # TODO: client.* calls should act just like a user request and
    # rollback/expunge prior to returning control to the test
    db.session.expunge_all()
    user_after = db.session.query(User).filter(User.id == user.id).one_or_none()
    track_after_call = get_user_active_track(user_after, track.id)
    assert track_after_call.current_phase.name == "end"


def test_virtual_events_is_user_registered(client, api_helpers, factories):
    user = factories.EnterpriseUserFactory(tracks__name="fertility")
    track_id = user.active_tracks[0].id
    category = factories.VirtualEventCategoryFactory(name="fertility-101")
    factories.VirtualEventCategoryTrackFactory(
        category=category, track_name="fertility"
    )
    event = factories.VirtualEventFactory(virtual_event_category=category)
    factories.VirtualEventUserRegistrationFactory(
        virtual_event_id=event.id, user_id=user.id
    )

    factories.VirtualEventFactory(virtual_event_category=category)

    res = client.get(
        f"/api/v1/library/virtual_events/{track_id}",
        headers=api_helpers.json_headers(user=user),
    )
    data = api_helpers.load_json(res)
    assert len(data["virtual_events"]) == 2
    assert data["virtual_events"][0]["is_user_registered"] is True
    assert data["virtual_events"][1]["is_user_registered"] is False


def test_virtual_events_registration_form_url(client, api_helpers, factories):
    user = factories.EnterpriseUserFactory(tracks__name="fertility")
    track_id = user.active_tracks[0].id
    category = factories.VirtualEventCategoryFactory(name="fertility-101")
    factories.VirtualEventCategoryTrackFactory(
        category=category, track_name="fertility"
    )
    event = factories.VirtualEventFactory(
        virtual_event_category=category, rsvp_required=True
    )
    event2 = factories.VirtualEventFactory(
        virtual_event_category=category, rsvp_required=False
    )
    event3 = factories.VirtualEventFactory(
        virtual_event_category=category, rsvp_required=True, registration_form_url=None
    )

    res = client.get(
        f"/api/v1/library/virtual_events/{track_id}",
        headers=api_helpers.json_headers(user=user),
    )
    data = api_helpers.load_json(res)
    events = sorted(data["virtual_events"], key=lambda event: event["id"])
    assert events[0]["registration_form_url"] == f"/app/event-registration/{event.id}"
    assert events[1]["registration_form_url"] == event2.registration_form_url
    assert events[2]["registration_form_url"] == f"/app/event-registration/{event3.id}"


def test_get_virtual_event_if_not_prac_or_enterprise(default_user, client, api_helpers):
    res = client.get(
        "/api/v1/virtual_events/9999",
        headers=api_helpers.json_headers(user=default_user),
    )
    assert res.status_code == 403


def test_get_virtual_event_404(client, api_helpers, factories):
    user = factories.EnterpriseUserFactory()
    res = client.get(
        "/api/v1/virtual_events/9999",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 404


def test_get_virtual_event_enterprise_success(client, api_helpers, factories):
    user = factories.EnterpriseUserFactory()
    event = factories.VirtualEventFactory(
        cadence=virtual_events.Cadences.MONTHLY, rsvp_required=False
    )
    response = client.get(
        f"/api/v1/virtual_events/{event.id}",
        headers=api_helpers.json_headers(user=user),
    )
    assert response.status_code == 200
    result = api_helpers.load_json(response)
    assert result["title"] == event.title
    assert result["host_name"] == event.host_name
    assert result["registration_form_url"] == event.registration_form_url
    assert result["rsvp_required"] == event.rsvp_required
    assert result["scheduled_start"] == event.scheduled_start.isoformat()
    assert result["scheduled_end"] == event.scheduled_end.isoformat()
    assert result["host_image_url"] == event.host_image_url
    assert result["cadence"] == event.cadence.value
    assert result["event_image_url"] == event.event_image_url
    assert result["host_specialty"] == event.host_specialty
    assert result["provider_profile_url"] == event.provider_profile_url
    assert result["description_body"] == event.description_body
    assert result["what_youll_learn_body"] == [event.what_youll_learn_body]
    assert result["what_to_expect_body"] == event.what_to_expect_body


def test_get_virtual_event_practitioner_success(client, api_helpers, factories):
    user = factories.PractitionerUserFactory()
    event = factories.VirtualEventFactory()
    response = client.get(
        f"/api/v1/virtual_events/{event.id}",
        headers=api_helpers.json_headers(user=user),
    )
    assert response.status_code == 200


def test_get_virtual_event_nullable_fields(client, api_helpers, factories):
    user = factories.EnterpriseUserFactory()
    event = factories.VirtualEventFactory()
    response = client.get(
        f"/api/v1/virtual_events/{event.id}",
        headers=api_helpers.json_headers(user=user),
    )
    assert response.status_code == 200
    result = api_helpers.load_json(response)
    assert result["host_image_url"] is None
    assert result["cadence"] is None
    assert result["event_image_url"] is None
    assert result["provider_profile_url"] is None
    assert result["what_to_expect_body"] is None


def test_what_youll_learn_split_whitespace_at_end(factories):
    event = factories.VirtualEventFactory()
    event.what_youll_learn_body = """- Hello
- darkness
- my old friend
    """
    schema = VirtualEventSchema()
    result = schema.dump(event)
    assert result["what_youll_learn_body"] == ["Hello", "darkness", "my old friend"]


def test_what_youll_learn_split_whitespace_at_start_n_middle(factories):
    event = factories.VirtualEventFactory()
    event.what_youll_learn_body = """
        - Hello
        - from the
        - other side"""
    schema = VirtualEventSchema()
    result = schema.dump(event)
    assert result["what_youll_learn_body"] == ["Hello", "from the", "other side"]


def test_what_youll_learn_split_random_hyphens(factories):
    event = factories.VirtualEventFactory()
    event.what_youll_learn_body = """
- Hello - is it 
- me you're 
- looking for"""
    schema = VirtualEventSchema()
    result = schema.dump(event)
    assert result["what_youll_learn_body"] == [
        "Hello - is it",
        "me you're",
        "looking for",
    ]


def test_get_virtual_event_user_registered(client, api_helpers, factories):
    user = factories.EnterpriseUserFactory()
    event = factories.VirtualEventFactory()
    factories.VirtualEventUserRegistrationFactory(
        virtual_event_id=event.id, user_id=user.id
    )

    response = client.get(
        f"/api/v1/virtual_events/{event.id}",
        headers=api_helpers.json_headers(user=user),
    )
    result = api_helpers.load_json(response)
    assert result["is_user_registered"] is True


def test_get_virtual_event_user_unregistered(client, api_helpers, factories):
    user = factories.EnterpriseUserFactory()
    event = factories.VirtualEventFactory()

    response = client.get(
        f"/api/v1/virtual_events/{event.id}",
        headers=api_helpers.json_headers(user=user),
    )
    result = api_helpers.load_json(response)
    assert result["is_user_registered"] is False


def test_virtual_event_user_registration(client, api_helpers, factories):
    mock_response = requests.Response()
    mock_response.status_code = 201
    mock_response.json = lambda: {"join_url": "https://us02web.zoom.us/j/83152434971"}
    user = factories.EnterpriseUserFactory(tracks__name="pregnancy")
    stress_category = factories.VirtualEventCategoryFactory(name="stress-and-anxiety")
    factories.VirtualEventCategoryTrackFactory(
        category=stress_category, track_name="pregnancy"
    )
    event = factories.VirtualEventFactory.create(
        scheduled_start=datetime.datetime.now() + datetime.timedelta(days=1),
        title="Don't be stressed!",
        virtual_event_category=stress_category,
        webinar_id=35,
    )

    with patch("views.virtual_events.zoom") as mock_zoom:
        mock_zoom.make_zoom_request.return_value = mock_response

        res = client.post(
            f"/api/v1/virtual_events/{event.id}/user_registration",
            headers=api_helpers.json_headers(user),
        )
        res_json = api_helpers.load_json(res)
        registration = virtual_events.user_is_registered_for_event(user.id, event.id)
        assert registration is True
        assert res.status_code == 201
        assert res_json["join_url"] == "https://us02web.zoom.us/j/83152434971"


def test_virtual_event_user_registration_for_non_existent_event(
    client, api_helpers, factories
):
    user = factories.EnterpriseUserFactory(tracks__name="pregnancy")

    event_id = 36

    res = client.post(
        f"/api/v1/virtual_events/{event_id}/user_registration",
        headers=api_helpers.json_headers(user),
    )
    registration = virtual_events.user_is_registered_for_event(user.id, event_id)
    assert registration is False
    assert res.status_code == 404


def test_virtual_event_user_registration_for_registered_user(
    client, api_helpers, factories
):
    user = factories.EnterpriseUserFactory(tracks__name="pregnancy")
    stress_category = factories.VirtualEventCategoryFactory(name="stress-and-anxiety")
    factories.VirtualEventCategoryTrackFactory(
        category=stress_category, track_name="pregnancy"
    )
    event = factories.VirtualEventFactory.create(
        scheduled_start=datetime.datetime.now() + datetime.timedelta(days=1),
        title="Don't be stressed!",
        virtual_event_category=stress_category,
        webinar_id=35,
    )
    factories.VirtualEventUserRegistrationFactory(
        virtual_event_id=event.id, user_id=user.id
    )

    res = client.post(
        f"/api/v1/virtual_events/{event.id}/user_registration",
        headers=api_helpers.json_headers(user),
    )
    assert res.status_code == 409


def test_virtual_event_user_registration_for_event_without_webinar_id(
    client, api_helpers, factories
):
    user = factories.EnterpriseUserFactory(tracks__name="pregnancy")
    stress_category = factories.VirtualEventCategoryFactory(name="stress-and-anxiety")
    factories.VirtualEventCategoryTrackFactory(
        category=stress_category, track_name="pregnancy"
    )
    event = factories.VirtualEventFactory.create(
        scheduled_start=datetime.datetime.now() + datetime.timedelta(days=1),
        title="Don't be stressed!",
        virtual_event_category=stress_category,
    )

    res = client.post(
        f"/api/v1/virtual_events/{event.id}/user_registration",
        headers=api_helpers.json_headers(user),
    )
    assert res.status_code == 400


def test_virtual_event_user_registration_for_event_zoom_error(
    factories, client, api_helpers
):
    mock_response = requests.Response()
    mock_response.status_code = 400
    mock_response.json = lambda: {}

    user = factories.EnterpriseUserFactory(tracks__name="pregnancy")
    stress_category = factories.VirtualEventCategoryFactory(name="stress-and-anxiety")
    factories.VirtualEventCategoryTrackFactory(
        category=stress_category, track_name="pregnancy"
    )
    event = factories.VirtualEventFactory.create(
        scheduled_start=datetime.datetime.now() + datetime.timedelta(days=1),
        title="Don't be stressed!",
        virtual_event_category=stress_category,
        webinar_id=35,
    )

    with patch("views.virtual_events.zoom") as mock_zoom:
        mock_zoom.make_zoom_request.return_value = mock_response

        res = client.post(
            f"/api/v1/virtual_events/{event.id}/user_registration",
            headers=api_helpers.json_headers(user),
        )

        registration = virtual_events.user_is_registered_for_event(user.id, event.id)
        assert registration is False
        assert res.status_code == 400
