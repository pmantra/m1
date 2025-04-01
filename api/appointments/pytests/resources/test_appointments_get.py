import datetime
from unittest import mock

import pytest
from dateutil.relativedelta import relativedelta

from authn.domain.model import User
from geography.repository import CountryRepository
from pytests.factories import (
    AppointmentFactory,
    CountryMetadataFactory,
    EnterpriseUserFactory,
    PractitionerUserFactory,
    ProductFactory,
    ScheduleEventFactory,
    ScheduleFactory,
)

now = datetime.datetime.utcnow()


@pytest.fixture
def three_valid_appointments(three_appointments_with_provider, practitioner_user):
    uk_metadata = CountryMetadataFactory.create(country_code="GB")
    ca = practitioner_user()
    member = EnterpriseUserFactory.create(
        member_profile__phone_number="2125555555",
        member_profile__country_code=uk_metadata.country_code,
    )
    a1, a2, a3 = three_appointments_with_provider(provider=ca, member=member)
    return member, ca, a1, a2, a3


@pytest.fixture
def three_valid_appointments_with_practitioner(three_appointments_with_provider):
    product = ProductFactory.create()
    practitioner = PractitionerUserFactory.create(
        practitioner_profile__verticals=[product.vertical],
        practitioner_profile__experience_started=datetime.date.today()
        - relativedelta(years=12),
    )

    member = EnterpriseUserFactory.create()
    a1, a2, a3 = three_appointments_with_provider(provider=practitioner, member=member)
    return member, practitioner, a1, a2, a3


@pytest.fixture
def three_appointments_with_provider(valid_appointment_with_user):
    def make_with_provider(provider: User, member: User):
        ms = ScheduleFactory.create(user=member)
        a1 = valid_appointment_with_user(
            practitioner=provider,
            member_schedule=ms,
            purpose="birth_needs_assessment",
            scheduled_start=now + datetime.timedelta(minutes=10),
        )
        a2 = valid_appointment_with_user(
            practitioner=provider,
            member_schedule=ms,
            purpose="follow_up",
            scheduled_start=now + datetime.timedelta(days=1),
        )
        a3 = valid_appointment_with_user(
            practitioner=provider,
            member_schedule=ms,
            purpose="third_appointment",
            scheduled_start=now + datetime.timedelta(days=7),
        )
        return a1, a2, a3

    return make_with_provider


@pytest.fixture
def past_appointment_with_provider(valid_appointment_with_user):
    def make_past_appointment(provider: User, member: User):
        if provider.schedule is None:
            ScheduleFactory.create(user=provider)
        week_ago_date = datetime.datetime.now() - datetime.timedelta(weeks=1)
        ScheduleEventFactory.create(
            starts_at=week_ago_date,
            ends_at=week_ago_date + datetime.timedelta(minutes=60),
            schedule=provider.schedule,
        )
        past_appointment = valid_appointment_with_user(
            practitioner=provider,
            member_schedule=member.schedule,
            purpose="past_appointment",
            scheduled_start=week_ago_date,
        )

        return past_appointment

    return make_past_appointment


@pytest.mark.parametrize("experiment_enabled_return_value", [True, False])
@mock.patch(
    "appointments.resources.appointments.AppointmentsResource.experiment_enabled",
    return_value=[True, False],
)
def test_order_direction_desc(
    mock_v3_enabled,
    experiment_enabled_return_value,
    client,
    api_helpers,
    three_valid_appointments,
):
    mock_v3_enabled.return_value = experiment_enabled_return_value
    _, ca, a1, a2, a3 = three_valid_appointments
    res = client.get(
        f"/api/v1/appointments?practitioner_id={ca.id}&order_direction=desc",
        headers=api_helpers.json_headers(ca),
    )
    data = api_helpers.load_json(res)
    assert len(data["data"]) == 3
    assert data["data"][0]["id"] == a3.api_id
    assert data["data"][1]["id"] == a2.api_id
    assert data["data"][2]["id"] == a1.api_id


@pytest.mark.parametrize("experiment_enabled_return_value", [True, False])
@mock.patch(
    "appointments.resources.appointments.AppointmentsResource.experiment_enabled",
    return_value=[True, False],
)
def test_order_direction_asc(
    mock_v3_enabled,
    experiment_enabled_return_value,
    client,
    api_helpers,
    three_valid_appointments,
):
    mock_v3_enabled.return_value = experiment_enabled_return_value
    _, ca, a1, a2, a3 = three_valid_appointments
    res = client.get(
        f"/api/v1/appointments?practitioner_id={ca.id}&order_direction=asc",
        headers=api_helpers.json_headers(ca),
    )
    data = api_helpers.load_json(res)
    assert len(data["data"]) == 3
    assert data["data"][0]["id"] == a1.api_id
    assert data["data"][1]["id"] == a2.api_id
    assert data["data"][2]["id"] == a3.api_id


@pytest.mark.parametrize("experiment_enabled_return_value", [True, False])
@mock.patch(
    "appointments.resources.appointments.AppointmentsResource.experiment_enabled",
    return_value=[True, False],
)
def test_member_id_filter_with_limit(
    mock_v3_enabled,
    experiment_enabled_return_value,
    client,
    api_helpers,
    three_valid_appointments,
):
    mock_v3_enabled.return_value = experiment_enabled_return_value
    member, ca, a1, a2, a3 = three_valid_appointments
    res = client.get(
        f"/api/v1/appointments?member_id={a3.member.id}&limit=1",
        headers=api_helpers.json_headers(a3.member),
    )
    data = api_helpers.load_json(res)
    assert len(data["data"]) == 1
    pagination = data["pagination"]
    assert pagination["total"] == 3
    assert pagination["limit"] == 1

    res = client.get(
        f"/api/v1/appointments?member_id={member.id}&limit=1&offset=1",
        headers=api_helpers.json_headers(member),
    )
    data = api_helpers.load_json(res)
    assert len(data["data"]) == 1
    assert data["pagination"]["total"] == 3
    assert data["pagination"]["limit"] == 1
    assert data["pagination"]["offset"] == 1


@pytest.mark.parametrize("experiment_enabled_return_value", [True, False])
@mock.patch(
    "appointments.resources.appointments.AppointmentsResource.experiment_enabled",
    return_value=[True, False],
)
def test_practitioner_as_member_zero_results(
    mock_v3_enabled,
    experiment_enabled_return_value,
    client,
    api_helpers,
    three_valid_appointments,
):
    mock_v3_enabled.return_value = experiment_enabled_return_value
    member, ca, a1, a2, a3 = three_valid_appointments
    res = client.get(
        f"/api/v1/appointments?member_id={ca.id}",
        headers=api_helpers.json_headers(ca),
    )
    data = api_helpers.load_json(res)
    assert len(data["data"]) == 0


@pytest.mark.parametrize("experiment_enabled_return_value", [True, False])
@mock.patch(
    "appointments.resources.appointments.AppointmentsResource.experiment_enabled",
    return_value=[True, False],
)
def test_practitioner_id_filter(
    mock_v3_enabled,
    experiment_enabled_return_value,
    client,
    api_helpers,
    three_valid_appointments,
):
    mock_v3_enabled.return_value = experiment_enabled_return_value
    member, ca, a1, a2, a3 = three_valid_appointments
    res = client.get(
        f"/api/v1/appointments?practitioner_id={ca.id}",
        headers=api_helpers.json_headers(ca),
    )
    data = api_helpers.load_json(res)
    assert len(data["data"]) == 3


@pytest.mark.parametrize("experiment_enabled_return_value", [True, False])
@mock.patch(
    "appointments.resources.appointments.AppointmentsResource.experiment_enabled",
    return_value=[True, False],
)
def test_start_and_end_filters(
    mock_v3_enabled,
    experiment_enabled_return_value,
    client,
    api_helpers,
    three_valid_appointments,
):
    mock_v3_enabled.return_value = experiment_enabled_return_value
    member, ca, a1, a2, a3 = three_valid_appointments
    res = client.get(
        f"/api/v1/appointments?scheduled_start={a1.scheduled_start.isoformat()}&scheduled_end={(a2.scheduled_end + datetime.timedelta(minutes=2)).isoformat()}",
        headers=api_helpers.json_headers(ca),
    )
    data = api_helpers.load_json(res)
    assert len(data["data"]) == 2

    res = client.get(
        f"/api/v1/appointments?scheduled_start={a1.scheduled_start.isoformat()}&scheduled_end={(a3.scheduled_end + datetime.timedelta(minutes=2)).isoformat()}",
        headers=api_helpers.json_headers(member),
    )
    data = api_helpers.load_json(res)
    assert len(data["data"]) == 3

    res = client.get(
        f"/api/v1/appointments?scheduled_start={a3.scheduled_start.isoformat()}&scheduled_end={(a3.scheduled_end + datetime.timedelta(minutes=2)).isoformat()}",
        headers=api_helpers.json_headers(ca),
    )
    data = api_helpers.load_json(res)
    assert len(data["data"]) == 1

    res = client.get(
        f"/api/v1/appointments?scheduled_start_before={a3.scheduled_start.isoformat()}&scheduled_end={(a3.scheduled_end + datetime.timedelta(minutes=2)).isoformat()}",
        headers=api_helpers.json_headers(ca),
    )
    data = api_helpers.load_json(res)
    assert len(data["data"]) == 2
    for a in data["data"]:
        assert (
            datetime.datetime.strptime(a.get("scheduled_start"), "%Y-%m-%dT%H:%M:%S")
            < a3.scheduled_start
        )


@pytest.mark.parametrize("experiment_enabled_return_value", [True, False])
@mock.patch(
    "appointments.resources.appointments.AppointmentsResource.experiment_enabled",
    return_value=[True, False],
)
def test_start_filter_only_400(
    mock_v3_enabled,
    experiment_enabled_return_value,
    client,
    api_helpers,
    three_valid_appointments,
):
    mock_v3_enabled.return_value = experiment_enabled_return_value
    member, ca, a1, a2, a3 = three_valid_appointments
    res = client.get(
        f"/api/v1/appointments?scheduled_start={a1.scheduled_start.isoformat()}",
        headers=api_helpers.json_headers(ca),
    )
    assert res.status_code == 400


@pytest.mark.parametrize("experiment_enabled_return_value", [True, False])
@mock.patch(
    "appointments.resources.appointments.AppointmentsResource.experiment_enabled",
    return_value=[True, False],
)
def test_end_filter_only_400(
    mock_v3_enabled,
    experiment_enabled_return_value,
    client,
    api_helpers,
    three_valid_appointments,
):
    mock_v3_enabled.return_value = experiment_enabled_return_value
    member, ca, a1, a2, a3 = three_valid_appointments
    res = client.get(
        f"/api/v1/appointments?scheduled_start={a1.scheduled_end.isoformat()}",
        headers=api_helpers.json_headers(ca),
    )
    assert res.status_code == 400


@pytest.mark.parametrize("experiment_enabled_return_value", [True, False])
@mock.patch(
    "appointments.resources.appointments.AppointmentsResource.experiment_enabled",
    return_value=[True, False],
)
def test_member_context_practitioner_id_403(
    mock_v3_enabled,
    experiment_enabled_return_value,
    client,
    api_helpers,
    three_valid_appointments,
):
    mock_v3_enabled.return_value = experiment_enabled_return_value
    member, ca, a1, a2, a3 = three_valid_appointments
    res = client.get(
        f"/api/v1/appointments?practitioner_id={ca.id}",
        headers=api_helpers.json_headers(member),
    )
    assert res.status_code == 403


@pytest.mark.parametrize("experiment_enabled_return_value", [True, False])
@mock.patch(
    "appointments.resources.appointments.AppointmentsResource.experiment_enabled",
    return_value=[True, False],
)
def test_practitioner_context_member_id_403(
    mock_v3_enabled,
    experiment_enabled_return_value,
    client,
    api_helpers,
    three_valid_appointments,
):
    mock_v3_enabled.return_value = experiment_enabled_return_value
    member, ca, a1, a2, a3 = three_valid_appointments
    res = client.get(
        f"/api/v1/appointments?member_id={member.id}",
        headers=api_helpers.json_headers(ca),
    )
    assert res.status_code == 403


@pytest.mark.parametrize("experiment_enabled_return_value", [True, False])
@mock.patch(
    "appointments.resources.appointments.AppointmentsResource.experiment_enabled",
    return_value=[True, False],
)
def test_purposes_filter(
    mock_v3_enabled,
    experiment_enabled_return_value,
    client,
    api_helpers,
    three_valid_appointments,
):
    mock_v3_enabled.return_value = experiment_enabled_return_value
    member, ca, a1, a2, a3 = three_valid_appointments
    res = client.get(
        "/api/v1/appointments?purposes=birth_needs_assessment",
        headers=api_helpers.json_headers(ca),
    )
    data = api_helpers.load_json(res)
    assert len(data["data"]) == 1


@pytest.mark.parametrize("experiment_enabled_return_value", [True, False])
@mock.patch(
    "appointments.resources.appointments.AppointmentsResource.experiment_enabled",
    return_value=[True, False],
)
def test_exclude_status_cancelled(
    mock_v3_enabled,
    experiment_enabled_return_value,
    client,
    api_helpers,
    three_valid_appointments,
):
    mock_v3_enabled.return_value = experiment_enabled_return_value
    member, ca, a1, a2, a3 = three_valid_appointments
    a3.cancelled_at = now
    res = client.get(
        f"/api/v1/appointments?member_id={member.id}&exclude_statuses=CANCELLED",
        headers=api_helpers.json_headers(member),
    )
    data = api_helpers.load_json(res)
    assert len(data["data"]) == 2
    assert a3.api_id not in [a["id"] for a in data["data"]]


@pytest.mark.parametrize("experiment_enabled_return_value", [True, False])
@mock.patch(
    "appointments.resources.appointments.AppointmentsResource.experiment_enabled",
    return_value=[True, False],
)
def test_get_valid_appointment_returns_200(
    mock_v3_enabled,
    experiment_enabled_return_value,
    client,
    api_helpers,
    three_valid_appointments,
):
    mock_v3_enabled.return_value = experiment_enabled_return_value
    member, ca, a1, a2, a3 = three_valid_appointments
    res = client.get(
        f"/api/v1/appointments/{a1.api_id}",
        headers=api_helpers.standard_headers(ca),
    )
    assert res.status_code == 200


@pytest.mark.parametrize("experiment_enabled_return_value", [True, False])
@mock.patch(
    "appointments.resources.appointments.AppointmentsResource.experiment_enabled",
    return_value=[True, False],
)
def test_get_appointment_that_does_not_exist_returns_404(
    mock_v3_enabled,
    experiment_enabled_return_value,
    client,
    api_helpers,
    three_valid_appointments,
):
    mock_v3_enabled.return_value = experiment_enabled_return_value
    member, ca, a1, a2, a3 = three_valid_appointments
    res = client.get(
        f"/api/v1/appointments/{a1.api_id + 1000000}",
        headers=api_helpers.standard_headers(ca),
    )
    assert res.status_code == 404


@pytest.mark.parametrize("experiment_enabled_return_value", [True, False])
@mock.patch(
    "appointments.resources.appointments.AppointmentsResource.experiment_enabled",
    return_value=[True, False],
)
def test_member_cannot_see_other_memebers_apointment(
    mock_v3_enabled,
    experiment_enabled_return_value,
    client,
    api_helpers,
    three_valid_appointments,
):
    mock_v3_enabled.return_value = experiment_enabled_return_value
    member, ca, a1, a2, a3 = three_valid_appointments
    viewing_member = EnterpriseUserFactory.create()
    ScheduleFactory.create(user=viewing_member)
    res = client.get(
        f"/api/v1/appointments/{a1.api_id}",
        headers=api_helpers.standard_headers(viewing_member),
    )
    assert res.status_code == 403


@pytest.mark.parametrize("experiment_enabled_return_value", [True, False])
@mock.patch(
    "appointments.resources.appointments.AppointmentsResource.experiment_enabled",
    return_value=[True, False],
)
def test_practitioner_info(
    mock_v3_enabled,
    experiment_enabled_return_value,
    client,
    api_helpers,
    three_valid_appointments_with_practitioner,
    practitioner_user,
):
    mock_v3_enabled.return_value = experiment_enabled_return_value
    member, practitioner, a1, a2, a3 = three_valid_appointments_with_practitioner
    res = client.get(
        f"/api/v1/appointments/{a2.api_id}",
        headers=api_helpers.standard_headers(practitioner),
    )
    data = api_helpers.load_json(res)
    assert (
        data["product"]["practitioner"]["profiles"]["practitioner"]["years_experience"]
    ) == 12


@pytest.mark.parametrize("experiment_enabled_return_value", [True, False])
@mock.patch(
    "appointments.resources.appointments.AppointmentsResource.experiment_enabled",
    return_value=[True, False],
)
def test_member_info(
    mock_v3_enabled,
    experiment_enabled_return_value,
    client,
    api_helpers,
    three_valid_appointments,
    practitioner_user,
):
    mock_v3_enabled.return_value = experiment_enabled_return_value
    member, ca, a1, a2, a3 = three_valid_appointments
    country_metadata = CountryRepository().get_metadata(
        country_code=member.profile.country_code
    )
    res = client.get(
        f"/api/v1/appointments/{a1.api_id}",
        headers=api_helpers.standard_headers(a1.practitioner),
    )
    assert res.status_code == 200
    data = api_helpers.load_json(res)
    assert "phone_number" in data["member"]["profiles"]["member"]
    assert data["member"]["profiles"]["member"]["phone_number"] == "2125555555"
    assert data["member"]["profiles"]["member"]["tel_number"] == "tel:+1-212-555-5555"
    assert data["member"]["country"] == {
        "name": member.country.name,
        "abbr": member.country_code,
        "ext_info_link": country_metadata.ext_info_link,
        "summary": country_metadata.summary or "",
    }


@pytest.mark.parametrize("experiment_enabled_return_value", [True, False])
@mock.patch(
    "appointments.resources.appointments.AppointmentsResource.experiment_enabled",
    return_value=[True, False],
)
def test_member_get_other_member_appointment_403(
    mock_v3_enabled,
    experiment_enabled_return_value,
    client,
    api_helpers,
    three_valid_appointments,
):
    mock_v3_enabled.return_value = experiment_enabled_return_value
    member, ca, a1, a2, a3 = three_valid_appointments
    viewing_member = EnterpriseUserFactory.create()
    ScheduleFactory.create(user=viewing_member)
    res = client.get(
        f"/api/v1/appointments/{a3.api_id}",
        headers=api_helpers.json_headers(viewing_member),
    )
    assert res.status_code == 403


@pytest.mark.parametrize("experiment_enabled_return_value", [True, False])
@mock.patch(
    "appointments.resources.appointments.AppointmentsResource.experiment_enabled",
    return_value=[True, False],
)
def test_repeat_patient_true(
    mock_v3_enabled,
    experiment_enabled_return_value,
    client,
    api_helpers,
    three_valid_appointments,
    past_appointment_with_provider,
    practitioner_with_availability,
):
    mock_v3_enabled.return_value = experiment_enabled_return_value
    member, ca, a1, a2, a3 = three_valid_appointments
    past_appointment_with_provider(provider=ca, member=member)

    res = client.get(
        f"/api/v1/appointments/{a1.api_id}",
        headers=api_helpers.json_headers(ca),
    )

    data = api_helpers.load_json(res)
    assert data["repeat_patient"]


@pytest.mark.parametrize("experiment_enabled_return_value", [True, False])
@mock.patch(
    "appointments.resources.appointments.AppointmentsResource.experiment_enabled",
    return_value=[True, False],
)
def test_repeat_patient_false(
    mock_v3_enabled,
    experiment_enabled_return_value,
    client,
    api_helpers,
    three_valid_appointments,
    practitioner_with_availability,
):
    mock_v3_enabled.return_value = experiment_enabled_return_value
    member, ca, a1, a2, a3 = three_valid_appointments
    res = client.get(
        f"/api/v1/appointments/{a1.api_id}",
        headers=api_helpers.json_headers(ca),
    )
    data = api_helpers.load_json(res)
    assert not data["repeat_patient"]


@pytest.mark.parametrize("experiment_enabled_return_value", [True, False])
@mock.patch(
    "appointments.resources.appointments.AppointmentsResource.experiment_enabled",
    return_value=[True, False],
)
@pytest.mark.usefixtures("frozen_now")
def test_anon_appointment_does_not_return_pharmacy_info(
    mock_v3_enabled,
    experiment_enabled_return_value,
    client,
    api_helpers,
    valid_appointment_with_user,
    practitioner_with_availability,
    appointment_with_pharmacy,
):
    mock_v3_enabled.return_value = experiment_enabled_return_value
    anon_appt = AppointmentFactory.create_anonymous()
    ca = anon_appt.practitioner
    dp = ca.practitioner_profile.dosespot
    dp["clinic_key"] = 1
    dp["clinic_id"] = 1
    dp["user_id"] = 1

    a = valid_appointment_with_user(
        practitioner=ca,
        purpose="birth_needs_assessment",
        scheduled_start=datetime.datetime.utcnow() + datetime.timedelta(minutes=10),
    )
    mp = a.member.member_profile
    mp.set_patient_info(patient_id=a.member.id, practitioner_id=a.practitioner.id)

    res = client.get(
        f"/api/v1/appointments/{anon_appt.api_id}",
        headers=api_helpers.json_headers(ca),
    )

    data = api_helpers.load_json(res)
    assert data["prescription_info"] == {}
