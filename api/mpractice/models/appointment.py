from __future__ import annotations

import dataclasses
from datetime import datetime


@dataclasses.dataclass
class MPracticeMember:
    id: int
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    created_at: datetime | None = None

    health_profile_json: str | None = None
    care_plan_id: int | None = None
    dosespot: str | None = None
    phone_number: str | None = None
    subdivision_code: str | None = None

    state_name: str | None = None
    state_abbreviation: str | None = None
    country_code: str | None = None

    organization_name: str | None = None
    organization_education_only: bool | None = None
    organization_rx_enabled: bool | None = None

    address_count: int | None = None


@dataclasses.dataclass
class MPracticePractitioner:
    id: int
    messaging_enabled: bool
    first_name: str | None = None
    last_name: str | None = None
    country_code: str | None = None
    dosespot: str | None = None


@dataclasses.dataclass
class ProviderAppointment:
    id: int
    scheduled_start: datetime
    scheduled_end: datetime
    practitioner_id: int
    member_id: int
    vertical_id: int

    privacy: str | None = None
    privilege_type: str | None = None
    purpose: str | None = None
    json: str | None = None
    video: str | None = None
    cancelled_at: datetime | None = None
    cancellation_policy_name: str | None = None
    disputed_at: datetime | None = None
    member_started_at: datetime | None = None
    member_ended_at: datetime | None = None
    practitioner_started_at: datetime | None = None
    practitioner_ended_at: datetime | None = None
    phone_call_at: datetime | None = None

    client_notes: str | None = None

    need_id: int | None = None
    need_name: str | None = None
    need_description: str | None = None


@dataclasses.dataclass
class ProviderAppointmentForList:
    id: int
    scheduled_start: datetime
    scheduled_end: datetime
    member_id: int
    practitioner_id: int

    member_first_name: str | None = None
    member_last_name: str | None = None
    member_country_code: str | None = None
    privacy: str | None = None
    privilege_type: str | None = None
    cancelled_at: datetime | None = None
    disputed_at: datetime | None = None
    member_started_at: datetime | None = None
    member_ended_at: datetime | None = None
    practitioner_started_at: datetime | None = None
    practitioner_ended_at: datetime | None = None
    json: str | None = None
    rescheduled_from_previous_appointment_time: datetime | None = None
    repeat_patient_appointment_count: int | None = None

    credit_latest_used_at: datetime | None = None
    total_used_credits: float | None = None
    fees_count: int | None = None
    payment_amount: float | None = None
    payment_captured_at: datetime | None = None


@dataclasses.dataclass(frozen=True)
class TransactionInfo:
    credit_latest_used_at: datetime | None = None
    total_used_credits: float | None = None
    fees_count: int | None = None
    payment_amount: float | None = None
    payment_captured_at: datetime | None = None


@dataclasses.dataclass
class Vertical:
    id: int
    name: str
    can_prescribe: bool
    filter_by_state: bool
