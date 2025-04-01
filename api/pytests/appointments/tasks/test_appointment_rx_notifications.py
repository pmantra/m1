import datetime
from unittest import mock
from unittest.mock import patch

import pytest

from appointments.tasks.appointment_rx_notifications import notify_about_rx_complete
from dosespot.resources.dosespot_api import DoseSpotAPI
from pytests.factories import PractitionerUserFactory, VerticalFactory


@pytest.fixture()
def valid_pharmacy():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return {
        "PharmacyId": "1",
        "StoreName": "Test One Pharmacy",
        "Address1": "90001 1ST ST",
        "Address2": "1ST FL",
        "City": "Washington",
        "State": "DC",
        "ZipCode": "20000",
        "PrimaryPhone": "2025551212",
        "PrimaryPhoneType": "Work",
        "PrimaryFax": "2025551213",
        "PharmacySpecialties": [],
    }


@pytest.fixture
def appointment_with_pharmacy(
    valid_appointment_with_user, practitioner_user, valid_pharmacy
):
    ca = practitioner_user()
    dp = ca.practitioner_profile.dosespot
    dp["clinic_key"] = 1
    dp["clinic_id"] = 1
    dp["user_id"] = 1

    a = valid_appointment_with_user(
        practitioner=ca,
        purpose="birth_needs_assessment",
        scheduled_start=datetime.datetime.utcnow() + datetime.timedelta(minutes=10),
    )
    mp = a.member.member_profile
    mp.phone_number = "+17733220000"

    mp.set_patient_info(patient_id=a.member.id, practitioner_id=a.practitioner.id)
    mp.set_prescription_info(pharmacy_info=valid_pharmacy)
    return ca, a


@pytest.fixture
def datetime_now():
    return datetime.datetime.utcnow()


@pytest.fixture
def valid_appointment_with_user(factories, datetime_now):
    def make_valid_appointment_with_user(
        practitioner,
        scheduled_start=datetime_now,
        scheduled_end=None,
        purpose=None,
        member_schedule=None,
    ):
        a = factories.AppointmentFactory.create_with_practitioner(
            member_schedule=member_schedule,
            purpose=purpose,
            practitioner=practitioner,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
        )
        a.json = {
            "rx_written_via": "dosespot",
            "rx_written_at": datetime.datetime.utcnow().isoformat(),
        }
        return a

    return make_valid_appointment_with_user


@pytest.fixture
def vertical_ca():
    return VerticalFactory.create_cx_vertical()


@pytest.fixture
def practitioner_user(vertical_ca):
    def make_practitioner_user(
        verticals=None,
    ):
        if verticals is None:
            verticals = [vertical_ca]
        practitioner_user = PractitionerUserFactory.create(
            practitioner_profile__verticals=verticals,
        )
        return practitioner_user

    return make_practitioner_user


@pytest.mark.parametrize("locale", ["en", "es", "fr", "fr_CA"])
@mock.patch("l10n.utils.localization_is_enabled")
@mock.patch("appointments.tasks.appointment_rx_notifications.send_sms")
@mock.patch("l10n.utils.get_locale_from_member_preference")
def test_localization__notify_about_rx_complete(
    mock_member_locale,
    mock_send_sms,
    mock_localization_is_enabled,
    locale,
    factories,
    appointment_with_pharmacy,
):
    # Given
    mock_member_locale.return_value = locale
    ca, a = appointment_with_pharmacy
    now = datetime.datetime.utcnow()

    # When
    with patch.object(
        DoseSpotAPI,
        "api_request",
        return_value=(
            200,
            {
                "Items": [
                    {
                        "PrescriptionId": 1,
                        "WrittenDate": datetime.datetime.strftime(
                            now + datetime.timedelta(minutes=60),
                            "%Y-%m-%dT%H:%M:%S.%f+00:00",
                        ),
                        "MedicationStatus": 1,
                        "PharmacyId": 1,
                        "PatientMedicationId": 123,
                        "Status": 1,
                    },
                    {
                        "PrescriptionId": 2,
                        "WrittenDate": datetime.datetime.strftime(
                            now + datetime.timedelta(minutes=60),
                            "%Y-%m-%dT%H:%M:%S.%f+00:00",
                        ),
                        "MedicationStatus": 0,
                        "PharmacyId": 2,
                        "PatientMedicationId": 321,
                        "Status": 4,
                    },
                ],
                "Result": {
                    "ResultCode": "Result Code 1",
                    "ResultDescription": "Result Code 2",
                },
            },
        ),
    ):
        # trigger 'notify_about_rx_complete'
        notify_about_rx_complete(appointment_id=a.id)

    # extract pharmacy info to use in assertion when evaluating the SMS message
    pharmacy_info = a.member.member_profile.get_prescription_info().get(
        "pharmacy_info", {}
    )
    pharmacy_name = pharmacy_info.get("StoreName", "").title()
    pharmacy_phone = pharmacy_info.get("PrimaryPhone")

    notify_member_about_written_rx = {
        "en": (
            "Your practitioner has sent your prescription to "
            "{pharmacy_name}. Please contact the pharmacy at "
            "{pharmacy_phone} with any questions."
        ).format(pharmacy_name=pharmacy_name, pharmacy_phone=pharmacy_phone),
        "es": "notify_member_about_written_rx",
        "fr": "notify_member_about_written_rx",
        "fr_CA": "notify_member_about_written_rx",
    }

    # Then
    expected_message_arg = notify_member_about_written_rx[locale]
    mock_send_sms.assert_called_once()
    message_arg = mock_send_sms.call_args_list[0][1]["message"]
    if locale == "en":
        assert message_arg == expected_message_arg
    else:
        assert message_arg != expected_message_arg
