from __future__ import annotations

from typing import Tuple

from .base import AdminCategory, AdminViewT, AuthenticatedMenuLink
from .models.billing import BillView
from .models.cost_breakdown import (
    CostBreakdownRecalculationView,
    CostBreakdownView,
    RTETransactionView,
)
from .models.reimbursement_request_calculator import ReimbursementRequestCalculatorView
from .models.treatment_procedure import TreatmentProcedureView
from .models.wallet import (
    AnnualInsuranceQuestionnaireResponseView,
    HealthPlanYearToDateSpendView,
    MemberHealthPlanView,
    OrganizationEmployeeDependentView,
    PharmacyPrescriptionView,
    ReimbursementAccountView,
    ReimbursementClaimView,
    ReimbursementCycleCreditsView,
    ReimbursementRequestSourceView,
    ReimbursementRequestsView,
    ReimbursementTransactionView,
    ReimbursementWalletAllowedCategoryRulesEvaluationResultView,
    ReimbursementWalletAllowedCategorySettingsView,
    ReimbursementWalletBillingConsentView,
    ReimbursementWalletDebitCardView,
    ReimbursementWalletE9YBlackListView,
    ReimbursementWalletE9YMetaView,
    ReimbursementWalletPlanHDHPView,
    ReimbursementWalletUsersView,
    ReimbursementWalletView,
    WalletUserConsentView,
    WalletUserInviteView,
)


def get_views() -> Tuple[AdminViewT, ...]:
    return (  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        # Wallets
        ReimbursementWalletView.factory(category=AdminCategory.WALLET.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        WalletUserInviteView.factory(category=AdminCategory.WALLET.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        WalletUserConsentView.factory(category=AdminCategory.WALLET.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        OrganizationEmployeeDependentView.factory(
            category=AdminCategory.WALLET.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Reimbursement Wallet Authorized User (Dependent)",
        ),
        ReimbursementWalletUsersView.factory(
            category=AdminCategory.WALLET.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Reimbursement Wallet User (Sharing)",
        ),
        ReimbursementWalletDebitCardView.factory(category=AdminCategory.WALLET.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ReimbursementWalletPlanHDHPView.factory(
            category=AdminCategory.WALLET.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Reimbursement Wallet HDHP Plan",
        ),
        ReimbursementAccountView.factory(
            category=AdminCategory.WALLET.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Reimbursement Wallet Alegeus Account",
        ),
        ReimbursementCycleCreditsView.factory(
            category=AdminCategory.WALLET.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Reimbursement Wallet Cycle Credits",
        ),
        ReimbursementWalletAllowedCategoryRulesEvaluationResultView.factory(
            category=AdminCategory.WALLET.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ),
        ReimbursementWalletAllowedCategorySettingsView.factory(category=AdminCategory.WALLET_CONFIG.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        MemberHealthPlanView.factory(category=AdminCategory.WALLET.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        HealthPlanYearToDateSpendView.factory(
            category=AdminCategory.WALLET.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Health Plan Year to Date RX Spend",
        ),
        ReimbursementRequestsView.factory(category=AdminCategory.WALLET.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ReimbursementRequestSourceView.factory(category=AdminCategory.WALLET.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ReimbursementClaimView.factory(category=AdminCategory.WALLET.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ReimbursementTransactionView.factory(category=AdminCategory.WALLET.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ReimbursementWalletBillingConsentView.factory(
            category=AdminCategory.WALLET.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Direct Payment Billing Consent",
        ),
        TreatmentProcedureView.factory(
            category=AdminCategory.WALLET.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Direct Payment Treatment Procedure",
        ),
        BillView.factory(
            category=AdminCategory.WALLET.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "BaseClassicalMappedView" has incompatible type "str"; expected "AdminCategory"
            name="Direct Payment Bills",
        ),
        CostBreakdownView.factory(
            category=AdminCategory.WALLET.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Direct Payment Cost Breakdown",
        ),
        CostBreakdownRecalculationView(
            category=AdminCategory.WALLET.value,
            name="Direct Payment Cost Breakdown Calculator",
            endpoint="cost_breakdown_calculator",
        ),
        ReimbursementRequestCalculatorView(
            name="Reimbursement Request Cost Breakdown Backend",
            endpoint="reimbursement_request_calculator",
            category=AdminCategory.WALLET.value,
        ),
        AnnualInsuranceQuestionnaireResponseView.factory(
            category=AdminCategory.WALLET.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Annual Insurance Questionnaire Responses",
        ),
        RTETransactionView.factory(
            category=AdminCategory.WALLET.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="RTE Transaction",
        ),
        PharmacyPrescriptionView.factory(
            category=AdminCategory.WALLET.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="SMP Pharmacy Prescription",
        ),
        ReimbursementWalletE9YMetaView.factory(
            category=AdminCategory.WALLET.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Reimbursement Wallet Eligibility Sync",
        ),
        ReimbursementWalletE9YBlackListView.factory(
            category=AdminCategory.WALLET.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Reimbursement Wallet Eligibility Sync Black List",
        ),
    )


class ReimbursementSurveyResponsesLink(AuthenticatedMenuLink):
    read_permission = "read:reimbursement-survey-responses"
    edit_permission = "edit:reimbursement-survey-responses"
    create_permission = "create:reimbursement-survey-responses"
    delete_permission = "delete:reimbursement-survey-responses"


def get_links() -> Tuple[AuthenticatedMenuLink, ...]:
    return (
        ReimbursementSurveyResponsesLink(
            name="Reimbursement Survey Responses",
            category=AdminCategory.WALLET.value,
            url="/admin/survey_responses",
        ),
    )
