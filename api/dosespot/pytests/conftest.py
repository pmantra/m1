import datetime
from typing import Dict, Tuple

import pytest

now = datetime.datetime.utcnow()


@pytest.fixture
def practitioner(factories):
    return factories.PractitionerUserFactory.create()


@pytest.fixture
def member(factories):
    return factories.MemberFactory.create()


@pytest.fixture
def health_profile_with_birthday(factories, member):
    return factories.HealthProfileFactory.create(user=member, has_birthday=True)


@pytest.fixture
def appointment(factories, practitioner, health_profile_with_birthday, member):
    return factories.AppointmentFactory.create_with_practitioner(
        practitioner=practitioner,
        scheduled_start=now,
        member_schedule=factories.ScheduleFactory.create(user=member),
    )


@pytest.fixture
def set_member_address(appointment):
    address_dict = {
        "street_address": "123 Foo Bar Road",
        "zip_code": "11234",
        "city": "Foo Bar",
        "state": "FB",
        "country": "US",
    }

    return appointment.member.member_profile.add_or_update_address(address_dict)


@pytest.fixture
def set_long_named_member_address(appointment):
    address_dict = {
        "street_address": "123 Super Duper Extra Incredulously Long Street Address",
        "zip_code": "11234",
        "city": "Foo Bar",
        "state": "FB",
        "country": "US",
    }

    return appointment.member.member_profile.add_or_update_address(address_dict)


@pytest.fixture(scope="function")
def active_prescription() -> Dict:
    return {
        "MedicationStatus": 1,
        "WrittenDate": "2021-06-14 19:17:42.649212",
        "PatientMedicationId": 301,
        "Status": 1,
    }


@pytest.fixture(scope="function")
def completed_prescription() -> Dict:
    return {
        "MedicationStatus": 5,
        "WrittenDate": "2021-06-14 20:17:42.649212",
        "PatientMedicationId": 302,
        "Status": 4,
    }


@pytest.fixture(scope="function")
def inactive_prescription() -> Dict:
    return {
        "MedicationStatus": 2,
        "WrittenDate": "2021-06-14 21:17:42.649212",
        "PatientMedicationId": 303,
        "Status": 0,
    }


@pytest.fixture(scope="function")
def translated_active_prescription() -> Dict:
    return {
        "MedicationStatus": 1,
        "WrittenDate": "2021-06-14 19:17:42.649212",
        "DateWritten": datetime.datetime(2021, 6, 14, 19, 17, 42, 649212),
        "PatientMedicationId": 301,
        "MedicationId": 301,
        "Status": 1,
        "PrescriptionStatus": "Entered",
    }


@pytest.fixture(scope="function")
def translated_completed_prescription() -> Dict:
    return {
        "MedicationStatus": 5,
        "WrittenDate": "2021-06-14 20:17:42.649212",
        "DateWritten": datetime.datetime(2021, 6, 14, 20, 17, 42, 649212),
        "PatientMedicationId": 302,
        "MedicationId": 302,
        "Status": 4,
        "PrescriptionStatus": "eRxSent",
    }


def paginated_medications(
    patient_id: str, params: Dict, method: str, endpoint: str
) -> Tuple[int, Dict]:
    if params["pageNumber"] == 1:
        return 200, {
            "Items": [
                {
                    "MedicationStatus": 1,
                    "WrittenDate": "2021-06-14 19:17:42.649212",
                    "PatientMedicationId": 301,
                    "Status": 1,
                }
            ],
            "PageResult": {"HasNext": True},
        }
    else:
        return 200, {
            "Items": [
                {
                    "MedicationStatus": 5,
                    "WrittenDate": "2021-06-14 20:17:42.649212",
                    "PatientMedicationId": 302,
                    "Status": 4,
                }
            ],
            "PageResult": {"HasNext": False},
        }
