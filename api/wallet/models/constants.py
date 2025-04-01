from __future__ import annotations

import enum
from enum import Enum

from flask_babel import lazy_gettext


class WalletState(str, enum.Enum):
    PENDING = "PENDING"
    QUALIFIED = "QUALIFIED"
    DISQUALIFIED = "DISQUALIFIED"
    EXPIRED = "EXPIRED"
    RUNOUT = "RUNOUT"


class ReimbursementRequestState(enum.Enum):
    NEW = "NEW"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REIMBURSED = "REIMBURSED"
    DENIED = "DENIED"
    FAILED = "FAILED"
    NEEDS_RECEIPT = "NEEDS_RECEIPT"
    RECEIPT_SUBMITTED = "RECEIPT_SUBMITTED"
    INSUFFICIENT_RECEIPT = "INSUFFICIENT_RECEIPT"
    INELIGIBLE_EXPENSE = "INELIGIBLE_EXPENSE"
    PENDING_MEMBER_INPUT = "PENDING_MEMBER_INPUT"
    RESOLVED = "RESOLVED"
    REFUNDED = "REFUNDED"


class ReimbursementRequestType(enum.Enum):
    MANUAL = 1
    DEBIT_CARD = 2
    DIRECT_BILLING = 3


class ReimbursementAccountStatus(enum.Enum):
    NEW = 1
    ACTIVE = 2
    TEMPORARILY_INACTIVE = 3
    PERMANENTLY_INACTIVE = 4
    TERMINATED = 5


class PlanType(enum.Enum):
    LIFETIME = "LIFETIME"
    ANNUAL = "ANNUAL"
    HYBRID = "HYBRID"
    PER_EVENT = "PER EVENT"


class AlegeusCoverageTier(enum.Enum):
    SINGLE = "SINGLE"
    FAMILY = "FAMILY"


class AlegeusAccountType(enum.Enum):
    HRA = "HRA"
    HR2 = "HR2"
    DTR = "DTR"
    HR4 = "HR4"
    HR3 = "HR3"
    HRX = "HRX"


class AlegeusClaimStatus(enum.Enum):
    NEEDS_RECEIPT = "NEEDS RECEIPT"
    SUBMITTED_UNDER_REVIEW = "SUBMITTED - UNDER REVIEW"
    DENIED = "DENIED"
    APPROVED = "APPROVED"
    PARTIALLY_APPROVED = "PARTIALLY APPROVED"
    PAID = "PAID"
    CLAIM_ADJUSTED_OVERPAYMENT = "CLAIM ADJUSTED-OVERPAYMENT"
    PARTIALLY_PAID = "PARTIALLY PAID"


class ReimbursementMethod(enum.Enum):
    DIRECT_DEPOSIT = 2
    PAYROLL = 6

    def __str__(self) -> str:
        return self.name


ALEGEUS_NONE_REIMBURSABLE_REIMBURSEMENT_METHOD = 0


class AlegeusBankAccountType(enum.Enum):
    NONE = 0
    CHECKING = 1
    SAVINGS = 2


class TaxationState(enum.Enum):
    TAXABLE = "TAXABLE"
    NON_TAXABLE = "NON_TAXABLE"
    ADOPTION_QUALIFIED = "ADOPTION_QUALIFIED"
    ADOPTION_NON_QUALIFIED = "ADOPTION_NON_QUALIFIED"


class TaxationStateConfig(enum.Enum):
    TAXABLE = "TAXABLE"
    NON_TAXABLE = "NON_TAXABLE"
    ADOPTION_QUALIFIED = "ADOPTION_QUALIFIED"
    ADOPTION_NON_QUALIFIED = "ADOPTION_NON_QUALIFIED"
    SPLIT_DX_INFERTILITY = "SPLIT_DX_INFERTILITY"


class InfertilityDX:
    name = "infertility_dx"
    label = lazy_gettext("payments_wallet_infertility_expense")


class BillingConsentAction(enum.Enum):
    CONSENT = "CONSENT"
    REVOKE = "REVOKE"


class CardStatus(enum.Enum):
    NEW = "NEW"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    CLOSED = "CLOSED"


class CardStatusReason(enum.IntEnum):
    NONE = 0

    # For INACTIVE cards
    PAST_DUE_RECEIPT = 100
    INELIGIBLE_EXPENSE = 101
    FRAUD_FLAG = 102
    HDHP_DEDUCTIBLE_UNMET = 103

    # For CLOSED cards
    LOST_STOLEN = 200
    HEALTH_PLAN_CHANGE = 201
    EMPLOYMENT_ENDED = 202


CardStatusReasonText = {
    CardStatusReason.NONE: "",
    # For INACTIVE cards
    CardStatusReason.PAST_DUE_RECEIPT: lazy_gettext(
        "payments_wallet_account_deactivated_past_due"
    ),
    CardStatusReason.INELIGIBLE_EXPENSE: lazy_gettext(
        "payments_wallet_account_deactivated_ineligible"
    ),
    CardStatusReason.FRAUD_FLAG: lazy_gettext(
        "payments_wallet_account_deactivated_fraud"
    ),
    CardStatusReason.HDHP_DEDUCTIBLE_UNMET: lazy_gettext(
        "payments_wallet_account_deactivated_deductible"
    ),
    # For CLOSED cards
    CardStatusReason.LOST_STOLEN: lazy_gettext(
        "payments_wallet_account_deactivated_lost"
    ),
    CardStatusReason.HEALTH_PLAN_CHANGE: lazy_gettext(
        "payments_wallet_account_deactivated_plan_change"
    ),
    CardStatusReason.EMPLOYMENT_ENDED: lazy_gettext(
        "payments_wallet_account_deactivated_employment_change"
    ),
}


state_descriptions = {
    # Special case -- Determined by ReimbursementRequestType instead of ReimbursementRequestState
    "DEBIT_CARD": lazy_gettext("payments_wallet_request_state_approved_debit_card"),
    ReimbursementRequestState.NEW: lazy_gettext("payments_wallet_request_state_new"),
    ReimbursementRequestState.PENDING: lazy_gettext(
        "payments_wallet_request_state_pending_review"
    ),
    ReimbursementRequestState.PENDING_MEMBER_INPUT: lazy_gettext(
        "payments_wallet_request_state_pending_input"
    ),
    ReimbursementRequestState.APPROVED: lazy_gettext(
        "payments_wallet_request_state_approved"
    ),
    ReimbursementRequestState.REIMBURSED: lazy_gettext(
        "payments_wallet_request_state_reimbursed"
    ),
    ReimbursementRequestState.DENIED: lazy_gettext(
        "payments_wallet_request_state_denied"
    ),
    ReimbursementRequestState.FAILED: lazy_gettext(
        "payments_wallet_request_state_failed"
    ),
    ReimbursementRequestState.NEEDS_RECEIPT: lazy_gettext(
        "payments_wallet_request_state_needs_receipt"
    ),
    ReimbursementRequestState.RECEIPT_SUBMITTED: lazy_gettext(
        "payments_wallet_request_state_submitted"
    ),
    ReimbursementRequestState.INSUFFICIENT_RECEIPT: lazy_gettext(
        "payments_wallet_request_state_insufficient"
    ),
    ReimbursementRequestState.INELIGIBLE_EXPENSE: lazy_gettext(
        "payments_wallet_request_state_ineligible"
    ),
    ReimbursementRequestState.RESOLVED: lazy_gettext(
        "payments_wallet_request_state_resolved"
    ),
    ReimbursementRequestState.REFUNDED: lazy_gettext(
        "payments_wallet_request_state_refunded"
    ),
}


class ShareWalletMessages(enum.Enum):
    NO_ACCESS = lazy_gettext("payments_wallet_share_no_access")
    INVALID_EMAIL = lazy_gettext("payments_wallet_share_invalid_email")
    INVALID_AGE = lazy_gettext("payments_wallet_share_invalid_age")
    WALLET_TEAM_HELP_NEEDED = lazy_gettext("payments_wallet_share_help_needed")
    ALREADY_A_MEMBER = lazy_gettext("payments_wallet_share_already_a_member")
    ALREADY_PENDING = lazy_gettext("payments_wallet_share_already_pending")
    SENT = lazy_gettext("payments_wallet_share_sent")


class WalletInvitationMessages(enum.Enum):
    INVITE_FOUND = lazy_gettext("payments_wallet_invite_found")
    INVITE_NOT_FOUND = lazy_gettext("payments_wallet_invite_not_found")
    INVITE_CANCELED = lazy_gettext("payments_wallet_invite_canceled")
    INVITE_CANCELED_FAILURE = lazy_gettext("payments_wallet_invite_canceled_failure")
    INVITE_ACCEPTED = lazy_gettext("payments_wallet_invite_accepted")
    INVITED_ACCEPTED_FAILURE = lazy_gettext("payments_wallet_invite_accepted_failure")
    INFORMATION_DOES_NOT_MATCH = lazy_gettext(
        "payments_wallet_invite_info_does_not_match"
    )
    EXPIRED = lazy_gettext("payments_wallet_invite_expired")
    ALREADY_EXPIRED = lazy_gettext("payments_wallet_invite_already_expired")
    ALREADY_USED = lazy_gettext("payments_wallet_invite_already_used")
    ALREADY_ACTIVE_WALLET = lazy_gettext("payments_wallet_invite_already_active")
    INVITE_DECLINED = lazy_gettext("payments_wallet_invite_declined")
    UNSHARABLE_WALLET = lazy_gettext("payments_wallet_invite_unsharable")
    WALLET_TEAM_HELP_NEEDED = lazy_gettext("payments_wallet_invite_help_needed")


class AlegeusCardStatus(enum.IntEnum):
    NEW = 1
    ACTIVE = 2
    TEMP_INACTIVE = 3
    PERM_INACTIVE = 4
    LOST_STOLEN = 5


class AlegeusTransactionStatus(enum.IntEnum):
    APPROVED = 1
    REFUNDED = 2
    RESOLVED_NO_REFUND = 4
    RECEIPT = 12
    FAILED = 13
    RESOLVED_PAYROLL = 15
    INELIGIBLE_EXPENSE = 16


class AlegeusDebitCardCountries(enum.Enum):
    US = "US"
    CA = "CA"
    ALL = [US, CA]


class WalletReportConfigCadenceTypes(enum.Enum):
    WEEKLY = "WEEKLY"
    BIWEEKLY = "BIWEEKLY"
    MONTHLY = "MONTHLY"


class WalletReportConfigColumnTypes(enum.Enum):
    EMPLOYEE_ID = "EMPLOYEE_ID"
    EMPLOYER_ASSIGNED_ID = "EMPLOYER_ASSIGNED_ID"
    DATE_OF_BIRTH = "DATE_OF_BIRTH"
    FIRST_NAME = "FIRST_NAME"
    LAST_NAME = "LAST_NAME"
    PROGRAM = "PROGRAM"
    VALUE_TO_APPROVE = "VALUE_TO_APPROVE"
    FX_RATE = "FX_RATE"
    VALUE_TO_APPROVE_USD = "VALUE_TO_APPROVE_USD"
    PRIOR_PROGRAM_TO_DATE = "PRIOR_PROGRAM_TO_DATE"
    TOTAL_PROGRAM_TO_DATE = "TOTAL_PROGRAM_TO_DATE"
    REIMBURSEMENT_TYPE = "REIMBURSEMENT_TYPE"
    COUNTRY = "COUNTRY"
    TAXATION = "TAXATION"
    PAYROLL_DEPT = "PAYROLL_DEPT"
    DEBIT_CARD_FUND_USAGE_USD = "DEBIT_CARD_FUND_USAGE_USD"
    DEBIT_CARD_FUND_AWAITING_SUBSTANTIATION = "DEBIT_CARD_FUND_AWAITING_SUBSTANTIATION"
    TOTAL_FUNDS_FOR_TAX_HANDLING = "TOTAL_FUNDS_FOR_TAX_HANDLING"
    LINE_OF_BUSINESS = "LINE_OF_BUSINESS"
    DIRECT_PAYMENT_FUND_USAGE = "DIRECT_PAYMENT_FUND_USAGE"
    EXPENSE_YEAR = "EXPENSE_YEAR"


class DebitBannerStatus(enum.Enum):
    NEW_DEBIT_BANNER = "NEW_DEBIT_BANNER"
    REQUEST_DEBIT_BANNER = "REQUEST_DEBIT_BANNER"
    HDHP_DEBIT_BANNER = "HDHP_DEBIT_BANNER"


class BenefitTypes(enum.Enum):
    CURRENCY = "CURRENCY"
    CYCLE = "CYCLE"


class CostSharingType(enum.Enum):
    COPAY = "COPAY"
    COPAY_NO_DEDUCTIBLE = "COPAY_NO_DEDUCTIBLE"
    COINSURANCE = "COINSURANCE"
    COINSURANCE_NO_DEDUCTIBLE = "COINSURANCE_NO_DEDUCTIBLE"
    COINSURANCE_MIN = "COINSURANCE_MIN"
    COINSURANCE_MAX = "COINSURANCE_MAX"


class CostSharingCategory(enum.Enum):
    CONSULTATION = "CONSULTATION"
    MEDICAL_CARE = "MEDICAL_CARE"
    DIAGNOSTIC_MEDICAL = "DIAGNOSTIC_MEDICAL"
    GENERIC_PRESCRIPTIONS = "GENERIC_PRESCRIPTIONS"
    SPECIALTY_PRESCRIPTIONS = "SPECIALTY_PRESCRIPTIONS"


class ReimbursementRequestExpenseTypes(enum.Enum):
    FERTILITY = "FERTILITY"
    ADOPTION = "ADOPTION"
    PRESERVATION = "PRESERVATION"
    SURROGACY = "SURROGACY"
    CHILDCARE = "CHILDCARE"
    MATERNITY = "MATERNITY"
    MENOPAUSE = "MENOPAUSE"
    PRECONCEPTION_WELLNESS = "PRECONCEPTION_WELLNESS"
    DONOR = "DONOR"

    def __str__(self) -> str:
        return str(self.value)


FERTILITY_EXPENSE_TYPES = [
    ReimbursementRequestExpenseTypes.FERTILITY,
    ReimbursementRequestExpenseTypes.PRESERVATION,
]


class FertilityProgramTypes(enum.Enum):
    CARVE_OUT = "CARVE_OUT"
    WRAP_AROUND = "WRAP_AROUND"


class WalletUserType(str, enum.Enum):
    EMPLOYEE = "EMPLOYEE"
    DEPENDENT = "DEPENDENT"


class WalletUserMemberStatus(str, enum.Enum):
    MEMBER = "MEMBER"
    NON_MEMBER = "NON_MEMBER"


class WalletUserStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    DENIED = "DENIED"
    REVOKED = "REVOKED"


class WalletDirectPaymentState(str, enum.Enum):
    WALLET_OPEN = "WALLET_OPEN"
    WALLET_CLOSED = "WALLET_CLOSED"
    DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY"
    FERTILITY_DX_REQUIRED = "FERTILITY_DX_REQUIRED"


class PatientInfertilityDiagnosis(str, enum.Enum):
    MEDICALLY_FERTILE = "MEDICALLY_FERTILE"
    MEDICALLY_INFERTILE = "MEDICALLY_INFERTILE"
    NOT_SURE = "NOT_SURE"


class MemberHealthPlanPatientSex(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    UNKNOWN = "UNKNOWN"


class MemberHealthPlanPatientRelationship(str, enum.Enum):
    CARDHOLDER = "CARDHOLDER"
    SPOUSE = "SPOUSE"
    CHILD = "CHILD"
    DOMESTIC_PARTNER = "DOMESTIC_PARTNER"
    FORMER_SPOUSE = "FORMER_SPOUSE"
    OTHER = "OTHER"
    STUDENT = "STUDENT"
    DISABLED_DEPENDENT = "DISABLED_DEPENDENT"
    ADULT_DEPENDENT = "ADULT_DEPENDENT"


class ConsentOperation(str, enum.Enum):
    GIVE_CONSENT = "GIVE_CONSENT"
    REVOKE_CONSENT = "REVOKE_CONSENT"


class AnnualQuestionnaireRequestStatus(str, enum.Enum):
    NOT_REQUIRED = "not_required"
    REQUIRED = "required"
    COMPLETED = "completed"


class AnnualQuestionnaireSyncStatus(str, enum.Enum):
    ALEGEUS_SUCCESS = "ALEGEUS_SUCCESS"
    ALEGEUS_FAILURE = "ALEGEUS_FAILURE"
    ALEGEUS_PRE_EXISTING_ACCOUNT = "ALEGEUS_PRE_EXISTING_ACCOUNT"
    ALEGEUS_MISSING_ACCOUNT = "ALEGEUS_MISSING_ACCOUNT"
    MISSING_WALLET_ERROR = "MISSING_WALLET_ERROR"
    MULTIPLE_WALLETS_ERROR = "MULTIPLE_WALLETS_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    PLAN_ERROR = "PLAN_ERROR"
    EMPLOYER_PLAN_MISSING_ERROR = "EMPLOYER_PLAN_MISSING_ERROR"
    MEMBER_HEALTH_PLAN_OVERLAP_ERROR = "MEMBER_HEALTH_PLAN_OVERLAP_ERROR"
    MEMBER_HEALTH_PLAN_GENERIC_ERROR = "MEMBER_HEALTH_PLAN_GENERIC_ERROR"
    MEMBER_HEALTH_PLAN_INVALID_DATES_ERROR = "MEMBER_HEALTH_PLAN_INVALID_DATES_ERROR"
    MANUAL_PROCESSING = "MANUAL_PROCESSING"
    ALEGEUS_SYNCH_INITIATED = "ALEGEUS_SYNCH_INITIATED"
    WAITING_ON_OPS_ACTION = "WAITING_ON_OPS_ACTION"
    MEMBER_HEALTH_PLAN_CREATION_INITIATED = "MEMBER_HEALTH_PLAN_CREATION_INITIATED"
    MEMBER_HEALTH_PLAN_CREATION_SUCCESS = "MEMBER_HEALTH_PLAN_CREATION_SUCCESS"
    MEMBER_HEALTH_PLAN_NOT_NEEDED = "MEMBER_HEALTH_PLAN_NOT_NEEDED"
    HDHP_REIMBURSEMENT_PLAN_NOT_NEEDED = "HDHP_REIMBURSEMENT_PLAN_NOT_NEEDED"
    RESPONSE_RECORDED = "RESPONSE_RECORDED"
    ASYNCH_PROCESSING_INITIATED = "ASYNCH_PROCESSING_INITIATED"


class MemberType(enum.Enum):
    MAVEN_ACCESS = "MAVEN_ACCESS"
    MAVEN_GREEN = "MAVEN_GREEN"
    MAVEN_GOLD = "MAVEN_GOLD"
    MARKETPLACE = "MARKETPLACE"


class AllowedMembers(enum.Enum):
    """
    Enum representing the allowed members for a benefit.

    The most up-to date implementation of these rules can be found in:
    wallet.resources.reimbursement_wallet_dashboard.can_apply_for_wallet
    """

    SHAREABLE = "SHAREABLE"
    """
    The wallet can be shared (the wallet itself will also have to have a ROS with direct_payment_enabled). 
    Only one person in the household can have a wallet.
    Other members of the household cannot have a wallet even if they are in a different ROS.
    """
    MULTIPLE_PER_MEMBER = "MULTIPLE_PER_MEMBER"
    """Multiple members of the household can have a wallet. These wallets are not shareable."""
    SINGLE_EMPLOYEE_ONLY = "SINGLE_EMPLOYEE_ONLY"
    """
    Only the employee can have a wallet. These are not shareable.
    Dependents may have wallets under other ROS-es but not if they are in the same ROS.
    """
    SINGLE_ANY_USER = "SINGLE_ANY_USER"
    """
    Only one member of the household can have a wallet. These are not shareable. Default.
    Employees and dependents should to belong to the same ROS. Once one member of the household has a wallet other
    members of the household cannot have a wallet even if they are in a different ROS.
    """
    SINGLE_DEPENDENT_ONLY = "SINGLE_DEPENDENT_ONLY"
    """Only the dependent may have a wallet. These are not shareable."""
    MULTIPLE_DEPENDENT_ONLY = "MULTIPLE_DEPENDENT_ONLY"
    """Multiple dependents may have a wallet. These are not shareable."""


class DashboardState(enum.Enum):
    APPLY = "APPLY"
    PENDING = "PENDING"
    DISQUALIFIED = "DISQUALIFIED"
    QUALIFIED = "QUALIFIED"
    RUNOUT = "RUNOUT"


class CategoryRuleAccessLevel(enum.Enum):
    FULL_ACCESS = "FULL_ACCESS"
    NO_ACCESS = "NO_ACCESS"


class CategoryRuleAccessSource(enum.Enum):
    RULES = "RULES"
    OVERRIDE = "OVERRIDE"
    NO_RULES = "NO_RULES"


class ReimbursementRequestAutoProcessing(enum.Enum):
    RX = "RX"


class EligibilityLossRule(str, enum.Enum):
    TERMINATION_DATE = "TERMINATION_DATE"
    END_OF_MONTH_FOLLOWING_TERMINATION = "END_OF_MONTH_FOLLOWING_TERMINATION"


class CoverageType(str, enum.Enum):
    MEDICAL = "MEDICAL"
    RX = "RX"


class FamilyPlanType(str, enum.Enum):
    UNDETERMINED = "UNDETERMINED"
    INDIVIDUAL = "INDIVIDUAL"
    FAMILY = "FAMILY"
    EMPLOYEE_PLUS = "EMPLOYEE_PLUS"


FAMILY_PLANS = [FamilyPlanType.FAMILY, FamilyPlanType.EMPLOYEE_PLUS]


class SyncIndicator(str, enum.Enum):
    CRON_JOB = "CRON_JOB"
    MANUAL = "MANUAL"


class ChangeType(str, enum.Enum):
    ROS_CHANGE = "ROS_CHANGE"
    RUNOUT = "RUNOUT"
    DISQUALIFIED = "DISQUALIFIED"
    DEPENDENT_CHANGE = "DEPENDENT_CHANGE"


class ReimbursementRequestSourceUploadSource(str, enum.Enum):
    INITIAL_SUBMISSION = "INITIAL_SUBMISSION"
    POST_SUBMISSION = "POST_SUBMISSION"
    ADMIN = "ADMIN"


class QuestionnaireType(str, Enum):
    TRADITIONAL_HDHP = "TRADITIONAL_HDHP"
    DIRECT_PAYMENT_HDHP = "DIRECT_PAYMENT_HDHP"  # Not currently in use
    DIRECT_PAYMENT_HEALTH_INSURANCE = "DIRECT_PAYMENT_HEALTH_INSURANCE"
    DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER = (
        "DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER"
    )
    DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER_TERMINAL = (
        "DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER_TERMINAL"
    )
    LEGACY = "LEGACY"


WALLET_QUALIFICATION_SERVICE_TAG = "creator: wallet_qualification_service"
WALLET_QUALIFICATION_UPDATER_TAG = "updater: wallet_qualification_rq_job"

UNLIMITED_BENEFITS_ADMIN_LABEL = "Unlimited"
