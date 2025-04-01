import dataclasses
from datetime import date
from enum import Enum

from wallet.models.constants import (
    FamilyPlanType,
    MemberHealthPlanPatientRelationship,
    MemberHealthPlanPatientSex,
)


class DirectPaymentSurveyFields(str, Enum):
    IS_HDHP = "annual_insurance_survey_dp_wallet_survey_q_01"
    COVERED_MEMBERS = "annual_insurance_survey_dp_wallet_survey_q_02"
    COVERED_MEMBERS_AMAZON = "annual_insurance_survey_dp_wallet_survey_q_02_amazon"
    COVERED_MEMBERS_OHIO = "annual_insurance_survey_dp_wallet_survey_q_02_ohio"
    PATIENT_SEX = "annual_insurance_survey_dp_wallet_survey_q_03"
    PAYER_PLAN_NAME = "annual_insurance_survey_dp_wallet_survey_gp1_q_01"
    INSURANCE_ID = "annual_insurance_survey_dp_wallet_survey_gp1_q_02"
    INSURANCE_ID_AMAZON = "annual_insurance_survey_dp_wallet_survey_amazon_gp1_q_02"
    MEMBER_HEALTH_PLAN_PATIENT_RELATIONSHIP = (
        "annual_insurance_survey_dp_wallet_survey_gp1_q_03"
    )
    FIRST_NAME = "annual_insurance_survey_dp_wallet_survey_gp1_q_04"
    LAST_NAME = "annual_insurance_survey_dp_wallet_survey_gp1_q_05"
    DOB = "annual_insurance_survey_dp_wallet_survey_gp1_q_06"

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


class TraditionalWalletFieldKeys(str, Enum):
    SELF_HDHP = "annual_insurance_survey_trad_wallet_hdhp_survey_self_q"
    PARTNER_HDHP = "annual_insurance_survey_trad_wallet_hdhp_survey_partner_q"
    EMPLOYER_PLAN = (
        "annual_insurance_survey_trad_wallet_hdhp_survey_q_health_pla_thru_employer"
    )

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"


class EmployerPlanCoverage(str, Enum):
    SELF_ONLY = "self_only"
    PARTNER = "partner_only"
    BOTH = "both"
    NEITHER = "neither"


@dataclasses.dataclass(frozen=True)
class DirectPaymentAnnualSurveyResponse:
    is_hdhp: bool
    family_plan_type: FamilyPlanType
    employer_health_plan_id: int
    subscriber_insurance_id: str
    subscriber_first_name: str
    subscriber_last_name: str
    subscriber_date_of_birth: date
    member_health_plan_patient_relationship: MemberHealthPlanPatientRelationship
    patient_sex: MemberHealthPlanPatientSex


@dataclasses.dataclass(frozen=True)
class HDHPAnnualSurveyResponse:
    self_hdhp: bool
    partner_hdhp: bool
    employer_plan_coverage: EmployerPlanCoverage
