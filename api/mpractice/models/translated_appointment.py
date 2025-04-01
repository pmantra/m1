from __future__ import annotations

import dataclasses
from datetime import datetime

from geography import Country
from mpractice.models.appointment import MPracticeMember, Vertical
from mpractice.models.note import SessionMetaInfo
from mpractice.models.translated_note import (
    MPracticeProviderAddendaAndQuestionnaire,
    StructuredInternalNote,
)


@dataclasses.dataclass
class TranslatedProviderAppointment:
    id: int
    appointment_id: int
    scheduled_start: datetime
    scheduled_end: datetime
    cancelled_at: datetime | None = None
    cancellation_policy: str | None = None
    cancelled_note: str | None = None
    member_started_at: datetime | None = None
    member_ended_at: datetime | None = None
    member_disconnected_at: datetime | None = None
    practitioner_started_at: datetime | None = None
    practitioner_ended_at: datetime | None = None
    practitioner_disconnected_at: datetime | None = None
    phone_call_at: datetime | None = None
    privacy: str | None = None
    privilege_type: str | None = None
    purpose: str | None = None
    state: str | None = None
    pre_session: SessionMetaInfo | None = None
    post_session: SessionMetaInfo | None = None
    need: Need | None = None
    video: Video | None = None
    product: Product | None = None
    member: TranslatedMPracticeMember | None = None
    prescription_info: PrescriptionInfo | None = None
    rx_enabled: bool | None = None
    rx_reason: str | None = None
    rx_written_via: str | None = None
    structured_internal_note: StructuredInternalNote | None = None
    provider_addenda: MPracticeProviderAddendaAndQuestionnaire | None = None


@dataclasses.dataclass
class TranslatedProviderAppointmentForList:
    id: int
    appointment_id: int
    scheduled_start: datetime
    scheduled_end: datetime
    member: TranslatedMPracticeMember | None = None
    repeat_patient: bool | None = None
    state: str | None = None
    privacy: str | None = None
    privilege_type: str | None = None
    rescheduled_from_previous_appointment_time: datetime | None = None
    cancelled_at: datetime | None = None
    post_session: SessionMetaInfo | None = None


@dataclasses.dataclass
class MemberProfile:
    care_plan_id: int | None = None
    subdivision_code: str | None = None
    state: State | None = None
    tel_number: str | None = None


@dataclasses.dataclass
class PractitionerProfile:
    can_prescribe: bool
    messaging_enabled: bool
    certified_subdivision_codes: list[str] | None = None
    vertical_objects: list[Vertical] | None = None


@dataclasses.dataclass
class Profiles:
    member: MemberProfile | None = None
    practitioner: PractitionerProfile | None = None


@dataclasses.dataclass
class TranslatedMPracticeMember(MPracticeMember):
    name: str | None = None
    country: Country | None = None
    organization: Organization | None = None
    profiles: Profiles | None = None


@dataclasses.dataclass
class TranslatedMPracticePractitioner:
    id: int
    name: str | None = None
    profiles: Profiles | None = None
    certified_states: list[str] | None = None
    dosespot: str | None = None


@dataclasses.dataclass(frozen=True)
class Need:
    id: int
    name: str | None = None
    description: str | None = None


@dataclasses.dataclass
class Organization:
    name: str
    education_only: bool
    rx_enabled: bool | None = None


@dataclasses.dataclass
class Product:
    practitioner: TranslatedMPracticePractitioner | None = None
    vertical_id: int | None = None


@dataclasses.dataclass(frozen=True)
class State:
    abbreviation: str | None


@dataclasses.dataclass(frozen=True)
class Video:
    member_token: str | None = None
    practitioner_token: str | None = None
    session_id: str | None = None


@dataclasses.dataclass(frozen=True)
class DoseSpotPharmacyInfo:
    PharmacyId: str | None = None
    Pharmacy: str | None = None
    State: str | None = None
    ZipCode: str | None = None
    PrimaryFax: str | None = None
    StoreName: str | None = None
    Address1: str | None = None
    Address2: str | None = None
    PrimaryPhone: str | None = None
    PrimaryPhoneType: str | None = None
    City: str | None = None
    IsPreferred: bool | None = None
    IsDefault: bool | None = None
    ServiceLevel: int | None = None


@dataclasses.dataclass(frozen=True)
class PrescriptionInfo:
    enabled: bool
    pharmacy_id: str | None = None
    pharmacy_info: DoseSpotPharmacyInfo | None = None
