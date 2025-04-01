from datetime import datetime, timedelta

import pytest

from appointments.services.v2.member_appointment import MemberAppointmentService
from appointments.utils.errors import AppointmentNotFoundException


def test_get_member_appointment_by_id(
    factories,
    valid_appointment_with_user,
    practitioner_user,
):
    provider = practitioner_user()
    member = factories.EnterpriseUserFactory.create()
    factories.ScheduleFactory.create(user=member)

    expected_appointment = valid_appointment_with_user(
        practitioner=provider,
        member_schedule=member.schedule,
        purpose="test purpose",
        scheduled_start=datetime.utcnow() + timedelta(minutes=10),
    )
    expected_appointment_id = expected_appointment.id

    res = MemberAppointmentService().get_member_appointment_by_id(
        member, expected_appointment_id
    )
    assert res.id == expected_appointment.id


def test_get_member_appointment_by_id__invalid_id(
    factories,
    valid_appointment_with_user,
    practitioner_user,
):
    provider = practitioner_user()
    member = factories.EnterpriseUserFactory.create()
    factories.ScheduleFactory.create(user=member)
    valid_appointment_with_user(
        practitioner=provider,
        member_schedule=member.schedule,
        purpose="test purpose",
        scheduled_start=datetime.utcnow() + timedelta(minutes=10),
    )

    bad_appointment_id = 99999997999

    with pytest.raises(AppointmentNotFoundException):
        MemberAppointmentService().get_member_appointment_by_id(
            member, bad_appointment_id
        )


def test_get_member_appointment_by_id__only_member(
    factories,
    valid_appointment_with_user,
    practitioner_user,
    enterprise_user,
):
    """Tests that only the member has permissions to view the appointment"""
    provider = practitioner_user()
    member = factories.EnterpriseUserFactory.create()
    factories.ScheduleFactory.create(user=member)

    expected_appointment = valid_appointment_with_user(
        practitioner=provider,
        member_schedule=member.schedule,
        purpose="test purpose",
        scheduled_start=datetime.utcnow() + timedelta(minutes=10),
    )
    expected_appointment_id = expected_appointment.id

    member_without_permissions = factories.EnterpriseUserFactory.create()
    factories.ScheduleFactory.create(user=member_without_permissions)

    # Tests that a member not associated with the appointment can't view
    with pytest.raises(AppointmentNotFoundException):
        MemberAppointmentService().get_member_appointment_by_id(
            member_without_permissions, expected_appointment_id
        )

    # Tests that the associated provider can't view
    with pytest.raises(AppointmentNotFoundException):
        MemberAppointmentService().get_member_appointment_by_id(
            provider, expected_appointment_id
        )


@pytest.mark.parametrize(
    ("appointment_time_deltas", "expected_appointment_index"),
    (
        ([], None),
        ([timedelta(hours=-1)], None),
        ([timedelta(hours=-1), timedelta(hours=-2)], None),
        ([timedelta()], 0),
        ([timedelta(hours=1)], 0),
        ([timedelta(hours=2), timedelta(hours=1)], 1),
        ([timedelta(hours=-1), timedelta(), timedelta(hours=1)], 1),
    ),
)
def test_get_current_or_next(
    factories, appointment_time_deltas, expected_appointment_index
):
    member = factories.EnterpriseUserFactory.create()
    factories.ScheduleFactory.create(user=member)
    appointments = [
        factories.AppointmentFactory.create(
            member_schedule=member.schedule,
            scheduled_start=datetime.utcnow()
            + appointment_time_delta
            - timedelta(minutes=10),
            scheduled_end=datetime.utcnow()
            + appointment_time_delta
            + timedelta(minutes=10),
        )
        for appointment_time_delta in appointment_time_deltas
    ]
    result = MemberAppointmentService().get_current_or_next_appointment_for_member(
        member
    )
    if result is None:
        assert expected_appointment_index is None
    else:
        assert appointments[expected_appointment_index].id == result.id
