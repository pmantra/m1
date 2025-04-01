from __future__ import annotations

import json

import pytest

from appointments.models.constants import PRIVACY_CHOICES, RX_REASONS
from mpractice.models.appointment import Vertical
from mpractice.models.translated_appointment import (
    DoseSpotPharmacyInfo,
    Organization,
    PractitionerProfile,
    PrescriptionInfo,
    Profiles,
    TranslatedMPracticeMember,
    TranslatedMPracticePractitioner,
)
from mpractice.utils import rx_utils

PHARMACY_INFO = {
    "PharmacyId": "1",
    "Pharmacy": "test pharma",
    "State": "NY",
    "ZipCode": "10027",
    "PrimaryFax": "555-555-5555",
    "StoreName": "999 Pharmacy",
    "Address1": "999 999th St",
    "Address2": "",
    "PrimaryPhone": "555-555-5556",
    "PrimaryPhoneType": "Work",
    "City": "NEW YORK",
    "IsPreferred": True,
    "IsDefault": False,
    "ServiceLevel": 9,
    "PhoneAdditional1": None,
    "PhoneAdditionalType1": 0,
}

DOSESPOT_WITH_GLOBAL_PHARMACY_INFO = {
    "global_pharmacy": {
        "pharmacy_id": "1",
        "pharmacy_info": PHARMACY_INFO,
    }
}

DOSESPOT_WITHOUT_GLOBAL_PHARMACY_INFO = {
    "practitioner:1": {
        "pharmacy_id": "1",
        "pharmacy_info": PHARMACY_INFO,
    }
}


@pytest.mark.parametrize(
    argnames="dosespot_string,prescription_info",
    argvalues=[
        (None, None),
        ("{}", PrescriptionInfo(enabled=False)),
        ("invalid_json_string", None),
    ],
    ids=[
        "none_dosespot_string",
        "empty_dosespot_string",
        "invalid_dosespot_string",
    ],
)
def test_get_prescription_info_return_none_or_empty(
    dosespot_string: str | None,
    translated_mpractice_practitioner: TranslatedMPracticePractitioner,
    prescription_info: PrescriptionInfo | None,
):
    member = TranslatedMPracticeMember(id=1, dosespot=dosespot_string)
    result = rx_utils.get_prescription_info(
        member=member, practitioner=translated_mpractice_practitioner
    )
    assert result == prescription_info


@pytest.mark.parametrize(
    argnames="dosespot_string",
    argvalues=[
        DOSESPOT_WITH_GLOBAL_PHARMACY_INFO,
        DOSESPOT_WITHOUT_GLOBAL_PHARMACY_INFO,
    ],
    ids=[
        "has_global_pharmacy_info",
        "no_global_pharmacy_info",
    ],
)
def test_get_prescription_info_when_enabled_is_false(
    dosespot_string: str,
    translated_mpractice_practitioner: TranslatedMPracticePractitioner,
    prescription_info_not_enabled: PrescriptionInfo,
):
    member = TranslatedMPracticeMember(id=1, dosespot=json.dumps(dosespot_string))
    result = rx_utils.get_prescription_info(
        member=member, practitioner=translated_mpractice_practitioner
    )
    assert result == prescription_info_not_enabled


@pytest.mark.parametrize(
    argnames="dosespot_string",
    argvalues=[
        DOSESPOT_WITH_GLOBAL_PHARMACY_INFO,
        DOSESPOT_WITHOUT_GLOBAL_PHARMACY_INFO,
    ],
    ids=[
        "has_global_pharmacy_info",
        "no_global_pharmacy_info",
    ],
)
def test_get_prescription_info_when_enabled_is_true(
    dosespot_string: str,
    translated_mpractice_member: TranslatedMPracticeMember,
    translated_mpractice_practitioner: TranslatedMPracticePractitioner,
    prescription_info_enabled: PrescriptionInfo,
):
    translated_mpractice_member.dosespot = json.dumps(dosespot_string)
    translated_mpractice_member.address_count = 1
    translated_mpractice_member.health_profile_json = json.dumps(
        {"birthday": "1999-01-01"}
    )
    translated_mpractice_practitioner.dosespot = json.dumps(
        {"clinic_key": "abc", "clinic_id": 123, "user_id": 456}
    )
    result = rx_utils.get_prescription_info(
        member=translated_mpractice_member,
        practitioner=translated_mpractice_practitioner,
    )
    assert result == prescription_info_enabled


@pytest.mark.parametrize(
    argnames="appointment_privacy,member,practitioner,rx_enabled",
    argvalues=[
        (
            PRIVACY_CHOICES.anonymous,
            TranslatedMPracticeMember(id=1),
            TranslatedMPracticePractitioner(
                id=2,
                profiles=Profiles(
                    practitioner=PractitionerProfile(
                        can_prescribe=True,
                        messaging_enabled=True,
                        vertical_objects=[
                            Vertical(
                                id=1,
                                name="test vertical",
                                can_prescribe=True,
                                filter_by_state=True,
                            )
                        ],
                    ),
                ),
                certified_states=["NY"],
                dosespot=json.dumps(DOSESPOT_WITH_GLOBAL_PHARMACY_INFO),
            ),
            False,
        ),
        (
            PRIVACY_CHOICES.basic,
            TranslatedMPracticeMember(id=1),
            TranslatedMPracticePractitioner(
                id=2,
                profiles=Profiles(
                    practitioner=PractitionerProfile(
                        can_prescribe=True,
                        messaging_enabled=True,
                        vertical_objects=[
                            Vertical(
                                id=1,
                                name="test vertical",
                                can_prescribe=True,
                                filter_by_state=True,
                            )
                        ],
                    ),
                ),
                certified_states=["NY"],
                dosespot=json.dumps(DOSESPOT_WITH_GLOBAL_PHARMACY_INFO),
            ),
            False,
        ),
        (
            PRIVACY_CHOICES.basic,
            TranslatedMPracticeMember(
                id=1,
                organization_rx_enabled=True,
                organization_education_only=False,
                country_code="US",
                state_abbreviation="CA",
                first_name="Alice",
                last_name="Johnson",
                address_count=1,
                phone_number="+12125551515",
                health_profile_json=json.dumps({"birthday": "2000-01-01"}),
            ),
            TranslatedMPracticePractitioner(
                id=2,
                profiles=Profiles(
                    practitioner=PractitionerProfile(
                        can_prescribe=True,
                        messaging_enabled=True,
                        vertical_objects=[
                            Vertical(
                                id=1,
                                name="test vertical",
                                can_prescribe=True,
                                filter_by_state=True,
                            )
                        ],
                    ),
                ),
                certified_states=["NY"],
                dosespot=json.dumps(DOSESPOT_WITH_GLOBAL_PHARMACY_INFO),
            ),
            False,
        ),
        (
            PRIVACY_CHOICES.basic,
            TranslatedMPracticeMember(
                id=1,
                organization_rx_enabled=True,
                organization_education_only=False,
                country_code="US",
                state_abbreviation="NY",
                first_name="Alice",
                last_name="Johnson",
                address_count=1,
                phone_number="+12125551515",
                health_profile_json=json.dumps({"birthday": "2000-01-01"}),
            ),
            TranslatedMPracticePractitioner(
                id=2,
                profiles=Profiles(
                    practitioner=PractitionerProfile(
                        can_prescribe=True,
                        messaging_enabled=True,
                        vertical_objects=[
                            Vertical(
                                id=1,
                                name="test vertical",
                                can_prescribe=True,
                                filter_by_state=True,
                            )
                        ],
                    ),
                ),
                certified_states=["NY"],
                dosespot=json.dumps(DOSESPOT_WITH_GLOBAL_PHARMACY_INFO),
            ),
            True,
        ),
    ],
    ids=[
        "rx_not_enabled_due_to_anonymous_appointment",
        "rx_not_enabled_due_to_member_not_enabled_for_prescription",
        "rx_not_enabled_due_to_practitioner_cannot_prescribe_to_member",
        "rx_is_enabled",
    ],
)
def test_rx_enabled(
    appointment_privacy: str | None,
    member: TranslatedMPracticeMember,
    practitioner: TranslatedMPracticePractitioner,
    rx_enabled: bool,
):
    result = rx_utils.rx_enabled(
        appointment_privacy=appointment_privacy,
        member=member,
        practitioner=practitioner,
    )
    assert result is rx_enabled


@pytest.mark.parametrize(
    argnames="rx_enabled,member,practitioner,prescription_info,rx_reason",
    argvalues=[
        (
            True,
            TranslatedMPracticeMember(id=1),
            TranslatedMPracticePractitioner(
                id=2,
            ),
            None,
            RX_REASONS.IS_ALLOWED.value,
        ),
        (
            False,
            TranslatedMPracticeMember(
                id=1,
                country_code="ZZ",
            ),
            TranslatedMPracticePractitioner(
                id=2,
                certified_states=["NY"],
            ),
            None,
            RX_REASONS.MEMBER_OUTSIDE_US.value,
        ),
        (
            False,
            TranslatedMPracticeMember(
                id=1,
                state_abbreviation="ZZ",
            ),
            TranslatedMPracticePractitioner(
                id=2,
                certified_states=["NY"],
            ),
            None,
            RX_REASONS.MEMBER_OUTSIDE_US.value,
        ),
        (
            False,
            TranslatedMPracticeMember(
                id=1,
                state_abbreviation="ZZ",
            ),
            TranslatedMPracticePractitioner(
                id=2,
                certified_states=["ZZ"],
            ),
            None,
            None,
        ),
        (
            False,
            TranslatedMPracticeMember(
                id=1,
                organization=Organization(
                    name="test org", rx_enabled=False, education_only=True
                ),
                country_code="US",
                state_abbreviation="NY",
            ),
            TranslatedMPracticePractitioner(
                id=2,
                profiles=Profiles(
                    practitioner=PractitionerProfile(
                        can_prescribe=True,
                        messaging_enabled=True,
                        vertical_objects=[
                            Vertical(
                                id=1,
                                name="test vertical",
                                can_prescribe=True,
                                filter_by_state=True,
                            )
                        ],
                    ),
                ),
                certified_states=["NY"],
                dosespot=json.dumps(DOSESPOT_WITH_GLOBAL_PHARMACY_INFO),
            ),
            None,
            RX_REASONS.NOT_ALLOWED_BY_ORG.value,
        ),
        (
            False,
            TranslatedMPracticeMember(
                id=1,
                organization=Organization(
                    name="test org", rx_enabled=True, education_only=True
                ),
                country_code="US",
                state_abbreviation="NY",
            ),
            TranslatedMPracticePractitioner(
                id=2,
                profiles=Profiles(
                    practitioner=PractitionerProfile(
                        can_prescribe=True,
                        messaging_enabled=True,
                        vertical_objects=[
                            Vertical(
                                id=1,
                                name="test vertical",
                                can_prescribe=True,
                                filter_by_state=True,
                            )
                        ],
                    ),
                ),
                certified_states=["NY"],
                dosespot=json.dumps(DOSESPOT_WITH_GLOBAL_PHARMACY_INFO),
            ),
            None,
            RX_REASONS.NOT_ALLOWED_BY_ORG.value,
        ),
        (
            False,
            TranslatedMPracticeMember(
                id=1,
                organization=Organization(
                    name="test org", rx_enabled=True, education_only=False
                ),
                first_name="Alice",
                last_name="Johnson",
                address_count=1,
                phone_number="+12125551515",
                health_profile_json=json.dumps({"birthday": "2000-01-01"}),
                country_code="US",
                state_abbreviation="NY",
            ),
            TranslatedMPracticePractitioner(
                id=2,
                profiles=Profiles(
                    practitioner=PractitionerProfile(
                        can_prescribe=True,
                        messaging_enabled=True,
                        vertical_objects=[
                            Vertical(
                                id=1,
                                name="test vertical",
                                can_prescribe=False,
                                filter_by_state=True,
                            )
                        ],
                    ),
                ),
                certified_states=["NY"],
                dosespot=json.dumps(DOSESPOT_WITH_GLOBAL_PHARMACY_INFO),
            ),
            PrescriptionInfo(
                pharmacy_id="123",
                pharmacy_info=DoseSpotPharmacyInfo(Pharmacy="test pharmacy"),
                enabled=True,
            ),
            RX_REASONS.CANNOT_PRESCRIBE.value,
        ),
        (
            False,
            TranslatedMPracticeMember(
                id=1,
                organization=Organization(
                    name="test org", rx_enabled=True, education_only=False
                ),
                first_name="Alice",
                last_name="Johnson",
                address_count=1,
                phone_number="+12125551515",
                health_profile_json=json.dumps({"birthday": "2000-01-01"}),
                country_code="US",
                state_abbreviation="NY",
            ),
            TranslatedMPracticePractitioner(
                id=2,
                profiles=Profiles(
                    practitioner=PractitionerProfile(
                        can_prescribe=True,
                        messaging_enabled=True,
                        vertical_objects=[
                            Vertical(
                                id=1,
                                name="test vertical",
                                can_prescribe=True,
                                filter_by_state=True,
                            )
                        ],
                    ),
                ),
                certified_states=["NY"],
                dosespot=None,
            ),
            PrescriptionInfo(
                pharmacy_id="123",
                pharmacy_info=DoseSpotPharmacyInfo(Pharmacy="test pharmacy"),
                enabled=True,
            ),
            RX_REASONS.NOT_SET_UP.value,
        ),
        (
            False,
            TranslatedMPracticeMember(
                id=1,
                organization=Organization(
                    name="test org", rx_enabled=True, education_only=False
                ),
                first_name="Alice",
                last_name="Johnson",
                address_count=1,
                phone_number="+12125551515",
                health_profile_json=json.dumps({"birthday": "2000-01-01"}),
                country_code="US",
                state_abbreviation="NY",
            ),
            TranslatedMPracticePractitioner(
                id=2,
                profiles=Profiles(
                    practitioner=PractitionerProfile(
                        can_prescribe=True,
                        messaging_enabled=True,
                        vertical_objects=[
                            Vertical(
                                id=1,
                                name="test vertical",
                                can_prescribe=True,
                                filter_by_state=True,
                            )
                        ],
                    ),
                ),
                certified_states=["NY"],
                dosespot="{}",
            ),
            PrescriptionInfo(
                pharmacy_id="123",
                pharmacy_info=DoseSpotPharmacyInfo(Pharmacy="test pharmacy"),
                enabled=True,
            ),
            RX_REASONS.NOT_SET_UP.value,
        ),
        (
            False,
            TranslatedMPracticeMember(
                id=1,
                organization=Organization(
                    name="test org", rx_enabled=True, education_only=False
                ),
                country_code="US",
                state_abbreviation="NY",
            ),
            TranslatedMPracticePractitioner(
                id=2,
                profiles=Profiles(
                    practitioner=PractitionerProfile(
                        can_prescribe=True,
                        messaging_enabled=True,
                        vertical_objects=[
                            Vertical(
                                id=1,
                                name="test vertical",
                                can_prescribe=True,
                                filter_by_state=True,
                            )
                        ],
                    ),
                ),
                certified_states=["NY"],
                dosespot=json.dumps(DOSESPOT_WITH_GLOBAL_PHARMACY_INFO),
            ),
            None,
            RX_REASONS.PHARMACY_INFO_NOT_ADDED.value,
        ),
        (
            False,
            TranslatedMPracticeMember(
                id=1,
                organization=Organization(
                    name="test org", rx_enabled=True, education_only=False
                ),
                country_code="US",
                state_abbreviation="NY",
            ),
            TranslatedMPracticePractitioner(
                id=2,
                profiles=Profiles(
                    practitioner=PractitionerProfile(
                        can_prescribe=True,
                        messaging_enabled=True,
                        vertical_objects=[
                            Vertical(
                                id=1,
                                name="test vertical",
                                can_prescribe=True,
                                filter_by_state=True,
                            )
                        ],
                    ),
                ),
                certified_states=["NY"],
                dosespot=json.dumps(DOSESPOT_WITH_GLOBAL_PHARMACY_INFO),
            ),
            PrescriptionInfo(enabled=False),
            RX_REASONS.PHARMACY_INFO_NOT_ADDED.value,
        ),
        (
            False,
            TranslatedMPracticeMember(
                id=1,
                organization=Organization(
                    name="test org", rx_enabled=True, education_only=False
                ),
                country_code="US",
                state_abbreviation="NY",
            ),
            TranslatedMPracticePractitioner(
                id=2,
                profiles=Profiles(
                    practitioner=PractitionerProfile(
                        can_prescribe=True,
                        messaging_enabled=True,
                        vertical_objects=[
                            Vertical(
                                id=1,
                                name="test vertical",
                                can_prescribe=True,
                                filter_by_state=True,
                            )
                        ],
                    ),
                ),
                certified_states=["NY"],
                dosespot=json.dumps(DOSESPOT_WITH_GLOBAL_PHARMACY_INFO),
            ),
            PrescriptionInfo(pharmacy_id="123", enabled=False),
            RX_REASONS.PHARMACY_INFO_NOT_ADDED.value,
        ),
        (
            False,
            TranslatedMPracticeMember(
                id=1,
                organization=Organization(
                    name="test org", rx_enabled=True, education_only=False
                ),
                country_code="US",
                state_abbreviation="NY",
            ),
            TranslatedMPracticePractitioner(
                id=2,
                profiles=Profiles(
                    practitioner=PractitionerProfile(
                        can_prescribe=True,
                        messaging_enabled=True,
                        vertical_objects=[
                            Vertical(
                                id=1,
                                name="test vertical",
                                can_prescribe=True,
                                filter_by_state=True,
                            )
                        ],
                    ),
                ),
                certified_states=["NY"],
                dosespot=json.dumps(DOSESPOT_WITH_GLOBAL_PHARMACY_INFO),
            ),
            PrescriptionInfo(
                pharmacy_id="123",
                pharmacy_info=DoseSpotPharmacyInfo(Pharmacy="test pharmacy"),
                enabled=True,
            ),
            RX_REASONS.PHARMACY_INFO_NOT_ADDED.value,
        ),
        (
            False,
            TranslatedMPracticeMember(
                id=1,
                organization=Organization(
                    name="test org", rx_enabled=True, education_only=False
                ),
                first_name="Alice",
                last_name="Johnson",
                address_count=1,
                phone_number="+12125551515",
                health_profile_json=json.dumps({"birthday": "2000-01-01"}),
                state_abbreviation="NY",
            ),
            TranslatedMPracticePractitioner(
                id=2,
                profiles=Profiles(
                    practitioner=PractitionerProfile(
                        can_prescribe=True,
                        messaging_enabled=True,
                        vertical_objects=[
                            Vertical(
                                id=1,
                                name="test vertical",
                                can_prescribe=True,
                                filter_by_state=True,
                            )
                        ],
                    ),
                ),
                certified_states=["CA"],
                dosespot=json.dumps(DOSESPOT_WITH_GLOBAL_PHARMACY_INFO),
            ),
            PrescriptionInfo(
                pharmacy_id="123",
                pharmacy_info=DoseSpotPharmacyInfo(Pharmacy="test pharmacy"),
                enabled=True,
            ),
            RX_REASONS.NOT_LICENSED_IN_STATE.value,
        ),
        (
            False,
            TranslatedMPracticeMember(
                id=1,
                organization=Organization(
                    name="test org", rx_enabled=True, education_only=False
                ),
                first_name="Alice",
                last_name="Johnson",
                address_count=1,
                phone_number="+12125551515",
                health_profile_json=json.dumps({"birthday": "2000-01-01"}),
                country_code="US",
                state_abbreviation="NY",
            ),
            TranslatedMPracticePractitioner(
                id=2,
                profiles=Profiles(
                    practitioner=PractitionerProfile(
                        can_prescribe=True,
                        messaging_enabled=True,
                        vertical_objects=[
                            Vertical(
                                id=1,
                                name="test vertical",
                                can_prescribe=True,
                                filter_by_state=True,
                            )
                        ],
                    ),
                ),
                certified_states=["NY"],
                dosespot=json.dumps(DOSESPOT_WITH_GLOBAL_PHARMACY_INFO),
            ),
            PrescriptionInfo(
                pharmacy_id="123",
                pharmacy_info=DoseSpotPharmacyInfo(Pharmacy="test pharmacy"),
                enabled=True,
            ),
            None,
        ),
    ],
    ids=[
        "is_allowed",
        "member_not_in_us",
        "member_state_not_in_us",
        "member_and_practitioner_outside_us",
        "not_allowed_by_org_due_to_org_not_rx_enabled",
        "not_allowed_by_org_due_to_org_edu_only",
        "provider_vertical_cannot_prescribe",
        "provider_no_dosespot_info",
        "provider_empty_dosespot_info",
        "pharmacy_info_not_added_due_to_no_prescription_info",
        "pharmacy_info_not_added_due_to_no_pharmacy_id",
        "pharmacy_info_not_added_due_to_no_pharmacy_info",
        "pharmacy_info_not_added_due_to_member_not_enabled_for_prescription",
        "practitioner_not_licensed",
        "none",
    ],
)
def test_get_rx_reason(
    rx_enabled: bool,
    member: TranslatedMPracticeMember,
    practitioner: TranslatedMPracticePractitioner,
    prescription_info: PrescriptionInfo | None,
    rx_reason: str | None,
):
    result = rx_utils.get_rx_reason(
        rx_enabled=rx_enabled,
        member=member,
        practitioner=practitioner,
        prescription_info=prescription_info,
    )
    assert result == rx_reason


@pytest.mark.parametrize(
    argnames="appointment_json,rx_written_via",
    argvalues=[
        (None, None),
        ("{}", None),
        ("abcd", None),
        ('{"rx_written_via": "dosespot"}', "dosespot"),
    ],
    ids=["none_json", "empty_json", "invalid_json", "valid_non_empty_json"],
)
def test_get_rx_written_via(appointment_json: str | None, rx_written_via: str | None):
    result = rx_utils.get_rx_written_via(appointment_json)
    assert result == rx_written_via


@pytest.mark.parametrize(
    argnames="member,enabled_for_prescription",
    argvalues=[
        (
            TranslatedMPracticeMember(
                id=1,
                first_name="Alice",
                last_name="Johnson",
                address_count=1,
                phone_number="+12125551515",
                health_profile_json=json.dumps({"birthday": "2000-01-01"}),
            ),
            True,
        ),
        (
            TranslatedMPracticeMember(
                id=1,
                address_count=1,
                phone_number="+12125551515",
                health_profile_json=json.dumps({"birthday": "2000-01-01"}),
            ),
            False,
        ),
        (
            TranslatedMPracticeMember(
                id=1,
                first_name="Alice",
                last_name="Johnson",
                phone_number="+12125551515",
                health_profile_json=json.dumps({"birthday": "2000-01-01"}),
            ),
            False,
        ),
        (
            TranslatedMPracticeMember(
                id=1,
                first_name="Alice",
                last_name="Johnson",
                address_count=0,
                phone_number="+12125551515",
                health_profile_json=json.dumps({"birthday": "2000-01-01"}),
            ),
            False,
        ),
        (
            TranslatedMPracticeMember(
                id=1,
                first_name="Alice",
                last_name="Johnson",
                address_count=1,
                health_profile_json=json.dumps({"birthday": "2000-01-01"}),
            ),
            False,
        ),
        (
            TranslatedMPracticeMember(
                id=1,
                first_name="Alice",
                last_name="Johnson",
                address_count=1,
                phone_number="+12125551515",
            ),
            False,
        ),
        (
            TranslatedMPracticeMember(
                id=1,
                first_name="Alice",
                last_name="Johnson",
                address_count=1,
                phone_number="+12125551515",
                health_profile_json="{}",
            ),
            False,
        ),
    ],
    ids=[
        "enabled_for_prescription",
        "not_enabled_for_prescription_due_to_missing_name",
        "not_enabled_for_prescription_due_to_missing_address_count",
        "not_enabled_for_prescription_due_to_zero_address_count",
        "not_enabled_for_prescription_due_to_missing_phone_number",
        "not_enabled_for_prescription_due_to_missing_health_profile",
        "not_enabled_for_prescription_due_to_no_birthday_in_health_profile",
    ],
)
def test_member_enabled_for_prescription(
    member: TranslatedMPracticeMember, enabled_for_prescription: bool
):
    assert rx_utils.member_enabled_for_prescription(member) is enabled_for_prescription


@pytest.mark.parametrize(
    argnames="dosespot,enabled_for_prescription",
    argvalues=[
        (None, False),
        ("abc", False),
        ("{}", False),
        ('{"clinic_id": 123, "user_id": 456}', False),
        ('{"clinic_key": "xyz", "user_id": 456}', False),
        ('{"clinic_key": "xyz", "clinic_id": 123}', False),
        ('{"clinic_key": "xyz", "clinic_id": 123, "user_id": 456}', True),
    ],
    ids=[
        "none_dosespot",
        "invalid_dosespot",
        "empty_dosespot",
        "no_clinic_key",
        "no_clinic_id",
        "no_user_id",
        "enabled_for_prescription",
    ],
)
def test_practitioner_enabled_for_prescription(
    dosespot: str | None, enabled_for_prescription: bool
):
    assert (
        rx_utils.practitioner_enabled_for_prescription(dosespot)
        == enabled_for_prescription
    )


@pytest.mark.parametrize(
    argnames="practitioner,member,can_prescribe",
    argvalues=[
        (
            TranslatedMPracticePractitioner(
                id=1,
                profiles=Profiles(
                    practitioner=PractitionerProfile(
                        can_prescribe=True,
                        messaging_enabled=True,
                        vertical_objects=[
                            Vertical(
                                id=1,
                                name="test vertical",
                                can_prescribe=True,
                                filter_by_state=True,
                            )
                        ],
                    ),
                ),
                certified_states=["NY"],
                dosespot=json.dumps(DOSESPOT_WITH_GLOBAL_PHARMACY_INFO),
            ),
            TranslatedMPracticeMember(
                id=2,
                organization_rx_enabled=True,
                organization_education_only=False,
                country_code="US",
                state_abbreviation="NY",
            ),
            True,
        ),
        (
            TranslatedMPracticePractitioner(
                id=1,
                profiles=Profiles(
                    practitioner=PractitionerProfile(
                        can_prescribe=True,
                        messaging_enabled=True,
                        vertical_objects=[
                            Vertical(
                                id=1,
                                name="test vertical",
                                can_prescribe=True,
                                filter_by_state=True,
                            )
                        ],
                    ),
                ),
                certified_states=["NY"],
                dosespot=json.dumps(DOSESPOT_WITH_GLOBAL_PHARMACY_INFO),
            ),
            TranslatedMPracticeMember(
                id=2,
                organization_rx_enabled=True,
                organization_education_only=False,
                country_code="US",
                state_abbreviation="CA",
            ),
            False,
        ),
    ],
    ids=["can_prescribe", "cannot_prescribe_due_to_state_mismatch"],
)
def test_practitioner_can_prescribe_to_member(
    practitioner: TranslatedMPracticePractitioner,
    member: TranslatedMPracticeMember,
    can_prescribe: bool,
):
    assert (
        rx_utils.practitioner_can_prescribe_to_member(
            practitioner=practitioner, member=member
        )
        is can_prescribe
    )


@pytest.mark.parametrize(
    argnames="member,prescribable_state",
    argvalues=[
        (
            TranslatedMPracticeMember(
                id=1,
                country_code="US",
                state_abbreviation="NY",
            ),
            "NY",
        ),
        (
            TranslatedMPracticeMember(
                id=1,
                country_code="UK",
                state_abbreviation="NY",
            ),
            None,
        ),
        (
            TranslatedMPracticeMember(
                id=1,
                country_code="US",
                state_abbreviation="ZZ",
            ),
            None,
        ),
    ],
    ids=[
        "state_is_prescribable",
        "no_prescribable_state_due_to_non_us_country_code",
        "no_prescribable_state_due_to_other_state_code",
    ],
)
def test_get_prescribable_state_for_member(
    member: TranslatedMPracticeMember, prescribable_state: str | None
):
    assert rx_utils.get_prescribable_state_for_member(member) == prescribable_state


@pytest.mark.parametrize(
    argnames="practitioner,can_prescribe",
    argvalues=[
        (
            TranslatedMPracticePractitioner(
                id=1,
                profiles=Profiles(
                    practitioner=PractitionerProfile(
                        can_prescribe=True,
                        messaging_enabled=True,
                        vertical_objects=[
                            Vertical(
                                id=1,
                                name="test vertical",
                                can_prescribe=True,
                                filter_by_state=True,
                            )
                        ],
                    ),
                ),
                dosespot=json.dumps(DOSESPOT_WITH_GLOBAL_PHARMACY_INFO),
            ),
            True,
        ),
        (
            TranslatedMPracticePractitioner(
                id=1,
                profiles=Profiles(
                    practitioner=PractitionerProfile(
                        can_prescribe=True,
                        messaging_enabled=True,
                        vertical_objects=[
                            Vertical(
                                id=1,
                                name="test vertical",
                                can_prescribe=False,
                                filter_by_state=True,
                            )
                        ],
                    ),
                ),
                dosespot=json.dumps(DOSESPOT_WITH_GLOBAL_PHARMACY_INFO),
            ),
            False,
        ),
        (
            TranslatedMPracticePractitioner(
                id=1,
                profiles=Profiles(
                    practitioner=PractitionerProfile(
                        can_prescribe=True,
                        messaging_enabled=True,
                        vertical_objects=[
                            Vertical(
                                id=1,
                                name="test vertical",
                                can_prescribe=True,
                                filter_by_state=True,
                            )
                        ],
                    ),
                ),
                dosespot="{}",
            ),
            False,
        ),
    ],
    ids=[
        "can_prescribe",
        "cannot_prescribe_due_to_vertical",
        "cannot_prescribe_due_to_dosespot",
    ],
)
def test_practitioner_can_prescribe(
    practitioner: TranslatedMPracticePractitioner, can_prescribe: bool
):
    assert rx_utils.practitioner_can_prescribe(practitioner) is can_prescribe
