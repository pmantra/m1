import datetime
from unittest.mock import patch

import pytest

from dosespot.resources.dosespot_api import DoseSpotAPI

now = datetime.datetime.utcnow()


@pytest.fixture
def appointment_with_pharmacy(valid_appointment_with_user, practitioner_user):
    ca = practitioner_user()
    dp = ca.practitioner_profile.dosespot
    dp["clinic_key"] = 1
    dp["clinic_id"] = 1
    dp["user_id"] = 1

    a = valid_appointment_with_user(
        practitioner=ca,
        purpose="birth_needs_assessment",
        scheduled_start=now + datetime.timedelta(minutes=10),
    )
    mp = a.member.member_profile
    mp.set_patient_info(patient_id=a.member.id, practitioner_id=a.practitioner.id)
    return ca, a


def test_rx_from_appointment_no_rx(appointment_with_pharmacy):
    with patch.object(
        DoseSpotAPI,
        "api_request",
        return_value=(
            200,
            {
                "Items": [],
                "Result": {
                    "ResultCode": "Result Code 1",
                    "ResultDescription": "Result Code 2",
                },
            },
        ),
    ):
        ca, a = appointment_with_pharmacy
        rx = a.rx_from_appointment()
        assert not len(rx)


def test_rx_from_appointment(appointment_with_pharmacy):
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
        ca, a = appointment_with_pharmacy
        rx = a.rx_from_appointment()
        assert len(rx) == 1
        for med in rx:
            assert "PrescriptionStatus" in med
            assert "PharmacyId" in med
            assert "MedicationId" in med
