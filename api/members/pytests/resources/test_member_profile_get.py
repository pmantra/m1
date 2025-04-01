import datetime

import pytest

from models.tracks import TrackName
from pytests import factories
from pytests.factories import AppointmentFactory, ScheduleFactory

now = datetime.datetime.utcnow()


@pytest.fixture
def states(create_state):
    return {
        "NY": create_state(name="New York", abbreviation="NY"),
        "NJ": create_state(name="New Jersey", abbreviation="NJ"),
        "TX": create_state(name="Texas", abbreviation="TX"),
    }


@pytest.fixture
def test_data(factories: factories, states: states):
    """Returns a dictionary of object references so that assertions can be made
    comparing the expected data and the result of the calls in the test.

    When adding new test cases via the @pytest.mark.parametrize decorator, reference the
    expected values by their dictionary key.
    """

    org_1 = factories.OrganizationFactory.create(
        id=1, name="ABC International", US_restricted=False
    )
    org_2 = factories.OrganizationFactory.create(
        id=2, name="US Foo Industries", US_restricted=True
    )

    practitioner_1 = factories.PractitionerUserFactory.create(
        first_name="cc1",
        last_name="cc1",
        email="testemailcc1@maventest.com",
        practitioner_profile__country_code="US",
    )

    member_1 = factories.MemberFactory.create(
        member_profile__first_name="member1",
        member_profile__last_name="member1",
        email="testemail1@maventest.com",
        member_profile__care_team=[practitioner_1],
        member_profile__phone_number="tel:2128675309",
        member_profile__state=states["NY"],
        member_profile__has_care_plan=True,
        member_profile__care_plan_id=1,
        member_profile__created_at="2010-11-29 19:18:41.000000",
        member_profile__country_code="US",
    )

    track_1_pregnancy = factories.MemberTrackFactory.create(
        name=TrackName.PREGNANCY,
        user=member_1,
        current_phase="week-15",
        client_track=factories.ClientTrackFactory(
            organization=org_1,
        ),
    )

    track_1_parenting = factories.MemberTrackFactory.create(
        name=TrackName.PARENTING_AND_PEDIATRICS,
        user=member_1,
        client_track=factories.ClientTrackFactory(
            organization=org_1,
        ),
        current_phase="static",
    )

    practitioner_2 = factories.PractitionerUserFactory.create(
        first_name="cc2",
        last_name="cc2",
        email="testemailcc2@maventest.com",
        practitioner_profile__country_code="US",
    )

    practitioner_3 = factories.PractitionerUserFactory.create(
        first_name="prac3",
        last_name="prac3",
        email="testemailprac3@maventest.com",
        practitioner_profile__country_code="US",
    )

    member_2 = factories.MemberFactory.create(
        member_profile__first_name="test2",
        member_profile__last_name="member2",
        email="testemail2@maventest.com",
        member_profile__care_team=[practitioner_2],
        member_profile__phone_number="tel:2018675309",
        member_profile__state=states["NJ"],
        member_profile__has_care_plan=True,
        member_profile__care_plan_id=2,
        member_profile__created_at="2011-11-29 19:18:41.000000",
        member_profile__country_code="US",
    )

    track_2 = factories.MemberTrackFactory.create(
        name=TrackName.ADOPTION,
        user=member_2,
        client_track=factories.ClientTrackFactory(
            organization=org_1,
        ),
        current_phase="static",
    )

    member_3 = factories.MemberFactory.create(
        member_profile__first_name="first3",
        member_profile__last_name="last3",
        email="testemail3@maventest.com",
        member_profile__care_team=[practitioner_2],
        member_profile__phone_number="tel:5128675309",
        member_profile__state=states["TX"],
        member_profile__has_care_plan=False,
        member_profile__care_plan_id=None,
        member_profile__created_at="2012-11-29 19:18:41.000000",
        member_profile__country_code="US",
    )

    track_3 = factories.MemberTrackFactory.create(
        name=TrackName.BREAST_MILK_SHIPPING,
        user=member_3,
        client_track=factories.ClientTrackFactory(
            organization=org_2,
        ),
        current_phase="static",
    )

    member_4 = factories.MemberFactory.create(
        member_profile__first_name="first4",
        member_profile__last_name="last4",
        email="testemail4@maventest.com",
        member_profile__care_team=[practitioner_2],
        member_profile__phone_number="tel:5128675309",
        member_profile__state=states["TX"],
        member_profile__has_care_plan=False,
        member_profile__care_plan_id=None,
        member_profile__created_at="2012-11-29 19:18:41.000000",
        member_profile__country_code="US",
    )

    track_4 = factories.MemberTrackFactory.create(
        name=TrackName.BREAST_MILK_SHIPPING,
        user=member_4,
        client_track=factories.ClientTrackFactory(
            organization=org_1,
        ),
        current_phase="static",
    )

    ca_vertical = factories.VerticalFactory.create(name="Care Advocate")

    ca_1 = factories.PractitionerUserFactory.create(
        first_name="pract1",
        last_name="test_pract1",
        email="testp1@maventest.com",
        practitioner_profile__verticals=[ca_vertical],
        practitioner_profile__country_code="CA",
    )

    ca_2 = factories.PractitionerUserFactory.create(
        first_name="test_pract2",
        last_name="test_pract2",
        email="testemailp2@maventest.com",
        practitioner_profile__verticals=[ca_vertical],
        practitioner_profile__country_code="US",
    )

    ca_3 = factories.PractitionerUserFactory.create(
        first_name="test_pract3",
        last_name="test_pract3",
        email="testemailp3@maventest.com",
        practitioner_profile__verticals=[ca_vertical],
    )

    member_schedule_1 = ScheduleFactory.create(user=member_2)
    member_schedule_2 = ScheduleFactory.create(user=member_4)

    appointment_1 = AppointmentFactory.create_with_practitioner(
        member_schedule=member_schedule_1,
        purpose="birth_needs_assessment",
        practitioner=ca_1,
        scheduled_start=now + datetime.timedelta(minutes=10),
        scheduled_end=None,
    )

    appointment_2 = AppointmentFactory.create_with_practitioner(
        member_schedule=member_schedule_1,
        purpose="follow_up",
        practitioner=ca_1,
        scheduled_start=now + datetime.timedelta(days=1),
        scheduled_end=None,
    )

    appointment_3 = AppointmentFactory.create_with_practitioner(
        member_schedule=member_schedule_1,
        purpose="third_appointment",
        practitioner=ca_2,
        scheduled_start=now + datetime.timedelta(days=7),
        scheduled_end=None,
    )

    appointment_4 = AppointmentFactory.create_with_practitioner(
        member_schedule=member_schedule_2,
        purpose="first_appointment",
        practitioner=practitioner_3,
        scheduled_start=now - datetime.timedelta(days=7),
    )

    channel_1 = factories.ChannelFactory.create(
        name=f"{member_3.first_name}, {practitioner_1.first_name}"
    )
    channel_user_member_1 = factories.ChannelUsersFactory.create(
        channel_id=channel_1.id,
        user_id=member_3.id,
    )
    channel_user_prac_1 = factories.ChannelUsersFactory.create(
        channel_id=channel_1.id,
        user_id=practitioner_1.id,
    )
    channel_1.participants = [channel_user_member_1, channel_user_prac_1]
    factories.MessageFactory.create(
        channel_id=channel_1.id,
        user_id=member_3.id,
    )

    channel_2 = factories.ChannelFactory.create(
        name=f"{member_3.first_name}, {practitioner_3.first_name}"
    )
    channel_user_member_2 = factories.ChannelUsersFactory.create(
        channel_id=channel_2.id,
        user_id=member_3.id,
    )
    channel_user_prac_2 = factories.ChannelUsersFactory.create(
        channel_id=channel_2.id,
        user_id=practitioner_3.id,
    )
    channel_2.participants = [channel_user_member_2, channel_user_prac_2]

    channel_3 = factories.ChannelFactory.create(
        name=f"{member_2.first_name}, {practitioner_3.first_name}"
    )
    channel_user_member_3 = factories.ChannelUsersFactory.create(
        channel_id=channel_3.id,
        user_id=member_2.id,
    )
    channel_user_prac_3 = factories.ChannelUsersFactory.create(
        channel_id=channel_3.id,
        user_id=practitioner_3.id,
    )
    channel_3.participants = [channel_user_member_3, channel_user_prac_3]
    factories.MessageFactory.create(
        channel_id=channel_3.id,
        user_id=practitioner_3.id,
    )

    return {
        "member_1": member_1,
        "member_2": member_2,
        "member_3": member_3,
        "member_4": member_4,
        "ca_1": ca_1,
        "ca_2": ca_2,
        "ca_3": ca_3,
        "org_1": org_1,
        "org_2": org_2,
        "track_1_parenting": track_1_parenting,
        "track_1_pregnancy": track_1_pregnancy,
        "track_2": track_2,
        "track_3": track_3,
        "track_4": track_4,
        "practitioner_1": practitioner_1,
        "practitioner_2": practitioner_2,
        "practitioner_3": practitioner_3,
        "member_schedule_1": member_schedule_1,
        "member_schedule_2": member_schedule_2,
        "appointment_1": appointment_1,
        "appointment_2": appointment_2,
        "appointment_3": appointment_3,
        "appointment_4": appointment_4,
        "channel_1": channel_1,
        "channel_2": channel_2,
        "channel_3": channel_3,
        "channel_user_member_1": channel_user_member_1,
        "channel_user_member_2": channel_user_member_2,
        "channel_user_member_3": channel_user_member_3,
        "channel_user_prac_1": channel_user_prac_1,
        "channel_user_prac_2": channel_user_prac_2,
        "channel_user_prac_3": channel_user_prac_3,
    }


@pytest.mark.parametrize(
    [
        "user",
        "expected_member",
        "expected_org",
        "expected_tracks",
        "expected_care_coordinators",
    ],
    [
        (
            "ca_1",
            "member_1",
            "org_1",
            ["track_1_pregnancy", "track_1_parenting"],
            ["practitioner_1"],
        ),
        ("ca_1", "member_2", "org_1", ["track_2"], ["practitioner_2"]),
        (
            "ca_2",
            "member_1",
            "org_1",
            ["track_1_pregnancy", "track_1_parenting"],
            ["practitioner_1"],
        ),
        ("ca_2", "member_2", "org_1", ["track_2"], ["practitioner_2"]),
        ("ca_2", "member_3", "org_2", ["track_3"], ["practitioner_2"]),
        ("practitioner_2", "member_2", "org_1", ["track_2"], ["practitioner_2"]),
        ("practitioner_2", "member_3", "org_2", ["track_3"], ["practitioner_2"]),
        ("practitioner_1", "member_3", "org_2", ["track_3"], ["practitioner_2"]),
        ("practitioner_3", "member_4", "org_1", ["track_4"], ["practitioner_2"]),
    ],
)
def test_member_profile_ok_ca(
    client,
    api_helpers,
    test_data,
    user,
    expected_member,
    expected_org,
    expected_tracks,
    expected_care_coordinators,
):
    u = test_data[user]
    expected = test_data[expected_member].member_profile
    member_id = expected.id
    org = None if expected_org is None else test_data[expected_org]
    res = client.get(
        f"/api/v1/members/{member_id}",
        headers=api_helpers.json_headers(user=u),
    )
    data = api_helpers.load_json(res)
    assert res.status_code == 200
    assert "member_profile_data" in data.keys()
    assert "upcoming_appointment_data" in data.keys()
    member_profile_data = data["member_profile_data"]
    upcoming_appointment_data = data["upcoming_appointment_data"]

    assert member_profile_data["id"] == expected.id
    assert member_profile_data["first_name"] == expected.first_name
    assert member_profile_data["last_name"] == expected.last_name
    assert member_profile_data["phone_number"] == expected.phone_number
    assert member_profile_data["state"] == expected.state.abbreviation
    assert member_profile_data["has_care_plan"] == expected.has_care_plan
    assert member_profile_data["care_plan_id"] == expected.care_plan_id
    assert member_profile_data["created_at"] == expected.created_at

    if expected_member == "member_2" and (
        u.is_care_coordinator or user in expected_care_coordinators
    ):
        assert (
            upcoming_appointment_data["data"][0]["id"]
            == test_data["appointment_1"].api_id
        )
        assert (
            upcoming_appointment_data["data"][1]["id"]
            == test_data["appointment_2"].api_id
        )
        assert (
            upcoming_appointment_data["data"][2]["id"]
            == test_data["appointment_3"].api_id
        )
    else:
        assert upcoming_appointment_data == {}
    if org is None:
        assert member_profile_data["organization"] is None
    else:
        assert member_profile_data["organization"] is not None
        assert member_profile_data["organization"]["name"] == org.name
        assert member_profile_data["organization"]["id"] == org.id

    if expected.country is None:
        assert member_profile_data["country"] is None
    else:
        assert member_profile_data["country"]["name"] == expected.country.name
        assert member_profile_data["country"]["abbr"] == expected.country.alpha_2

    assert len(member_profile_data["care_coordinators"]) == len(
        expected_care_coordinators
    )
    for cc_key in expected_care_coordinators:
        cc = test_data[cc_key]
        assert any(
            elem["first_name"] == cc.first_name and elem["last_name"] == cc.last_name
            for elem in member_profile_data["care_coordinators"]
        )

    assert len(member_profile_data["active_tracks"]) == len(expected_tracks)
    for track_key in expected_tracks:
        track = test_data[track_key]
        assert any(
            elem["name"] == track.name
            and elem["current_phase"] == track.current_phase.display_name
            for elem in member_profile_data["active_tracks"]
        )

    if u.is_care_coordinator:
        assert member_profile_data["email"] == expected.email
    else:
        assert member_profile_data["email"] is None


@pytest.mark.parametrize(
    [
        "user",
        "member",
    ],
    [
        ("member_2", "member_1"),
        ("member_3", "member_2"),
        ("member_1", "member_3"),
        ("practitioner_2", "member_1"),
        ("practitioner_3", "member_1"),
        ("practitioner_3", "member_2"),
    ],
    ids=[
        "when_member_2_get_other_member_then_no_access",
        "when_member_3_get_other_member_then_no_access",
        "when_member_1_get_other_member_then_no_access",
        "when_practitioner_2_get_member_without_practitioner_2_in_care_team_then_no_access",
        "when_practitioner_3_get_member_with_channel_no_messages_then_no_access",
        "when_practitioner_3_get_member_with_channel_no_messages_from_member_then_no_access",
    ],
)
def test_member_profile_user_no_access(
    client,
    api_helpers,
    test_data,
    user,
    member,
):
    u = test_data[user]
    member_id = test_data[member].id
    res = client.get(
        f"/api/v1/members/{member_id}",
        headers=api_helpers.json_headers(user=u),
    )
    error_data = api_helpers.load_json(res)["errors"]
    assert res.status_code == 403
    assert len(error_data) == 1
    error_info = error_data[0]
    assert (
        error_info["detail"]
        == "You do not have access to that target user's information."
    )
    assert error_info["status"] == 403
    assert error_info["title"] == "Forbidden"


@pytest.mark.parametrize(
    [
        "user",
        "member",
        "expected_http_status",
        "expected_message",
        "expected_error_title",
    ],
    [
        (
            "ca_1",
            "member_3",
            403,
            "The current user isn't authorized to view this resource",
            "Forbidden",
        ),
        ("ca_2", "ca_1", 404, "No user found for id {0}", "Not Found"),
        (
            "ca_3",
            "member_3",
            403,
            "The current user isn't authorized to view this resource",
            "Forbidden",
        ),
    ],
    ids=["US Restricted Org", "No member for submitted id", "No country on User"],
)
def test_member_profile_other_errors(
    client,
    api_helpers,
    test_data,
    user,
    member,
    expected_http_status,
    expected_message,
    expected_error_title,
):
    u = test_data[user]
    member_id = test_data[member].id
    res = client.get(
        f"/api/v1/members/{member_id}",
        headers=api_helpers.json_headers(user=u),
    )
    data = api_helpers.load_json(res)
    assert res.status_code == expected_http_status
    assert len(data) == 2
    assert data["message"] == expected_message.format(member_id)
    error_info = data["errors"][0]
    assert error_info["detail"] == expected_message.format(member_id)
    assert error_info["status"] == expected_http_status
    assert error_info["title"] == expected_error_title
