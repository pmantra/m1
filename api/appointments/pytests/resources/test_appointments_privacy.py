import datetime
import json

from pytests.factories import EnterpriseUserFactory, ScheduleFactory

now = datetime.datetime.utcnow()


def test_privacy_practitioners_have_full_access_to_patient_info_via_non_anonymous_appointment(
    client,
    api_helpers,
    setup_post_appointment_test,
    get_appointment_from_endpoint,
    patch_authorize_payment,
):
    """Tests that practitioners have full access to patients' info via non-anonymous appointment"""
    appointment_setup_values = setup_post_appointment_test()
    member = appointment_setup_values.member
    practitioner = appointment_setup_values.practitioner
    data = appointment_setup_values.data

    res = client.post(
        "/api/v1/appointments",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    res_data = json.loads(res.data)

    assert res.status_code == 201
    assert res_data["member"]
    assert "last_name" in res_data["member"]
    assert res_data["privacy"] == "basic"
    assert "member" in res_data["member"]["profiles"]
    assert "phone_number" in res_data["member"]["profiles"]["member"]
    assert len(res_data["member"]) > 2

    res1 = get_appointment_from_endpoint(api_id=res_data["id"], user=practitioner)

    assert res1.status_code == 200

    res1_data = json.loads(res1.data)

    assert res1_data["member"]["email"] == member.email
    assert len(res1_data["member"]) > 2

    res2 = client.get(
        "/api/v1/appointments",
        headers=api_helpers.json_headers(practitioner),
    )

    assert res2.status_code == 200

    res2_data = json.loads(res2.data)
    for appt in res2_data["data"]:
        assert len(appt["member"]) > 2


def test_privacy_non_ca_practitioners_cannot_access_member_email(
    wellness_coach_user,
    valid_appointment_with_user,
    get_appointment_from_endpoint,
):
    """Tests that non-ca practitioners do not have access to member email"""
    non_ca_provider = wellness_coach_user()
    member = EnterpriseUserFactory.create()
    ms = ScheduleFactory.create(user=member)
    a = valid_appointment_with_user(
        scheduled_start=now + datetime.timedelta(minutes=15),
        practitioner=non_ca_provider,
        member_schedule=ms,
    )

    res = get_appointment_from_endpoint(api_id=a.api_id, user=non_ca_provider)
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert res_data["member"]["email"] is None


def test_privacy_member_has_full_access_to_profile_when_member_is_requester_via_anonymous_appointment(
    client,
    api_helpers,
    setup_post_appointment_test,
    get_appointment_from_endpoint,
    patch_authorize_payment,
):
    """Tests that a member has full access to member's profile when member is requester via anonymous appointment"""
    appointment_setup_values = setup_post_appointment_test()
    member = appointment_setup_values.member
    data = appointment_setup_values.data
    data["privacy"] = "anonymous"

    res = client.post(
        "/api/v1/appointments",
        data=json.dumps(data),
        headers=api_helpers.json_headers(member),
    )

    res_data = json.loads(res.data)

    assert res.status_code == 201
    assert res_data["member"]
    assert res_data["privacy"] == "anonymous"
    assert len(res_data["member"]) > 1
    assert res_data["member"]["profiles"]
    assert res_data["member"]["profiles"]["member"]
    assert "phone_number" in res_data["member"]["profiles"]["member"]
    assert len(res_data["member"]["profiles"]["member"]) > 2

    # get appointment - member is requester, expose full member profile info
    res1 = get_appointment_from_endpoint(api_id=res_data["id"], user=member)

    assert res1.status_code == 200

    res1_data = json.loads(res1.data)
    assert len(res1_data["member"]) > 1
    assert len(res1_data["member"]["profiles"]["member"]) > 4


def test_privacy_practitioner_only_has_access_to_minimum_member_profile_when_practitioner_is_requester_via_anonymous_appointment(
    client,
    api_helpers,
    setup_post_appointment_test,
    get_appointment_from_endpoint,
    patch_authorize_payment,
):
    """Tests that a practitioner only has access to minimum member's profile when practitioner is requester via anonymous appointment"""
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

    res_data = json.loads(res.data)

    assert res.status_code == 201
    assert res_data["member"]
    assert res_data["privacy"] == "anonymous"
    assert len(res_data["member"]) > 1
    assert res_data["member"]["profiles"]
    assert res_data["member"]["profiles"]["member"]
    assert "phone_number" in res_data["member"]["profiles"]["member"]
    assert len(res_data["member"]["profiles"]["member"]) > 2

    # get appointment - practitioner is requester, expose only minimum member profile info
    res1 = get_appointment_from_endpoint(api_id=res_data["id"], user=practitioner)

    assert res1.status_code == 200

    res1_data = json.loads(res1.data)
    assert len(res1_data["member"]["profiles"]["member"]) <= 4
    assert list(res1_data["member"].keys()) == ["profiles", "country"]
