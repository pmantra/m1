from __future__ import annotations

import dataclasses
import datetime
import enum
from typing import Optional

from models.enterprise import MatchType

__all__ = (
    "EligibilityMember",
    "DateRange",
    "WalletEnablement",
    "EligibilityVerification",
    "PreEligibilityResponse",
    "PreEligibilityOrganization",
    "EligibilityVerificationAttempt",
)


@dataclasses.dataclass
class EligibilityMember:
    id: int
    organization_id: int
    file_id: Optional[int]
    first_name: str
    last_name: str
    date_of_birth: datetime.date
    created_at: datetime.datetime
    updated_at: datetime.datetime
    record: dict
    custom_attributes: dict
    work_state: Optional[str] = None
    work_country: Optional[str] = None
    email: str = ""
    unique_corp_id: str = ""
    dependent_id: str = ""
    employer_assigned_id: str = ""
    effective_range: Optional[DateRange] = None
    is_v2: bool | None = False
    member_1_id: int | None = None
    member_2_id: int | None = None
    member_2_version: int | None = None


@dataclasses.dataclass
class DateRange:
    lower: Optional[datetime.date] = None
    upper: Optional[datetime.date] = None
    lower_inc: Optional[bool] = None
    upper_inc: Optional[bool] = None


@dataclasses.dataclass
class WalletEnablement:
    member_id: int
    organization_id: int
    enabled: bool
    insurance_plan: Optional[str] = None
    start_date: Optional[datetime.date] = None
    eligibility_date: Optional[datetime.date] = None
    eligibility_end_date: Optional[datetime.date] = None
    created_at: Optional[datetime.datetime] = None
    updated_at: Optional[datetime.datetime] = None


""" Note: please ensure you cycle the redis cache for eligibility verifications if the structure of EligibilityVerification is changed. Otherwise, incorrectly structured reponses will be returned"""


@dataclasses.dataclass
class EligibilityVerification:
    user_id: int
    organization_id: int
    unique_corp_id: str
    dependent_id: str
    first_name: str
    last_name: str
    date_of_birth: datetime.date
    email: str
    record: dict
    verified_at: datetime.datetime
    created_at: datetime.datetime
    verification_type: str
    is_active: bool
    work_state: str | None = None
    verification_id: int | None = None
    deactivated_at: datetime.datetime | None = None
    eligibility_member_id: int | None = None
    employer_assigned_id: str | None = None
    effective_range: Optional[DateRange] = None
    additional_fields: dict | None = None
    verification_session: str | None = None
    is_v2: bool | None = False
    verification_1_id: int | None = None
    verification_2_id: int | None = None
    eligibility_member_2_id: int | None = None
    eligibility_member_2_version: int | None = None


@dataclasses.dataclass
class EligibilityVerificationAttempt:
    user_id: int
    organization_id: int
    unique_corp_id: str
    dependent_id: str
    first_name: str
    last_name: str
    date_of_birth: datetime.date
    email: str
    work_state: str
    policy_used: str
    verified_at: datetime.datetime
    created_at: datetime.datetime
    verification_type: str
    successful_verification: bool
    id: int
    eligibility_member_id: int | None = None
    additional_fields: dict | None = None


@dataclasses.dataclass
class EligibilityTestMemberRecord:
    first_name: str
    last_name: str
    date_of_birth: datetime.date
    email: str
    effective_range: DateRange
    work_state: str
    work_country: str
    dependent_id: str
    unique_corp_id: str


@dataclasses.dataclass
class VerificationData:
    eligibility_member_id: Optional[int]
    organization_id: int
    unique_corp_id: str
    dependent_id: str
    email: str
    work_state: Optional[str]
    additional_fields: str


class EligibilitySource(str, enum.Enum):
    ORG_EMPLOYEE = "org_employee"
    ELIGIBILITY = "eligibility"


@dataclasses.dataclass
class PreEligibilityResponse:
    __slots__ = ("match_type", "pre_eligibility_organizations")

    match_type: MatchType
    pre_eligibility_organizations: list[PreEligibilityOrganization]


@dataclasses.dataclass
class PreEligibilityOrganization:
    __slots__ = ("organization_id", "eligibility_end_date")

    organization_id: int
    eligibility_end_date: datetime.datetime


@dataclasses.dataclass
class EligibleFeaturesForUserResponse:
    __slots__ = ("features", "has_population")
    features: list[int]
    has_population: bool


@dataclasses.dataclass
class EligibleFeaturesForUserAndOrgResponse:
    __slots__ = ("features", "has_population")
    features: list[int]
    has_population: bool


@dataclasses.dataclass
class EligibleFeaturesBySubPopulationIdResponse:
    __slots__ = ("features", "has_definition")
    features: list[int]
    has_definition: bool


class FeatureTypes(enum.IntEnum):
    TRACK_FEATURE = 1
    WALLET_FEATURE = 2
