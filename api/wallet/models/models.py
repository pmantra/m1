from __future__ import annotations

import dataclasses
import math
from datetime import datetime
from decimal import Decimal
from typing import List, TypedDict, Union

from wallet.models.constants import (
    UNLIMITED_BENEFITS_ADMIN_LABEL,
    AllowedMembers,
    BenefitTypes,
    DashboardState,
    FertilityProgramTypes,
    MemberType,
    WalletState,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.currency import Money
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.services.currency import DEFAULT_CURRENCY_CODE, CurrencyService
from wallet.utils.currency import format_display_amount_with_currency_code


@dataclasses.dataclass(frozen=True)
class WalletUser:
    """
    Data class for passing display information to the WalletUsersGetResponse.
    """

    title: str
    status: str
    invitation_id: str = ""
    can_cancel_invitation: bool = False


@dataclasses.dataclass(frozen=True)
class WalletUsersGetResponse:
    """
    Data class for constructing the /reimbursement_wallet/{wallet_id}/users
    GET endpoint response.
    """

    # DO NOT ADD __slots__ to frozen dataclass, pickling fails
    # https://bugs.python.org/issue36424

    users: list[WalletUser]


class GetInvitationResponse(TypedDict):
    """
    Container for constructing the reimbursement_wallet/invitation/{invitation_id}
    GET endpoint response.
    """

    message: str
    inviter_name: str
    """First name of the individual who sent the invitation, used for display in the client."""
    survey_url: str
    """Url for the wallet survey in Survey Monkey"""


@dataclasses.dataclass(frozen=True)
class WalletAddUserPostRequest:
    """
    Data class for constructing the reimbursement_wallet/{wallet_id}/add_user
    POST endpoint request.
    """

    # DO NOT ADD __slots__ to frozen dataclass, pickling fails
    # https://bugs.python.org/issue36424
    email: str
    date_of_birth: str

    @staticmethod
    def from_request(request: dict) -> WalletAddUserPostRequest:
        return WalletAddUserPostRequest(
            email=request["email"].strip().casefold(),
            date_of_birth=request["date_of_birth"],
        )


class WalletAddUserPostResponse(TypedDict):
    """
    Container for constructing the reimbursement_wallet/{wallet_id}/add_user
    POST endpoint response.
    """

    message: str
    can_retry: bool


class DeleteInvitationResponse(TypedDict):
    """
    Container for constructing the reimbursement_wallet/invitation/{invitation_id}
    DELETE endpoint response.
    """

    message: str


@dataclasses.dataclass(frozen=True)
class PostInvitationRequest:
    """
    Data class for constructing the reimbursement_wallet/invitation/{invitation_id}
    POST endpoint request.
    """

    # DO NOT ADD __slots__ to frozen dataclass, pickling fails
    # https://bugs.python.org/issue36424
    accept: bool
    """
    True indicates that the user accepts the invitation.
    False indicates that the user declines the invitation.
    """

    @staticmethod
    def from_request(request: dict) -> PostInvitationRequest:
        return PostInvitationRequest(accept=request["accept"])


class PostInvitationResponse(TypedDict):
    """
    Container for constructing the reimbursement_wallet/invitation/{invitation_id}
    DELETE endpoint response.
    """

    message: str


@dataclasses.dataclass(frozen=True)
class AnnualInsuranceQuestionnaireHDHPData:
    """
    Data class to convert Questionnaire data into a form that can be consumed by the Alegeus integration module
    """

    # DO NOT ADD __slots__ to frozen dataclass, pickling fails
    # https://bugs.python.org/issue36424
    survey_responder_has_hdhp: bool
    partner_has_hdhp: bool


@dataclasses.dataclass()
class MemberTypeDetailsFlags:
    wallet_organization: bool = False
    direct_payment: bool = False
    member_country: bool = False
    member_track: bool = False
    wallet_active: bool = False
    wallet_expense_type: bool = False


@dataclasses.dataclass()
class MemberTypeDetails:
    member_type: MemberType
    flags: MemberTypeDetailsFlags
    active_wallet: ReimbursementWallet | None


@dataclasses.dataclass(frozen=True)
class ReimbursementPostRequest:
    service_provider: str
    description: str
    wallet_id: str
    service_start_date: str
    person_receiving_service_id: str
    person_receiving_service_name: str
    amount: int
    currency_code: str
    sources: list[dict]  # expect one key: source_id, based on openapi spec
    document_mapping_uuid: str | None = None
    infertility_dx: bool = False
    expense_type: str | None = None
    expense_subtype_id: str | None = None
    category_id: str | None = None

    @staticmethod
    def from_request(request: dict) -> ReimbursementPostRequest:
        currency_code: str | None = request.get("currency_code", DEFAULT_CURRENCY_CODE)
        if currency_code is None:
            raise ValueError("currency_code can't be None")
        if currency_code.strip() == "":
            raise ValueError("currency_code can't be empty string")

        return ReimbursementPostRequest(
            category_id=request.get("category_id"),
            service_provider=request["service_provider"],
            description=request.get("description", ""),
            wallet_id=request["wallet_id"],
            service_start_date=request["service_start_date"],
            person_receiving_service_id=request["person_receiving_service_id"],
            person_receiving_service_name=request["person_receiving_service_name"],
            sources=request["sources"],
            amount=request["amount"],
            currency_code=currency_code.strip(),
            expense_type=request.get("expense_type"),
            expense_subtype_id=request.get("expense_subtype_id"),
            infertility_dx=request.get("infertility_dx", False),
            document_mapping_uuid=request.get("document_mapping_uuid", None),
        )


# Data classes handed over to the service layer from repository


@dataclasses.dataclass(frozen=True)
class MemberBenefitProfile:
    user_id: int
    benefit_id: str
    first_name: str
    last_name: str
    date_of_birth: datetime
    phone: str
    email: str


@dataclasses.dataclass(frozen=True)
class OrganizationWalletSettings:
    organization_id: int
    organization_name: str
    excluded_procedures: List[str] = dataclasses.field(default_factory=list)
    dx_required_procedures: List[str] = dataclasses.field(default_factory=list)
    direct_payment_enabled: bool | None = None
    org_settings_id: int | None = None
    fertility_program_type: FertilityProgramTypes | None = None
    fertility_allows_taxable: bool | None = None


@dataclasses.dataclass(frozen=True)
class MemberWalletSummary:
    org_id: int
    org_settings_id: int
    direct_payment_enabled: bool
    org_survey_url: str
    faq_resource_title: str
    faq_resource_content_type: str
    faq_resource_slug: str
    wallet_state: WalletState | None = None
    wallet: ReimbursementWallet | None = None
    payments_customer_id: str | None = None
    overview_resource_title: str | None = None
    overview_resource_id: int | None = None
    member_id_hash: str | None = None
    wallet_id: int | None = None
    channel_id: int | None = None
    wallet_user_status: WalletUserStatus | None = None
    is_shareable: bool | None = None


@dataclasses.dataclass(frozen=True)
class WalletUserTypeAndAllowedMembers:
    wallet_user_type: WalletUserType
    allowed_members: AllowedMembers


@dataclasses.dataclass(frozen=True)
class UserWalletAndOrgInfo:
    user_id: int
    user_type: str
    user_status: str
    wallet_id: int
    wallet_state: str
    ros_id: int
    ros_allowed_members: str


class CurrencyBalanceData(TypedDict):
    currency_code: str
    is_unlimited: bool
    limit_amount: int | None
    spent_amount: int
    pending_reimbursements_amount: int
    pending_procedures_with_cb_amount: int
    pending_procedures_without_cb_amount: int


class CreditBalanceData(TypedDict):
    limit_credits: int
    remaining_credits: int
    pending_reimbursements_credits: int
    pending_procedures_with_cb_credits: int
    pending_procedures_without_cb_credits: int


@dataclasses.dataclass(frozen=True)
class CategoryBalance:
    id: int
    name: str
    spent_amount: int
    pending_amount: int
    benefit_type: BenefitTypes
    direct_payment_category: bool
    active: bool
    is_unlimited: bool = False
    limit_amount: int | None = None
    remaining_credits: int | None = None
    currency_code: str | None = None

    @property
    def available_balance(self) -> Union[int, math.inf]:
        # If the category is unlimited, the current balance is unlimited
        if self.is_unlimited:
            return math.inf
        # Ensure balance doesn't go below 0
        return max(self.current_balance - self.pending_amount, 0)

    @property
    def current_balance(self) -> Union[int, math.inf]:
        # If the category is unlimited, the current balance is unlimited
        if self.is_unlimited:
            return math.inf
        elif self.benefit_type == BenefitTypes.CYCLE:
            # If the category is a cycle benefit, the current balance is the remaining credits
            return self.remaining_credits
        else:
            # Ensure balance doesn't go below 0
            return max(self.limit_amount - self.spent_amount, 0)

    @property
    def formatted_limit_amount(self) -> str:
        if self.is_unlimited:
            return UNLIMITED_BENEFITS_ADMIN_LABEL
        elif self.currency_code:
            currency_service = CurrencyService()
            amount: Money = currency_service.to_money(
                amount=self.limit_amount,
                currency_code=self.currency_code,
            )
            return format_display_amount_with_currency_code(money=amount)
        return str(self.limit_amount)

    @property
    def formatted_spent_amount(self) -> str:
        if self.currency_code:
            currency_service = CurrencyService()
            amount: Money = currency_service.to_money(
                amount=self.spent_amount,
                currency_code=self.currency_code,
            )
            return format_display_amount_with_currency_code(money=amount)
        return str(self.spent_amount)

    @property
    def formatted_current_balance(self) -> str:
        if self.is_unlimited:
            return UNLIMITED_BENEFITS_ADMIN_LABEL
        elif self.currency_code:
            currency_service = CurrencyService()
            amount: Money = currency_service.to_money(
                amount=self.current_balance,
                currency_code=self.currency_code,
            )
            return format_display_amount_with_currency_code(money=amount)
        return str(self.current_balance)

    @property
    def formatted_available_balance(self) -> str:
        if self.is_unlimited:
            return UNLIMITED_BENEFITS_ADMIN_LABEL
        elif self.currency_code:
            currency_service = CurrencyService()
            amount: Money = currency_service.to_money(
                amount=self.available_balance,
                currency_code=self.currency_code,
            )
            return format_display_amount_with_currency_code(money=amount)
        return str(self.available_balance)


@dataclasses.dataclass(frozen=True)
class WalletBalance:
    id: int
    state: WalletState
    user_status: WalletUserStatus
    categories: List[CategoryBalance]


# Data classes used to represent the API response schema


@dataclasses.dataclass(frozen=True)
class PharmacySchema:
    name: str
    url: str

    def serialize(self) -> dict:
        return {"name": self.name, "url": self.url}


@dataclasses.dataclass(frozen=True)
class ReimbursementWalletStateSummarySchema:
    show_wallet: bool
    member_type: MemberType
    dashboard_state: DashboardState | None = None
    member_benefit_id: str | None = None
    pharmacy: PharmacySchema | None = None
    wallet_id: int | None = None
    channel_id: int | None = None
    is_shareable: bool | None = None

    def serialize(self) -> dict:
        return {
            "show_wallet": self.show_wallet,
            "member_type": self.member_type.value,
            "dashboard_state": self.dashboard_state.value
            if self.dashboard_state
            else None,
            "member_benefit_id": self.member_benefit_id,
            "wallet_id": str(self.wallet_id) if self.wallet_id else None,
            "channel_id": self.channel_id if self.channel_id else None,
            "is_shareable": self.is_shareable,
            "pharmacy": self.pharmacy.serialize() if self.pharmacy else None,
        }


@dataclasses.dataclass(frozen=True)
class BenefitResourceSchema:
    title: str
    url: str

    def serialize(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
        }


@dataclasses.dataclass(frozen=True)
class EligibleWalletSchema:
    organization_setting_id: int
    survey_url: str
    benefit_overview_resource: BenefitResourceSchema
    benefit_faq_resource: BenefitResourceSchema
    wallet_id: int | None = None
    state: WalletState | None = None

    def serialize(self) -> dict:
        return {
            "organization_setting_id": str(self.organization_setting_id),
            "survey_url": self.survey_url,
            "benefit_overview_resource": self.benefit_overview_resource.serialize(),
            "benefit_faq_resource": self.benefit_faq_resource.serialize(),
            "wallet_id": str(self.wallet_id) if self.wallet_id else None,
            "state": self.state.value if self.state else None,
        }


@dataclasses.dataclass(frozen=True)
class EnrolledWalletSchema:
    wallet_id: int
    state: WalletState
    channel_id: int
    benefit_overview_resource: BenefitResourceSchema
    benefit_faq_resource: BenefitResourceSchema

    def serialize(self) -> dict:
        return {
            "wallet_id": str(self.wallet_id),
            "state": self.state.value if self.state else None,
            "channel_id": self.channel_id,
            "benefit_overview_resource": self.benefit_overview_resource.serialize(),
            "benefit_faq_resource": self.benefit_faq_resource.serialize(),
        }


@dataclasses.dataclass(frozen=True)
class MemberWalletStateSchema:
    summary: ReimbursementWalletStateSummarySchema
    eligible: List[EligibleWalletSchema]
    enrolled: List[EnrolledWalletSchema]

    def serialize(self) -> dict:
        return {
            "summary": self.summary.serialize(),
            "eligible": [w.serialize() for w in self.eligible],
            "enrolled": [w.serialize() for w in self.enrolled],
        }


class CategoryRuleProcessingResultSchema:
    wallet_id: int
    category_id: int
    rule_evaluation_result: bool | None
    setting_id: int | None
    success: bool

    def __str__(self) -> str:
        return (
            f"Wallet Id: {self.wallet_id}, Category ID: {self.category_id}, Rule Evaluation Result: "
            f"{self.rule_evaluation_result}, Setting ID: {self.setting_id}, Success: {self.success}"
        )


class AllowedCategoryAccessLevel(TypedDict):
    allowed_category_id: int
    wallet_access_level: str


class CurrencyAmount(TypedDict):
    amount: int
    currency_code: str | None


class PriorSpend(TypedDict):
    benefit_currency_amount: CurrencyAmount
    usd_amount: CurrencyAmount


class AlegeusAccountBalanceUpdate(TypedDict):
    usd_amount: Decimal
    employee_id: str
    employer_id: str
    account_type: str
