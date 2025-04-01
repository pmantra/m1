from typing import TYPE_CHECKING

from marshmallow_v1 import ValidationError

from models.profiles import State
from utils.data import normalize_phone_number, normalize_phone_number_old

if TYPE_CHECKING:
    from appointments.models.appointment import Appointment


def create_dosespot_patient_data(appointment: "Appointment") -> dict:
    HOME_PHONE_TYPE = 4
    profile = appointment.member.member_profile
    member = appointment.member
    health_profile = profile.user.health_profile
    address = profile.address
    gender_string = get_gender_string(
        health_profile.json.get("gender", "Unknown") or "Unknown"
    )
    # DoseSpot encodes gender as "Male" = 1, "Female" = 2, "Unknown" = 3
    genders = {"male": 1, "female": 2, "unknown": 3}
    gender = genders[gender_string.lower()]

    # NonDoseSpotMedicalRecordNumber not required, but acts to consolidate multiple patient records in DoseSpot
    data = {
        "FirstName": member.first_name[:35],
        "LastName": member.last_name[:35],
        "DateOfBirth": health_profile.json["birthday"],
        "Gender": gender,
        "Address1": address.street_address[:35],
        "City": address.city,
        "State": address.state,
        "ZipCode": address.zip_code,
        "PrimaryPhone": convert_phone_number(profile.phone_number),
        "PrimaryPhoneType": HOME_PHONE_TYPE,
        "Active": True,
        "NonDoseSpotMedicalRecordNumber": str(member.id)[:35],
    }

    if member.middle_name:
        data["MiddleName"] = member.middle_name[:35]

    if len(address.street_address) > 35:
        data["Address2"] = address.street_address[35:70]

    return data


def get_existing_patient_id(appointment: "Appointment") -> str:
    existing_patient_info = appointment.member.member_profile.get_patient_info(
        appointment.practitioner.id  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "id"
    )
    return existing_patient_info["patient_id"]


def get_gender_string(gender: str) -> str:
    _male = ("male", "m", "man")
    _female = ("female", "f", "woman")

    return (
        "Male"
        if gender.lower() in _male
        else "Female"
        if gender.lower() in _female
        else "Unknown"
    )


def convert_phone_number(phone_number: str) -> str:
    try:
        _, num = normalize_phone_number(phone_number, None)
        return normalize_phone_number_old(num, include_extension=False)
    except (ValidationError, TypeError):
        return ""


def is_same_state(state: State, dosespot_state: str) -> bool:
    return state is not None and (
        state.name == dosespot_state or state.abbreviation == dosespot_state
    )
