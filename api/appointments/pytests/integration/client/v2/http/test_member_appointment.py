from datetime import datetime, timedelta
from unittest import mock

import pytest

from appointments.services.common import obfuscate_appointment_id
from models.common import PrivilegeType
from models.profiles import CareTeamTypes
from models.tracks.client_track import TrackModifiers
from pytests.freezegun import freeze_time

FREEZE_TIME_STR = "2024-03-01T12:00:00"


@pytest.fixture
@freeze_time(FREEZE_TIME_STR)
def care_advocate(factories, vertical_ca):
    # practitioner_profile__verticals gets set in create_with_practitioner below
    provider = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[],
    )
    factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=provider)
    return provider


@pytest.fixture
@freeze_time(FREEZE_TIME_STR)
def member_with_ca(factories, care_advocate):
    member = factories.MemberFactory.create()
    ms = factories.ScheduleFactory.create(user=member)
    care_team_type = CareTeamTypes.CARE_COORDINATOR
    factories.MemberPractitionerAssociationFactory.create(
        user_id=member.id,
        practitioner_id=care_advocate.id,
        type=care_team_type,
    )
    return member, ms, care_team_type


@freeze_time(FREEZE_TIME_STR)
def test_get_member_appointment_by_id(
    client,
    api_helpers,
    factories,
    valid_appointment_with_user,
    practitioner_user,
):
    now = datetime.utcnow()
    provider = practitioner_user()
    member = factories.EnterpriseUserFactory.create()
    ms = factories.ScheduleFactory.create(user=member)

    appointment = valid_appointment_with_user(
        practitioner=provider,
        member_schedule=ms,
        purpose="test purpose",
        scheduled_start=now + timedelta(minutes=10),
    )
    appointment.privilege_type = PrivilegeType.ANONYMOUS

    obfuscated_appt_id = obfuscate_appointment_id(appointment.id)
    res = client.get(
        f"/api/v2/member/appointments/{obfuscated_appt_id}",
        headers=api_helpers.json_headers(member),
    )
    assert res.status_code == 200
    data = res.json
    assert data["id"] == obfuscated_appt_id
    assert data["product_id"] == appointment.product_id
    assert data["need"] is None
    assert data["scheduled_start"] == appointment.scheduled_start.isoformat()
    assert data["scheduled_end"] == appointment.scheduled_end.isoformat()
    assert data["appointment_type"] == "anonymous"
    assert set(data["survey_types"]) == {
        "member_rating_v2",
        "member_rating_followup_v2",
    }


@pytest.mark.parametrize("is_doula_only", [True, False])
@mock.patch("models.tracks.client_track.should_enable_doula_only_track")
def test_get_member_appointment_by_id__check_is_doula_only(
    mock_should_enable_doula_only_track,
    is_doula_only,
    client,
    api_helpers,
    factories,
    create_doula_only_member,
    practitioner_user,
):
    # Given
    utcnow = datetime.utcnow().replace(second=0, microsecond=0)
    one_hour_from_now = utcnow + timedelta(hours=1)

    member_schedule = factories.ScheduleFactory.create(user=create_doula_only_member)

    vertical = factories.VerticalFactory.create(
        name=(
            "Doula And Childbirth Educator"
            if is_doula_only
            else "Fertility Awareness Educator"
        )
    )

    # create doula and non-doula allowed providers
    provider = factories.PractitionerUserFactory(
        practitioner_profile__verticals=[vertical]
    )

    active_member_track = create_doula_only_member.active_tracks[0]
    client_track_id = active_member_track.client_track_id

    # create a VerticalAccessByTrack record to allow vertical <> client track interaction
    factories.VerticalAccessByTrackFactory.create(
        client_track_id=client_track_id,
        vertical_id=vertical.id,
        track_modifiers=TrackModifiers.DOULA_ONLY if is_doula_only else None,
    )

    # create appointments with either doula and non-doula provider
    appointment = factories.AppointmentFactory.create_with_practitioner(
        member_schedule=member_schedule,
        practitioner=provider,
        scheduled_start=one_hour_from_now,
    )

    appointment.privilege_type = PrivilegeType.ANONYMOUS

    obfuscated_appt_id = obfuscate_appointment_id(appointment.id)

    # When
    res = client.get(
        f"/api/v2/member/appointments/{obfuscated_appt_id}",
        headers=api_helpers.json_headers(create_doula_only_member),
    )

    # Then
    assert res.status_code == 200
    data = res.json
    assert data["id"] == obfuscated_appt_id
    assert data["provider"]["can_member_interact"] == is_doula_only


def test_get_member_appointment_by_id__marketplace_member(
    client,
    api_helpers,
    factories,
):
    member = factories.MemberFactory()
    utcnow = datetime.utcnow().replace(second=0, microsecond=0)
    one_hour_from_now = utcnow + timedelta(hours=1)

    member_schedule = factories.ScheduleFactory.create(user=member)

    provider = factories.PractitionerUserFactory(
        practitioner_profile__verticals=[
            factories.VerticalFactory.create(name="Doula And Childbirth Educator")
        ]
    )

    appointment = factories.AppointmentFactory.create_with_practitioner(
        member_schedule=member_schedule,
        practitioner=provider,
        scheduled_start=one_hour_from_now,
    )

    appointment.privilege_type = PrivilegeType.ANONYMOUS

    obfuscated_appt_id = obfuscate_appointment_id(appointment.id)

    res = client.get(
        f"/api/v2/member/appointments/{obfuscated_appt_id}",
        headers=api_helpers.json_headers(member),
    )

    assert res.json["provider"]["can_member_interact"]


@freeze_time(FREEZE_TIME_STR)
def test_get_member_appointment_by_id__ca_has_care_team_type(
    client,
    api_helpers,
    valid_appointment_with_user,
    member_with_ca,
    care_advocate,
):
    now = datetime.utcnow()
    member, member_schedule, care_team_type = member_with_ca
    appointment = valid_appointment_with_user(
        practitioner=care_advocate,
        member_schedule=member_schedule,
        purpose="test purpose",
        scheduled_start=now + timedelta(minutes=10),
    )

    obfuscated_appt_id = obfuscate_appointment_id(appointment.id)
    res = client.get(
        f"/api/v2/member/appointments/{obfuscated_appt_id}",
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 200
    data = res.json
    assert data["id"] == obfuscated_appt_id
    assert data["product_id"] == appointment.product_id
    assert data["scheduled_start"] == appointment.scheduled_start.isoformat()
    assert data["scheduled_end"] == appointment.scheduled_end.isoformat()
    assert data["provider"]["id"] == appointment.practitioner_id
    assert data["provider"]["care_team_type"] == care_team_type.value


@freeze_time(FREEZE_TIME_STR)
def test_get_member_appointment_by_id__valid_json_str(
    client,
    api_helpers,
    factories,
    valid_appointment_with_user,
    practitioner_user,
):
    """
    Tests that member_disconnected_at and practitioner_disconnected_at both work with
    valid input
    """
    now = datetime.utcnow()
    provider = practitioner_user()
    member = factories.EnterpriseUserFactory.create()
    ms = factories.ScheduleFactory.create(user=member)

    date_str = now.isoformat()
    appointment = valid_appointment_with_user(
        practitioner=provider,
        member_schedule=ms,
        purpose="test purpose",
        scheduled_start=now + timedelta(minutes=10),
    )
    appointment.json = {
        "member_disconnected_at": date_str,
        "practitioner_disconnected_at": date_str,
    }

    obfuscated_appt_id = obfuscate_appointment_id(appointment.id)
    res = client.get(
        f"/api/v2/member/appointments/{obfuscated_appt_id}",
        headers=api_helpers.json_headers(member),
    )
    assert res.status_code == 200
    data = res.json
    assert data["id"] == obfuscated_appt_id
    assert data["product_id"] == appointment.product_id
    assert data["scheduled_start"] == appointment.scheduled_start.isoformat()
    assert data["scheduled_end"] == appointment.scheduled_end.isoformat()
    assert data["member_disconnected_at"] == date_str
    assert data["practitioner_disconnected_at"] == date_str


@freeze_time(FREEZE_TIME_STR)
def test_get_member_appointment_by_id__need(
    client,
    api_helpers,
    factories,
):
    """
    Tests that the need object gets set correctly when an appointment has a need
    """
    member = factories.EnterpriseUserFactory.create()
    ms = factories.ScheduleFactory.create(user=member)

    need = factories.NeedFactory.create()
    expected_appointment = factories.AppointmentFactory(
        member_schedule=ms,
        scheduled_start=datetime.utcnow(),
        need=need,
    )

    obfuscated_appt_id = obfuscate_appointment_id(expected_appointment.id)
    res = client.get(
        f"/api/v2/member/appointments/{obfuscated_appt_id}",
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 200
    data = res.json
    assert data["id"] == obfuscated_appt_id
    assert data["need"]["id"] == expected_appointment.need.id
    assert data["need"]["name"] == expected_appointment.need.name


@freeze_time(FREEZE_TIME_STR)
def test_get_member_appointment_by_id__l10n(
    client,
    api_helpers,
    factories,
    valid_appointment_with_user,
    practitioner_user,
):
    now = datetime.utcnow()
    provider = practitioner_user()
    member = factories.EnterpriseUserFactory.create()
    ms = factories.ScheduleFactory.create(user=member)

    appointment = valid_appointment_with_user(
        practitioner=provider,
        member_schedule=ms,
        purpose="test purpose",
        scheduled_start=now + timedelta(minutes=10),
    )
    appointment.privilege_type = PrivilegeType.ANONYMOUS

    obfuscated_appt_id = obfuscate_appointment_id(appointment.id)
    expected_translation = "translatedtext"
    with mock.patch(
        "appointments.client.v2.http.member_appointment.feature_flags.bool_variation",
        return_value=True,
    ), mock.patch(
        "l10n.db_strings.translate.TranslateDBFields.get_translated_vertical",
        return_value=expected_translation,
    ) as translation_mock:
        res = client.get(
            f"/api/v2/member/appointments/{obfuscated_appt_id}",
            headers=api_helpers.json_headers(member),
        )

        # 2 calls per vertical
        assert translation_mock.call_count == 2

    assert res.status_code == 200
    data = res.json
    assert data["id"] == obfuscated_appt_id

    assert len(data["provider"]["verticals"]) == 1
    assert data["provider"]["verticals"][0]["name"] == expected_translation
    assert data["provider"]["verticals"][0]["description"] == expected_translation
    assert data["provider"]["vertical"]["name"] == expected_translation
    assert data["provider"]["vertical"]["description"] == expected_translation
