from __future__ import annotations

import datetime
import secrets
from datetime import date
from typing import Any, List, Optional, Tuple

import ddtrace
from flask import current_app

import configuration
from authn.models.user import User
from cost_breakdown.models.cost_breakdown import CostBreakdown
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
)
from direct_payment.treatment_procedure.repository.treatment_procedure import (
    TreatmentProcedureRepository,
)
from models.enterprise import Organization
from utils.log import logger
from wallet.constants import NUM_CREDITS_PER_CYCLE
from wallet.models.constants import (
    BenefitTypes,
    DashboardState,
    MemberType,
    ReimbursementRequestState,
    WalletState,
    WalletUserStatus,
)
from wallet.models.currency import Money
from wallet.models.models import (
    AlegeusAccountBalanceUpdate,
    BenefitResourceSchema,
    CategoryBalance,
    CreditBalanceData,
    CurrencyBalanceData,
    EligibleWalletSchema,
    EnrolledWalletSchema,
    MemberWalletStateSchema,
    MemberWalletSummary,
    PharmacySchema,
    PriorSpend,
    ReimbursementWalletStateSummarySchema,
    WalletBalance,
)
from wallet.models.organization_employee_dependent import OrganizationEmployeeDependent
from wallet.models.reimbursement import (
    ReimbursementPlan,
    ReimbursementRequest,
    ReimbursementRequestCategory,
)
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
    ReimbursementOrgSettingCategoryAssociation,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_credit import ReimbursementCycleCredits
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.repository.cycle_credits import CycleCreditsRepository
from wallet.repository.member_benefit import MemberBenefitRepository
from wallet.repository.reimbursement_request import ReimbursementRequestRepository
from wallet.repository.reimbursement_wallet import ReimbursementWalletRepository
from wallet.services.currency import DEFAULT_CURRENCY_CODE, CurrencyService
from wallet.utils.pharmacy import get_pharmacy_details_for_wallet

log = logger(__name__)


class ReimbursementWalletService:
    def __init__(
        self,
        wallet_repo: ReimbursementWalletRepository | None = None,
        requests_repo: ReimbursementRequestRepository | None = None,
        member_benefit_repo: MemberBenefitRepository | None = None,
        procedures_repo: TreatmentProcedureRepository | None = None,
        credits_repo: CycleCreditsRepository | None = None,
    ):
        self.wallet_repo: ReimbursementWalletRepository = (
            wallet_repo or ReimbursementWalletRepository()
        )
        self.requests_repo: ReimbursementRequestRepository = (
            requests_repo or ReimbursementRequestRepository()
        )
        self.member_benefit_repo: MemberBenefitRepository = (
            member_benefit_repo or MemberBenefitRepository()
        )
        self.procedures_repo: TreatmentProcedureRepository = (
            procedures_repo or TreatmentProcedureRepository()
        )
        self.credits_repo: CycleCreditsRepository = (
            credits_repo or CycleCreditsRepository()
        )

    @ddtrace.tracer.wrap()
    def get_member_wallet_state(self, user: User) -> MemberWalletStateSchema:
        # Get eligible (but not enrolled) wallets
        eligible_wallets: List[
            MemberWalletSummary
        ] = self.wallet_repo.get_eligible_wallets(user_id=user.id)
        # Get all enrolled wallets
        member_wallets: List[
            MemberWalletSummary
        ] = self.wallet_repo.get_wallet_summaries(user_id=user.id)
        disqualified_wallets: List[
            MemberWalletSummary
        ] = ReimbursementWalletService.get_disqualified_wallets(wallets=member_wallets)
        enrolled_wallets: List[
            MemberWalletSummary
        ] = ReimbursementWalletService.get_enrolled_wallets(
            wallets=member_wallets
        )  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Union[List[MemberWalletSummary], List[ClinicPortalMemberWalletSummary]]", variable has type "List[MemberWalletSummary]")

        # Get the member type and benefit ID
        member_type: MemberType = self.wallet_repo.get_member_type(user_id=user.id)

        member_benefit_id: str | None = None
        rx_information: dict | None = None

        if member_type in (
            MemberType.MAVEN_ACCESS,
            MemberType.MAVEN_GREEN,
            MemberType.MAVEN_GOLD,
        ):
            member_benefit_id = self.member_benefit_repo.get_member_benefit_id(
                user_id=user.id
            )
            rx_information = get_pharmacy_details_for_wallet(
                member=user,
                wallet=enrolled_wallets[0].wallet if enrolled_wallets else None,
            )

        summary_wallets: List[MemberWalletSummary] = (
            enrolled_wallets + disqualified_wallets
        )

        summary_wallet_id: int | None = None
        summary_channel_id: int | None = None
        summary_is_shareable: bool | None = None
        summary_wallet_state: WalletState | None = None
        # Prefer the first enrolled wallet in list when pulling summary fields
        summary_wallet_instance: MemberWalletSummary | None = (
            summary_wallets[0] if summary_wallets else None
        )

        if summary_wallet_instance:
            summary_wallet_id = summary_wallet_instance.wallet_id
            summary_channel_id = summary_wallet_instance.channel_id
            summary_is_shareable = summary_wallet_instance.is_shareable
            summary_wallet_state = ReimbursementWalletService.resolve_eligible_state(
                default_wallet_state=summary_wallet_instance.wallet_state,
                wallet_user_status=summary_wallet_instance.wallet_user_status,
            )

        return MemberWalletStateSchema(
            eligible=[
                EligibleWalletSchema(
                    organization_setting_id=wallet_summary.org_settings_id,
                    survey_url=ReimbursementWalletService.get_member_survey_url(),
                    benefit_overview_resource=BenefitResourceSchema(
                        title=wallet_summary.overview_resource_title,  # type: ignore[arg-type] # Argument "title" to "BenefitResourceSchema" has incompatible type "Optional[str]"; expected "str"
                        url=ReimbursementWalletService.format_benefit_overview_url(
                            resource_id=wallet_summary.overview_resource_id
                        )
                        if wallet_summary.overview_resource_id
                        else None,
                    ),
                    benefit_faq_resource=BenefitResourceSchema(
                        title=wallet_summary.faq_resource_title,
                        url=ReimbursementWalletService.format_benefit_faq_url(
                            content_type=wallet_summary.faq_resource_content_type,
                            slug=wallet_summary.faq_resource_slug,
                        ),
                    ),
                    wallet_id=wallet_summary.wallet_id,
                    state=ReimbursementWalletService.resolve_eligible_state(
                        default_wallet_state=wallet_summary.wallet_state,
                        wallet_user_status=wallet_summary.wallet_user_status,
                    ),
                )
                for wallet_summary in eligible_wallets + disqualified_wallets
            ],  # Disqualified wallets can re-apply
            enrolled=[
                EnrolledWalletSchema(
                    benefit_overview_resource=BenefitResourceSchema(
                        title=wallet_summary.overview_resource_title,  # type: ignore[arg-type] # Argument "title" to "BenefitResourceSchema" has incompatible type "Optional[str]"; expected "str"
                        url=ReimbursementWalletService.format_benefit_overview_url(
                            resource_id=wallet_summary.overview_resource_id
                        ),
                    ),
                    benefit_faq_resource=BenefitResourceSchema(
                        title=wallet_summary.faq_resource_title,
                        url=ReimbursementWalletService.format_benefit_faq_url(
                            content_type=wallet_summary.faq_resource_content_type,
                            slug=wallet_summary.faq_resource_slug,
                        ),
                    ),
                    wallet_id=wallet_summary.wallet_id,  # type: ignore[arg-type] # Argument "wallet_id" to "EnrolledWalletSchema" has incompatible type "Optional[int]"; expected "int"
                    channel_id=wallet_summary.channel_id,  # type: ignore[arg-type] # Argument "channel_id" to "EnrolledWalletSchema" has incompatible type "Optional[int]"; expected "int"
                    state=ReimbursementWalletService.resolve_eligible_state(
                        default_wallet_state=wallet_summary.wallet_state,
                        wallet_user_status=wallet_summary.wallet_user_status,
                    ),
                )
                for wallet_summary in enrolled_wallets
            ],
            summary=ReimbursementWalletStateSummarySchema(
                show_wallet=ReimbursementWalletService._resolve_show_wallet(
                    current_state=summary_wallet_state,
                    is_eligible=bool(eligible_wallets),
                ),
                dashboard_state=ReimbursementWalletService._resolve_dashboard_state(
                    current_state=summary_wallet_state,
                    is_eligible=bool(eligible_wallets),
                ),
                member_type=member_type,
                member_benefit_id=member_benefit_id,
                wallet_id=summary_wallet_id,
                channel_id=summary_channel_id,
                is_shareable=summary_is_shareable,
                pharmacy=PharmacySchema(
                    name=rx_information["name"], url=rx_information["url"]
                )
                if rx_information
                else None,
            ),
        )

    @staticmethod
    @ddtrace.tracer.wrap()
    def _resolve_show_wallet(
        is_eligible: bool, current_state: WalletState | None = None
    ) -> bool:
        if (
            current_state
            in (
                WalletState.PENDING,
                WalletState.QUALIFIED,
                WalletState.DISQUALIFIED,
                WalletState.RUNOUT,
            )
            or is_eligible
        ):
            return True

        # WalletState.EXPIRED or not eligible
        return False

    @staticmethod
    @ddtrace.tracer.wrap()
    def is_disqualified(settings: MemberWalletSummary) -> bool:
        return (
            settings.wallet_state == WalletState.DISQUALIFIED
            or settings.wallet_user_status == WalletUserStatus.DENIED
        )

    @staticmethod
    @ddtrace.tracer.wrap()
    def is_enrolled(settings: MemberWalletSummary) -> bool:
        return settings.wallet_state in (
            WalletState.QUALIFIED,
            WalletState.PENDING,
            WalletState.RUNOUT,
        ) and settings.wallet_user_status in (
            WalletUserStatus.PENDING,
            WalletUserStatus.ACTIVE,
        )

    @staticmethod
    def get_disqualified_wallets(
        wallets: List[MemberWalletSummary],
    ) -> List[MemberWalletSummary]:
        return list(
            filter(lambda w: ReimbursementWalletService.is_disqualified(w), wallets)
        )

    @staticmethod
    def get_enrolled_wallets(
        wallets: List[MemberWalletSummary],
    ) -> List[MemberWalletSummary]:
        return list(
            filter(lambda w: ReimbursementWalletService.is_enrolled(w), wallets)
        )

    @staticmethod
    @ddtrace.tracer.wrap()
    def _resolve_dashboard_state(
        is_eligible: bool, current_state: WalletState | None = None
    ) -> DashboardState | None:
        if is_eligible and current_state in (
            None,
            WalletState.DISQUALIFIED,
            WalletState.EXPIRED,
        ):
            return DashboardState.APPLY

        if current_state in (
            WalletState.PENDING,
            WalletState.QUALIFIED,
            WalletState.DISQUALIFIED,
            WalletState.RUNOUT,
        ):
            return DashboardState(value=current_state.value)

        # WalletState.EXPIRED or not eligible
        return None

    @staticmethod
    @ddtrace.tracer.wrap()
    def resolve_eligible_state(
        default_wallet_state: WalletState, wallet_user_status: WalletUserStatus
    ) -> WalletState:
        if default_wallet_state == WalletState.EXPIRED:
            return WalletState.EXPIRED
        elif (
            default_wallet_state == WalletState.DISQUALIFIED
            or wallet_user_status == WalletUserStatus.DENIED
        ):
            return WalletState.DISQUALIFIED
        elif wallet_user_status == WalletUserStatus.PENDING:
            return WalletState.PENDING

        return default_wallet_state

    @staticmethod
    @ddtrace.tracer.wrap()
    def get_member_survey_url() -> str:
        base_url = current_app.config["BASE_URL"].rstrip("/")
        return f"{base_url}/app/wallet/apply"

    @staticmethod
    @ddtrace.tracer.wrap()
    def format_benefit_overview_url(resource_id: int) -> str:
        config = configuration.get_api_config()
        return f"{config.common.base_url}/resources/custom/{str(resource_id)}"

    @staticmethod
    @ddtrace.tracer.wrap()
    def format_benefit_faq_url(content_type: str, slug: str) -> str:
        config = configuration.get_api_config()
        return f"{config.common.base_url}/resources/content/{content_type}/{slug}"

    @staticmethod
    def _compute_pending_reimbursements_amount(
        reimbursement_requests: List[ReimbursementRequest],
    ) -> int:
        """
        Calculate the pending amount for reimbursement requests, only if the amount is > $0

        Args:
            reimbursement_requests List[ReimbursementRequest]: List of reimbursement requests

        Returns: int - Total pending amount from reimbursement requests
        """
        pending_amount: int = 0

        for rr in reimbursement_requests:
            if rr.amount > 0:
                pending_amount += rr.amount

        return pending_amount

    @staticmethod
    def _compute_pending_reimbursements_credits(
        reimbursement_requests: List[ReimbursementRequest],
    ) -> int:
        """
        Calculate the pending credit amount for reimbursement requests, only if the amount is > $0

        Args:
            reimbursement_requests List[ReimbursementRequest]: List of reimbursement requests

        Returns: int - Total pending amount from reimbursement requests
        """
        pending_credits: int = 0

        for rr in reimbursement_requests:
            if rr.amount > 0:
                pending_credits += rr.cost_credit or 0

        return pending_credits

    @staticmethod
    def _compute_pending_procedures_with_cb_amount(
        treatment_procedures_and_cbs: List[
            Tuple[TreatmentProcedure, Optional[CostBreakdown]]
        ]
    ) -> int:
        """
        Calculate the pending amount for treatment procedures with cost breakdowns, only if the employer responsibility is > $0

        Args:
            treatment_procedures_and_cbs List[Tuple[TreatmentProcedure, Optional[CostBreakdown]]]:
                List of treatment procedures and cost breakdowns

        Returns: int - Total pending amount from procedures with cost breakdowns
        """
        pending_amount: int = 0

        for _, cb in treatment_procedures_and_cbs:
            if cb and cb.total_employer_responsibility > 0:
                pending_amount += cb.total_employer_responsibility

        return pending_amount

    @staticmethod
    def _compute_pending_procedures_with_cb_credits(
        treatment_procedures_and_cbs: List[
            Tuple[TreatmentProcedure, Optional[CostBreakdown]]
        ]
    ) -> int:
        """
        Calculate the pending credits for treatment procedures with cost breakdowns, only if the employer responsibility is > $0

        Args:
            treatment_procedures_and_cbs List[Tuple[TreatmentProcedure, Optional[CostBreakdown]]]:
                List of treatment procedures and cost breakdowns

        Returns: int - Total pending amount from procedures with cost breakdowns
        """
        pending_credits: int = 0

        for tp, cb in treatment_procedures_and_cbs:
            if cb and cb.total_employer_responsibility > 0:
                pending_credits += tp.cost_credit or 0

        return pending_credits

    @staticmethod
    def _compute_pending_procedures_without_cb_amount(
        treatment_procedures_and_cbs: List[
            Tuple[TreatmentProcedure, Optional[CostBreakdown]]
        ]
    ) -> int:
        """
        Calculate the pending amount for treatment procedures without cost breakdowns

        Args:
            treatment_procedures_and_cbs List[Tuple[TreatmentProcedure, Optional[CostBreakdown]]]:
                List of treatment procedures and cost breakdowns

        Returns: int - Total pending amount from procedures without cost breakdowns
        """
        pending_amount: int = 0

        for tp, cb in treatment_procedures_and_cbs:
            if cb is None:
                pending_amount += tp.cost

        return pending_amount

    @staticmethod
    def _compute_pending_procedures_without_cb_credits(
        treatment_procedures_and_cbs: List[
            Tuple[TreatmentProcedure, Optional[CostBreakdown]]
        ]
    ) -> int:
        """
        Calculate the pending credits for treatment procedures without cost breakdowns

        Args:
            treatment_procedures_and_cbs List[Tuple[TreatmentProcedure, Optional[CostBreakdown]]]:
                List of treatment procedures and cost breakdowns

        Returns: int - Total pending amount from procedures without cost breakdowns
        """
        pending_credits: int = 0

        for tp, cb in treatment_procedures_and_cbs:
            if cb is None:
                pending_credits += tp.cost_credit or 0

        return pending_credits

    @staticmethod
    def _sum_pending_currency_spend(
        reimbursement_amount: int,
        procedure_with_cb_amount: int,
        remaining_balance: Optional[int] = None,
        procedure_without_cb_amount: Optional[int] = None,
    ) -> int:
        """
        Sum up pending currency spend from reimbursement requests and treatment procedures

        Args:
            reimbursement_amount int: Total pending amount from reimbursement requests
            procedure_with_cb_amount int: Total pending amount from procedures with cost breakdowns
            procedure_without_cb_amount int: Total pending amount from procedures without cost breakdowns

        Returns: int - Total pending currency spend
        """
        pending_reimbursements_and_procedures_with_cb = (
            reimbursement_amount + procedure_with_cb_amount
        )

        # Unlimited - we don't take remaining balance into account
        if remaining_balance is None:
            pending_total = pending_reimbursements_and_procedures_with_cb

            if procedure_without_cb_amount:
                pending_total += procedure_without_cb_amount
        # Sum up spend for traditional limited categories
        else:
            pending_total = min(
                remaining_balance, pending_reimbursements_and_procedures_with_cb
            )
            updated_remaining_balance: int = remaining_balance - pending_total

            if procedure_without_cb_amount:
                pending_total += min(
                    updated_remaining_balance, procedure_without_cb_amount
                )

        return pending_total

    @staticmethod
    def _sum_pending_credit_spend(
        reimbursement_credits: int,
        procedure_with_cb_credits: int,
        remaining_credit_balance: int,
        procedure_without_cb_credits: Optional[int] = None,
    ) -> int:
        """
        Sum up pending credit spend from reimbursement requests and treatment procedures

        Args:
            reimbursement_credits int: Total pending amount from reimbursement requests
            procedure_with_cb_credits int: Total pending amount from procedures with cost breakdowns
            remaining_credit_balance int: Total remaining credits
            procedure_without_cb_credits int: Total pending amount from procedures without cost breakdowns

        Returns: int - Total pending credit spend
        """
        # Don't go below the remaining credit balance when summing up pending spend
        if procedure_without_cb_credits:
            # If there are procedures without cost breakdowns, we need to take them into account
            pending_credit_spend = min(
                remaining_credit_balance,
                reimbursement_credits
                + procedure_with_cb_credits
                + procedure_without_cb_credits,
            )
        else:
            # If there are no procedures without cost breakdowns
            pending_credit_spend = min(
                remaining_credit_balance,
                reimbursement_credits + procedure_with_cb_credits,
            )

        return pending_credit_spend

    @ddtrace.tracer.wrap()
    def get_wallet_balances(self, user: User) -> List[WalletBalance]:
        wallets_and_rwus: List[
            Tuple[ReimbursementWallet, ReimbursementWalletUsers]
        ] = self.wallet_repo.get_wallets_and_rwus_for_user(user_id=user.id)
        balances: List[WalletBalance] = []

        for wallet, rwu in wallets_and_rwus:
            balance = self.get_wallet_balance(wallet=wallet, rwu=rwu)
            balances.append(balance)

        return balances

    @ddtrace.tracer.wrap()
    def get_wallet_balance(
        self,
        wallet: ReimbursementWallet,
        rwu: ReimbursementWalletUsers,
        include_procedures_without_cb: bool = False,
    ) -> WalletBalance:
        categories: List[CategoryBalance] = self.get_wallet_category_balances(
            wallet=wallet, include_procedures_without_cb=include_procedures_without_cb
        )

        return WalletBalance(
            id=wallet.id,
            state=WalletState(wallet.state),
            user_status=WalletUserStatus(rwu.status),
            categories=categories,
        )

    @ddtrace.tracer.wrap()
    def get_wallet_category_balances(
        self,
        wallet: ReimbursementWallet,
        include_procedures_without_cb: bool = False,
    ) -> List[CategoryBalance]:
        category_balances: List[CategoryBalance] = []
        for category_association in wallet.get_or_create_wallet_allowed_categories:
            category_balance: CategoryBalance = self.get_wallet_category_balance(
                wallet=wallet,
                category_association=category_association,
                include_procedures_without_cb=include_procedures_without_cb,
            )
            category_balances.append(category_balance)

        return category_balances

    @ddtrace.tracer.wrap()
    def get_wallet_category_balance(
        self,
        wallet: ReimbursementWallet,
        category_association: ReimbursementOrgSettingCategoryAssociation,
        include_procedures_without_cb: bool = False,
    ) -> CategoryBalance:
        # Initialize common variables
        category: ReimbursementRequestCategory = (
            category_association.reimbursement_request_category
        )
        is_unlimited: bool = category_association.is_unlimited
        direct_payment_eligible: bool = category.is_direct_payment_eligible(
            reimbursement_wallet=wallet
        )
        to_return_currency_code: Optional[str] = None
        to_return_remaining_credits: Optional[int] = None

        # Check if plan is active
        plan = category.reimbursement_plan
        plan_active = bool(plan and plan.start_date <= date.today() <= plan.end_date)

        # Process based on benefit type
        if category_association.benefit_type == BenefitTypes.CURRENCY:
            balance_data = self._get_currency_balance_data(
                wallet=wallet,
                category_association=category_association,
                direct_payment_eligible=direct_payment_eligible,
            )
            remaining_balance = (
                max(balance_data["limit_amount"] - balance_data["spent_amount"], 0)
                if not is_unlimited
                else None
            )
            pending_amount = self._sum_pending_currency_spend(
                reimbursement_amount=balance_data["pending_reimbursements_amount"],
                procedure_with_cb_amount=balance_data[
                    "pending_procedures_with_cb_amount"
                ],
                remaining_balance=remaining_balance,
                procedure_without_cb_amount=balance_data[
                    "pending_procedures_without_cb_amount"
                ]
                if include_procedures_without_cb
                else None,
            )
            to_return_limit = balance_data["limit_amount"]
            to_return_spent = balance_data["spent_amount"]
            to_return_currency_code = balance_data["currency_code"]

        elif category_association.benefit_type == BenefitTypes.CYCLE:
            balance_data = self._get_credit_balance_data(
                wallet=wallet,
                category_association=category_association,
                direct_payment_eligible=direct_payment_eligible,
            )
            pending_amount = self._sum_pending_credit_spend(
                reimbursement_credits=balance_data["pending_reimbursements_credits"],
                procedure_with_cb_credits=balance_data[
                    "pending_procedures_with_cb_credits"
                ],
                remaining_credit_balance=balance_data["remaining_credits"],
                procedure_without_cb_credits=balance_data[
                    "pending_procedures_without_cb_credits"
                ]
                if include_procedures_without_cb
                else None,
            )
            to_return_limit = balance_data["limit_credits"]
            to_return_remaining_credits = balance_data["remaining_credits"]
            to_return_spent = 0

        else:
            raise Exception("Invalid category found")

        # Build and return the category balance
        return CategoryBalance(
            id=category_association.reimbursement_request_category_id,
            name=category.label,
            active=plan_active,
            benefit_type=category_association.benefit_type,
            direct_payment_category=direct_payment_eligible,
            is_unlimited=is_unlimited,
            limit_amount=to_return_limit,
            remaining_credits=to_return_remaining_credits,
            spent_amount=to_return_spent,
            pending_amount=pending_amount,
            currency_code=to_return_currency_code,
        )

    def _get_currency_balance_data(
        self,
        wallet: ReimbursementWallet,
        category_association: ReimbursementOrgSettingCategoryAssociation,
        direct_payment_eligible: bool,
    ) -> CurrencyBalanceData:
        """Helper method to get currency balance data"""
        currency_code: str = category_association.currency_code or "USD"
        limit_amount: Optional[int] = None
        pending_reimbursements_amount: int = 0
        pending_procedures_with_cb_amount: int = 0
        pending_procedures_without_cb_amount: int = 0

        if (is_unlimited := category_association.is_unlimited) is False:
            limit_amount = category_association.reimbursement_request_category_maximum

        if direct_payment_eligible:
            # Get approved amount and pending transactions
            spent_amount = self.wallet_repo.get_approved_amount_for_category(
                wallet_id=wallet.id,
                category_id=category_association.reimbursement_request_category.id,
            )
            # Initialize collections for pending calculations
            pending_reimbursements = self.requests_repo.get_pending_reimbursements(
                wallet_id=wallet.id,
                category_id=category_association.reimbursement_request_category_id,
            )
            scheduled_tp_and_cbs = (
                self.procedures_repo.get_scheduled_procedures_and_cbs(
                    wallet_id=wallet.id,
                    category_id=category_association.reimbursement_request_category.id,
                )
            )
            pending_reimbursements_amount = self._compute_pending_reimbursements_amount(
                reimbursement_requests=pending_reimbursements
            )
            pending_procedures_with_cb_amount = (
                self._compute_pending_procedures_with_cb_amount(
                    treatment_procedures_and_cbs=scheduled_tp_and_cbs
                )
            )
            pending_procedures_without_cb_amount = (
                self._compute_pending_procedures_without_cb_amount(
                    treatment_procedures_and_cbs=scheduled_tp_and_cbs
                )
            )
        else:
            # Non-direct payment case
            spent_amount = self.wallet_repo.get_reimbursed_amount_for_category(
                wallet_id=wallet.id,
                category_id=category_association.reimbursement_request_category.id,
            )

        return {
            "currency_code": currency_code,
            "is_unlimited": is_unlimited,
            "limit_amount": limit_amount,
            "spent_amount": spent_amount,
            "pending_reimbursements_amount": pending_reimbursements_amount,
            "pending_procedures_with_cb_amount": pending_procedures_with_cb_amount,
            "pending_procedures_without_cb_amount": pending_procedures_without_cb_amount,
        }

    def _get_credit_balance_data(
        self,
        wallet: ReimbursementWallet,
        category_association: ReimbursementOrgSettingCategoryAssociation,
        direct_payment_eligible: bool,
    ) -> CreditBalanceData:
        """Helper method to get cycle balance data"""
        # Get the cycle credits remaining
        cycle_credit: Optional[
            ReimbursementCycleCredits
        ] = self.credits_repo.get_cycle_credit_by_category(
            reimbursement_wallet_id=wallet.id,
            category_id=category_association.reimbursement_request_category.id,
        )

        if cycle_credit:
            limit_credits = category_association.num_cycles * NUM_CREDITS_PER_CYCLE
            remaining_credits = cycle_credit.amount
        else:
            limit_credits = 0
            remaining_credits = 0
            log.error(
                "Cycle credits not found for wallet with cycle category",
                wallet_id=wallet.id,
                category_association_id=category_association.id,
            )

        # Spent is 0, because there is no good way to determine it
        pending_reimbursements_credits: int = 0
        pending_procedures_with_cb_credits: int = 0
        pending_procedures_without_cb_credits: int = 0

        if direct_payment_eligible:
            # Initialize collections for pending calculations
            pending_reimbursements = self.requests_repo.get_pending_reimbursements(
                wallet_id=wallet.id,
                category_id=category_association.reimbursement_request_category_id,
            )
            scheduled_tp_and_cbs = (
                self.procedures_repo.get_scheduled_procedures_and_cbs(
                    wallet_id=wallet.id,
                    category_id=category_association.reimbursement_request_category_id,
                )
            )

            # Calculate pending credits
            pending_reimbursements_credits = (
                self._compute_pending_reimbursements_credits(
                    reimbursement_requests=pending_reimbursements
                )
            )
            pending_procedures_with_cb_credits = (
                self._compute_pending_procedures_with_cb_credits(
                    treatment_procedures_and_cbs=scheduled_tp_and_cbs
                )
            )
            pending_procedures_without_cb_credits = (
                self._compute_pending_procedures_without_cb_credits(
                    treatment_procedures_and_cbs=scheduled_tp_and_cbs
                )
            )
        else:
            # Log warning for non-direct payment cycle-based category
            log.warning(
                "Non-direct payment cycle based category detected",
                wallet_id=wallet.id,
                category_association_id=category_association.id,
            )

        return {
            "limit_credits": limit_credits,
            "remaining_credits": remaining_credits,
            "pending_reimbursements_credits": pending_reimbursements_credits,
            "pending_procedures_with_cb_credits": pending_procedures_with_cb_credits,
            "pending_procedures_without_cb_credits": pending_procedures_without_cb_credits,
        }

    @staticmethod
    def expire_wallet_and_rwus(wallet: ReimbursementWallet) -> None:
        """
        Set the wallet state to EXPIRED and all RWUs to DENIED

        Args:
            wallet ReimbursementWallet:

        Returns: None
        """
        wallet.state = WalletState.EXPIRED
        for rwu in wallet.reimbursement_wallet_users:
            rwu.status = WalletUserStatus.DENIED

    def expire_wallets_for_ros(
        self, ros_id: int, wallet_states: set[WalletState] = None
    ) -> list[dict]:
        """
        Set wallets under ROS to EXPIRED and all RWUs to DENIED, with optional filter for fetching wallets

        Args:
            ros_id int: ReimbursementOrganizationSetting.id
            wallet_states set[WalletState]: Optional filter for fetching wallets to expire

        Returns: dict of metadata containing wallet state before and after update
        """
        updated_wallet_metadata: list[dict] = []
        wallets: list[ReimbursementWallet] = self.wallet_repo.get_wallets_by_ros(
            ros_id=ros_id, wallet_states=wallet_states
        )
        for wallet in wallets:
            previous_wallet_state = wallet.state.value
            self.expire_wallet_and_rwus(wallet=wallet)
            metadata = {
                "wallet_id": wallet.id,
                "previous_wallet_state": previous_wallet_state,
                "updated_wallet_state": wallet.state.value,
                "updated_at": datetime.datetime.utcnow().isoformat(),
            }
            updated_wallet_metadata.append(metadata)
        return updated_wallet_metadata

    def _can_copy_from(self, wallet: ReimbursementWallet) -> bool:
        """
        To return True, the wallet must
        1. Be in EXPIRED state
        2. Make sure source wallet's ROS only has a single category
        3. All reimbursement requests are in a (FAILED, REIMBURSED, DENIED) state

        Args:
            wallet ReimbursementWallet:

        Returns: bool
        """
        # Check that wallet is EXPIRED
        if wallet.state != WalletState.EXPIRED:
            raise CopyWalletValidationError("Source wallet is not in EXPIRED state")

        # Check that the source wallet has a single category
        if (
            len(
                wallet.reimbursement_organization_settings.allowed_reimbursement_categories
            )
            != 1
        ):
            raise CopyWalletValidationError(
                "Source ROS does not have a single category"
            )

        # Check that reimbursements are (FAILED, REIMBURSED, DENIED, APPROVED)
        if self.requests_repo.wallet_has_unresolved_reimbursements(wallet_id=wallet.id):
            raise CopyWalletValidationError(
                "Source wallet has unresolved reimbursements"
            )

        return True

    def _calculate_prior_spend(
        self,
        wallet_id: int,
        category_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> PriorSpend:
        """
        Sum up all prior spend of a wallet/category and return as a tuple of amount and currency code

        Args:
            wallet_id int: Reimbursement wallet ID
            category_id int: Reimbursement Request category ID
            start_date date: optional date filter
            end_date date: optional date filter

        Returns: PriorSpend (TypedDict)
        """
        reimbursed_requests: list[
            ReimbursementRequest
        ] = self.requests_repo.get_reimbursed_reimbursements(
            wallet_id=wallet_id,
            category_id=category_id,
            start_date=start_date,
            end_date=end_date,
        )
        currencies = set()
        benefit_amount: int = 0
        usd_amount: int = 0

        if not reimbursed_requests:
            return {
                "benefit_currency_amount": {
                    "amount": benefit_amount,
                    "currency_code": None,
                },
                "usd_amount": {
                    "amount": usd_amount,
                    "currency_code": DEFAULT_CURRENCY_CODE,
                },
            }

        for reimbursed in reimbursed_requests:
            benefit_amount += reimbursed.amount
            usd_amount += reimbursed.usd_amount
            currencies.add(reimbursed.benefit_currency_code)

        if len(currencies) > 1:
            raise Exception("Mix of currencies detected when calculating prior spend")

        if (currency_code := currencies.pop()) is None:
            raise Exception("Missing currency code when calculating prior spend")

        return {
            "benefit_currency_amount": {
                "amount": benefit_amount,
                "currency_code": currency_code,
            },
            "usd_amount": {
                "amount": usd_amount,
                "currency_code": "USD",
            },
        }

    @staticmethod
    def create_prior_spend_reimbursement_request(
        amount: int,
        currency_code: str,
        wallet: ReimbursementWallet,
        category: ReimbursementRequestCategory,
    ) -> ReimbursementRequest:
        currency_service = CurrencyService()
        transaction: Money = currency_service.to_money(
            amount=amount,
            currency_code=currency_code,
        )
        prior_spend_entry = ReimbursementRequest(
            label="Prior Spend Adjustment",
            description="",
            service_provider="Prior Spend Adjustment",
            state=ReimbursementRequestState.REIMBURSED,
            wallet=wallet,
            category=category,
            service_start_date=datetime.date.today(),
        )
        currency_service.process_reimbursement_request(
            transaction=transaction, request=prior_spend_entry
        )
        return prior_spend_entry

    @staticmethod
    def _can_copy_to(
        wallet: ReimbursementWallet, ros: ReimbursementOrganizationSettings
    ) -> bool:
        """
        To return True, the following criteria must be met
        1. The ROS must be part of the same original wallet organization
        2. The ROS must only have 1 category configured

        Args:
            wallet ReimbursementWallet:
            ros ReimbursementOrganizationSettings:

        Returns: bool
        """
        # Check that the wallet and ros are in the same org
        if (
            wallet.reimbursement_organization_settings.organization_id
            != ros.organization_id
        ):
            raise CopyWalletValidationError(
                "Source wallet and target ROS must be part of same organization"
            )

        # Check that this ROS only has a single category configured
        # ^^ Important because we will need a single category to assign the prior spend entry to
        if len(ros.allowed_reimbursement_categories) != 1:
            raise CopyWalletValidationError("Target ROS must only have single category")

        return True

    def _copy_wallet_and_adjacent_objs(
        self, source: ReimbursementWallet, target: ReimbursementOrganizationSettings
    ) -> dict[str, Any]:
        """
        Initialize a copy of the ReimbursementWallet, RWUs, and OEDs attached to the source against the target ROS

        Args:
            source ReimbursementWallet:
            target ReimbursementOrganizationSettings:

        Returns: dict[str, Any]
        """
        target_wallet = ReimbursementWallet(
            user_id=source.user_id,
            reimbursement_organization_settings=target,
            reimbursement_method=source.reimbursement_method,
            primary_expense_type=source.primary_expense_type,
            taxation_status=source.taxation_status,
            note=source.note + f"\nDuplicated from wallet ID: {str(source.id)}",
            # Set to PENDING
            state=WalletState.PENDING,
            # Reporting fields
            initial_eligibility_member_id=source.initial_eligibility_member_id,
            initial_eligibility_verification_id=source.initial_eligibility_verification_id,
            initial_eligibility_member_2_id=source.initial_eligibility_member_2_id,
            initial_eligibility_member_2_version=source.initial_eligibility_member_2_version,
            initial_eligibility_verification_2_id=source.initial_eligibility_verification_2_id,
        )
        new_rwus: list[ReimbursementWalletUsers] = []

        for source_rwu in source.reimbursement_wallet_users:
            target_rwu = ReimbursementWalletUsers(
                reimbursement_wallet_id=target_wallet.id,
                user_id=source_rwu.user_id,
                zendesk_ticket_id=source_rwu.zendesk_ticket_id,
                channel_id=source_rwu.channel_id,
                type=source_rwu.type,
                status=WalletUserStatus.ACTIVE,
            )
            source_rwu.channel_id = None
            new_rwus.append(target_rwu)

        new_oeds: list[OrganizationEmployeeDependent] = []
        for source_oed in source.authorized_users:
            target_oed = OrganizationEmployeeDependent(
                first_name=source_oed.first_name,
                last_name=source_oed.last_name,
                middle_name=source_oed.middle_name,
                reimbursement_wallet_id=target_wallet.id,
                alegeus_dependent_id=secrets.token_hex(15),
            )
            new_oeds.append(target_oed)

        return {"wallet": target_wallet, "rwus": new_rwus, "oeds": new_oeds}

    def copy_wallet(
        self,
        source: ReimbursementWallet,
        target: ReimbursementOrganizationSettings,
        create_prior_spend_entry: bool = False,
    ) -> dict[str, Any]:
        """
        Copy a wallet and its RWUs and OEDs to a new ROS within the same organization

        Args:
            source ReimbursementWallet:
            target ReimbursementOrganizationSettings:
            create_prior_spend_entry bool:

        Returns: dictionary of objects created
        """
        self._can_copy_from(wallet=source)
        self._can_copy_to(wallet=source, ros=target)

        new_objs = self._copy_wallet_and_adjacent_objs(source=source, target=target)
        prior_spend_entry: ReimbursementRequest | None = None

        if create_prior_spend_entry:
            source_category_association = source.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ]
            prior_spend: PriorSpend = self._calculate_prior_spend(
                wallet_id=source.id,
                category_id=source_category_association.reimbursement_request_category_id,
            )
            # Only create an entry for amounts greater than 0
            if (
                prior_spend["benefit_currency_amount"]["amount"] > 0
                and prior_spend["benefit_currency_amount"]["currency_code"]
            ):
                target_category_association = target.allowed_reimbursement_categories[0]
                # Temporarily set wallet to qualified so reimbursement request can be attached
                # This hack bypasses validation that a wallet must be QUALIFIED/RUNOUT to have RRs
                new_objs["wallet"].state = WalletState.QUALIFIED
                prior_spend_entry = self.create_prior_spend_reimbursement_request(
                    amount=prior_spend["benefit_currency_amount"]["amount"],
                    currency_code=prior_spend["benefit_currency_amount"][
                        "currency_code"
                    ],
                    wallet=new_objs["wallet"],
                    category=target_category_association.reimbursement_request_category,
                )
                # set wallet back to pending
                new_objs["wallet"].state = WalletState.PENDING

        new_objs["prior_spend_entry"] = prior_spend_entry

        return new_objs

    def copy_and_persist_wallet_objs(
        self,
        source: ReimbursementWallet,
        target: ReimbursementOrganizationSettings,
        create_prior_spend_entry: bool = False,
    ) -> dict[str, Any]:
        try:
            created_dict = self.copy_wallet(
                source=source,
                target=target,
                create_prior_spend_entry=create_prior_spend_entry,
            )
            models = created_dict["oeds"] + created_dict["rwus"]
            models.append(created_dict["wallet"])

            if created_dict["prior_spend_entry"]:
                models.append(created_dict["prior_spend_entry"])

            self.wallet_repo.session.add_all(models)

        except Exception as e:
            self.wallet_repo.session.rollback()
            log.exception(
                "Exception encountered while attempting to copy wallet",
                source_wallet_id=str(source.id),
                target_ros_id=str(target.id),
                error=e,
            )
            raise
        else:
            self.wallet_repo.session.commit()

        log.info(
            "Successfully copied wallet to new ROS",
            source_wallet_id=str(source.id),
            target_ros_id=str(target.id),
            create_prior_spend=str(create_prior_spend_entry),
            target_wallet_id=created_dict["wallet"].id,
            prior_spend_request_id=created_dict["prior_spend_entry"].id
            if created_dict["prior_spend_entry"]
            else "",
        )

        return created_dict

    def calculate_usd_ltm_for_year(
        self,
        year: int,
        wallet: ReimbursementWallet,
        category_association: ReimbursementOrgSettingCategoryAssociation,
        currency_service: CurrencyService,
    ) -> int:
        """
        For the `year`, calculate the new updated USD ltm for the year, taking into consideration prior spend

        Args:
            year int: The calendar year that we want to calculate the balance for
            wallet ReimbursementWallet:
            category_association ReimbursementOrgSettingCategoryAssociation:
            currency_service CurrencyService:

        Returns: int - USD LTM amount
        """
        end_date: date = date(year=year, month=1, day=1)
        if not category_association.reimbursement_request_category_id:
            raise Exception("Category ID is missing for category association")

        benefit_type: BenefitTypes = category_association.benefit_type
        ltm_amount: int = category_association.reimbursement_request_category_maximum
        ltm_currency: str = category_association.currency_code

        if benefit_type != BenefitTypes.CURRENCY or not ltm_amount or not ltm_currency:
            error_str = "Incompatible category association configuration"
            log.error(
                error_str,
                wallet_id=str(wallet.id),
                category_association_id=str(category_association.id),
                ltm_amount=ltm_amount,
                ltm_currency=ltm_currency,
                benefit_type=category_association.benefit_type,
            )
            raise Exception(error_str)

        prior_spend: PriorSpend = self._calculate_prior_spend(
            wallet_id=wallet.id,
            category_id=category_association.reimbursement_request_category_id,
            end_date=end_date,
        )

        if (
            prior_spend["benefit_currency_amount"]["amount"] > 0
            and ltm_currency != prior_spend["benefit_currency_amount"]["currency_code"]
        ):
            error_str = "Prior spend currency different from LTM currency"
            log.error(
                error_str,
                wallet_id=str(wallet.id),
                category_association_id=str(category_association.id),
                ltm_amount=ltm_amount,
                ltm_currency=ltm_currency,
                prior_spend_currency=prior_spend["benefit_currency_amount"][
                    "currency_code"
                ],
                benefit_type=category_association.benefit_type,
            )
            raise Exception(error_str)

        # Remaining amount of the LTM in benefit currency
        remaining_amount: int = (
            ltm_amount - prior_spend["benefit_currency_amount"]["amount"]
        )
        # The value of that amount in USD based on exchange rates for `year`
        remaining_usd_amount, _ = currency_service.convert(
            amount=remaining_amount,
            source_currency_code=ltm_currency,
            target_currency_code=DEFAULT_CURRENCY_CODE,
            as_of_date=end_date,
        )
        # The LTM in USD will be what was spent + amount remaining in USD
        updated_usd_ltm_amount: int = (
            prior_spend["usd_amount"]["amount"] + remaining_usd_amount
        )

        return updated_usd_ltm_amount

    def calculate_ltm_updates(
        self, year: int, currency_service: CurrencyService, **kwargs: list[int]
    ) -> list[AlegeusAccountBalanceUpdate]:
        """
        Generate a list of dicts, each corresponding to a row in the IH edi file
        Args:
            year int: The calendar year that we want to calculate the balance for
            currency_service CurrencyService: instance of CurrencyService
            **kwargs list[int]: filters for repo function

        Returns: list[AlegeusAccountBalanceUpdate]
        """
        non_usd_wallets: list[
            ReimbursementWallet
        ] = self.wallet_repo.get_non_usd_wallets(**kwargs)
        balance_updates: list[AlegeusAccountBalanceUpdate] = []

        for wallet in non_usd_wallets:
            for category_association in wallet.get_or_create_wallet_allowed_categories:
                plan: ReimbursementPlan = (
                    category_association.reimbursement_request_category.reimbursement_plan
                )
                organization: Organization = (
                    wallet.reimbursement_organization_settings.organization
                )
                updated_usd_amount: int = self.calculate_usd_ltm_for_year(
                    year=year,
                    wallet=wallet,
                    category_association=category_association,
                    currency_service=currency_service,
                )

                if plan.reimbursement_account_type.alegeus_account_type is None:
                    error_str = (
                        f"alegeus_account_type can't be None - wallet_id: {wallet.id}"
                    )
                    log.exception(
                        error_str,
                        wallet_id=str(wallet.id),
                        category_association_id=str(category_association.id),
                        plan_id=str(plan.id),
                    )
                    raise Exception(error_str)
                if organization.alegeus_employer_id is None:
                    error_str = (
                        f"alegeus_employer_id can't be None - wallet_id: {wallet.id}"
                    )
                    log.exception(
                        error_str,
                        wallet_id=str(wallet.id),
                        category_association_id=str(category_association.id),
                        organization_id=str(organization.id),
                    )
                    raise Exception(error_str)
                if wallet.alegeus_id is None:
                    error_str = f"alegeus_id can't be None - wallet_id: {wallet.id}"
                    log.exception(
                        error_str,
                        wallet_id=str(wallet.id),
                        category_association_id=str(category_association.id),
                    )
                    raise Exception(error_str)

                money_amount: Money = currency_service.to_money(
                    amount=updated_usd_amount, currency_code=DEFAULT_CURRENCY_CODE
                )

                ltm_update_row: AlegeusAccountBalanceUpdate = {
                    "usd_amount": money_amount.amount,
                    "employee_id": wallet.alegeus_id,
                    "employer_id": organization.alegeus_employer_id,
                    "account_type": plan.reimbursement_account_type.alegeus_account_type,
                }
                balance_updates.append(ltm_update_row)

        return balance_updates


class CopyWalletException(Exception):
    pass


class CopyWalletValidationError(CopyWalletException):
    pass
