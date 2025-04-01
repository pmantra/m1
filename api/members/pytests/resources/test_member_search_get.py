from datetime import datetime

import pytest

from appointments.models.constants import PRIVACY_CHOICES
from members.schemas.search import MemberSearchResultSchema
from pytests import factories


@pytest.fixture
def id_test_data(factories: factories):
    """Returns a dictionary of object references so that assertions can be made
    comparing the expected data and the result of the calls in the test.

    When adding new test cases via the @pytest.mark.parametrize decorator, reference the
    expected values by their dictionary key.
    """
    prac_1 = factories.PractitionerUserFactory.create(
        first_name="pract1",
        last_name="test_pract1",
        email="testp1@maventest.com",
    )
    prac_2 = factories.PractitionerUserFactory.create(
        first_name="pract2",
        last_name="test_pract2",
        email="testp2@maventest.com",
    )

    org_1 = factories.OrganizationFactory.create(US_restricted=False)
    org_2 = factories.OrganizationFactory.create(US_restricted=True)

    member_1 = factories.MemberFactory.create(
        member_profile__first_name="A_test1",
        member_profile__last_name="member1",
        email="testemail1@maventest.com",
    )
    member_2 = factories.MemberFactory.create(
        member_profile__first_name="B_test2",
        member_profile__last_name="member2",
        email="testemail2@maventest.com",
    )
    member_3 = factories.MemberFactory.create(
        member_profile__first_name="C_test3",
        member_profile__last_name="member3",
        email="testemail3@maventest.com",
    )
    member_4 = factories.MemberFactory.create(
        member_profile__first_name="D_One",
        member_profile__last_name="Two",
        email="testemail4@maventest.com",
    )
    member_5 = factories.MemberFactory.create(
        member_profile__first_name="E_One Two",
        member_profile__last_name="Three",
        email="testemail5@maventest.com",
    )
    member_6 = factories.MemberFactory.create(
        member_profile__first_name="F_Two",
        member_profile__last_name="Three",
        email="testemail6@maventest.com",
    )
    member_7 = factories.MemberFactory.create(
        member_profile__first_name="G_Two",
        member_profile__last_name="Three Four",
        email="testemail7@maventest.com",
    )
    member_8 = factories.MemberFactory.create(
        member_profile__first_name="H_Four",
        member_profile__last_name="Three",
        email="testemail8@maventest.com",
    )
    member_9 = factories.MemberFactory.create(
        member_profile__first_name="I_One",
        member_profile__last_name="Two-Three",
        email="testemail9@maventest.com",
    )
    factories.MemberTrackFactory.create(
        user=member_1,
        client_track=factories.ClientTrackFactory.create(
            organization=org_1,
        ),
    )
    factories.MemberTrackFactory.create(
        user=member_2,
        client_track=factories.ClientTrackFactory.create(
            organization=org_1,
        ),
    )
    factories.MemberTrackFactory.create(
        user=member_3,
        client_track=factories.ClientTrackFactory.create(
            organization=org_2,
        ),
    )

    ca_vertical = factories.VerticalFactory.create(name="Care Advocate")

    ca_1 = factories.PractitionerUserFactory.create(
        first_name="ca1",
        last_name="test_ca1",
        email="testca1@maventest.com",
        practitioner_profile__verticals=[ca_vertical],
    )

    ca_2 = factories.PractitionerUserFactory.create(
        first_name="ca2",
        last_name="test_ca2",
        email="testca2@maventest.com",
        practitioner_profile__verticals=[ca_vertical],
    )

    channel = factories.ChannelFactory.create(
        name=f"{member_9.first_name}, {prac_1.first_name}"
    )
    channel_user_member = factories.ChannelUsersFactory.create(
        channel_id=channel.id,
        user_id=member_9.id,
        channel=channel,
        user=member_9,
    )
    channel_user_prac = factories.ChannelUsersFactory.create(
        channel_id=channel.id,
        user_id=prac_1.id,
        channel=channel,
        user=prac_1,
    )
    channel.participants = [channel_user_member, channel_user_prac]
    factories.MessageFactory.create(channel_id=channel.id, user_id=member_9.id)
    channel_no_messages = factories.ChannelFactory.create(
        name=f"{member_8.first_name}, {prac_1.first_name}"
    )
    channel_user_member_no_messages = factories.ChannelUsersFactory.create(
        channel_id=channel_no_messages.id,
        user_id=member_8.id,
        channel=channel_no_messages,
        user=member_8,
    )
    channel_user_prac_no_messages = factories.ChannelUsersFactory.create(
        channel_id=channel_no_messages.id,
        user_id=prac_1.id,
        channel=channel_no_messages,
        user=prac_1,
    )
    channel_no_messages.participants = [
        channel_user_member_no_messages,
        channel_user_prac_no_messages,
    ]
    product = factories.ProductFactory.create(practitioner=prac_2)
    schedule_1 = factories.ScheduleFactory.create(user=member_1)
    schedule_2 = factories.ScheduleFactory.create(user=member_2)
    appointment_cancelled = factories.AppointmentFactory.create(
        product=product,
        member_schedule=schedule_2,
        cancelled_at=datetime.utcnow(),
        privacy=PRIVACY_CHOICES.basic,
    )
    appointment = factories.AppointmentFactory.create(
        product=product,
        member_schedule=schedule_1,
        cancelled_at=None,
        privacy=PRIVACY_CHOICES.basic,
    )

    return {
        "member_1": member_1,
        "member_2": member_2,
        "member_3": member_3,
        "member_4": member_4,
        "member_5": member_5,
        "member_6": member_6,
        "member_7": member_7,
        "member_8": member_8,
        "member_9": member_9,
        "prac_1": prac_1,
        "prac_2": prac_2,
        "ca_1": ca_1,
        "ca_2": ca_2,
        "channel": channel,
        "channel_user_member": channel_user_member,
        "channel_user_prac": channel_user_prac,
        "channel_no_messages": channel_no_messages,
        "channel_user_member_no_messages": channel_user_member_no_messages,
        "channel_user_prac_no_messages": channel_user_prac_no_messages,
        "product": product,
        "schedule_1": schedule_1,
        "schedule_2": schedule_2,
        "appointment_cancelled": appointment_cancelled,
        "appointment": appointment,
    }


@pytest.mark.parametrize(
    [
        "user",
        "term",
        "expected_ids",
        "restricted_ids",
        "offset",
        "limit",
        "order_direction",
        "expected_total",
    ],
    [
        ("ca_1", "test1", ["member_1"], [], None, None, None, 1),
        ("ca_1", "testemail1@", ["member_1"], [], None, None, None, 1),
        ("ca_1", "testemail1@maventest.com", ["member_1"], [], None, None, None, 1),
        (
            "ca_1",
            "test",
            [
                "member_1",
                "member_2",
                "member_3",
                "member_4",
                "member_5",
                "member_6",
                "member_7",
                "member_8",
                "member_9",
            ],
            ["member_3"],
            None,
            None,
            "asc",
            9,
        ),
        (
            "ca_1",
            "test",
            [
                "member_9",
                "member_8",
                "member_7",
                "member_6",
                "member_5",
                "member_4",
                "member_3",
                "member_2",
                "member_1",
            ],
            ["member_3"],
            None,
            None,
            None,
            9,
        ),
        (
            "ca_1",
            "test",
            [
                "member_9",
                "member_8",
                "member_7",
                "member_6",
                "member_5",
                "member_4",
                "member_3",
                "member_2",
                "member_1",
            ],
            ["member_3"],
            None,
            None,
            "desc",
            9,
        ),
        (
            "ca_1",
            "test",
            ["member_1", "member_2", "member_3", "member_4"],
            ["member_3"],
            None,
            4,
            "asc",
            9,
        ),
        (
            "ca_1",
            "test",
            ["member_5", "member_6", "member_7", "member_8"],
            ["member_3"],
            4,
            4,
            "asc",
            9,
        ),
        ("ca_1", "test", ["member_9"], ["member_3"], 8, 4, "asc", 9),
        (
            "ca_1",
            "test",
            ["member_1", "member_2", "member_3"],
            ["member_3"],
            0,
            3,
            "asc",
            9,
        ),
        (
            "ca_1",
            "test",
            ["member_4", "member_5", "member_6"],
            ["member_3"],
            3,
            3,
            "asc",
            9,
        ),
        (
            "ca_1",
            "test",
            ["member_7", "member_8", "member_9"],
            ["member_3"],
            6,
            3,
            "asc",
            9,
        ),
        ("ca_1", "member2", ["member_2"], [], None, None, None, 1),
        ("ca_1", "D One", ["member_4"], [], None, None, None, 1),
        (
            "ca_1",
            "One",
            ["member_4", "member_5", "member_9"],
            [],
            None,
            None,
            "asc",
            3,
        ),
        (
            "ca_1",
            "One Two",
            ["member_4", "member_5", "member_9"],
            [],
            None,
            None,
            "asc",
            3,
        ),
        ("ca_1", "One Two Three", ["member_9", "member_5"], [], None, None, None, 2),
        ("ca_1", "One Two-Three", ["member_5", "member_9"], [], None, None, "asc", 2),
        (
            "ca_1",
            "Two Three",
            ["member_5", "member_6", "member_7", "member_9"],
            [],
            None,
            None,
            "asc",
            4,
        ),
        ("ca_1", "Two Three Four", ["member_7"], [], None, None, None, 1),
        ("ca_1", "Two Three Four Five", [], [], None, None, None, 0),
        (
            "ca_1",
            "Three",
            ["member_9", "member_8", "member_7", "member_6", "member_5"],
            [],
            None,
            None,
            None,
            5,
        ),
        ("ca_1", "Three Four", ["member_7"], [], None, None, None, 1),
        ("ca_1", "Four", ["member_7", "member_8"], [], None, None, "asc", 2),
        ("ca_1", "Four Three", ["member_8"], [], None, None, None, 1),
        ("ca_1", "prac_2", [], [], None, None, None, 0),
        (
            "prac_1",
            "test",
            ["member_9"],
            [],
            None,
            None,
            "asc",
            1,
        ),
        ("prac_2", "test", ["member_1"], [], None, None, "asc", 1),
    ],
)
def test_member_search_ids(
    client,
    api_helpers,
    id_test_data,
    user,
    term,
    expected_ids,
    restricted_ids,
    offset,
    limit,
    order_direction,
    expected_total,
):
    query_string = {"q": term}
    if offset:
        query_string["offset"] = offset
    if order_direction:
        query_string["order_direction"] = order_direction
    if limit:
        query_string["limit"] = limit

    u = id_test_data[user]
    res = client.get(
        "/api/v1/members/search",
        query_string=query_string,
        headers=api_helpers.json_headers(user=u),
    )

    data = api_helpers.load_json(res)
    assert data["pagination"]["limit"] == (limit if limit else 10)
    assert data["pagination"]["order_direction"] == (
        order_direction if order_direction else "desc"
    )
    assert data["pagination"]["total"] == expected_total
    assert data["pagination"]["offset"] == (offset if offset else 0)

    assert len(data["data"]) == len(expected_ids)

    actual_ids = [sub["id"] for sub in data["data"]]
    for (actual_id, expected_id) in zip(actual_ids, expected_ids):
        assert actual_id == id_test_data[expected_id].id
    restricted = []
    for r_id in restricted_ids:
        restricted.append(id_test_data[r_id].id)
    assert all(
        (x["id"] not in restricted and x["is_restricted"] is False)
        or (
            x["first_name"] is None
            and x["last_name"] is None
            and x["email"] is None
            and x["organization"] is None
            and x["is_restricted"] is True
        )
        for x in data["data"]
    )


@pytest.fixture
def schema_test_data(factories: factories):
    """Returns a dictionary of object references so that assertions can be made
    comparing the expected data and the result of the calls in the test.

    When adding new test cases via the @pytest.mark.parametrize decorator, reference the
    expected values by their dictionary key.
    """

    org_1 = factories.OrganizationFactory.create(
        name="ABC International", US_restricted=False
    )
    org_2 = factories.OrganizationFactory.create(
        name="US Foo Industries", US_restricted=True
    )

    care_coordinator_1 = factories.PractitionerUserFactory.create(
        first_name="cc1",
        last_name="cc1",
        email="testemailcc1@maventest.com",
        practitioner_profile__country_code="US",
    )

    member_1 = factories.MemberFactory.create(
        email="testemail1@maventest.com",
        member_profile__first_name="test1",
        member_profile__last_name="member1",
        member_profile__country_code="US",
        member_profile__care_team=[care_coordinator_1],
    )

    care_coordinator_2 = factories.PractitionerUserFactory.create(
        first_name="cc2",
        last_name="cc2",
        email="testemailcc2@maventest.com",
        practitioner_profile__country_code="US",
    )

    member_2 = factories.MemberFactory.create(
        email="testemail2@maventest.com",
        member_profile__first_name="test2",
        member_profile__last_name="member2",
        member_profile__country_code="US",
        member_profile__care_team=[care_coordinator_2],
    )

    member_3 = factories.MemberFactory.create(
        email="testemail3@maventest.com",
        member_profile__first_name="test3",
        member_profile__last_name="member3",
        member_profile__country_code="US",
        member_profile__care_team=[care_coordinator_1, care_coordinator_2],
    )

    factories.MemberTrackFactory.create(
        user=member_1,
        client_track=factories.ClientTrackFactory.create(
            organization=org_1,
        ),
    )
    factories.MemberTrackFactory.create(
        user=member_2,
        client_track=factories.ClientTrackFactory.create(
            organization=org_1,
        ),
    )
    factories.MemberTrackFactory.create(
        user=member_3,
        client_track=factories.ClientTrackFactory.create(
            organization=org_2,
        ),
    )

    prac_1 = factories.PractitionerUserFactory.create(
        first_name="pract1",
        last_name="test_pract1",
        email="testp1@maventest.com",
        practitioner_profile__country_code="CA",
    )

    prac_2 = factories.PractitionerUserFactory.create(
        first_name="test_pract2",
        last_name="test_pract2",
        email="testemailp2@maventest.com",
        practitioner_profile__country_code="US",
    )

    prac_3 = factories.PractitionerUserFactory.create(
        first_name="test_pract7",
        last_name="test_pract7",
        email="testemailp3@maventest.com",
    )

    return {
        "member_1": member_1,
        "member_2": member_2,
        "member_3": member_3,
        "prac_1": prac_1,
        "prac_2": prac_2,
        "prac_3": prac_3,
        "org_1": org_1,
        "org_2": org_2,
        "care_coordinator_1": care_coordinator_1,
        "care_coordinator_2": care_coordinator_2,
    }


@pytest.mark.parametrize(
    ["user", "member", "organization", "restricted", "care_coordinators"],
    [
        ("prac_1", "member_1", "org_1", False, ["care_coordinator_1"]),
        ("prac_1", "member_2", "org_1", False, ["care_coordinator_2"]),
        (
            "prac_1",
            "member_3",
            "org_2",
            True,
            ["care_coordinator_1", "care_coordinator_2"],
        ),
        ("prac_2", "member_1", "org_1", False, ["care_coordinator_1"]),
        ("prac_2", "member_2", "org_1", False, ["care_coordinator_2"]),
        (
            "prac_2",
            "member_3",
            "org_2",
            False,
            ["care_coordinator_1", "care_coordinator_2"],
        ),
        (
            "prac_3",
            "member_3",
            "org_2",
            True,
            ["care_coordinator_1", "care_coordinator_2"],
        ),
    ],
)
def test_member_search_schema(
    user,
    member,
    schema_test_data,
    organization,
    restricted,
    care_coordinators,
):
    expected_member = schema_test_data[member]
    schema = MemberSearchResultSchema()
    schema.context["user"] = schema_test_data[user]
    result = schema.dump(schema_test_data[member])[0]

    if restricted:
        assert result["first_name"] is None
        assert result["last_name"] is None
        assert result["email"] is None
        assert result["organization"] is None
    else:
        assert result["first_name"] == expected_member.first_name
        assert result["last_name"] == expected_member.last_name
        assert result["email"] == expected_member.email

        org = schema_test_data[organization]
        assert result["organization"]["name"] == org.name
        assert result["organization"]["US_restricted"] == org.US_restricted

    expected_care_coordinators = [schema_test_data[key] for key in care_coordinators]
    assert len(result["care_coordinators"]) == len(expected_care_coordinators)
    for cc in expected_care_coordinators:
        assert any(
            elem["first_name"] == cc.first_name and elem["last_name"] == cc.last_name
            for elem in result["care_coordinators"]
        )
