from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from appointments.services.common import deobfuscate_appointment_id
from authz.models.roles import ROLES
from models.common import PrivilegeType
from pytests.freezegun import freeze_time

FREEZE_TIME_STR = "2024-03-01T12:00:00"


@pytest.fixture
@freeze_time(FREEZE_TIME_STR)
def setup_three_appointments(
    factories,
    valid_appointment_with_user,
    practitioner_user,
):
    provider = practitioner_user()
    member = factories.EnterpriseUserFactory.create()
    ms = factories.ScheduleFactory.create(user=member)

    appointments = [
        valid_appointment_with_user(
            practitioner=provider,
            member_schedule=ms,
            purpose="test purpose",
            scheduled_start=datetime.utcnow(),
        ),
        valid_appointment_with_user(
            practitioner=provider,
            member_schedule=ms,
            purpose="test purpose",
            scheduled_start=datetime.utcnow() + timedelta(minutes=60),
        ),
        valid_appointment_with_user(
            practitioner=provider,
            member_schedule=ms,
            purpose="test purpose",
            scheduled_start=datetime.utcnow() + timedelta(minutes=120),
        ),
    ]
    appointments[0].privilege_type = PrivilegeType.ANONYMOUS

    return provider, member, appointments


@freeze_time(FREEZE_TIME_STR)
def test_get_member_appointments_list(
    client,
    api_helpers,
    setup_three_appointments,
):
    now = datetime.utcnow()
    provider, member, appointments = setup_three_appointments
    expected_appts_by_id = {a.id: a for a in appointments}
    expected_ids = expected_appts_by_id.keys()

    query_str = {
        "scheduled_start": now.isoformat(),
        "scheduled_end": (now + timedelta(hours=3)).isoformat(),
        "order_direction": "asc",
    }
    res = client.get(
        "/api/v2/member/appointments",
        headers=api_helpers.json_headers(member),
        query_string=query_str,
    )

    assert res.status_code == 200
    assert res.json["pagination"]["total"]
    data = res.json["data"]
    for appt in data:
        appt["id"] = deobfuscate_appointment_id(appt["id"])

    actual_ids = {a.get("id") for a in data}
    assert actual_ids == expected_ids

    for actual_appt in data:
        expected_appt = expected_appts_by_id[actual_appt["id"]]
        actual_appt_provider = actual_appt["provider"]

        assert actual_appt["product_id"] == expected_appt.product_id
        assert actual_appt["need"] is None
        assert (
            actual_appt["scheduled_start"] == expected_appt.scheduled_start.isoformat()
        )
        assert actual_appt["scheduled_end"] == expected_appt.scheduled_end.isoformat()
        assert actual_appt_provider["id"] == expected_appt.practitioner.id
        assert len(actual_appt_provider["verticals"]) == len(
            expected_appt.practitioner.practitioner_profile.verticals
        )
        assert (
            actual_appt_provider["verticals"][0]["id"]
            == expected_appt.practitioner.practitioner_profile.verticals[0].id
        )
        assert (
            actual_appt_provider["verticals"][0]["name"]
            == expected_appt.practitioner.practitioner_profile.verticals[0].name
        )
        assert len(actual_appt_provider["certified_states"]) == len(
            expected_appt.practitioner.practitioner_profile.certified_states
        )
        assert (
            actual_appt_provider["certified_states"][0]["id"]
            == expected_appt.practitioner.practitioner_profile.certified_states[0].id
        )
        assert (
            actual_appt_provider["certified_states"][0]["name"]
            == expected_appt.practitioner.practitioner_profile.certified_states[0].name
        )

        if expected_appt.cancelled_at:
            assert actual_appt["cancelled_at"] == expected_appt.cancelled_at.isoformat()
        else:
            assert actual_appt["cancelled_at"] is None
    assert data[0]["appointment_type"] == "anonymous"


@freeze_time(FREEZE_TIME_STR)
def test_get_member_appointments_list_limit(
    client,
    api_helpers,
    setup_three_appointments,
):
    now = datetime.utcnow()
    provider, member, appointments = setup_three_appointments

    query_str = {
        "scheduled_start": now.isoformat(),
        "scheduled_end": (now + timedelta(hours=3)).isoformat(),
        "order_direction": "asc",
        "limit": 1,
    }
    res = client.get(
        "/api/v2/member/appointments",
        headers=api_helpers.json_headers(member),
        query_string=query_str,
    )

    assert res.status_code == 200
    assert res.json["pagination"]["total"] == len(appointments)
    data = res.json["data"]
    for appt in data:
        appt["id"] = deobfuscate_appointment_id(appt["id"])

    actual_ids = [a.get("id") for a in data]
    assert actual_ids == [appointments[0].id]

    query_str_2 = {
        "scheduled_start": now.isoformat(),
        "scheduled_end": (now + timedelta(hours=3)).isoformat(),
        "order_direction": "asc",
        "limit": 1,
        "offset": 1,
    }
    res = client.get(
        "/api/v2/member/appointments",
        headers=api_helpers.json_headers(member),
        query_string=query_str_2,
    )

    assert res.status_code == 200
    assert res.json["pagination"]["total"] == len(appointments)
    data = res.json["data"]
    for appt in data:
        appt["id"] = deobfuscate_appointment_id(appt["id"])

    actual_ids = [a.get("id") for a in data]
    assert actual_ids == [appointments[1].id]


@freeze_time(FREEZE_TIME_STR)
def test_get_member_appointments_list_with_survey_types(
    client,
    api_helpers,
    factories,
    valid_appointment_with_user,
    practitioner_user,
    wellness_coach_user,
):
    # Given
    now = datetime.utcnow()
    ca_provider = practitioner_user()
    other_provider = wellness_coach_user()
    member = factories.EnterpriseUserFactory.create()
    ms = factories.ScheduleFactory.create(user=member)

    # Add the ca-vertical-specific questionnaire
    member_role = factories.RoleFactory.create(name=ROLES.member)
    ca_questionnaire_oid = "member_rating_ca"
    factories.QuestionnaireFactory.create(
        oid=ca_questionnaire_oid,
        verticals=[ca_provider.practitioner_profile.verticals[0]],
        roles=[member_role],
    )

    # Create two appointments, one cancelled appt w/ a ca
    # and a normal appointment in a different vertical.
    # We created a CA-specific questionnaire above that we expect to see,
    # and also cancelled appointments have an additional questionnaire
    cancelled_appointment_with_ca = valid_appointment_with_user(
        practitioner=ca_provider,
        member_schedule=ms,
        purpose="test purpose",
        scheduled_start=datetime.utcnow(),
    )
    cancelled_appointment_with_ca.cancelled_at = datetime.utcnow()

    valid_appointment_with_user(
        practitioner=other_provider,
        member_schedule=ms,
        purpose="test purpose",
        scheduled_start=datetime.utcnow() + timedelta(minutes=60),
    )

    query_str = {
        "scheduled_start": now.isoformat(),
        "scheduled_end": (now + timedelta(hours=3)).isoformat(),
        "order_direction": "asc",
    }

    # When
    # for experiment-post-appointment-questionnaire-from-vertical
    with patch(
        "maven.feature_flags.bool_variation",
        return_value=True,
    ):
        res = client.get(
            "/api/v2/member/appointments",
            headers=api_helpers.json_headers(member),
            query_string=query_str,
        )

    # Then
    data = res.json["data"]
    assert res.status_code == 200
    assert set(data[0]["survey_types"]) == {"cancellation_survey", ca_questionnaire_oid}
    assert set(data[1]["survey_types"]) == {
        "member_rating_v2",
        "member_rating_followup_v2",
    }


@freeze_time(FREEZE_TIME_STR)
def test_get_member_appointments_list_with_survey_types_flag_off(
    client,
    api_helpers,
    factories,
    valid_appointment_with_user,
    practitioner_user,
    wellness_coach_user,
):
    # Given
    # experiment-post-appointment-questionnaire-from-vertical flag off
    now = datetime.utcnow()
    ca_provider = practitioner_user()
    other_provider = wellness_coach_user()
    member = factories.EnterpriseUserFactory.create()
    ms = factories.ScheduleFactory.create(user=member)

    # Add the ca-vertical-specific questionnaire
    member_role = factories.RoleFactory.create(name=ROLES.member)
    ca_questionnaire_oid = "member_rating_ca"
    factories.QuestionnaireFactory.create(
        oid=ca_questionnaire_oid,
        verticals=[ca_provider.practitioner_profile.verticals[0]],
        roles=[member_role],
    )

    # Create two appointments, one cancelled appt w/ a ca
    # and a normal appointment in a different vertical.
    # We created a CA-specific questionnaire above that we expect to see,
    # and also cancelled appointments have an additional questionnaire
    cancelled_appointment_with_ca = valid_appointment_with_user(
        practitioner=ca_provider,
        member_schedule=ms,
        purpose="test purpose",
        scheduled_start=datetime.utcnow(),
    )
    cancelled_appointment_with_ca.cancelled_at = datetime.utcnow()

    valid_appointment_with_user(
        practitioner=other_provider,
        member_schedule=ms,
        purpose="test purpose",
        scheduled_start=datetime.utcnow() + timedelta(minutes=60),
    )

    query_str = {
        "scheduled_start": now.isoformat(),
        "scheduled_end": (now + timedelta(hours=3)).isoformat(),
        "order_direction": "asc",
    }

    # When

    res = client.get(
        "/api/v2/member/appointments",
        headers=api_helpers.json_headers(member),
        query_string=query_str,
    )

    # Then
    data = res.json["data"]
    assert res.status_code == 200
    assert set(data[0]["survey_types"]) == {
        "cancellation_survey",
        "member_rating_v2",
        "member_rating_followup_v2",
    }
    assert set(data[1]["survey_types"]) == {
        "member_rating_v2",
        "member_rating_followup_v2",
    }


@freeze_time(FREEZE_TIME_STR)
def test_get_member_appointments_list_with_no_appts(
    client,
    api_helpers,
    factories,
    valid_appointment_with_user,
    practitioner_user,
    wellness_coach_user,
):
    # Given
    now = datetime.utcnow()
    member = factories.EnterpriseUserFactory.create()

    query_str = {
        "scheduled_start": now.isoformat(),
        "scheduled_end": (now + timedelta(hours=3)).isoformat(),
        "order_direction": "asc",
    }

    # When
    res = client.get(
        "/api/v2/member/appointments",
        headers=api_helpers.json_headers(member),
        query_string=query_str,
    )

    # Then
    data = res.json["data"]
    assert res.status_code == 200
    assert 0 == len(data)


@freeze_time(FREEZE_TIME_STR)
def test_get_member_appointments_list_with_two_survey_types(
    client, api_helpers, factories, valid_appointment_with_user, practitioner_user
):
    # Given
    now = datetime.utcnow()
    ca_provider = practitioner_user()
    member = factories.EnterpriseUserFactory.create()
    ms = factories.ScheduleFactory.create(user=member)

    # Add two ca-vertical-specific questionnaires
    member_role = factories.RoleFactory.create(name=ROLES.member)
    ca_questionnaire_oid = "member_rating_ca"
    factories.QuestionnaireFactory.create(
        oid=ca_questionnaire_oid,
        verticals=[ca_provider.practitioner_profile.verticals[0]],
        roles=[member_role],
    )
    ca_questionnaire_oid2 = "member_rating_ca_part2"
    factories.QuestionnaireFactory.create(
        oid=ca_questionnaire_oid2,
        verticals=[ca_provider.practitioner_profile.verticals[0]],
        roles=[member_role],
    )

    valid_appointment_with_user(
        practitioner=ca_provider,
        member_schedule=ms,
        purpose="test purpose",
        scheduled_start=datetime.utcnow(),
    )

    query_str = {
        "scheduled_start": now.isoformat(),
        "scheduled_end": (now + timedelta(hours=3)).isoformat(),
        "order_direction": "asc",
    }

    # When
    # for experiment-post-appointment-questionnaire-from-vertical
    with patch(
        "maven.feature_flags.bool_variation",
        return_value=True,
    ):
        res = client.get(
            "/api/v2/member/appointments",
            headers=api_helpers.json_headers(member),
            query_string=query_str,
        )

    # Then
    data = res.json["data"]
    assert res.status_code == 200
    assert set(data[0]["survey_types"]) == {ca_questionnaire_oid, ca_questionnaire_oid2}


@freeze_time(FREEZE_TIME_STR)
def test_get_member_appointments_list__need_fields(
    client,
    api_helpers,
    factories,
    practitioner_user,
):
    """
    Tests that need fields are correctly return for appointments with needs
    """
    member = factories.EnterpriseUserFactory.create()
    ms = factories.ScheduleFactory.create(user=member)

    need = factories.NeedFactory.create()
    expected_appointment = factories.AppointmentFactory(
        member_schedule=ms,
        scheduled_start=datetime.utcnow(),
        need=need,
    )

    now = datetime.utcnow()

    query_str = {
        "scheduled_start": now.isoformat(),
        "scheduled_end": (now + timedelta(hours=3)).isoformat(),
        "order_direction": "asc",
    }
    res = client.get(
        "/api/v2/member/appointments",
        headers=api_helpers.json_headers(member),
        query_string=query_str,
    )

    assert res.status_code == 200
    assert res.json["pagination"]["total"]

    actual_appointment = res.json["data"][0]
    assert actual_appointment["id"] == deobfuscate_appointment_id(
        expected_appointment.id
    )
    assert actual_appointment["need"]["id"] == expected_appointment.need.id
    assert actual_appointment["need"]["name"] == expected_appointment.need.name


@freeze_time(FREEZE_TIME_STR)
def test_get_member_appointments_list__l10n(
    client,
    api_helpers,
    setup_three_appointments,
):
    now = datetime.utcnow()
    provider, member, appointments = setup_three_appointments
    expected_appts_by_id = {a.id: a for a in appointments}
    expected_ids = expected_appts_by_id.keys()

    query_str = {
        "scheduled_start": now.isoformat(),
        "scheduled_end": (now + timedelta(hours=3)).isoformat(),
        "order_direction": "asc",
    }

    expected_translation = "translatedtext"
    with patch(
        "appointments.client.v2.http.member_appointments.feature_flags.bool_variation",
        return_value=True,
    ), patch(
        "l10n.db_strings.translate.TranslateDBFields.get_translated_vertical",
        return_value=expected_translation,
    ) as translation_mock:
        res = client.get(
            "/api/v2/member/appointments",
            headers=api_helpers.json_headers(member),
            query_string=query_str,
        )

        # 2 calls per vertical * 3 appointments
        assert translation_mock.call_count == 6

    assert res.status_code == 200
    assert res.json["pagination"]["total"]
    data = res.json["data"]
    for appt in data:
        appt["id"] = deobfuscate_appointment_id(appt["id"])

    actual_ids = {a.get("id") for a in data}
    assert actual_ids == expected_ids

    for actual_appt in data:
        expected_appt = expected_appts_by_id[actual_appt["id"]]
        actual_appt_provider = actual_appt["provider"]

        assert len(actual_appt_provider["verticals"]) == 1
        assert (
            actual_appt_provider["verticals"][0]["id"]
            == expected_appt.practitioner.practitioner_profile.verticals[0].id
        )
        assert actual_appt_provider["verticals"][0]["name"] == expected_translation
        assert (
            actual_appt_provider["verticals"][0]["description"] == expected_translation
        )

        assert actual_appt_provider["vertical"]["name"] == expected_translation
        assert actual_appt_provider["vertical"]["description"] == expected_translation
