from __future__ import annotations

from typing import Tuple

from common.global_procedures import constants

from .base import AdminCategory, AdminViewT, AuthenticatedMenuLink
from .models.clinic import (
    FeeScheduleView,
    FertilityClinicLocationContactView,
    FertilityClinicLocationEmployerHealthPlanTierView,
    FertilityClinicLocationView,
    FertilityClinicUserProfileView,
    FertilityClinicView,
    QuestionnaireGlobalProcedureView,
)
from .models.cost_breakdown import CostBreakdownIRSMinimumDeductibleView
from .models.direct_payment_invoicing_setting import DirectPaymentInvoicingSettingView
from .models.employer_health_plan import (
    EmployerHealthPlanCostSharingView,
    EmployerHealthPlanCoverageView,
    EmployerHealthPlanView,
)
from .models.wallet import (
    CountryCurrencyCodeView,
    PayerListView,
    ReimbursementAccountTypeView,
    ReimbursementOrgSettingsAllowedCategoryRuleView,
    ReimbursementOrgSettingsExpenseTypeView,
    ReimbursementPlanCoverageTierView,
    ReimbursementPlanView,
    ReimbursementRequestExchangeRatesView,
    ReimbursementServiceCategoryView,
    ReimbursementWalletDashboardCardsView,
    ReimbursementWalletDashboardCardView,
    ReimbursementWalletDashboardView,
    WalletClientReportConfigurationView,
    WalletExpenseSubtypeView,
)
from .models.wallet_category import (
    ReimbursementOrgSettingCategoryAssociationView,
    ReimbursementRequestCategoryView,
)
from .models.wallet_org_setting import ReimbursementOrganizationSettingsView


def get_views() -> Tuple[AdminViewT, ...]:
    return (
        # Organizations
        ReimbursementOrganizationSettingsView.factory(
            category=AdminCategory.WALLET_CONFIG.value  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ),
        ReimbursementOrgSettingCategoryAssociationView.factory(
            category=AdminCategory.WALLET_CONFIG.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Reimbursement Organization Category Association",
        ),
        DirectPaymentInvoicingSettingView.factory(
            category=AdminCategory.WALLET_CONFIG.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Reimbursement Organization Invoicing Settings",
        ),
        ReimbursementPlanView.factory(
            category=AdminCategory.WALLET_CONFIG.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Alegeus Plan",
        ),
        ReimbursementRequestCategoryView.factory(category=AdminCategory.WALLET_CONFIG.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ReimbursementOrgSettingsExpenseTypeView.factory(
            category=AdminCategory.WALLET_CONFIG.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ),
        EmployerHealthPlanView.factory(category=AdminCategory.WALLET_CONFIG.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        EmployerHealthPlanCoverageView.factory(category=AdminCategory.WALLET_CONFIG.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        EmployerHealthPlanCostSharingView.factory(category=AdminCategory.WALLET_CONFIG.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        FertilityClinicLocationEmployerHealthPlanTierView.factory(category=AdminCategory.WALLET_CONFIG.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ReimbursementOrgSettingsAllowedCategoryRuleView.factory(category=AdminCategory.WALLET_CONFIG.value),  # type: ignore[arg-type]
        # Fertility Clinics
        FertilityClinicView.factory(category=AdminCategory.WALLET_CONFIG.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        FertilityClinicLocationView.factory(category=AdminCategory.WALLET_CONFIG.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        FertilityClinicLocationContactView.factory(category=AdminCategory.WALLET_CONFIG.value),  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        FertilityClinicUserProfileView.factory(
            category=AdminCategory.WALLET_CONFIG.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Fertility Clinic Users",
        ),
        FeeScheduleView.factory(
            category=AdminCategory.WALLET_CONFIG.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Fertility Clinic Fee Schedules",
        ),
        ReimbursementPlanCoverageTierView.factory(
            category=AdminCategory.WALLET_CONFIG.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Alegeus Plan Coverage Tier",
        ),
        CostBreakdownIRSMinimumDeductibleView.factory(
            category=AdminCategory.WALLET_CONFIG.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="IRS Minimum Deductible",
        ),
        ReimbursementRequestExchangeRatesView.factory(
            category=AdminCategory.WALLET_CONFIG.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Exchange Rates",
        ),
        CountryCurrencyCodeView.factory(
            category=AdminCategory.WALLET_CONFIG.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Country Currency Code",
        ),
        WalletClientReportConfigurationView.factory(
            category=AdminCategory.WALLET_REPORTING.value  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
        ),
        PayerListView.factory(
            category=AdminCategory.WALLET_CONFIG.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Direct Payment Benefits Payer",
        ),
        ReimbursementServiceCategoryView.factory(
            category=AdminCategory.WALLET_CONFIG.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Alegeus Service Category",
        ),
        WalletExpenseSubtypeView.factory(
            category=AdminCategory.WALLET_CONFIG.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Alegeus Service Category Code",
        ),
        # Dashboard
        ReimbursementWalletDashboardView.factory(
            category=AdminCategory.WALLET_CONFIG.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Wallet Dashboard",
        ),
        ReimbursementWalletDashboardCardView.factory(
            category=AdminCategory.WALLET_CONFIG.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Wallet Dashboard Card",
        ),
        ReimbursementWalletDashboardCardsView.factory(
            category=AdminCategory.WALLET_CONFIG.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Wallet Dashboard Cards",
        ),
        QuestionnaireGlobalProcedureView.factory(
            category=AdminCategory.WALLET.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Questionnaire Global Procedures",
        ),
        ReimbursementAccountTypeView.factory(
            category=AdminCategory.WALLET_CONFIG.value,  # type: ignore[arg-type] # Argument "category" to "factory" of "MavenAdminView" has incompatible type "str"; expected "Optional[AdminCategory]"
            name="Alegeus Account Type",
        ),
    )


class GlobalProceduresAdminLink(AuthenticatedMenuLink):
    read_permission = "read:global-procedures-admin"
    edit_permission = "edit:global-procedures-admin"
    create_permission = "create:global-procedures-admin"
    delete_permission = "delete:global-procedures-admin"


def get_links() -> Tuple[AuthenticatedMenuLink, ...]:
    return (
        GlobalProceduresAdminLink(
            name="Global Procedures Admin",
            category=AdminCategory.WALLET_CONFIG.value,
            url=constants.PROCEDURE_ADMIN_PATH,
            target="_blank",
        ),
    )
