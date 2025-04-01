from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from appointments.models.constants import APPOINTMENT_STATES
from appointments.tasks.state import resolve_appointment_pending_payments
from pytests.freezegun import freeze_time

FREEZE_TIME_STR = "2024-03-01T12:00:00"


@pytest.fixture
@freeze_time(FREEZE_TIME_STR)
def setup_payment_pending_tests(
    factories,
    vertical_ca,
    vertical_wellness_coach_cannot_prescribe,
):
    """
    Sets up member, practitioner, and appointments

    2 appointments will be in payment pending state, and the third will be payment complete
    """
    now = datetime.utcnow()

    practitioner = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[vertical_ca],
    )
    factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule,
        starts_at=now - timedelta(days=2) - timedelta(hours=5),
        ends_at=now - timedelta(days=2) + timedelta(hours=5),
    )

    member = factories.EnterpriseUserFactory.create()
    member.schedule = factories.ScheduleFactory.create(user=member)

    # Make appointments for tomorrow that were booked yesterday
    appt_start = now - timedelta(days=2)
    appt_end = (
        now - timedelta(days=2) + timedelta(minutes=practitioner.products[0].minutes)
    )
    appointment = factories.AppointmentFactory.create(
        created_at=now - timedelta(days=3),
        modified_at=now - timedelta(days=2),
        product=practitioner.products[0],
        scheduled_start=appt_start,
        scheduled_end=appt_end,
        member_schedule=member.member_profile.schedule,
        member_started_at=appt_start,
        practitioner_started_at=appt_start,
        member_ended_at=appt_end,
        practitioner_ended_at=appt_end,
    )

    return practitioner, member, appointment


@freeze_time(FREEZE_TIME_STR)
def test_resolve_appointment_pending_payments(factories, setup_payment_pending_tests):
    """
    Resolves appointments and triggers payments.
    """
    _, member, appointment = setup_payment_pending_tests
    factories.CreditFactory.create(
        user_id=member.id,
        amount=2000,
    )

    assert appointment.state == APPOINTMENT_STATES.payment_pending

    with patch(
        "tracks.service.TrackSelectionService.is_enterprise"
    ) as is_enterprise_mock, patch("appointments.tasks.state.log.info") as info_mock:
        is_enterprise_mock.return_value = True
        resolve_appointment_pending_payments()

    info_mock.assert_called_once_with(
        "Successfully migrated all appointments to PAYMENT_RESOLVED",
        appointment_ids=[appointment.id],
    )
