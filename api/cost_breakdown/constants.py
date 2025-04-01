import dataclasses
import enum
import os
from typing import Optional

from common.constants import Environment
from wallet.models.constants import CostSharingCategory

MAVEN_PROVIDER_LASTNAME = "maven"
MAVEN_PROVIDER_NPI = 1326898982

ELIGIBILITY_SUMMARY_ENDPOINT_NAME = "api/EligibilitySummary"
TOKEN_ENDPOINT_NAME = "Token"
PVERIFY_PROD_URL = "https://api.pverify.com/"
PVERIFY_TEST_URL = "https://api.pverify.com/test/"
PVERIFY_CLIENT_API_ID = os.environ.get("PVERIFY_CLIENT_API_ID")
PVERIFY_CLIENT_API_SECRET = os.environ.get("PVERIFY_CLIENT_API_SECRET")

PVERIFY_RESPONSE_KEY_SUBSET = (
    "APIResponseCode",
    "APIResponseMessage",
    "PayerName",
    "PlanCoverageSummary",
    "HBPC_Deductible_OOP_Summary",
    "SpecialistOfficeSummary",
    "AddtionalInfo",
)

IS_INTEGRATIONS_K8S_CLUSTER = (
    True if os.environ.get("IS_INTEGRATIONS_K8S_CLUSTER") == "true" else False
)
PVERIFY_URL = (
    PVERIFY_PROD_URL
    if Environment.current() == Environment.PRODUCTION
    else PVERIFY_TEST_URL
)

# feature flags
DISABLE_COST_BREAKDOWN_FOR_PAYER = "disable-cost-breakdown-for-payer"
ENABLE_UNLIMITED_BENEFITS_FOR_CB = "unlimited-benefits-cost-breakdown"


class EligibilityInfoKeys(enum.Enum):
    INDIVIDUAL_DEDUCTIBLE = "individual_deductible"
    INDIVIDUAL_DEDUCTIBLE_REMAINING = "individual_deductible_remaining"
    FAMILY_DEDUCTIBLE = "family_deductible"
    FAMILY_DEDUCTIBLE_REMAINING = "family_deductible_remaining"
    INDIVIDUAL_OOP = "individual_oop"
    INDIVIDUAL_OOP_REMAINING = "individual_oop_remaining"
    FAMILY_OOP = "family_oop"
    FAMILY_OOP_REMAINING = "family_oop_remaining"


PVERIFY_HBPC_SUMMARY_TO_ELGIBILITY_INFO = {
    "IndividualDeductibleInNet": EligibilityInfoKeys.INDIVIDUAL_DEDUCTIBLE.value,
    "IndividualDeductibleRemainingInNet": EligibilityInfoKeys.INDIVIDUAL_DEDUCTIBLE_REMAINING.value,
    "FamilyDeductibleInNet": EligibilityInfoKeys.FAMILY_DEDUCTIBLE.value,
    "FamilyDeductibleRemainingInNet": EligibilityInfoKeys.FAMILY_DEDUCTIBLE_REMAINING.value,
    "IndividualOOP_InNet": EligibilityInfoKeys.INDIVIDUAL_OOP.value,
    "IndividualOOPRemainingInNet": EligibilityInfoKeys.INDIVIDUAL_OOP_REMAINING.value,
    "FamilyOOPInNet": EligibilityInfoKeys.FAMILY_OOP.value,
    "FamilyOOPRemainingInNet": EligibilityInfoKeys.FAMILY_OOP_REMAINING.value,
}


class AmountType(enum.Enum):
    INDIVIDUAL = "INDIVIDUAL"
    FAMILY = "FAMILY"


class PverifyPracticeCodes(enum.Enum):
    SPECIALIST_OFFICE = "18"
    DIAGNOSTIC_MEDICAL = "113"
    PRIMARY_CARE = "70"


class PverifyKeys(enum.Enum):
    SPECIALIST_OFFICE_SUMMARY = "SpecialistOfficeSummary"
    DIAGNOSTIC_SUMMARY = "DiagnosticMedicalSummary"
    PRIMARY_CARE_SUMMARY = "PrimaryCareSummary"
    PLAN_COVERAGE_SUMMARY = "PlanCoverageSummary"
    API_RESPONSE_MESSAGE = "APIResponseMessage"
    DEDUCTIBLE_OOP_SUMMARY = "HBPC_Deductible_OOP_Summary"
    ADDITIONAL_INFO = "AddtionalInfo"


class Tier2PverifyKeys(enum.Enum):
    DEDUCTIBLE = "Deductible"
    OUT_OF_POCKET = "Out of Pocket"
    INDIVIDUAL_COVERAGE_VALUE = "Individual"
    FAMILY_COVERAGE_VALUE = "Family"
    REMAINING = "Remaining"
    YEAR_LIMIT = "Calendar Year"


TIER2_ELIGIBILITY_MAP = {
    Tier2PverifyKeys.INDIVIDUAL_COVERAGE_VALUE.value: {
        Tier2PverifyKeys.DEDUCTIBLE.value: {
            Tier2PverifyKeys.YEAR_LIMIT.value: EligibilityInfoKeys.INDIVIDUAL_DEDUCTIBLE.value,
            Tier2PverifyKeys.REMAINING.value: EligibilityInfoKeys.INDIVIDUAL_DEDUCTIBLE_REMAINING.value,
        },
        Tier2PverifyKeys.OUT_OF_POCKET.value: {
            Tier2PverifyKeys.YEAR_LIMIT.value: EligibilityInfoKeys.INDIVIDUAL_OOP.value,
            Tier2PverifyKeys.REMAINING.value: EligibilityInfoKeys.INDIVIDUAL_OOP_REMAINING.value,
        },
    },
    Tier2PverifyKeys.FAMILY_COVERAGE_VALUE.value: {
        Tier2PverifyKeys.DEDUCTIBLE.value: {
            Tier2PverifyKeys.YEAR_LIMIT.value: EligibilityInfoKeys.FAMILY_DEDUCTIBLE.value,
            Tier2PverifyKeys.REMAINING.value: EligibilityInfoKeys.FAMILY_DEDUCTIBLE_REMAINING.value,
        },
        Tier2PverifyKeys.OUT_OF_POCKET.value: {
            Tier2PverifyKeys.YEAR_LIMIT.value: EligibilityInfoKeys.FAMILY_OOP.value,
            Tier2PverifyKeys.REMAINING.value: EligibilityInfoKeys.FAMILY_OOP_REMAINING.value,
        },
    },
}


# If we add many more mappings or more vendors we can move this to a db table or separate config
COST_SHARING_CATEGORY_TO_PVERIFY_MAPPINGS = {
    CostSharingCategory.CONSULTATION: {
        "PRACTICE_CODE": PverifyPracticeCodes.SPECIALIST_OFFICE,
        "SUMMARY_OBJECT": PverifyKeys.SPECIALIST_OFFICE_SUMMARY,
    },
    CostSharingCategory.DIAGNOSTIC_MEDICAL: {
        "PRACTICE_CODE": PverifyPracticeCodes.DIAGNOSTIC_MEDICAL,
        "SUMMARY_OBJECT": PverifyKeys.DIAGNOSTIC_SUMMARY,
    },
    CostSharingCategory.MEDICAL_CARE: {
        "PRACTICE_CODE": PverifyPracticeCodes.PRIMARY_CARE,
        "SUMMARY_OBJECT": PverifyKeys.PRIMARY_CARE_SUMMARY,
    },
    CostSharingCategory.GENERIC_PRESCRIPTIONS: {
        "PRACTICE_CODE": PverifyPracticeCodes.PRIMARY_CARE,
        "SUMMARY_OBJECT": PverifyKeys.PRIMARY_CARE_SUMMARY,
    },
    CostSharingCategory.SPECIALTY_PRESCRIPTIONS: {
        "PRACTICE_CODE": PverifyPracticeCodes.PRIMARY_CARE,
        "SUMMARY_OBJECT": PverifyKeys.PRIMARY_CARE_SUMMARY,
    },
}


class ClaimType(enum.Enum):
    EMPLOYER = 1
    EMPLOYEE_DEDUCTIBLE = 2


class CostBreakdownType(enum.Enum):
    FIRST_DOLLAR_COVERAGE = "FIRST_DOLLAR_COVERAGE"
    HDHP = "HDHP"
    DEDUCTIBLE_ACCUMULATION = "DEDUCTIBLE_ACCUMULATION"


class CostBreakdownTriggerSource(enum.Enum):
    CLINIC = "CLINIC"
    ADMIN = "ADMIN"


@dataclasses.dataclass
class PlanCoverage:
    individual_deductible: Optional[int]
    family_deductible: Optional[int]
    individual_oop: Optional[int]
    family_oop: Optional[int]
    max_oop_per_covered_individual: Optional[int]
    is_deductible_embedded: bool
    is_oop_embedded: bool


class Tier(int, enum.Enum):
    PREMIUM = 1
    SECONDARY = 2
