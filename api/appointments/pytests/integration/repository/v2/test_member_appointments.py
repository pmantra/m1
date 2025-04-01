from datetime import datetime, timedelta

import pytest

from appointments.repository.v2.member_appointments import (
    MemberAppointmentsListRepository,
)
from pytests.freezegun import freeze_time

FREEZE_TIME_STR = "2024-03-01T12:00:00"


@pytest.fixture()
@freeze_time(FREEZE_TIME_STR)
def setup_appointments_sqlalchemy(
    factories,
    valid_appointment_with_user,
    practitioner_user,
):
    """
    Populate the DB
    This will need to be refactored in triforce, as we don't have sqlalchemy
    """
    provider = practitioner_user()
    member = factories.EnterpriseUserFactory.create()
    factories.ScheduleFactory.create(user=member)

    scheduled_start = datetime.utcnow()
    scheduled_end = datetime.utcnow() + timedelta(hours=3)
    expected_appointments = [
        valid_appointment_with_user(
            practitioner=provider,
            member_schedule=member.schedule,
            purpose="test purpose",
            scheduled_start=scheduled_start + timedelta(minutes=10),
        ),
        valid_appointment_with_user(
            practitioner=provider,
            member_schedule=member.schedule,
            purpose="test purpose",
            scheduled_start=scheduled_start + timedelta(minutes=30),
        ),
        valid_appointment_with_user(
            practitioner=provider,
            member_schedule=member.schedule,
            purpose="test purpose",
            scheduled_start=scheduled_start + timedelta(minutes=50),
        ),
    ]
    expected_appointment_ids = {a.id for a in expected_appointments}

    # Appointment before scheduled_start that should not be found
    valid_appointment_with_user(
        practitioner=provider,
        member_schedule=member.schedule,
        purpose="test purpose",
        scheduled_start=scheduled_start - timedelta(hours=1),
    )
    # Appointment after scheduled_end that should not be found
    valid_appointment_with_user(
        practitioner=provider,
        member_schedule=member.schedule,
        purpose="test purpose",
        scheduled_start=scheduled_end + timedelta(hours=1),
    )
    return (
        provider,
        member,
        scheduled_start,
        scheduled_end,
        expected_appointments,
        expected_appointment_ids,
    )


class TestMemberAppointmentsListRepository:
    @freeze_time(FREEZE_TIME_STR)
    def test_list_member_appointments(self, db, setup_appointments_sqlalchemy):
        (
            _,
            member,
            scheduled_start,
            scheduled_end,
            _,
            expected_appointment_ids,
        ) = setup_appointments_sqlalchemy

        session = db.session

        res = MemberAppointmentsListRepository(
            session=session
        ).list_member_appointments(
            member.id,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
        )
        actual_ids = {a.id for a in res}
        assert actual_ids == expected_appointment_ids

    @freeze_time(FREEZE_TIME_STR)
    def test_list_member_appointments__order_by_desc(
        self, db, setup_appointments_sqlalchemy
    ):
        """
        Tests that list_member_appointments() respects descending sort order
        """
        (
            _,
            member,
            scheduled_start,
            scheduled_end,
            _,
            expected_appointment_ids,
        ) = setup_appointments_sqlalchemy

        res = MemberAppointmentsListRepository(
            session=db.session
        ).list_member_appointments(
            member.id,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            order_direction="desc",
        )
        actual_ids = {a.id for a in res}
        assert actual_ids == expected_appointment_ids

        # Assert order by descending (latest date first)
        first_appt = res[0]
        second_appt = res[1]
        third_appt = res[2]
        assert first_appt.scheduled_start > second_appt.scheduled_start
        assert second_appt.scheduled_start > third_appt.scheduled_start

    @freeze_time(FREEZE_TIME_STR)
    def test_list_member_appointments__order_by_asc(
        self, db, setup_appointments_sqlalchemy
    ):
        """
        Tests that list_member_appointments() respects descending sort order
        """
        (
            _,
            member,
            scheduled_start,
            scheduled_end,
            _,
            expected_appointment_ids,
        ) = setup_appointments_sqlalchemy

        res = MemberAppointmentsListRepository(
            session=db.session
        ).list_member_appointments(
            member.id,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            order_direction="asc",
        )
        actual_ids = {a.id for a in res}
        assert actual_ids == expected_appointment_ids

        # Assert order by descending (oldest date first)
        first_appt = res[0]
        second_appt = res[1]
        third_appt = res[2]
        assert first_appt.scheduled_start < second_appt.scheduled_start
        assert second_appt.scheduled_start < third_appt.scheduled_start
