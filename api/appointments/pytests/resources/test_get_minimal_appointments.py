import json
from http import HTTPStatus

from pytests.factories import RescheduleHistoryFactory
from views.schemas.common import MavenDateTime


def test_get_minimal_appointment(
    client,
    api_helpers,
    setup_post_appointment_test,
    patch_authorize_payment,
):
    """Tests that minimal appointment can be retrieved"""
    appointment_setup_values = setup_post_appointment_test()
    member = appointment_setup_values.member
    practitioner = appointment_setup_values.practitioner
    data = appointment_setup_values.data

    res = client.post(
        "/api/v1/appointments",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 201

    res_1 = client.get(
        "/api/v1/appointments?minimal=true",
        data=json.dumps(data),
        headers=api_helpers.json_headers(practitioner),
    )

    res_data1 = json.loads(res_1.data)

    assert res_1.status_code == 200
    assert "meta" in res_data1
    assert "data" in res_data1
    assert "pagination" in res_data1
    assert len(res_data1["data"]) == 1

    keys = [
        "id",
        "scheduled_start",
        "cancelled_at",
        "member",
        "product",
        "pre_session",
        "post_session",
        "privacy",
        "need",
    ]
    for key in keys:
        assert key in res_data1["data"][0]


def test_get_product_field(
    factories, client, api_helpers, setup_post_appointment_test, patch_authorize_payment
):
    """Tests that minimal appointment product matches the specified dictionary"""
    appointment_setup_values = setup_post_appointment_test()
    member = appointment_setup_values.member
    practitioner = appointment_setup_values.practitioner
    data = appointment_setup_values.data

    practitioner.first_name = "First"
    practitioner.last_name = "Last"

    vertical_name = "Allergist"
    vertical = factories.VerticalFactory(name=vertical_name, filter_by_state=False)
    profile = practitioner.practitioner_profile
    profile.verticals = [vertical]

    res = client.post(
        "/api/v1/appointments",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 201

    res_1 = client.get(
        "/api/v1/appointments?minimal=true",
        data=json.dumps(data),
        headers=api_helpers.json_headers(practitioner),
    )

    res_data1 = json.loads(res_1.data)

    assert res_1.status_code == 200

    dict1 = res_data1["data"][0]["product"]
    dict2 = {
        "practitioner": {
            "name": f"{practitioner.first_name} {practitioner.last_name}",
            "image_url": None,
            "profiles": {"practitioner": {"verticals": [vertical_name]}},
        }
    }

    assert dict1 == dict2


def test_get_member_field_anonymous(
    client,
    api_helpers,
    setup_post_appointment_test,
    patch_authorize_payment,
):
    """Tests that minimal appointment member dictionary contains 'country' key and verifies minimal appointment privilege type matches appointment privilege type"""
    """
    scenario:
        We want to return the country key regardless of privacy,
        but display `null` if the member is in the United States.
        This is because of a default shown on certain clients.
    """
    appointment_setup_values = setup_post_appointment_test()
    member = appointment_setup_values.member
    practitioner = appointment_setup_values.practitioner
    data = appointment_setup_values.data
    data["privacy"] = "anonymous"

    res = client.post(
        "/api/v1/appointments",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 201

    res_data = json.loads(res.data)

    res_1 = client.get(
        "/api/v1/appointments?minimal=true",
        data=json.dumps(data),
        headers=api_helpers.json_headers(practitioner),
    )

    res_data1 = json.loads(res_1.data)

    assert res_1.status_code == 200

    assert not res_data1["data"][0]["member"]["country"]
    assert res_data1["data"][0]["privilege_type"] == res_data["privilege_type"]


def test_get_member_field_non_anonymous(
    client,
    api_helpers,
    setup_post_appointment_test,
    patch_authorize_payment,
):
    """Tests that minimal appointment member and privilege type matches appointment member and privilege type"""
    appointment_setup_values = setup_post_appointment_test()
    member = appointment_setup_values.member
    practitioner = appointment_setup_values.practitioner
    data = appointment_setup_values.data

    member.first_name = "first"
    member.last_name = "last"

    res = client.post(
        "/api/v1/appointments",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 201

    res_data = json.loads(res.data)

    res_1 = client.get(
        "/api/v1/appointments?minimal=true",
        data=json.dumps(data),
        headers=api_helpers.json_headers(practitioner),
    )

    res_data1 = json.loads(res_1.data)
    member_response = res_data1["data"][0]["member"]

    assert res_1.status_code == 200
    assert member_response["name"] == f"{member.first_name} {member.last_name}"
    assert res_data1["data"][0]["privilege_type"] == res_data["privilege_type"]


def test_get_member_field_international(
    client,
    api_helpers,
    setup_post_appointment_test,
    patch_authorize_payment,
):
    """Tests that appointment member's country name matches minimal appointment member's country name when country is international"""
    """
    scenario:
        We want to return the member's country regardless of privacy,
        but only if the member is not located in the United States
    """
    appointment_setup_values = setup_post_appointment_test()
    member = appointment_setup_values.member
    practitioner = appointment_setup_values.practitioner
    data = appointment_setup_values.data
    data["privilege_type"] = "international"
    data["privacy"] = "anonymous"

    member.profile.country_code = "IN"

    res = client.post(
        "/api/v1/appointments",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 201

    res_1 = client.get(
        "/api/v1/appointments?minimal=true",
        data=json.dumps(data),
        headers=api_helpers.json_headers(practitioner),
    )

    res_data1 = json.loads(res_1.data)
    member_response = res_data1["data"][0]["member"]

    assert res_1.status_code == 200
    assert member_response["country"]["name"] == member.country.name


def test_contains_rescheduled_from_previous_appointment_time(
    basic_appointment, get_minimal_appointments_from_endpoint
):
    appointment = basic_appointment
    reschedule_history = RescheduleHistoryFactory.create(
        appointment_id=basic_appointment.id
    )

    # Get the appointment from the endpoint
    response = get_minimal_appointments_from_endpoint(user=appointment.practitioner)

    assert response.status_code == HTTPStatus.OK
    assert response.json["data"][0].get(
        "rescheduled_from_previous_appointment_time"
    ) == MavenDateTime()._serialize(reschedule_history.scheduled_start, None, None)


def test_no_rescheduled_from_previous_appointment_time_for_member_user(
    enterprise_appointment,
    get_minimal_appointments_from_endpoint,
):
    appointment = enterprise_appointment
    RescheduleHistoryFactory.create(appointment_id=enterprise_appointment.id)

    # Get the appointment from the endpoint
    response = get_minimal_appointments_from_endpoint(user=appointment.member)

    assert response.status_code == HTTPStatus.OK
    assert (
        response.json["data"][0].get("rescheduled_from_previous_appointment_time")
        is None
    )
