import datetime

import pytest

from appointments.repository.v2.member_appointment import MemberAppointmentRepository
from storage.connection import db


class TestMemberAppointmentRepository:
    def test_get_by_id_not_exist(self, factories):
        # Create an appointment that shouldn't be found
        factories.AppointmentFactory.create()

        session = db.session
        result = MemberAppointmentRepository(session).get_by_id(5555555)

        assert result is None

    def test_get_by_id(self, factories):
        session = db.session
        appointment = factories.AppointmentFactory.create()
        result = MemberAppointmentRepository(session).get_by_id(appointment.id)

        assert result.id == appointment.id

    @pytest.mark.parametrize(
        ("appointment_time_deltas", "expected_appointment_index"),
        (
            ([], None),
            ([datetime.timedelta(hours=-1)], None),
            ([datetime.timedelta(hours=-1), datetime.timedelta(hours=-2)], None),
            ([datetime.timedelta()], 0),
            ([datetime.timedelta(hours=1)], 0),
            ([datetime.timedelta(hours=2), datetime.timedelta(hours=1)], 1),
            (
                [
                    datetime.timedelta(hours=-1),
                    datetime.timedelta(),
                    datetime.timedelta(hours=1),
                ],
                1,
            ),
        ),
    )
    def test_get_current_or_next(
        self, factories, appointment_time_deltas, expected_appointment_index
    ):
        member = factories.EnterpriseUserFactory.create()
        factories.ScheduleFactory.create(user=member)
        appointments = [
            factories.AppointmentFactory.create(
                member_schedule=member.schedule,
                scheduled_start=datetime.datetime.utcnow()
                + appointment_time_delta
                - datetime.timedelta(minutes=10),
                scheduled_end=datetime.datetime.utcnow()
                + appointment_time_delta
                + datetime.timedelta(minutes=10),
            )
            for appointment_time_delta in appointment_time_deltas
        ]
        result = MemberAppointmentRepository(db.session).get_current_or_next(member.id)
        if result is None:
            assert expected_appointment_index is None
        else:
            assert appointments[expected_appointment_index].id == result.id
