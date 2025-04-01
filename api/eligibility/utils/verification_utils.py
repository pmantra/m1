from __future__ import annotations

import dataclasses
import datetime
from enum import Enum
from typing import Literal, Set

from maven.feature_flags import bool_variation, json_variation

from eligibility.utils import feature_flags


# region verification parameter
@dataclasses.dataclass(frozen=True)
class VerificationParams:
    user_id: int
    verification_type: VerificationTypeT | None = None
    organization_id: int | None = None
    is_employee: bool | None = None
    date_of_birth: datetime.date | None = None
    dependent_date_of_birth: datetime.date | None = None
    company_email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    work_state: str | None = None
    unique_corp_id: str | None = None
    employee_first_name: str | None = None
    employee_last_name: str | None = None
    verification_type_v2: str | None = None

    def has_necessary_client_specific_params(self) -> bool:
        return (
            None not in (self.date_of_birth, self.organization_id, self.is_employee)
        ) and bool(self.unique_corp_id)

    def has_work_state(self) -> bool:
        # in e9y-api, empty string was taken as NULL in SQL
        # https://gitlab.com/maven-clinic/maven/eligibility-api/-/blob/main/db/queries/member_versioned/fetch.sql#L71
        # here should be non empty string not just None
        return bool(self.work_state)

    def has_necessary_params_for_no_dob_verification(self) -> bool:
        return self.has_email_and_name() or self.has_email_and_employee_name()

    def has_email_and_name(self) -> bool:
        email_and_name = (
            self.company_email,
            self.first_name,
            self.last_name,
        )
        return all(email_and_name)

    def has_email_and_employee_name(self) -> bool:
        email_and_employee_name = (
            self.company_email,
            self.employee_first_name,
            self.employee_last_name,
        )
        return all(email_and_employee_name)

    def has_necessary_standard_params(self) -> bool:
        return all(
            (
                self.date_of_birth,
                self.company_email,
            )
        )

    def has_necessary_alternate_params(self) -> bool:
        return all(
            (
                self.first_name,
                self.last_name,
                self.date_of_birth,
            )
        )

    def has_necessary_params_for_overeligibility(self) -> bool:
        return all((self.first_name, self.last_name, self.date_of_birth,)) and any(
            (
                self.company_email,
                self.unique_corp_id,
            )
        )

    def has_necessary_multistep_params(self) -> bool:
        return (
            self.has_necessary_alternate_params()
            or self.has_necessary_standard_params()
        )

    def has_necessary_basic_params(self) -> bool:
        return all((self.first_name, self.last_name, self.date_of_birth))

    def has_necessary_employer_params(self) -> bool:
        return (
            all((self.company_email, self.date_of_birth))
            or all((self.first_name, self.last_name, self.company_email))
            or all(
                (self.employee_first_name, self.employee_last_name, self.company_email)
            )
            or all(
                (self.first_name, self.last_name, self.date_of_birth, self.work_state)
            )
            or all((self.company_email, self.dependent_date_of_birth))
        )

    def has_necessary_healthplan_params(self) -> bool:
        return (
            all((self.unique_corp_id, self.date_of_birth))
            or all((self.unique_corp_id, self.dependent_date_of_birth))
            or all((self.first_name, self.last_name, self.unique_corp_id))
            or all(
                (self.employee_first_name, self.employee_last_name, self.unique_corp_id)
            )
        )

    def has_necessary_multistep_v2_params(self) -> bool:
        return (
            self.has_necessary_healthplan_params()
            or self.has_necessary_employer_params()
            or self.has_necessary_basic_params()
        )

    def has_verification_type_v2(self) -> bool:
        return bool(self.verification_type_v2 and self.verification_type_v2.strip())

    def is_organization_enabled_for_e9y_ingestion_v2(self) -> bool:
        if not self.organization_id:
            return False
        enabled_orgs = set(
            json_variation(
                feature_flags.RELEASE_ELIGIBILITY_2_ENABLED_ORGS_WRITE,
                default=[],
            )
        )
        return self.organization_id in enabled_orgs


# end region


def is_no_dob_verification_enabled() -> bool:
    """
    Check if the no-dob verification feature flag is enabled.
    """
    is_flag_enabled = bool_variation(feature_flags.NO_DOB_VERIFICATION, default=False)
    return is_flag_enabled


def is_over_eligibility_enabled() -> bool:
    enabled = bool_variation(feature_flags.OVER_ELIGIBILITY, default=False)
    return enabled


def is_oe_deprecated_for_user_enterprise() -> bool:
    return bool_variation(
        feature_flags.RELEASE_OE_DEPRECATION_USER_IS_ENTERPRISE, default=False
    )


def is_enterprise_compare_enabled() -> bool:
    return bool_variation(
        feature_flags.RELEASE_OE_DEPRECATION_ENABLE_IS_ENTERPRISE_COMPARE, default=False
    )


def is_organization_deprecation_enabled() -> bool:
    return bool_variation(
        feature_flags.RELEASE_OE_DEPRECATION_USER_ORGANIZATION, default=False
    )


def is_organization_compare_enabled() -> bool:
    return bool_variation(
        feature_flags.RELEASE_OE_DEPRECATION_ENABLE_ORGANIZATION_COMPARE, default=False
    )


def no_oe_creation_enabled() -> bool:
    return bool_variation(
        feature_flags.RELEASE_OE_DEPRECATION_NO_OE_CREATION, default=False
    )


VerificationTypeT = Literal[
    "standard",
    "alternate",
    "client_specific",
    "multistep",
    "fileless",
    "lookup",
    "sso",
]


class VerificationType(str, Enum):
    BASIC = "basic"
    EMPLOYER = "employer"
    HEALTHPLAN = "healthplan"
    MULTISTEP = "multistep"
    NOT_FOUND = "not_found"


def _translate_verification_type(verification_type_str: str) -> VerificationType:
    """Translate input string to v2 verification type."""
    try:
        return VerificationType(verification_type_str.lower())
    except ValueError:
        return VerificationType.NOT_FOUND


valid_v2_verification_types: Set[VerificationType] = {
    VerificationType.BASIC,
    VerificationType.EMPLOYER,
    VerificationType.HEALTHPLAN,
    VerificationType.MULTISTEP,
}
