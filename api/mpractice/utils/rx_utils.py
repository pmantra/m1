from __future__ import annotations

import json

from appointments.models.constants import PRIVACY_CHOICES, RX_REASONS
from mpractice.models.translated_appointment import (
    DoseSpotPharmacyInfo,
    PrescriptionInfo,
    TranslatedMPracticeMember,
    TranslatedMPracticePractitioner,
)
from utils.log import logger

log = logger(__name__)


GLOBAL_PHARMACY_KEY = "global_pharmacy"


def get_prescription_info(
    member: TranslatedMPracticeMember, practitioner: TranslatedMPracticePractitioner
) -> PrescriptionInfo | None:
    if not member.dosespot:
        return None

    try:
        dosespot = json.loads(member.dosespot)
    except Exception as e:
        log.warning("Failed to parse dosespot string into json", error=e)
        return None

    full_pharmacy_info = dosespot.get(GLOBAL_PHARMACY_KEY, {})
    dosespot_keys = [key for key in dosespot.keys() if "practitioner:" in key]
    if full_pharmacy_info == {} and len(dosespot_keys) > 0:
        last_key = dosespot_keys.pop()
        full_pharmacy_info = dosespot.get(last_key, {})

    if full_pharmacy_info.get("pharmacy_info"):
        pharmacy_info = full_pharmacy_info.get("pharmacy_info")
        dosespot_pharmacy_info = DoseSpotPharmacyInfo(
            PharmacyId=pharmacy_info.get("PharmacyId"),
            Pharmacy=pharmacy_info.get("Pharmacy"),
            State=pharmacy_info.get("State"),
            ZipCode=pharmacy_info.get("ZipCode"),
            PrimaryFax=pharmacy_info.get("PrimaryFax"),
            StoreName=pharmacy_info.get("StoreName"),
            Address1=pharmacy_info.get("Address1"),
            Address2=pharmacy_info.get("Address2"),
            PrimaryPhone=pharmacy_info.get("PrimaryPhone"),
            PrimaryPhoneType=pharmacy_info.get("PrimaryPhoneType"),
            City=pharmacy_info.get("City"),
            IsPreferred=pharmacy_info.get("IsPreferred"),
            IsDefault=pharmacy_info.get("IsDefault"),
            ServiceLevel=pharmacy_info.get("ServiceLevel"),
        )
    else:
        dosespot_pharmacy_info = None

    enabled = member_enabled_for_prescription(
        member
    ) and practitioner_enabled_for_prescription(practitioner.dosespot)
    return PrescriptionInfo(
        pharmacy_id=full_pharmacy_info.get("pharmacy_id"),
        pharmacy_info=dosespot_pharmacy_info,
        enabled=enabled,
    )


def rx_enabled(
    appointment_privacy: str | None,
    member: TranslatedMPracticeMember,
    practitioner: TranslatedMPracticePractitioner,
) -> bool:
    # checks:
    # ✔ privacy is not anonymous TODO: Remove when scope of practice work is finished
    # ✔ filter by state true vertical
    # ✔ provider licensed in member state
    # ✔ provider country === USA
    # ✔ member country === USA (if there is a state, the member is in USA)
    # ✔ member not in a coaching-only org
    # ✔ member org allows RX
    # ✔ provider is set up to prescribe
    # ✔ member has first/last name and pharmacy info TODO: MPC-5074 allow this to work without this clause
    if appointment_privacy == PRIVACY_CHOICES.anonymous:
        return False
    if member.organization and (
        not member.organization.rx_enabled or member.organization.education_only
    ):
        return False
    if not member_enabled_for_prescription(member=member):
        return False
    return practitioner_can_prescribe_to_member(
        practitioner=practitioner, member=member
    )


def get_rx_reason(
    rx_enabled: bool,
    member: TranslatedMPracticeMember,
    practitioner: TranslatedMPracticePractitioner,
    prescription_info: PrescriptionInfo | None,
) -> str | None:
    if rx_enabled:
        return RX_REASONS.IS_ALLOWED.value

    if not get_prescribable_state_for_member(member):
        if practitioner_is_international(practitioner):
            return None
        else:
            return RX_REASONS.MEMBER_OUTSIDE_US.value

    if member.organization and (
        not member.organization.rx_enabled or member.organization.education_only
    ):
        return RX_REASONS.NOT_ALLOWED_BY_ORG.value

    if not practitioner_vertical_can_prescribe(practitioner):
        return RX_REASONS.CANNOT_PRESCRIBE.value

    if not practitioner_can_prescribe(practitioner):
        return RX_REASONS.NOT_SET_UP.value

    if not practitioner_can_prescribe_to_member(
        practitioner=practitioner, member=member
    ):
        return RX_REASONS.NOT_LICENSED_IN_STATE.value

    if (
        not prescription_info
        or not prescription_info.pharmacy_id
        or not prescription_info.pharmacy_info
        or not member_enabled_for_prescription(member)
    ):
        return RX_REASONS.PHARMACY_INFO_NOT_ADDED.value
    return None


def get_rx_written_via(appointment_json: str | None) -> str | None:
    if not appointment_json:
        return None
    try:
        return json.loads(appointment_json).get("rx_written_via", None)
    except Exception as e:
        log.error("Failed to load rx_written_via from appointment.json", exception=e)
        return None


def member_enabled_for_prescription(member: TranslatedMPracticeMember) -> bool:
    if not member.first_name and not member.last_name:
        return False
    if not member.address_count or member.address_count == 0:
        return False
    if not member.phone_number:
        return False
    if not member.health_profile_json or not json.loads(member.health_profile_json).get(
        "birthday"
    ):
        return False
    return True


def practitioner_enabled_for_prescription(dosespot_json: str | None) -> bool:
    if not dosespot_json:
        return False
    try:
        dosespot = json.loads(dosespot_json)
        if not dosespot.get("clinic_key"):
            return False
        if not dosespot.get("clinic_id"):
            return False
        if not dosespot.get("user_id"):
            return False
        return True
    except Exception as e:
        log.error("Failed to load dosespot from json", exception=e)
        return False


def practitioner_is_international(
    practitioner: TranslatedMPracticePractitioner,
) -> bool:
    if practitioner.certified_states:
        states = practitioner.certified_states
        return len(states) == 1 and states[0] == "ZZ"
    return False


def practitioner_can_prescribe_to_member(
    practitioner: TranslatedMPracticePractitioner, member: TranslatedMPracticeMember
) -> bool:

    prescribable_state_for_member = get_prescribable_state_for_member(member)
    return (
        practitioner_can_prescribe(practitioner)
        and prescribable_state_for_member in practitioner.certified_states
    )


def get_prescribable_state_for_member(member: TranslatedMPracticeMember) -> str | None:
    if all(
        [
            # We currently only allow prescriptions inside the US
            # We assume members are in the US if they have no country set.
            ((not member.country_code) or member.country_code == "US"),
            # ZZ is the value of "Other" in the state drop down.
            member.state_abbreviation and member.state_abbreviation != "ZZ",
        ]
    ):
        return member.state_abbreviation
    return None


def practitioner_vertical_can_prescribe(
    practitioner: TranslatedMPracticePractitioner,
) -> bool:
    can_prescribe = False
    if (
        practitioner.profiles
        and practitioner.profiles.practitioner
        and practitioner.profiles.practitioner.vertical_objects
    ):
        for vertical in practitioner.profiles.practitioner.vertical_objects:
            if vertical.can_prescribe:
                can_prescribe = True
                break
    return can_prescribe


def practitioner_can_prescribe(practitioner: TranslatedMPracticePractitioner) -> bool:
    can_prescribe = practitioner_vertical_can_prescribe(practitioner)
    return (
        can_prescribe
        and bool(practitioner.dosespot)
        and (practitioner.dosespot != "{}")
    )
