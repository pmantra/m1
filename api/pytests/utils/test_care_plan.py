import dataclasses
import datetime
from unittest.mock import patch

import pytest

from care_plans.care_plans_service import CarePlansService
from pytests import factories

utcnow = datetime.datetime.utcnow().replace(second=0, microsecond=0)
one_hour_ago = utcnow - datetime.timedelta(hours=1)
one_hour_from_now = utcnow + datetime.timedelta(hours=1)


@pytest.fixture
def setup_care_plan_activity_publishing_test():
    """Sets up the Care Plan Activity Publishing test"""

    def setup_func(*args, **kwargs):
        appointment = factories.AppointmentFactory.create(**kwargs)
        return appointment

    return setup_func


@pytest.fixture
def setup_care_plan_appointment():
    """Sets up the Care Plan Meet Activity event test by generating a new Appointment object"""

    def setup_func(*args, **kwargs):
        appointment = factories.AppointmentFactory.create(**kwargs)
        return appointment

    return setup_func


@pytest.fixture()
def send_activity_occurred_mock():
    with patch.object(CarePlansService, "send_activity_occurred") as p:
        yield p


def test_care_plan_send_appointment_activity_member_has_care_plan(
    setup_care_plan_appointment, send_activity_occurred_mock
):
    """Tests that when send_appointment_completed() is called on a completed
    appointment that is not cancelled or disputed and the member has a care plan,
    the helper function to call cps' activity-occurred endpoint is called.
    """
    # Given
    appointment = setup_care_plan_appointment(
        created_at=one_hour_ago,
        scheduled_start=one_hour_ago,
        member_started_at=one_hour_ago,
        practitioner_started_at=one_hour_ago,
        member_ended_at=utcnow,
        practitioner_ended_at=utcnow,
        cancelled_at=None,
        disputed_at=None,
    )
    member_profile = appointment.member.profile
    member_profile.has_care_plan = True

    # When
    CarePlansService.send_appointment_completed(appointment, "")

    # Then
    args = send_activity_occurred_mock.call_args.args
    assert args[0] == appointment.member.id
    args1 = dataclasses.asdict(args[1])
    assert args1["type"] == "meet"
    assert args1["vertical_id"] == appointment.product.vertical_id
    assert args1["appointment_purpose"] == appointment.purpose


def test_care_plan_send_appointment_activity_member_has_no_care_plan(
    setup_care_plan_appointment, send_activity_occurred_mock
):
    """Tests that when send_appointment_completed() is called on a completed
    appointment that is not cancelled or disputed and the member has no care plan,
    the helper function to call cps' activity-occurred endpoint is not called.
    """
    # Given
    appointment = setup_care_plan_appointment(
        created_at=one_hour_ago,
        scheduled_start=one_hour_ago,
        member_started_at=one_hour_ago,
        practitioner_started_at=one_hour_ago,
        member_ended_at=utcnow,
        practitioner_ended_at=utcnow,
        cancelled_at=None,
        disputed_at=None,
    )
    member_profile = appointment.member.profile
    member_profile.has_care_plan = False

    # When
    CarePlansService.send_appointment_completed(appointment)

    # Then
    send_activity_occurred_mock.assert_not_called()


def test_care_plan_send_appointment_activity_upcoming_appointment(
    setup_care_plan_appointment, send_activity_occurred_mock
):
    """Tests that when send_appointment_completed() is called on an upcoming
    appointment that is not cancelled or disputed,
    the helper function to call cps' activity-occurred endpoint is not called.
    """
    # Given
    appointment = setup_care_plan_appointment(
        created_at=utcnow,
        scheduled_start=one_hour_from_now,
        member_started_at=None,
        practitioner_started_at=None,
        member_ended_at=None,
        practitioner_ended_at=None,
        cancelled_at=None,
        disputed_at=None,
    )

    # When
    CarePlansService.send_appointment_completed(appointment)

    # Then
    send_activity_occurred_mock.assert_not_called()


def test_care_plan_send_appointment_activity_ongoing_appointment(
    setup_care_plan_appointment, send_activity_occurred_mock
):
    """Tests that when send_appointment_completed() is called on an ongoing
    appointment that is not cancelled or disputed,
    the helper function to call cps' activity-occurred endpoint is not called.
    """
    # Given
    appointment = setup_care_plan_appointment(
        created_at=one_hour_ago,
        scheduled_start=one_hour_ago,
        member_started_at=one_hour_ago,
        practitioner_started_at=one_hour_ago,
        member_ended_at=None,
        practitioner_ended_at=None,
        cancelled_at=None,
        disputed_at=None,
    )

    # When
    CarePlansService.send_appointment_completed(appointment)

    # Then
    send_activity_occurred_mock.assert_not_called()


def test_care_plan_send_appointment_activity_cancelled_appointment(
    setup_care_plan_appointment, send_activity_occurred_mock
):
    """Tests that when send_appointment_completed() is called on an
    appointment that is cancelled, the helper
    function to call cps' activity-occurred endpoint is not called.
    """
    # Given
    appointment = setup_care_plan_appointment(
        created_at=one_hour_ago,
        scheduled_start=one_hour_ago,
        member_started_at=one_hour_ago,
        practitioner_started_at=one_hour_ago,
        member_ended_at=utcnow,
        practitioner_ended_at=utcnow,
        cancelled_at=utcnow,
        disputed_at=None,
    )

    # When
    CarePlansService.send_appointment_completed(appointment)

    # Then
    send_activity_occurred_mock.assert_not_called()


def test_care_plan_send_appointment_activity_disputed_appointment(
    setup_care_plan_appointment, send_activity_occurred_mock
):
    """Tests that when send_appointment_completed() is called on an
    appointment that is disputed, the helper
    function to call cps' activity-occurred endpoint is not called.
    """
    # Given
    appointment = setup_care_plan_appointment(
        created_at=one_hour_ago,
        scheduled_start=one_hour_ago,
        member_started_at=one_hour_ago,
        practitioner_started_at=one_hour_ago,
        member_ended_at=utcnow,
        practitioner_ended_at=utcnow,
        cancelled_at=None,
        disputed_at=utcnow,
    )

    # When
    CarePlansService.send_appointment_completed(appointment)

    # Then
    send_activity_occurred_mock.assert_not_called()
