import datetime

import pytest

from pytests.factories import AddressFactory

now = datetime.datetime.utcnow()


@pytest.fixture
def appointment_with_pharmacy(valid_appointment_with_user, practitioner_user):
    ca = practitioner_user()
    # Enable prescription for member by setting "valid" information
    dp = ca.practitioner_profile.dosespot
    dp["clinic_key"] = 1
    dp["clinic_id"] = 1
    dp["user_id"] = 1

    a = valid_appointment_with_user(
        practitioner=ca,
        purpose="birth_needs_assessment",
        scheduled_start=now + datetime.timedelta(minutes=10),
    )
    a.member.member_profile.phone_number = "+1-913-476-8475"
    a.member.addresses.append(AddressFactory.create())
    a.member.health_profile.json = {"birthday": "a birthday"}
    mp = a.member.member_profile
    mp.set_patient_info(patient_id=a.member.id, practitioner_id=a.practitioner.id)
    return a
