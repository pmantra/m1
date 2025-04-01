from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from appointments.utils.availability_notifications import (
    update_next_availability_and_alert_about_availability,
)


@pytest.fixture
def practitioner(practitioner_user):
    return practitioner_user()


@patch(
    "appointments.utils.availability_notifications.update_practitioner_profile_next_availability"
)
@patch("appointments.utils.availability_notifications.notify_bookings_channel")
@patch("appointments.utils.availability_notifications.notify_about_availability.delay")
def test_update_next_availability_and_alert_about_availability_not_called(
    mock_update_practitioner_profile_next_availability,
    mock_notify_bookings_channel,
    mock_notify_about_availability,
    factories,
    schedule,
    practitioner,
):
    now = datetime.now(timezone.utc)
    ends_at = now + timedelta(days=2)
    user_full_name = practitioner.first_name + " " + practitioner.last_name
    practitioner_profile = practitioner.practitioner_profile
    update_next_availability_and_alert_about_availability(
        practitioner_profile=practitioner_profile,
        user_full_name=user_full_name,
        starts_at=now,
        ends_at=ends_at,
    )

    assert mock_update_practitioner_profile_next_availability.called_with(
        practitioner_profile
    )
    assert not mock_notify_bookings_channel.called
    assert mock_notify_about_availability.called_with(
        practitioner.id, "mpractice_core", "provider_availability"
    )


@patch(
    "appointments.utils.availability_notifications.update_practitioner_profile_next_availability"
)
@patch("appointments.utils.availability_notifications.notify_bookings_channel")
@patch("appointments.utils.availability_notifications.notify_about_availability.delay")
def test_update_next_availability_and_alert_about_availability_not_recurring(
    mock_update_practitioner_profile_next_availability,
    mock_notify_bookings_channel,
    mock_notify_about_availability,
    factories,
    schedule,
    practitioner,
):
    now = datetime.now(timezone.utc)
    ends_at = now + timedelta(days=2)
    practitioner_profile = practitioner.practitioner_profile
    practitioner_profile.alert_about_availability = True
    user_full_name = practitioner.first_name + " " + practitioner.last_name
    update_next_availability_and_alert_about_availability(
        practitioner_profile=practitioner_profile,
        user_full_name=user_full_name,
        starts_at=now,
        ends_at=ends_at,
    )

    assert mock_update_practitioner_profile_next_availability.called_with(
        practitioner_profile
    )
    mock_notify_bookings_channel.assert_called_with(
        f"<!channel>: {user_full_name} set availability from {now} to {ends_at}"
    )
    assert mock_notify_about_availability.called_with(
        practitioner.id, "mpractice_core", "provider_availability"
    )


@patch(
    "appointments.utils.availability_notifications.update_practitioner_profile_next_availability"
)
@patch("appointments.utils.availability_notifications.notify_bookings_channel")
@patch("appointments.utils.availability_notifications.notify_about_availability.delay")
def test_update_next_availability_and_alert_about_availability_recurring(
    mock_update_practitioner_profile_next_availability,
    mock_notify_bookings_channel,
    mock_notify_about_availability,
    factories,
    schedule,
    practitioner,
):
    now = datetime.now(timezone.utc)
    ends_at = now + timedelta(days=2)
    until = now + timedelta(weeks=1)
    practitioner_profile = practitioner.practitioner_profile
    practitioner_profile.alert_about_availability = True
    user_full_name = practitioner.first_name + " " + practitioner.last_name
    update_next_availability_and_alert_about_availability(
        practitioner_profile=practitioner_profile,
        user_full_name=user_full_name,
        starts_at=now,
        ends_at=ends_at,
        until=until,
        recurring=True,
    )

    assert mock_update_practitioner_profile_next_availability.called_with(
        practitioner_profile
    )
    mock_notify_bookings_channel.assert_called_with(
        f"<!channel>: {user_full_name} set recurring availability from {now} to {ends_at} until {until}"
    )
    assert mock_notify_about_availability.called_with(
        practitioner.id, "mpractice_core", "provider_availability"
    )
