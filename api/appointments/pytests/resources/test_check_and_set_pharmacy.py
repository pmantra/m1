import pytest
from werkzeug.exceptions import HTTPException

from appointments.models.constants import PRIVACY_CHOICES
from appointments.resources.appointment import AppointmentResource
from models.profiles import MemberProfile
from pytests import factories


@pytest.fixture
def test_data(factories: factories):
    """Returns a dictionary of object references so that assertions can be made
    comparing the expected data and the result of the calls in the test.

    When adding new test cases via the @pytest.mark.parametrize decorator, reference the
    expected values by their dictionary key.
    """

    member_1 = factories.MemberFactory.create(
        id=1,
        first_name="One",
        last_name="One",
        email="one@maventest.com",
    )
    member_2 = factories.MemberFactory.create(
        id=2,
        first_name="Two",
        last_name="Two",
        email="two@maventest.com",
    )

    pract_1 = factories.PractitionerUserFactory.create()
    pract_2 = factories.PractitionerUserFactory.create()

    member_1.member_profile.dosespot = {
        MemberProfile.GLOBAL_PHARMACY_KEY: {"pharmacy_id": 1}
    }
    member_schedule_1 = factories.ScheduleFactory.create(user=member_1)
    appointment_1 = factories.AppointmentFactory.create(
        id=1, member_schedule=member_schedule_1
    )

    member_2.member_profile.dosespot = {
        MemberProfile.GLOBAL_PHARMACY_KEY: {"pharmacy_id": 1}
    }
    member_2.member_profile.phone_number = "2025555555"
    member_2.health_profile.json = {"birthday": "01/01/2000"}
    factories.AddressFactory.create(user=member_2)
    member_schedule_2 = factories.ScheduleFactory.create(user=member_2)
    appointment_2 = factories.AppointmentFactory.create(
        id=2, member_schedule=member_schedule_2, privacy=PRIVACY_CHOICES.anonymous
    )

    pract_1.practitioner_profile.dosespot = {}
    appointment_3 = factories.AppointmentFactory.create(
        id=3, member_schedule=member_schedule_2, product=pract_1.products[0]
    )
    pract_2.practitioner_profile.dosespot = {
        "clinic_key": "test_key",
        "clinic_id": "test_clinic_id",
        "user_id": "test_user_id",
    }
    appointment_4 = factories.AppointmentFactory.create(
        id=4, member_schedule=member_schedule_2, product=pract_2.products[0]
    )

    return {
        "appointment_1": appointment_1,
        "appointment_2": appointment_2,
        "appointment_3": appointment_3,
        "appointment_4": appointment_4,
    }


@pytest.mark.parametrize(
    ["appt", "pharmacy_id", "expected_message"],
    [
        ("appointment_1", "1", None),
        ("appointment_1", "2", "Member needs to complete prescription info!"),
        ("appointment_2", "2", "Cannot set pharmacy on anonymous appointment!"),
        ("appointment_3", "2", "Practitioner not enabled!"),
        ("appointment_4", "-1", None),
        ("appointment_4", "2", None),
    ],
    ids=[
        "PharmacyID matches member Global Pharmacy",
        "Member not enabled_for_prescription",
        "Anonymous appointment",
        "Practitioner not enabled_for_prescribing",
        "Invalid pharmacy in Dosespot",
        "Valid pharmacy in Dosespot",
    ],
)
def test_check_and_set_pharmacy(test_data, appt, pharmacy_id, expected_message):
    resource = AppointmentResource()
    appt = test_data.get(appt)
    try:
        resource._check_and_set_pharmacy(appt, pharmacy_id)
    except HTTPException as e:
        assert e.data.get("message") == expected_message
        return

    assert not expected_message
