import datetime
from unittest import mock

import pytest
from flask import current_app

from appointments.tasks.availability_notifications import notify_about_availability


@pytest.mark.parametrize("country_accepts_url_in_sms_response", [True, False])
@pytest.mark.parametrize("locale", ["en", "es", "fr", "fr_CA"])
@mock.patch("appointments.tasks.availability_notifications.country_accepts_url_in_sms")
@mock.patch("l10n.utils.localization_is_enabled")
@mock.patch("appointments.tasks.availability_notifications.send_sms")
@mock.patch("l10n.utils.get_locale_from_member_preference")
def test_localization__notify_about_availability(
    mock_member_locale,
    mock_send_sms,
    mock_localization_is_enabled,
    mock_country_accepts_url_in_sms,
    country_accepts_url_in_sms_response,
    locale,
    factories,
):
    # Given
    mock_member_locale.return_value = locale
    mock_country_accepts_url_in_sms.return_value = country_accepts_url_in_sms_response

    # create a new practitioner
    practitioner = factories.PractitionerUserFactory.create()

    # create a new member with a phone number
    member = factories.MemberFactory.create()
    member.member_profile.phone_number = "1-212-555-5555"

    # create an availability request for the practitioner
    factories.AvailabilityNotificationRequestFactory.create(
        member=member,
        practitioner=practitioner,
        member_timezone="America/New_York",
        created_at=datetime.datetime.utcnow() - datetime.timedelta(days=2, minutes=30),
        modified_at=datetime.datetime.utcnow() - datetime.timedelta(days=2, minutes=30),
    )

    # When
    notify_about_availability(practitioner_id=practitioner.id)

    notify_member_about_new_appointment_sms_enabled = {}
    notify_member_about_new_appointment_sms_disabled = {}

    if country_accepts_url_in_sms_response:
        notify_member_about_new_appointment_sms_enabled = {
            "en": (
                "Great news! {practitioner_name} has added new availability for "
                "appointments on Maven! To view available times and book, please head "
                "here: {url}/practitioner/{practitioner_id}"
            ).format(
                practitioner_name=practitioner.full_name,
                url=current_app.config["BASE_URL"],
                practitioner_id=practitioner.id,
            ),
            "es": "notify_member_about_new_prac_availability_url_enabled",
            "fr": "notify_member_about_new_prac_availability_url_enabled",
            "fr_CA": "notify_member_about_new_prac_availability_url_enabled",
        }
    else:
        notify_member_about_new_appointment_sms_disabled = {
            "en": "Great news! {practitioner_name} has added new availability for appointments on Maven! To view available times and book, please head to the Maven application.".format(
                practitioner_name=practitioner.full_name,
            ),
            "es": "notify_member_about_new_prac_availability_url_enabled",
            "fr": "notify_member_about_new_prac_availability_url_enabled",
            "fr_CA": "notify_member_about_new_prac_availability_url_enabled",
        }

    # Then
    expected_message_arg = (
        notify_member_about_new_appointment_sms_enabled[locale]
        if country_accepts_url_in_sms_response
        else notify_member_about_new_appointment_sms_disabled[locale]
    )
    mock_send_sms.assert_called_once()
    message_arg = mock_send_sms.call_args_list[0][1]["message"]
    if locale == "en":
        assert message_arg == expected_message_arg
    else:
        assert message_arg != expected_message_arg
