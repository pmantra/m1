import datetime
import json

import pytz

from appointments.resources.practitioners_availabilities import (
    _get_practitioner_contract_priorities,
)
from models.profiles import PractitionerProfile
from payments.models.practitioner_contract import ContractType
from payments.pytests.factories import PractitionerContractFactory
from pytests import freezegun
from storage.connection import db

DATE_STRING_FORMAT = "%Y-%m-%d %H:%M:%S"


@freezegun.freeze_time("2022-04-06 00:17:10.0")
def test_post_practitioners_availabilities(
    factories,
    client,
    api_helpers,
    create_practitioner,
    add_schedule_event,
):
    """Tests that we can get availability for a single practitioner"""
    now = datetime.datetime.utcnow()
    member = factories.EnterpriseUserFactory.create()
    practitioner = create_practitioner(
        practitioner_profile__next_availability=now,
    )

    # Time for 3 appointment slots
    add_schedule_event(practitioner, now, 3)

    data = {
        "practitioner_ids": [practitioner.id],
    }

    res = client.post(
        "/api/v1/practitioners/availabilities",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    res_data = json.loads(res.data)
    assert len(res_data["data"]) == 1

    practitioner_availabilities = res_data["data"][0]
    assert practitioner_availabilities["practitioner_id"] == practitioner.id
    assert len(practitioner_availabilities["availabilities"]) == 3
    assert (
        practitioner_availabilities["availabilities"][0]["start_time"]
        == "2022-04-06T00:30:00+00:00"
    )


@freezegun.freeze_time("2022-04-06 12:17:10.0")
def test_post_practitioners_availabilities_filters_past_appointments(
    factories,
    client,
    api_helpers,
    create_practitioner,
    add_schedule_event,
):
    """Tests that we can get availability for a single practitioner"""
    now = datetime.datetime.utcnow()
    member = factories.EnterpriseUserFactory.create()
    practitioner = create_practitioner(
        practitioner_profile__next_availability=now,
    )

    first_appointment_time = now - datetime.timedelta(
        minutes=(practitioner.default_product.minutes * 3)
    )

    # Time for 3 appointment slots
    add_schedule_event(practitioner, first_appointment_time, 6)

    data = {
        "practitioner_ids": [practitioner.id],
        "start_time": (now - datetime.timedelta(hours=2)).strftime(DATE_STRING_FORMAT),
        "end_time": (now + datetime.timedelta(hours=2)).strftime(DATE_STRING_FORMAT),
    }

    res = client.post(
        "/api/v1/practitioners/availabilities",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    res_data = json.loads(res.data)
    assert len(res_data["data"]) == 1

    practitioner_availabilities = res_data["data"][0]
    assert practitioner_availabilities["practitioner_id"] == practitioner.id
    assert len(practitioner_availabilities["availabilities"]) == 3

    assert all(
        datetime.datetime.fromisoformat(availability["start_time"])
        > now.replace(tzinfo=pytz.UTC)
        for availability in practitioner_availabilities["availabilities"]
    )


@freezegun.freeze_time("2022-04-06 00:17:10.0")
def test_post_practitioners_availabilities_unavailable(
    factories,
    client,
    api_helpers,
    create_practitioner,
    add_schedule_event,
):
    """Tests that a practitioner who has availability outside the time range returns as an empty list"""
    now = datetime.datetime.utcnow()
    practitioner_next_available = now + datetime.timedelta(days=14)
    member = factories.EnterpriseUserFactory.create()
    practitioner = create_practitioner(
        practitioner_profile__next_availability=practitioner_next_available,
    )

    # Time for 3 appointment slots, but very far in the future
    add_schedule_event(practitioner, practitioner_next_available, 3)

    # Practitioner has no next_availability, which gets displayed as "Available by request" on the FE
    practitioner_2 = create_practitioner(
        practitioner_profile__next_availability=None,
    )

    data = {
        "practitioner_ids": [practitioner.id, practitioner_2.id],
    }

    res = client.post(
        "/api/v1/practitioners/availabilities",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    res_data = json.loads(res.data)
    assert len(res_data["data"]) == 1

    practitioner_availabilities = res_data["data"][0]
    assert practitioner_availabilities["practitioner_id"] == practitioner.id
    assert len(practitioner_availabilities["availabilities"]) == 0


@freezegun.freeze_time("2022-04-06 00:17:10.0")
def test_post_practitioners_availabilities_no_product(
    factories,
    client,
    api_helpers,
    create_practitioner,
):
    """Tests that we can get availability for a single practitioner"""
    now = datetime.datetime.utcnow()
    member = factories.EnterpriseUserFactory.create()
    practitioner = create_practitioner(
        practitioner_profile__next_availability=now,
    )
    practitioner.products = []

    factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule,
        starts_at=now,
        ends_at=now + datetime.timedelta(minutes=60),
    )

    data = {
        "practitioner_ids": [practitioner.id],
    }

    res = client.post(
        "/api/v1/practitioners/availabilities",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    res_data = json.loads(res.data)
    assert len(res_data["data"]) == 0


@freezegun.freeze_time("2022-04-06 00:17:10.0")
def test_post_practitioners_availabilities_no_padding_rounding(
    factories,
    client,
    api_helpers,
    create_practitioner,
    add_schedule_event,
):
    """Tests that availability has the appropriate padding and rounding"""
    now = datetime.datetime.utcnow()
    member = factories.EnterpriseUserFactory.create()

    product = factories.ProductFactory.create(minutes=10)
    practitioner = create_practitioner(
        practitioner_profile__next_availability=now,
        practitioner_profile__booking_buffer=0,
        practitioner_profile__rounding_minutes=15,
        products=[product],
    )

    # Time for 5 appointment slots
    add_schedule_event(practitioner, now, 5)

    data = {
        "practitioner_ids": [practitioner.id],
    }

    res = client.post(
        "/api/v1/practitioners/availabilities",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    res_data = json.loads(res.data)
    assert len(res_data["data"]) == 1

    practitioner_availabilities = res_data["data"][0]
    assert practitioner_availabilities["practitioner_id"] == practitioner.id

    availabilities_list = practitioner_availabilities["availabilities"]
    assert len(availabilities_list) == 7

    # Verify that all breaks are as minimal length
    for i in range(1, len(availabilities_list)):
        prev_availability = availabilities_list[i - 1]
        next_availability = availabilities_list[i]

        prev_end = datetime.datetime.fromisoformat(prev_availability["end_time"])
        next_start = datetime.datetime.fromisoformat(next_availability["start_time"])

        break_duration = next_start - prev_end

        # An appointment starting at 0:00 ends at 0:10. Because there are no rounding_minutes,
        # the earliest time for a following-appointment would be 0:10-0:20
        assert break_duration.seconds == 0
        assert break_duration.days == 0
        assert break_duration.microseconds == 0


@freezegun.freeze_time("2022-04-06 00:17:10.0")
def test_post_practitioners_availabilities_with_member_conflict(
    factories,
    client,
    api_helpers,
    create_practitioner,
    valid_appointment_with_user,
    add_schedule_event,
):
    """We should not show available slots that conflict with the member's existing appointments"""
    now = datetime.datetime.utcnow()
    member = factories.EnterpriseUserFactory.create()
    member_schedule = factories.ScheduleFactory.create(user=member)
    practitioner_1 = create_practitioner(
        practitioner_profile__next_availability=now,
    )
    product = practitioner_1.products[0]

    # Time for 3 appointment slots
    event = add_schedule_event(practitioner_1, now, 3)

    practitioner_2 = create_practitioner()
    scheduled_start = event.starts_at
    scheduled_end = scheduled_start + datetime.timedelta(minutes=product.minutes)
    valid_appointment_with_user(
        practitioner_2,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        member_schedule=member_schedule,
    )

    data = {
        "practitioner_ids": [practitioner_1.id],
    }

    res = client.post(
        "/api/v1/practitioners/availabilities",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    res_data = json.loads(res.data)
    assert len(res_data["data"]) == 1

    practitioner_availabilities = res_data["data"][0]
    assert len(practitioner_availabilities["availabilities"]) == 2

    for availability in practitioner_availabilities["availabilities"]:
        assert datetime.datetime.fromisoformat(
            availability["start_time"]
        ) >= scheduled_end.replace(tzinfo=pytz.UTC)
        assert datetime.datetime.fromisoformat(
            availability["end_time"]
        ) > scheduled_end.replace(tzinfo=pytz.UTC)


@freezegun.freeze_time("2022-04-06 00:17:10.0")
def test_post_practitioners_availabilities_with_practitioner_conflict(
    factories,
    client,
    api_helpers,
    create_practitioner,
    valid_appointment_with_user,
    add_schedule_event,
):
    """Available slots should not conflict with the practitioner's existing appointment"""
    now = datetime.datetime.utcnow()
    member = factories.EnterpriseUserFactory.create()
    practitioner = create_practitioner(
        practitioner_profile__next_availability=now,
    )
    product = practitioner.products[0]

    # Time for 3 appointment slots
    event = add_schedule_event(practitioner, now, 3)

    scheduled_start = event.starts_at
    scheduled_end = scheduled_start + datetime.timedelta(minutes=product.minutes)
    valid_appointment_with_user(
        practitioner,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
    )

    data = {
        "practitioner_ids": [practitioner.id],
    }

    res = client.post(
        "/api/v1/practitioners/availabilities",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    res_data = json.loads(res.data)
    assert len(res_data["data"]) == 1

    practitioner_availabilities = res_data["data"][0]
    assert len(practitioner_availabilities["availabilities"]) == 2

    for availability in practitioner_availabilities["availabilities"]:
        assert datetime.datetime.fromisoformat(
            availability["start_time"]
        ) >= scheduled_end.replace(tzinfo=pytz.UTC)
        assert datetime.datetime.fromisoformat(
            availability["end_time"]
        ) > scheduled_end.replace(tzinfo=pytz.UTC)


@freezegun.freeze_time("2022-04-06 00:17:10.0")
def test_post_practitioners_availabilities_pagination(
    factories,
    client,
    api_helpers,
    create_practitioner,
    add_schedule_event,
):
    """
    Basic pagination test.
    Results are returned in chrono order by start time, and increasing `offset` returns later results.
    """
    now = datetime.datetime.utcnow()
    member = factories.EnterpriseUserFactory.create()
    practitioner = create_practitioner(
        practitioner_profile__next_availability=now,
    )
    start_time = now + datetime.timedelta(minutes=practitioner.profile.booking_buffer)

    # Add two schedule events
    availability_1 = add_schedule_event(practitioner, start_time, 3)
    add_schedule_event(practitioner, availability_1.ends_at, 3)

    data = {
        "practitioner_ids": [practitioner.id],
        "limit": 2,
    }

    res = client.post(
        "/api/v1/practitioners/availabilities",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    res_data = json.loads(res.data)
    assert len(res_data["data"]) == 1

    practitioner_availabilities = res_data["data"][0]
    assert practitioner_availabilities["practitioner_id"] == practitioner.id
    assert len(practitioner_availabilities["availabilities"]) == 2

    # Get the max start/end time to verify that the next call
    # only returns appointment slots after these.
    max_start = max(
        datetime.datetime.fromisoformat(a["start_time"])
        for a in practitioner_availabilities["availabilities"]
    )
    max_end = max(
        datetime.datetime.fromisoformat(a["end_time"])
        for a in practitioner_availabilities["availabilities"]
    )

    data = {
        "practitioner_ids": [practitioner.id],
        "limit": 2,
        "offset": 2,
    }

    res = client.post(
        "/api/v1/practitioners/availabilities",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    res_data = json.loads(res.data)
    assert len(res_data["data"]) == 1

    practitioner_availabilities = res_data["data"][0]
    assert practitioner_availabilities["practitioner_id"] == practitioner.id
    assert len(practitioner_availabilities["availabilities"]) == 2

    # All response objects should be chronologically after the first response
    for availability in practitioner_availabilities["availabilities"]:
        start_time = datetime.datetime.fromisoformat(availability["start_time"])

        assert start_time > max_start
        assert start_time >= max_end


@freezegun.freeze_time("2022-04-06 00:17:10.0")
def test_post_practitioners_availabilities_can_prescribe(
    factories,
    client,
    api_helpers,
    add_schedule_event,
):
    """Tests the endpoint handles the `can_prescribe` param"""
    now = datetime.datetime.utcnow()
    member = factories.EnterpriseUserFactory.create()

    can_prescribe_true_vertical = factories.VerticalFactory(
        name="Yes Prescribe",
        can_prescribe=True,
    )
    can_prescribe_true_product = factories.ProductFactory(
        vertical=can_prescribe_true_vertical, minutes=10, price=1
    )
    practitioner_1 = can_prescribe_true_product.practitioner
    # Lets make all other potential products of the same vertical
    for p in practitioner_1.products:
        p.vertical = can_prescribe_true_vertical

    practitioner_1_pp = db.session.query(PractitionerProfile).get(practitioner_1.id)
    practitioner_1_pp.verticals = [can_prescribe_true_vertical]
    practitioner_1_pp.next_availability = now
    practitioner_1_pp.dosespot = json.dumps({"clinic_key": 1234})

    # Time for 3 appointment slots
    add_schedule_event(practitioner_1, now, 3)

    can_prescribe_false_vertical = factories.VerticalFactory(
        name="No Prescribe", can_prescribe=False
    )
    can_prescribe_false_product = factories.ProductFactory(
        vertical=can_prescribe_false_vertical
    )
    practitioner_2 = can_prescribe_false_product.practitioner
    # Lets make all other potential products of the same vertical
    for p in practitioner_2.products:
        p.vertical = can_prescribe_false_vertical

    practitioner_2_pp = db.session.query(PractitionerProfile).get(practitioner_2.id)
    practitioner_2_pp.verticals = [can_prescribe_false_vertical]
    practitioner_2_pp.next_availability = now
    practitioner_2_pp.dosespot = json.dumps({"clinic_key": 1234})
    # Time for 3 appointment slots
    add_schedule_event(practitioner_2, now, 3)

    data = {
        "practitioner_ids": [practitioner_1.id, practitioner_2.id],
        "can_prescribe": True,
    }

    res = client.post(
        "/api/v1/practitioners/availabilities",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    res_data = json.loads(res.data)
    assert len(res_data["data"]) == 1

    # Only return data for practitioner_1, because they have can_prescribe=True
    practitioner_availabilities = res_data["data"][0]
    assert practitioner_availabilities["practitioner_id"] == practitioner_1.id
    assert len(practitioner_availabilities["availabilities"]) == 3


@freezegun.freeze_time("2022-04-06 00:17:10.0")
def test_post_practitioners_availabilities_provider_type(
    factories,
    client,
    api_helpers,
    add_schedule_event,
):
    """Tests that the endpoint handles the `provider_type` param to filter by vertical"""
    now = datetime.datetime.utcnow()
    member = factories.EnterpriseUserFactory.create()

    purple_vertical = factories.VerticalFactory(name="Purple")
    purple_product = factories.ProductFactory(
        vertical=purple_vertical, minutes=10, price=1
    )

    practitioner_1 = purple_product.practitioner
    # Lets make all other potential products of the same vertical
    for p in practitioner_1.products:
        p.vertical = purple_vertical

    practitioner_1_pp = db.session.query(PractitionerProfile).get(practitioner_1.id)
    practitioner_1_pp.verticals = [
        purple_vertical
    ]  # Not really needed but for consistency
    practitioner_1_pp.next_availability = now

    add_schedule_event(practitioner_1, now, 3, purple_product)

    green_vertical = factories.VerticalFactory(name="Green")
    green_product = factories.ProductFactory(
        vertical=green_vertical, minutes=10, price=1
    )
    practitioner_2 = green_product.practitioner

    # Lets make all other potential products of the same vertical
    for p in practitioner_2.products:
        p.vertical = green_vertical

    practitioner_2_pp = db.session.query(PractitionerProfile).get(practitioner_2.id)
    practitioner_2_pp.verticals = [
        green_vertical
    ]  # Not really needed but for consistency
    practitioner_2_pp.next_availability = now

    # Time for 3 appointment slots
    add_schedule_event(practitioner_2, now, 3, green_product)
    data = {
        "practitioner_ids": [practitioner_1.id, practitioner_2.id],
        "provider_type": "Purple",
    }

    res = client.post(
        "/api/v1/practitioners/availabilities",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    res_data = json.loads(res.data)
    assert len(res_data["data"]) == 1

    # Only return data for practitioner_1, because they have the "Purple" vertical
    practitioner_availabilities = res_data["data"][0]
    assert practitioner_availabilities["practitioner_id"] == practitioner_1.id
    assert practitioner_availabilities["product_id"] == purple_product.id
    assert len(practitioner_availabilities["availabilities"]) == 3


@freezegun.freeze_time("2022-04-06 00:17:10.0")
def test_post_practitioners_availabilities_state_matching(
    factories,
    client,
    api_helpers,
    create_practitioner,
    add_schedule_event,
):
    """Tests that /practitioners/availabilities respects in-state-matching requirements"""
    now = datetime.datetime.utcnow()
    nj_state = factories.StateFactory.create(name="New Jersey", abbreviation="NJ")
    ma_state = factories.StateFactory.create(name="Massachusetts", abbreviation="MA")

    filter_by_state_vertical = factories.VerticalFactory(
        name="OB-GYN", filter_by_state=True
    )
    non_filter_vertical = factories.VerticalFactory(
        name="Wellness Coach", filter_by_state=False
    )

    ma_member = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=ma_member, state=ma_state)
    nj_member = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(user=nj_member, state=nj_state)

    filter_prac = create_practitioner(
        state=nj_state,
        practitioner_profile__verticals=[filter_by_state_vertical],
        practitioner_profile__next_availability=now,
        practitioner_profile__anonymous_allowed=False,
    )
    anon_allowed_prac = create_practitioner(
        state=nj_state,
        practitioner_profile__verticals=[filter_by_state_vertical],
        practitioner_profile__next_availability=now,
        practitioner_profile__anonymous_allowed=True,
    )
    non_filter_prac = create_practitioner(
        state=nj_state,
        practitioner_profile__verticals=[non_filter_vertical],
        practitioner_profile__next_availability=now,
        practitioner_profile__anonymous_allowed=False,
    )

    # Time for 3 appointment slots
    add_schedule_event(filter_prac, now, 3)
    add_schedule_event(anon_allowed_prac, now, 3)
    add_schedule_event(non_filter_prac, now, 3)

    data = {
        "practitioner_ids": [filter_prac.id, non_filter_prac.id, anon_allowed_prac.id],
    }

    # Make a request with ma_member
    # This member is out of state, so should only receive availabilities for
    # non_filter_prac
    res = client.post(
        "/api/v1/practitioners/availabilities",
        data=json.dumps(data),
        headers=api_helpers.json_headers(ma_member),
    )

    res_data = json.loads(res.data)
    assert len(res_data["data"]) == 2

    received_ids = set()
    for practitioner_availabilities in res_data["data"]:
        received_ids.add(practitioner_availabilities["practitioner_id"])
        assert len(practitioner_availabilities["availabilities"]) == 3
    assert received_ids == {non_filter_prac.id, anon_allowed_prac.id}

    # Make a request with nj_member
    # This member is in state, so should receive availabilities for both practitioners
    res = client.post(
        "/api/v1/practitioners/availabilities",
        data=json.dumps(data),
        headers=api_helpers.json_headers(nj_member),
    )

    res_data = json.loads(res.data)
    assert len(res_data["data"]) == 3

    received_ids = set()
    for practitioner_availabilities in res_data["data"]:
        received_ids.add(practitioner_availabilities["practitioner_id"])
        assert len(practitioner_availabilities["availabilities"]) == 3
    assert received_ids == {filter_prac.id, non_filter_prac.id, anon_allowed_prac.id}


@freezegun.freeze_time("2022-04-06 00:17:10.0")
def test_post_practitioners_ordering(
    factories,
    client,
    api_helpers,
    create_practitioner,
    add_schedule_event,
):
    """Tests that we sort practitioners by contract tier."""
    # This test borrows heavily from test_practitioner_search.py::test_search__orders_providers_by_contract_and_availability
    now = datetime.datetime.utcnow()
    member = factories.EnterpriseUserFactory.create()
    practitioners = [
        create_practitioner(
            practitioner_profile__next_availability=now + datetime.timedelta(hours=i),
        )
        for i in range(0, 8)
    ]

    # Pair practitioners with contracts in order of tier time
    # Within each tier we don't expect their order to change because they already have
    # ascending next-availability
    non_contract_practitioner = practitioners[0]
    expected_practitioner_order_and_contracts = [
        (practitioners[2], ContractType.FIXED_HOURLY),
        (practitioners[4], ContractType.W2),
        (practitioners[6], ContractType.FIXED_HOURLY_OVERNIGHT),
        (practitioners[3], ContractType.HYBRID_1_0),
        (practitioners[5], ContractType.HYBRID_2_0),
        (practitioners[1], ContractType.BY_APPOINTMENT),
        (practitioners[7], ContractType.NON_STANDARD_BY_APPOINTMENT),
    ]
    for practitioner, contract in expected_practitioner_order_and_contracts:
        PractitionerContractFactory.create(
            practitioner=practitioner.practitioner_profile,
            contract_type=contract,
        )

    # Time for 3 appointment slots
    for practitioner in practitioners:
        add_schedule_event(practitioner, now, 3)

    data = {
        "practitioner_ids": [practitioner.id for practitioner in practitioners],
    }

    res = client.post(
        "/api/v1/practitioners/availabilities",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    res_data = json.loads(res.data)
    actual_practitioner_ids = [
        availability["practitioner_id"] for availability in res_data["data"]
    ]
    expected_practitioner_ids = [
        t[0].id for t in expected_practitioner_order_and_contracts
    ]
    # practitioners with no active contracts are sorted at the end
    expected_practitioner_ids.append(non_contract_practitioner.id)

    assert len(res_data["data"]) == 8
    assert expected_practitioner_ids == actual_practitioner_ids


def test_post_practitioners__sort_by_availability_within_range__provider_steerage_sort_false(
    factories,
    client,
    api_helpers,
    create_practitioner,
    add_schedule_event,
):
    """Tests that we sort practitioners by availability within contract tier."""
    # Given 9 practitioners with contracts, 1 without
    now = datetime.datetime.utcnow()
    member = factories.EnterpriseUserFactory.create()
    practitioners = [
        create_practitioner(
            practitioner_profile__next_availability=now + datetime.timedelta(hours=i),
        )
        for i in range(0, 10)
    ]

    # Pair practitioners with contracts in order of tier time
    # Within each tier we don't expect their order to change because they already have
    # ascending next-availability
    non_contract_practitioner = practitioners[0]
    expected_practitioner_order_and_contracts = [
        (practitioners[2], ContractType.FIXED_HOURLY),
        (practitioners[4], ContractType.W2),
        (practitioners[6], ContractType.FIXED_HOURLY_OVERNIGHT),
        (practitioners[3], ContractType.HYBRID_1_0),
        (practitioners[5], ContractType.HYBRID_2_0),
        (practitioners[8], ContractType.HYBRID_2_0),
        (practitioners[1], ContractType.BY_APPOINTMENT),
        (practitioners[7], ContractType.NON_STANDARD_BY_APPOINTMENT),
        (practitioners[9], ContractType.BY_APPOINTMENT),
    ]
    for practitioner, contract in expected_practitioner_order_and_contracts:
        PractitionerContractFactory.create(
            practitioner=practitioner.practitioner_profile,
            contract_type=contract,
        )

    # Time for 3 appointment slots
    for i in range(1, 10):
        add_schedule_event(
            practitioners[i], now + datetime.timedelta(hours=(12 - i)), 3
        )

    # don't include provider_steerage_sort param
    data = {
        "practitioner_ids": [practitioner.id for practitioner in practitioners],
    }

    # When we hit the post practitioners endpoint
    res = client.post(
        "/api/v1/practitioners/availabilities",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    res_data = json.loads(res.data)
    actual_practitioner_ids = [
        availability["practitioner_id"] for availability in res_data["data"]
    ]
    expected_practitioner_ids = [
        t[0].id for t in expected_practitioner_order_and_contracts
    ]
    # practitioners with no active contracts are sorted at the end
    expected_practitioner_ids.append(non_contract_practitioner.id)

    # Then the practitioner_ids are sorted by contract priority first, then availability
    assert len(res_data["data"]) == 10
    assert expected_practitioner_ids == actual_practitioner_ids


def test_post_practitioners__sort_by_availability_within_range__provider_steerage_sort_true(
    factories,
    client,
    api_helpers,
    create_practitioner,
    add_schedule_event,
):
    """Tests that we sort practitioners by availability within contract tier."""
    # Given 9 practitioners with contracts, 1 without
    now = datetime.datetime.utcnow()
    member = factories.EnterpriseUserFactory.create()
    practitioners = [
        create_practitioner(
            practitioner_profile__next_availability=now + datetime.timedelta(hours=i),
        )
        for i in range(0, 10)
    ]

    # Pair practitioners with contracts in order of tier time
    # Within each tier we don't expect their order to change because they already have
    # ascending next-availability
    non_contract_practitioner = practitioners[0]
    expected_practitioner_order_and_contracts = [
        (practitioners[6], ContractType.FIXED_HOURLY_OVERNIGHT),
        (practitioners[4], ContractType.W2),
        (practitioners[2], ContractType.FIXED_HOURLY),
        (practitioners[8], ContractType.HYBRID_2_0),
        (practitioners[5], ContractType.HYBRID_2_0),
        (practitioners[3], ContractType.HYBRID_1_0),
        (practitioners[9], ContractType.BY_APPOINTMENT),
        (practitioners[7], ContractType.NON_STANDARD_BY_APPOINTMENT),
        (practitioners[1], ContractType.BY_APPOINTMENT),
    ]
    for practitioner, contract in expected_practitioner_order_and_contracts:
        PractitionerContractFactory.create(
            practitioner=practitioner.practitioner_profile,
            contract_type=contract,
        )

    # Time for 3 appointment slots
    for i in range(1, 10):
        add_schedule_event(
            practitioners[i], now + datetime.timedelta(hours=(12 - i)), 3
        )

    data = {
        "practitioner_ids": [practitioner.id for practitioner in practitioners],
        "provider_steerage_sort": True,
    }

    # When we hit the post practitioners endpoint
    res = client.post(
        "/api/v1/practitioners/availabilities",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    res_data = json.loads(res.data)
    actual_practitioner_ids = [
        availability["practitioner_id"] for availability in res_data["data"]
    ]
    expected_practitioner_ids = [
        t[0].id for t in expected_practitioner_order_and_contracts
    ]
    # practitioners with no active contracts are sorted at the end
    expected_practitioner_ids.append(non_contract_practitioner.id)

    # Then the practitioner_ids are sorted by contract priority first, then availability
    assert len(res_data["data"]) == 10
    assert expected_practitioner_ids == actual_practitioner_ids


def test_get_practitioner_contract_priorities(factories):
    # Given 7 practitioners with different contract types, 1 without a contract
    now = datetime.datetime.utcnow()
    practitioners = [
        factories.PractitionerUserFactory.create(
            practitioner_profile__next_availability=now + datetime.timedelta(hours=i),
        )
        for i in range(0, 8)
    ]
    non_contract_practitioner = practitioners[0]
    practitioner_contract_mapping = [
        (practitioners[1], ContractType.BY_APPOINTMENT),
        (practitioners[2], ContractType.FIXED_HOURLY),
        (practitioners[3], ContractType.HYBRID_1_0),
        (practitioners[4], ContractType.W2),
        (practitioners[5], ContractType.HYBRID_2_0),
        (practitioners[6], ContractType.FIXED_HOURLY_OVERNIGHT),
        (practitioners[7], ContractType.NON_STANDARD_BY_APPOINTMENT),
    ]
    for practitioner, contract in practitioner_contract_mapping:
        PractitionerContractFactory.create(
            practitioner=practitioner.practitioner_profile,
            contract_type=contract,
        )

    expected_contract_priority_results = {
        practitioners[1].id: 3,
        practitioners[2].id: 1,
        practitioners[3].id: 2,
        practitioners[4].id: 1,
        practitioners[5].id: 2,
        practitioners[6].id: 1,
        practitioners[7].id: 3,
    }

    practitioner_profiles = [p.practitioner_profile for p in practitioners]

    # When we call _get_practitioner_contract_priorities
    get_practitioner_contract_priority_results = _get_practitioner_contract_priorities(
        practitioner_profiles
    )

    # Then the resulting practitioner_ids are mapped to the contract prioritization that we expect
    assert (
        get_practitioner_contract_priority_results == expected_contract_priority_results
    )
    # And non_contract_practitioner is excluded from the results
    assert not get_practitioner_contract_priority_results.get(non_contract_practitioner)


@freezegun.freeze_time("2022-04-06 00:17:10.0")
def test_post_practitioners_availabilities_invalid(
    factories,
    client,
    api_helpers,
    create_practitioner,
    add_schedule_event,
):
    now = datetime.datetime.utcnow()
    member = factories.EnterpriseUserFactory.create()
    practitioner = create_practitioner(
        practitioner_profile__next_availability=now,
    )

    # Time for 3 appointment slots
    add_schedule_event(practitioner, now, 3)

    data = {"practitioner_ids": [practitioner.id], "start_time": "garbage"}

    res = client.post(
        "/api/v1/practitioners/availabilities",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 400
