from http import HTTPStatus

from appointments.models.constants import PRIVACY_CHOICES, AppointmentTypes
from models.common import PrivilegeType


def test_get_appointment_type_anonymous(
    basic_appointment, get_appointment_from_endpoint_using_appointment
):
    basic_appointment.privilege_type = PrivilegeType.ANONYMOUS
    response = get_appointment_from_endpoint_using_appointment(basic_appointment)
    _assert_valid_appointment_type(response, AppointmentTypes.ANONYMOUS)

    basic_appointment.privilege_type = PrivilegeType.INTERNATIONAL
    basic_appointment.privacy = PRIVACY_CHOICES.anonymous
    response = get_appointment_from_endpoint_using_appointment(basic_appointment)
    _assert_valid_appointment_type(response, AppointmentTypes.ANONYMOUS)


def test_get_appointment_type_education_only(
    basic_appointment, get_appointment_from_endpoint_using_appointment
):
    basic_appointment.privilege_type = PrivilegeType.EDUCATION_ONLY
    response = get_appointment_from_endpoint_using_appointment(basic_appointment)
    _assert_valid_appointment_type(response, AppointmentTypes.EDUCATION_ONLY)

    basic_appointment.privilege_type = PrivilegeType.INTERNATIONAL
    basic_appointment.privacy = PRIVACY_CHOICES.basic
    response = get_appointment_from_endpoint_using_appointment(basic_appointment)
    _assert_valid_appointment_type(response, AppointmentTypes.EDUCATION_ONLY)

    basic_appointment.privacy = PRIVACY_CHOICES.full_access
    response = get_appointment_from_endpoint_using_appointment(basic_appointment)
    _assert_valid_appointment_type(response, AppointmentTypes.EDUCATION_ONLY)


def test_get_appointment_type_standard(
    basic_appointment, get_appointment_from_endpoint_using_appointment
):
    basic_appointment.privilege_type = PrivilegeType.STANDARD
    response = get_appointment_from_endpoint_using_appointment(basic_appointment)

    _assert_valid_appointment_type(response, AppointmentTypes.STANDARD)


def _assert_valid_appointment_type(response, expected_appointment_type):
    assert response.status_code == HTTPStatus.OK
    assert response.json["appointment_type"]
    assert response.json["appointment_type"] == expected_appointment_type
