from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from appointments.models.appointment import Appointment
from appointments.tasks.appointment_monitors import find_overlapping_appointments
from pytests.freezegun import freeze_time

FREEZE_TIME_STR = "2024-03-01T12:00:00"


@pytest.fixture
@freeze_time(FREEZE_TIME_STR)
def setup_overlapping_tests(
    factories,
    vertical_ca,
    vertical_wellness_coach_cannot_prescribe,
):
    """
    Sets up 2 practitioners and 2 members, with 3 appointments

    2 appointments are overlapping with the same practitioner and should be found by the
    cronjob, while the third appointment is with a different practitioner
    """
    now = datetime.utcnow()
    yesterday = now - timedelta(hours=24)
    tomorrow = now + timedelta(hours=24)

    practitioners = [
        factories.PractitionerUserFactory.create(
            practitioner_profile__verticals=[vertical_ca],
        ),
        factories.PractitionerUserFactory.create(
            practitioner_profile__verticals=[vertical_wellness_coach_cannot_prescribe],
        ),
    ]
    for practitioner in practitioners:
        factories.ScheduleEventFactory.create(
            schedule=practitioner.schedule,
            starts_at=tomorrow - timedelta(hours=5),
            ends_at=tomorrow + timedelta(hours=5),
        )

    members = [
        factories.EnterpriseUserFactory.create(),
        factories.EnterpriseUserFactory.create(),
    ]
    for member in members:
        member.schedule = factories.ScheduleFactory.create(user=member)

    # Make appointments for tomorrow that were booked yesterday
    appointments: Appointment = [
        factories.AppointmentFactory.create(
            created_at=yesterday,
            modified_at=yesterday,
            product=practitioners[0].products[0],
            scheduled_start=tomorrow,
            scheduled_end=tomorrow
            + timedelta(minutes=practitioners[0].products[0].minutes),
            member_schedule=members[0].member_profile.schedule,
        ),
        factories.AppointmentFactory.create(
            created_at=yesterday,
            modified_at=yesterday,
            product=practitioners[0].products[0],
            scheduled_start=tomorrow,
            scheduled_end=tomorrow
            + timedelta(minutes=practitioners[0].products[0].minutes),
            member_schedule=members[1].member_profile.schedule,
        ),
        # Different practitioner
        factories.AppointmentFactory.create(
            created_at=yesterday,
            modified_at=yesterday,
            product=practitioners[1].products[0],
            scheduled_start=tomorrow,
            scheduled_end=tomorrow
            + timedelta(minutes=practitioners[1].products[0].minutes),
            member_schedule=members[0].member_profile.schedule,
        ),
    ]

    return practitioners, members, appointments


@freeze_time(FREEZE_TIME_STR)
def test_find_overlapping_appointments(setup_overlapping_tests):
    """
    Finds overlapping appointments with the default setup
    """
    _, _, appointments = setup_overlapping_tests

    # Only the first two default appointments are expected to be found, as the third
    # has a different practitioner
    expected_appt_ids = {a.id for a in appointments[:2]}

    # To find overlapping appointments, they must have a modified date within the last 2 hours
    appointments[0].modified_at = datetime.utcnow() - timedelta(hours=1)

    with patch("appointments.tasks.appointment_monitors.log.error") as logger_mock:
        find_overlapping_appointments()

    logger_mock.assert_called_once_with(
        "Found overlapping appointments",
        overlapping_appointments=str([expected_appt_ids]),
    )


@freeze_time(FREEZE_TIME_STR)
def test_find_overlapping_appointments__different_products(
    setup_overlapping_tests, factories
):
    """
    Finds overlapping appointments that have different products but the same practitioner
    """
    practitioners, _, appointments = setup_overlapping_tests

    # Create a new product and set the second appointment to use it
    new_product = factories.ProductFactory(
        practitioner=practitioners[0],
        vertical=practitioners[0].practitioner_profile.verticals[0],
        minutes=30,
    )
    appointments[1].product_id = new_product.id
    # To find overlapping appointments, they must have a modified date within the last 2 hours
    appointments[1].modified_at = datetime.utcnow() - timedelta(hours=1)

    # Only the first two default appointments are expected to be found, as the third
    # has a different practitioner
    expected_appt_ids = {a.id for a in appointments[:2]}

    with patch("appointments.tasks.appointment_monitors.log.error") as logger_mock:
        find_overlapping_appointments()

    logger_mock.assert_called_once_with(
        "Found overlapping appointments",
        overlapping_appointments=str([expected_appt_ids]),
    )


@freeze_time(FREEZE_TIME_STR)
def test_find_overlapping_appointments__none_found(setup_overlapping_tests):
    """
    Tests that no overlapping appointments are found when the appointments aren't
    overlapping
    """
    _, _, appointments = setup_overlapping_tests

    # To find overlapping appointments, one must have a modified date within the last 2 hours
    appointments[0].modified_at = datetime.utcnow() - timedelta(hours=28)

    # Set the start/end time to not overlap with appointment[0]
    appt_0_duration = timedelta(minutes=appointments[0].product.minutes)
    appt_1_duration = timedelta(minutes=appointments[1].product.minutes)
    appointments[1].scheduled_start = (
        appointments[0].scheduled_start + appt_0_duration + timedelta(minutes=10)
    )
    appointments[1].scheduled_end = appointments[1].scheduled_start + appt_1_duration

    with patch("appointments.tasks.appointment_monitors.log.error") as logger_mock:
        find_overlapping_appointments()

    logger_mock.assert_not_called()


@freeze_time(FREEZE_TIME_STR)
def test_find_overlapping_appointments__starts_earlier_ends_later(
    setup_overlapping_tests,
):
    """
    Finds overlapping appointments when the unmodified appointment starts earlier and
    ends later than the recently modified one
    """
    _, _, appointments = setup_overlapping_tests

    # Only the first two default appointments are expected to be found, as the third
    # has a different practitioner
    expected_appt_ids = {a.id for a in appointments[:2]}

    # To find overlapping appointments, they must have a modified date within the last 2 hours
    appointments[0].modified_at = datetime.utcnow() - timedelta(hours=1)

    # Change appointments[1] to start before and end after appointments[0]
    appointments[1].scheduled_start = appointments[0].scheduled_start - timedelta(
        minutes=10
    )
    appointments[1].scheduled_end = appointments[0].scheduled_end + timedelta(
        minutes=10
    )
    appointments[1].modified_at = datetime.utcnow() - timedelta(hours=5)

    with patch("appointments.tasks.appointment_monitors.log.error") as logger_mock:
        find_overlapping_appointments()

    logger_mock.assert_called_once_with(
        "Found overlapping appointments",
        overlapping_appointments=str([expected_appt_ids]),
    )


@freeze_time(FREEZE_TIME_STR)
def test_find_overlapping_appointments__no_cancelled_appointments(
    setup_overlapping_tests,
):
    """
    Tests that cancelled appointments are not found
    """
    _, _, appointments = setup_overlapping_tests

    # To find overlapping appointments, they must have a modified date within the last 2 hours
    appointments[0].modified_at = datetime.utcnow() - timedelta(hours=1)

    # Cancel one of the overlapping appointments
    appointments[1].cancelled_at = datetime.utcnow()

    with patch("appointments.tasks.appointment_monitors.log.error") as logger_mock:
        find_overlapping_appointments()

    logger_mock.assert_not_called()
