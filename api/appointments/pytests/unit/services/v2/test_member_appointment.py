import json
from datetime import datetime, timedelta
from typing import Tuple
from unittest.mock import ANY, MagicMock, patch

import pytest

from appointments.models.constants import APPOINTMENT_STATES
from appointments.models.v2.member_appointment_video_timestamp import (
    AppointmentVideoTimestampStruct,
)
from appointments.models.v2.member_appointments import MemberAppointmentsListElement
from appointments.services.v2.appointment_timestamp import AppointmentTimestampService
from appointments.services.v2.member_appointment import MemberAppointmentService
from pytests.freezegun import freeze_time

FREEZE_TIME_STR = "2024-03-01T12:00:00"


@pytest.fixture()
@freeze_time(FREEZE_TIME_STR)
def setup_test_member_appointments_service(
    factories,
):
    member_id = 33

    member_appointments: list[MemberAppointmentsListElement] = [
        factories.MemberAppointmentsListElementFactory.create() for _ in range(3)
    ]

    return member_id, member_appointments


@pytest.fixture()
@freeze_time(FREEZE_TIME_STR)
def setup_video_timestamps_test(
    factories,
) -> Tuple[int, AppointmentVideoTimestampStruct]:
    now = datetime.utcnow()
    video_timestamp_struct: AppointmentVideoTimestampStruct = (
        # get_member_appointment_state() will evaluate to "overdue" for this appointment
        factories.MemberAppointmentVideoTimestampStructFactory.create(
            scheduled_start=now - timedelta(hours=1)
        )
    )
    member_id = video_timestamp_struct.member_id

    return member_id, video_timestamp_struct


@pytest.fixture()
def member_mock(setup_video_timestamps_test):
    id, _ = setup_video_timestamps_test
    member_mock = MagicMock()
    member_mock.user_id = id
    return member_mock


class TestMemberAppointments:
    @freeze_time(FREEZE_TIME_STR)
    def test_list_member_appointments(
        self, factories, setup_test_member_appointments_service, member_mock
    ):
        member_id, member_appointments = setup_test_member_appointments_service
        expected_ids = {a.id for a in member_appointments}

        scheduled_start = datetime.utcnow()
        scheduled_end = datetime.utcnow() + timedelta(hours=3)

        mock_providers_by_product_id = {}
        mock_needs_by_appt_id = {}
        for appointment in member_appointments:
            mock_providers_by_product_id[
                appointment.product_id
            ] = factories.MemberAppointmentServiceResponseProviderFactory.create()
            mock_needs_by_appt_id[
                appointment.id
            ] = factories.MemberAppointmentServiceResponseNeedFactory.create()
        mock_external_response = (
            mock_providers_by_product_id,
            mock_needs_by_appt_id,
        )

        service = MemberAppointmentService()
        with patch(
            "appointments.repository.v2.member_appointments.MemberAppointmentsListRepository.list_member_appointments",
            return_value=member_appointments,
        ), patch.object(
            service,
            "_list_member_appointments_external_dependencies",
        ) as external_mock:
            external_mock.return_value = mock_external_response
            member_appts, pagination = service.list_member_appointments(
                member_mock,
                member_id,
                scheduled_start,
                scheduled_end,
            )

        actual_ids = {a.id for a in member_appts}
        assert actual_ids == expected_ids

    def test_list_member_appointments__doula_only(
        self, factories, create_doula_only_member
    ):

        # Given
        scheduled_start = datetime.utcnow()
        scheduled_end = datetime.utcnow() + timedelta(hours=3)

        # create doula and non-doula allowed practitioners
        doula_practitioner = factories.PractitionerUserFactory(
            practitioner_profile__verticals=[
                factories.VerticalFactory.create(name="Doula And Childbirth Educator")
            ]
        )

        non_doula_practitioner = factories.PractitionerUserFactory(
            practitioner_profile__verticals=[
                factories.VerticalFactory.create(name="Fertility Awareness Educator")
            ]
        )

        utcnow = datetime.utcnow().replace(second=0, microsecond=0)
        one_hour_from_now = utcnow + timedelta(hours=1)

        member_schedule = factories.ScheduleFactory.create(
            user=create_doula_only_member
        )

        # create appointments with doula and non-doula practitioners
        doula_appointment = factories.AppointmentFactory.create_with_practitioner(
            member_schedule=member_schedule,
            practitioner=doula_practitioner,
            scheduled_start=one_hour_from_now,
        )

        non_doula_appointment = factories.AppointmentFactory.create_with_practitioner(
            member_schedule=member_schedule,
            practitioner=non_doula_practitioner,
            scheduled_start=one_hour_from_now,
        )

        service = MemberAppointmentService()

        # When
        member_appts, pagination = service.list_member_appointments(
            create_doula_only_member,
            create_doula_only_member.id,
            scheduled_start,
            scheduled_end,
        )

        # Then
        actual_ids = {a.id for a in member_appts}
        assert len(actual_ids) == 2
        assert actual_ids == {doula_appointment.id, non_doula_appointment.id}
        provider_1 = member_appts[0].provider
        provider_2 = member_appts[1].provider

        # we cannot guarantee the return order
        if provider_1 and provider_1.vertical.name == "Doula And Childbirth Educator":
            assert provider_1.can_member_interact is True
        elif provider_2 and provider_2.vertical.name == "Doula And Childbirth Educator":
            assert provider_2.can_member_interact is False

        elif provider_1 and provider_1.vertical.name == "Fertility Awareness Educator":
            assert provider_1.can_member_interact is True
        elif provider_2 and provider_2.vertical.name == "Fertility Awareness Educator":
            assert provider_2.can_member_interact is False

    @freeze_time(FREEZE_TIME_STR)
    def test_list_member_appointments__verticals(
        self, factories, setup_test_member_appointments_service, member_mock
    ):
        """
        Tests that the provider response for list_member_appointments contains both
        `verticals` and `vertical`
        """
        member_id, member_appointments = setup_test_member_appointments_service
        expected_ids = {a.id for a in member_appointments}

        scheduled_start = datetime.utcnow()
        scheduled_end = datetime.utcnow() + timedelta(hours=3)

        mock_providers_by_product_id = {}
        mock_needs_by_appt_id = {}
        for appointment in member_appointments:
            mock_providers_by_product_id[
                appointment.product_id
            ] = factories.MemberAppointmentServiceResponseProviderFactory.create()
            mock_needs_by_appt_id[
                appointment.id
            ] = factories.MemberAppointmentServiceResponseNeedFactory.create()
        mock_external_response = (
            mock_providers_by_product_id,
            mock_needs_by_appt_id,
        )

        service = MemberAppointmentService()
        with patch(
            "appointments.repository.v2.member_appointments.MemberAppointmentsListRepository.list_member_appointments",
            return_value=member_appointments,
        ), patch.object(
            service,
            "_list_member_appointments_external_dependencies",
        ) as external_mock:
            external_mock.return_value = mock_external_response
            actual_member_appts, pagination = service.list_member_appointments(
                member_mock,
                member_id,
                scheduled_start,
                scheduled_end,
            )

        actual_ids = {a.id for a in actual_member_appts}
        assert actual_ids == expected_ids

        for actual_appt in actual_member_appts:
            actual_verticals = actual_appt.provider.verticals
            assert len(actual_verticals) == 1
            assert actual_verticals[0].id is not None
            assert actual_verticals[0].name is not None
            assert actual_verticals[0].name != ""

            actual_vertical = actual_appt.provider.vertical
            assert actual_vertical.id is not None
            assert actual_vertical.name is not None
            assert actual_vertical.name != ""


class TestMemberAppointmentServiceVideoTimestamp:
    @freeze_time(FREEZE_TIME_STR)
    def test_add_all_video_timestamps(
        self,
        setup_video_timestamps_test,
        member_mock,
    ):
        """
        Test that you can add all 3 timestamps when they aren't already set
        """
        member_id, video_timestamp_struct = setup_video_timestamps_test
        expected_appointment_id = video_timestamp_struct.id
        video_timestamp_struct.practitioner_started_at = None
        video_timestamp_struct.member_started_at = None
        video_timestamp_struct.practitioner_ended_at = None
        video_timestamp_struct.member_ended_at = None

        # Update all times to a different value than their current
        updated_started_at = video_timestamp_struct.scheduled_start + timedelta(
            minutes=10
        )
        updated_ended_at = video_timestamp_struct.scheduled_end + timedelta(minutes=10)
        expected_disconnected_at = updated_ended_at - timedelta(minutes=1)
        expected_json_str = json.dumps(
            {
                "member_disconnected_at": None,
                "practitioner_disconnected_at": None,
                "member_disconnect_times": [expected_disconnected_at.isoformat()],
                "platforms": {"member_started": "NONE", "member_started_raw": None},
            }
        )

        # Mock both repository calls and the external dependency call
        with patch(
            "appointments.repository.v2.appointment_video_timestamp.AppointmentVideoTimestampRepository.get_appointment_video_timestamp",
            return_value=video_timestamp_struct,
        ), patch(
            "appointments.repository.v2.appointment_video_timestamp.AppointmentVideoTimestampRepository.set_appointment_video_timestamp",
        ) as set_video_timestamp_mock:
            res = AppointmentTimestampService().add_video_timestamp(
                member_id,
                video_timestamp_struct.id,
                updated_started_at,
                updated_ended_at,
                expected_disconnected_at,
                video_timestamp_struct.phone_call_at,
            )

        assert res == expected_appointment_id
        set_video_timestamp_mock.assert_called_once_with(
            expected_appointment_id,
            updated_started_at,
            updated_ended_at,
            video_timestamp_struct.practitioner_started_at,
            video_timestamp_struct.practitioner_ended_at,
            video_timestamp_struct.phone_call_at,
            expected_json_str,
        )

    @freeze_time(FREEZE_TIME_STR)
    def test_started_at_gets_set_to_disconnected_at(
        self,
        factories,
        setup_video_timestamps_test,
        member_mock,
    ):
        """
        Test that if started_at is not set and not passed in, then it will be set to disconnected_at
        """
        video_timestamp_struct: AppointmentVideoTimestampStruct = (
            factories.MemberAppointmentVideoTimestampStructFactory.create(
                member_started_at=None,
            )
        )
        member_id = video_timestamp_struct.member_id
        expected_appointment_id = video_timestamp_struct.id

        expected_disconnected_at = video_timestamp_struct.scheduled_start + timedelta(
            minutes=10
        )

        # Mock both repository calls, the external dependency call, and get_member_appointment_state to a "reconnecting state"
        with patch(
            "appointments.repository.v2.appointment_video_timestamp.AppointmentVideoTimestampRepository.get_appointment_video_timestamp",
            return_value=video_timestamp_struct,
        ), patch(
            "appointments.repository.v2.appointment_video_timestamp.AppointmentVideoTimestampRepository.set_appointment_video_timestamp",
        ) as set_video_timestamp_mock, patch(
            "appointments.utils.appointment_utils.get_member_appointment_state",
            return_value=APPOINTMENT_STATES.overdue,
        ):
            # Send only the disconnected_at time
            res = AppointmentTimestampService().add_video_timestamp(
                member_id,
                video_timestamp_struct.id,
                started_at=None,
                ended_at=None,
                disconnected_at=expected_disconnected_at,
                phone_call_at=video_timestamp_struct.phone_call_at,
            )

        assert res == expected_appointment_id
        # Check that started_at was passed in as disconnected_at
        set_video_timestamp_mock.assert_called_once_with(
            expected_appointment_id,
            expected_disconnected_at,
            ANY,
            ANY,
            ANY,
            ANY,
            ANY,
        )

    def test_add_all_video_timestamps__timestamps_not_overwritten(
        self,
        setup_video_timestamps_test,
        member_mock,
    ):
        """
        Test that when the start and end timestamps are set, they don't get overwritten
        """
        member_id, video_timestamp_struct = setup_video_timestamps_test
        expected_appointment_id = video_timestamp_struct.id

        # Update all times to a different value than their current
        updated_started_at = video_timestamp_struct.scheduled_start + timedelta(
            minutes=10
        )
        updated_ended_at = video_timestamp_struct.scheduled_end + timedelta(minutes=10)
        expected_disconnected_at = updated_ended_at - timedelta(minutes=1)
        expected_json_str = json.dumps(
            {
                "member_disconnected_at": None,
                "practitioner_disconnected_at": None,
                "platforms": {"member_started": "NONE", "member_started_raw": None},
            }
        )

        # Mock both repository calls and the external dependency call
        with patch(
            "appointments.repository.v2.appointment_video_timestamp.AppointmentVideoTimestampRepository.get_appointment_video_timestamp",
            return_value=video_timestamp_struct,
        ), patch(
            "appointments.repository.v2.appointment_video_timestamp.AppointmentVideoTimestampRepository.set_appointment_video_timestamp",
        ) as set_video_timestamp_mock:
            res = AppointmentTimestampService().add_video_timestamp(
                member_id,
                video_timestamp_struct.id,
                updated_started_at,
                updated_ended_at,
                expected_disconnected_at,
                video_timestamp_struct.phone_call_at,
            )

        assert res == expected_appointment_id
        set_video_timestamp_mock.assert_called_once_with(
            expected_appointment_id,
            video_timestamp_struct.member_started_at,
            video_timestamp_struct.member_ended_at,
            video_timestamp_struct.practitioner_started_at,
            video_timestamp_struct.practitioner_ended_at,
            video_timestamp_struct.phone_call_at,
            expected_json_str,
        )
