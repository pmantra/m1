from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from appointments.utils.booking import (
    AvailabilityCalculator,
    MassAvailabilityCalculator,
    PotentialAppointment,
    TimeRange,
)
from pytests.freezegun import freeze_time


@pytest.fixture
def practitioner(factories):
    return factories.PractitionerUserFactory.create(
        practitioner_profile__booking_buffer=0,
    )


@pytest.fixture
def assignable_advocate(factories, practitioner):
    return factories.AssignableAdvocateFactory.create_with_practitioner(
        practitioner=practitioner
    )


@pytest.fixture
def availability_calculator(practitioner, assignable_advocate):
    return AvailabilityCalculator(
        product=practitioner.products[0],
        practitioner_profile=practitioner.practitioner_profile,
    )


@pytest.fixture
def availability(factories, practitioner, appointment_datetime):
    return factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule,
        starts_at=appointment_datetime,
        ends_at=appointment_datetime
        + timedelta(minutes=practitioner.products[0].minutes),
    )


@pytest.fixture
def appointment_datetime():
    return datetime(2021, 1, 1, 0, 0)


@pytest.fixture
def existing_appointment(factories, practitioner, appointment_datetime):
    return factories.AppointmentFactory.create_with_practitioner(
        practitioner=practitioner,
        scheduled_start=appointment_datetime,
    )


@pytest.fixture
def potential_appointment(factories, appointment_datetime):
    appointment = factories.AppointmentFactory.create_with_cancellable_state()
    appointment.scheduled_start = appointment_datetime
    return appointment


@pytest.fixture
def credit(factories, existing_appointment):
    return factories.CreditFactory.create(
        user_id=existing_appointment.member.id,
        amount=10,
        expires_at=None,
    )


def test_availability_calculator_assignable_advocate(
    availability_calculator,
    assignable_advocate,
):
    """Tests that the AvailabilityCalculator returns the associated AssignableAdvocate"""
    assert availability_calculator.assignable_advocate == assignable_advocate


def test_get_availability_zero_limit_raises_value_error(
    availability_calculator, appointment_datetime
):
    """Tests that having a limit of 0 will raise a ValueError"""
    with pytest.raises(ValueError):
        availability_calculator.get_availability(
            start_time=appointment_datetime, end_time=appointment_datetime, limit=0
        )


def test_calculate_availability(
    practitioner,
    availability_calculator,
    availability,
    appointment_datetime,
    credit,
):
    """Tests the AvailabilityCalculator's return values for calculate_availability
    when there are and aren't appointment conflicts
    """
    with freeze_time(appointment_datetime):
        # If the appointments all have conflicts the result will be empty
        with patch.object(
            availability_calculator, "has_appointment_conflict", return_value=True
        ):
            res = availability_calculator.calculate_availability(
                start_time=appointment_datetime,
                end_time=appointment_datetime + timedelta(days=1),
                availabilities=[availability],
                existing_appointments=[],
                all_credits=[credit],
                member_has_had_ca_intro_appt=True,
            )
            assert res == []

        # If there are no conflicts we will get results.
        with patch.object(
            availability_calculator, "has_appointment_conflict", return_value=False
        ):
            res = availability_calculator.calculate_availability(
                start_time=appointment_datetime,
                end_time=appointment_datetime + timedelta(days=1),
                availabilities=[availability],
                existing_appointments=[],
                all_credits=[credit],
                member_has_had_ca_intro_appt=True,
            )
            assert res == [
                PotentialAppointment(
                    scheduled_start=appointment_datetime,
                    scheduled_end=appointment_datetime
                    + timedelta(minutes=practitioner.products[0].minutes),
                    total_available_credits=credit.amount,
                )
            ]


@freeze_time("2021-01-01T00:00:00Z")
def test_calculate_availability_respects_booking_buffer_with_multiple_schedule_events__no_result(
    factories,
    credit,
):
    """
    Tests that calculate_availability respects the booking buffer when there
    are multiple schedule events before it
    """
    now = datetime.utcnow()
    booking_buffer = 240
    practitioner = factories.PractitionerUserFactory.create(
        practitioner_profile__booking_buffer=booking_buffer,
        practitioner_profile__default_prep_buffer=15,
        products__minutes=15,
    )
    product = practitioner.products[0]
    availability = [
        # Schedule Event 1 -- before booking_buffer
        factories.ScheduleEventFactory.create(
            schedule=practitioner.schedule,
            starts_at=now - timedelta(hours=2),
            ends_at=now + timedelta(minutes=30),
        ),
        # Schedule Event 2 -- before booking_buffer
        factories.ScheduleEventFactory.create(
            schedule=practitioner.schedule,
            starts_at=now + timedelta(hours=1),
            ends_at=now + timedelta(hours=2),
        ),
    ]

    ac = AvailabilityCalculator(
        product=product,
        practitioner_profile=practitioner.practitioner_profile,
    )
    appointments = ac.calculate_availability(
        start_time=now,
        end_time=now + timedelta(days=1),
        availabilities=availability,
        existing_appointments=[],
        all_credits=[credit],
        member_has_had_ca_intro_appt=True,
    )
    assert len(appointments) == 0


@freeze_time("2021-01-01T00:00:00Z")
def test_calculate_availability_respects_booking_buffer_with_multiple_schedule_events(
    factories,
    credit,
):
    """
    Tests that calculate_availability respects the booking buffer when there
    are multiple schedule events before it
    """
    now = datetime.utcnow()
    booking_buffer = 240
    practitioner = factories.PractitionerUserFactory.create(
        practitioner_profile__booking_buffer=booking_buffer,
        practitioner_profile__default_prep_buffer=15,
        products__minutes=15,
    )
    product = practitioner.products[0]
    availability = [
        # Schedule Event 1 -- before booking_buffer
        factories.ScheduleEventFactory.create(
            schedule=practitioner.schedule,
            starts_at=now - timedelta(hours=2),
            ends_at=now,
        ),
        # Schedule Event 2 -- before booking_buffer
        factories.ScheduleEventFactory.create(
            schedule=practitioner.schedule,
            starts_at=now + timedelta(hours=1),
            ends_at=now + timedelta(hours=2),
        ),
        # Schedule Event 3 -- after booking_buffer
        factories.ScheduleEventFactory.create(
            schedule=practitioner.schedule,
            starts_at=now + timedelta(hours=4),
            ends_at=now + timedelta(hours=5),
        ),
    ]

    ac = AvailabilityCalculator(
        product=product,
        practitioner_profile=practitioner.practitioner_profile,
    )
    appointments = ac.calculate_availability(
        start_time=now,
        end_time=now + timedelta(days=1),
        availabilities=availability,
        existing_appointments=[],
        all_credits=[credit],
        member_has_had_ca_intro_appt=True,
    )

    assert len(appointments) > 0
    for availability in appointments:
        expected_min_start = now + timedelta(minutes=booking_buffer)
        assert availability.scheduled_start >= expected_min_start


def test_has_appointment_conflict_checks_unavailable_dates_first(
    availability_calculator,
    appointment_datetime,
    existing_appointment,
    potential_appointment,
):
    """Tests that the AvailabilityCalculator will check the unavailable dates first before
    checking for actual conflicts using Appointment.contains()
    """
    with patch.object(existing_appointment, "contains", return_value=False):
        # If the appointment is on an unavailable date, existing appointments should not
        # be checked and has_appointment_conflict should return True
        has_conflict = availability_calculator.has_appointment_conflict(
            potential_appointment=potential_appointment,
            existing_appointments=[existing_appointment],
            unavailable_dates=[TimeRange(appointment_datetime, appointment_datetime)],
        )
        existing_appointment.contains.assert_not_called()
        assert has_conflict

        # If the appointment is not on an unavailable date, existing appointments should
        # be checked and has_appointment_conflict should return False if the existing
        # appointments do not overlap with the potential appointment
        has_conflict = availability_calculator.has_appointment_conflict(
            potential_appointment=potential_appointment,
            existing_appointments=[existing_appointment],
            unavailable_dates=[],
        )
        existing_appointment.contains.assert_called()
        assert not has_conflict

    with patch.object(existing_appointment, "contains", return_value=True):
        # If the appointment is not on an unavailable date, existing appointments should
        # be checked and has_appointment_conflict should return True if the existing
        # appointments overlap with the potential appointment
        has_conflict = availability_calculator.has_appointment_conflict(
            potential_appointment=potential_appointment,
            existing_appointments=[existing_appointment],
            unavailable_dates=[],
        )
        existing_appointment.contains.assert_called()
        assert has_conflict


def test_get_availability_uses_prep_buffer_outside(
    factories,
    availability_calculator,
    appointment_datetime,
    member_with_add_appointment,
):
    """
    Test that get_availability takes into account the prep buffer
    before the given time/search block
    """
    vertical = factories.VerticalFactory.create(
        products=[{"minutes": 15, "price": 60}],
        filter_by_state=False,
    )
    practitioner = factories.PractitionerUserFactory.create(
        practitioner_profile__booking_buffer=30,
        practitioner_profile__default_prep_buffer=15,
        practitioner_profile__verticals=[vertical],
        products__minutes=15,
    )
    schedule = factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule,
        starts_at=appointment_datetime - timedelta(hours=2),
        ends_at=appointment_datetime + timedelta(hours=2),
    )
    product = practitioner.products[0]

    # Create first appointment
    first_appt = factories.AppointmentFactory.create_with_practitioner(
        practitioner,
        scheduled_start=appointment_datetime,
        scheduled_end=appointment_datetime + timedelta(minutes=product.minutes),
    )

    member = member_with_add_appointment
    factories.ScheduleFactory.create(user=member)

    with freeze_time(schedule.starts_at):
        ac = AvailabilityCalculator(
            product=product,
            practitioner_profile=practitioner.practitioner_profile,
        )

        # Look for availability starting 5 minutes after the first one ends
        # shouldn't result in any availability due to the prep buffer
        second_appt_start = first_appt.scheduled_end + timedelta(minutes=5)
        availability = ac.get_availability(
            second_appt_start,
            (second_appt_start + timedelta(minutes=product.minutes)),
            member=member,
        )
        assert availability == []

        # Look for availability that ends 5 minutes before the first one starts
        # also shouldn't result in any availability due to the prep buffer
        third_appt_end = first_appt.scheduled_start - timedelta(minutes=5)
        third_appt_start = third_appt_end - timedelta(minutes=product.minutes)
        availability = ac.get_availability(
            third_appt_start,
            third_appt_end,
            member=member,
        )
        assert availability == []


def test_get_existing_appointments__prep_buffer(
    factories,
    availability_calculator,
    appointment_datetime,
    member_with_add_appointment,
):
    """
    Test that get_existing_appointments takes into account the prep buffer
    at the beginning and end of a given time block
    """
    vertical = factories.VerticalFactory.create(
        products=[{"minutes": 15, "price": 60}],
        filter_by_state=False,
    )
    practitioner = factories.PractitionerUserFactory.create(
        practitioner_profile__booking_buffer=30,
        practitioner_profile__default_prep_buffer=15,
        practitioner_profile__verticals=[vertical],
        products__minutes=15,
    )
    schedule = factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule,
        starts_at=appointment_datetime - timedelta(hours=2),
        ends_at=appointment_datetime + timedelta(hours=2),
    )
    product = practitioner.products[0]

    # Create first appointment
    factories.AppointmentFactory.create_with_practitioner(
        practitioner,
        scheduled_start=appointment_datetime,
        scheduled_end=appointment_datetime + timedelta(minutes=product.minutes),
    )

    member = member_with_add_appointment
    factories.ScheduleFactory.create(user=member)

    with freeze_time(schedule.starts_at):
        ac = AvailabilityCalculator(
            product=product,
            practitioner_profile=practitioner.practitioner_profile,
        )
        # Search for appointments after the first scheduled appt
        existing_appointments = ac.get_existing_appointments(
            (appointment_datetime + timedelta(minutes=20)),
            (appointment_datetime + timedelta(minutes=35)),
            member=member,
        )
        assert len(existing_appointments) == 1
        assert existing_appointments[0].scheduled_start == appointment_datetime

        # Search for appointments before the first scheduled appt
        third_appt_end = appointment_datetime - timedelta(minutes=5)
        third_appt_start = third_appt_end - timedelta(minutes=product.minutes)
        existing_appointments = ac.get_existing_appointments(
            third_appt_start,
            third_appt_end,
            member=member,
        )
        assert len(existing_appointments) == 1
        assert existing_appointments[0].scheduled_start == appointment_datetime


def test_get_mass_existing_appointments_fields__no_member_appts_in_prep_buffer(
    factories,
    availability_calculator,
    appointment_datetime,
    member_with_add_appointment,
):
    """
    Test that get_mass_existing_appointments doesn't return member appointments
    in the prep buffer outside of search time
    """
    vertical = factories.VerticalFactory.create(
        products=[{"minutes": 15, "price": 60}],
        filter_by_state=False,
    )
    practitioner_1 = factories.PractitionerUserFactory.create(
        practitioner_profile__booking_buffer=30,
        practitioner_profile__default_prep_buffer=15,
        practitioner_profile__verticals=[vertical],
        products__minutes=15,
    )
    practitioner_2 = factories.PractitionerUserFactory.create(
        practitioner_profile__booking_buffer=30,
        practitioner_profile__default_prep_buffer=15,
        practitioner_profile__verticals=[vertical],
        products__minutes=15,
    )
    schedule_1 = factories.ScheduleEventFactory.create(
        schedule=practitioner_1.schedule,
        starts_at=appointment_datetime - timedelta(hours=2),
        ends_at=appointment_datetime + timedelta(hours=2),
    )
    factories.ScheduleEventFactory.create(
        schedule=practitioner_2.schedule,
        starts_at=appointment_datetime - timedelta(hours=2),
        ends_at=appointment_datetime + timedelta(hours=2),
    )
    product_1 = practitioner_1.products[0]

    member = member_with_add_appointment
    member_schedule = factories.ScheduleFactory.create(user=member)

    # Create an appointment which _should_ be found when searching,
    # as it's within our searching time w/o prep_buffer
    factories.AppointmentFactory.create_with_practitioner(
        practitioner_1,
        scheduled_start=appointment_datetime,
        scheduled_end=appointment_datetime + timedelta(minutes=product_1.minutes),
        member_schedule=member_schedule,
    )
    # Create an appointment which _shouldn't_ be found when searching,
    # as it's only within our prep_buffer time
    factories.AppointmentFactory.create_with_practitioner(
        practitioner_1,
        scheduled_start=appointment_datetime - timedelta(minutes=15),
        scheduled_end=appointment_datetime,
        member_schedule=member_schedule,
    )

    with freeze_time(schedule_1.starts_at):
        # Search for appointments with practitioner_2, as we are only looking for member appointments,
        # which have been scheduled with practitioner_1
        (
            _,
            member_appointments,
        ) = MassAvailabilityCalculator().get_mass_existing_appointments(
            appointment_datetime,
            (appointment_datetime + timedelta(minutes=30)),
            [practitioner_2.id],
            member,
        )

        assert len(member_appointments) == 1, f"{member_appointments = }"
        assert member_appointments[0].scheduled_start == appointment_datetime


def test_get_mass_existing_appointments_fields__prep_buffer_outside(
    factories,
    availability_calculator,
    appointment_datetime,
    member_with_add_appointment,
):
    """
    Test that get_mass_existing_appointments takes into account the prep buffer
    outside of a given time block
    """
    vertical = factories.VerticalFactory.create(
        products=[{"minutes": 15, "price": 60}],
        filter_by_state=False,
    )
    practitioner = factories.PractitionerUserFactory.create(
        practitioner_profile__booking_buffer=30,
        practitioner_profile__default_prep_buffer=15,
        practitioner_profile__verticals=[vertical],
        products__minutes=15,
    )
    schedule = factories.ScheduleEventFactory.create(
        schedule=practitioner.schedule,
        starts_at=appointment_datetime - timedelta(hours=2),
        ends_at=appointment_datetime + timedelta(hours=2),
    )
    product = practitioner.products[0]

    # Create first appointment
    factories.AppointmentFactory.create_with_practitioner(
        practitioner,
        scheduled_start=appointment_datetime,
        scheduled_end=appointment_datetime + timedelta(minutes=product.minutes),
    )

    member = member_with_add_appointment
    factories.ScheduleFactory.create(user=member)

    with freeze_time(schedule.starts_at):
        # Search for appointments after the first scheduled appt
        (
            existing_appointments,
            _,
        ) = MassAvailabilityCalculator().get_mass_existing_appointments(
            (appointment_datetime + timedelta(minutes=20)),
            (appointment_datetime + timedelta(minutes=35)),
            [practitioner.id],
            member,
        )

        existing_appointments_for_prac = existing_appointments.get(practitioner.id)
        assert (
            len(existing_appointments_for_prac) == 1
        ), f"{existing_appointments_for_prac = }"
        assert existing_appointments_for_prac[0].scheduled_start == appointment_datetime

        # Search for appointments before the first scheduled appt
        third_appt_end = appointment_datetime - timedelta(minutes=5)
        third_appt_start = third_appt_end - timedelta(minutes=product.minutes)
        (
            existing_appointments,
            _,
        ) = MassAvailabilityCalculator().get_mass_existing_appointments(
            third_appt_start,
            third_appt_end,
            [practitioner.id],
            member,
        )

        existing_appointments_for_prac = existing_appointments.get(practitioner.id)
        assert (
            len(existing_appointments_for_prac) == 1
        ), f"{existing_appointments_for_prac = }"
        assert existing_appointments_for_prac[0].scheduled_start == appointment_datetime


def test_get_first_scheduled_start_time_defaults_to_booking_buffer(
    factories,
    availability_calculator,
    appointment_datetime,
):
    """
    Tests that get_first_scheduled_start_time() defaults to prep buffer when
    it's longer than the booking buffer
    """
    booking_buffer = 30
    prep_buffer = 15
    practitioner = factories.PractitionerUserFactory.create(
        practitioner_profile__booking_buffer=booking_buffer,
        practitioner_profile__default_prep_buffer=prep_buffer,
    )
    product = practitioner.products[0]

    with freeze_time(appointment_datetime):
        now = appointment_datetime
        now_minus_10 = now - timedelta(minutes=10)
        expected_start = now + timedelta(minutes=20)

        ac = AvailabilityCalculator(
            product=product,
            practitioner_profile=practitioner.practitioner_profile,
        )
        appointment_starts_at = now  # this just needs to be less than expected_start
        actual_start = ac.get_first_scheduled_start_time(
            appointment_starts_at, now_minus_10
        )
        assert actual_start == expected_start


def test_get_first_scheduled_start_time_defaults_to_prep_buffer(
    factories,
    availability_calculator,
    appointment_datetime,
):
    """
    Tests that get_first_scheduled_start_time() defaults to prep buffer when
    it's longer than the booking buffer
    """
    booking_buffer = 15
    prep_buffer = 30
    practitioner = factories.PractitionerUserFactory.create(
        practitioner_profile__booking_buffer=booking_buffer,
        practitioner_profile__default_prep_buffer=prep_buffer,
    )
    product = practitioner.products[0]

    with freeze_time(appointment_datetime):
        now = appointment_datetime
        now_minus_10 = now - timedelta(minutes=10)
        expected_start = now + timedelta(minutes=20)

        ac = AvailabilityCalculator(
            product=product,
            practitioner_profile=practitioner.practitioner_profile,
        )
        appointment_starts_at = now  # this just needs to be less than expected_start
        actual_start = ac.get_first_scheduled_start_time(
            appointment_starts_at, now_minus_10
        )
        assert actual_start == expected_start
