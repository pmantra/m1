from datetime import date

import pytest

from cost_breakdown.constants import ClaimType
from cost_breakdown.pytests.factories import (
    CostBreakdownFactory,
    ReimbursementRequestToCostBreakdownFactory,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from wallet.models.constants import (
    BenefitTypes,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
    ReimbursementRequestType,
    WalletState,
)
from wallet.models.reimbursement import (
    ReimbursementAccountType,
    ReimbursementRequestCategory,
)
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
    ReimbursementOrgSettingCategoryAssociation,
)
from wallet.pytests.factories import (
    ReimbursementAccountTypeFactory,
    ReimbursementCycleCreditsFactory,
    ReimbursementCycleMemberCreditTransactionFactory,
    ReimbursementOrganizationSettingsFactory,
    ReimbursementOrgSettingCategoryAssociationFactory,
    ReimbursementPlanFactory,
    ReimbursementRequestCategoryExpenseTypesFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementRequestFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
)
from wallet.services.currency import DEFAULT_CURRENCY_CODE


@pytest.fixture(scope="function")
def cycle_dp_ros(enterprise_user) -> ReimbursementOrganizationSettings:
    org_setting = ReimbursementOrganizationSettingsFactory(
        organization_id=enterprise_user.organization.id,
        allowed_reimbursement_categories__no_categories=True,
        direct_payment_enabled=True,
    )
    return org_setting


@pytest.fixture(scope="function")
def currency_dp_ros(enterprise_user) -> ReimbursementOrganizationSettings:
    org_setting = ReimbursementOrganizationSettingsFactory(
        organization_id=enterprise_user.organization.id,
        allowed_reimbursement_categories__no_categories=True,
        direct_payment_enabled=True,
    )
    return org_setting


@pytest.fixture(scope="function")
def non_dp_ros(enterprise_user) -> ReimbursementOrganizationSettings:
    org_setting = ReimbursementOrganizationSettingsFactory(
        organization_id=enterprise_user.organization.id,
        allowed_reimbursement_categories__no_categories=True,
        direct_payment_enabled=False,
    )
    return org_setting


@pytest.fixture(scope="function")
def another_non_dp_ros(enterprise_user) -> ReimbursementOrganizationSettings:
    org_setting = ReimbursementOrganizationSettingsFactory(
        organization_id=enterprise_user.organization.id,
        allowed_reimbursement_categories__no_categories=True,
        direct_payment_enabled=False,
    )
    return org_setting


@pytest.fixture(scope="function")
def reimbursement_account_type() -> ReimbursementAccountType:
    account_type = ReimbursementAccountTypeFactory.create(alegeus_account_type="HRA")
    return account_type


@pytest.fixture(scope="function")
def currency_based_category(reimbursement_account_type) -> ReimbursementRequestCategory:
    plan = ReimbursementPlanFactory.create(
        reimbursement_account_type=reimbursement_account_type,
        alegeus_plan_id="FERTCURRENCY",
        start_date=date(year=2000, month=1, day=1),
        end_date=date(year=9999, month=12, day=31),
        is_hdhp=False,
    )
    category = ReimbursementRequestCategoryFactory.create(
        label="fertility-currency", reimbursement_plan=plan
    )
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category=category,
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
    )
    return category


@pytest.fixture(scope="function")
def cycle_based_category(reimbursement_account_type) -> ReimbursementRequestCategory:
    plan = ReimbursementPlanFactory.create(
        reimbursement_account_type=reimbursement_account_type,
        alegeus_plan_id="FERTCYCLE",
        start_date=date(year=2000, month=1, day=1),
        end_date=date(year=9999, month=12, day=31),
        is_hdhp=False,
    )
    category = ReimbursementRequestCategoryFactory.create(
        label="fertility-cycle", reimbursement_plan=plan
    )
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category=category,
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
    )
    return category


@pytest.fixture(scope="function")
def shared_adoption_category(
    reimbursement_account_type,
) -> ReimbursementRequestCategory:
    plan = ReimbursementPlanFactory.create(
        reimbursement_account_type=reimbursement_account_type,
        alegeus_plan_id="ADOPTION",
        start_date=date(year=2000, month=1, day=1),
        end_date=date(year=9999, month=12, day=31),
        is_hdhp=False,
    )
    category = ReimbursementRequestCategoryFactory.create(
        label="adoption", reimbursement_plan=plan
    )
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category=category,
        expense_type=ReimbursementRequestExpenseTypes.ADOPTION,
    )
    return category


@pytest.fixture(scope="function")
def shared_surrogacy_category(
    reimbursement_account_type,
) -> ReimbursementRequestCategory:
    plan = ReimbursementPlanFactory.create(
        reimbursement_account_type=reimbursement_account_type,
        alegeus_plan_id="SURROGACY",
        start_date=date(year=2000, month=1, day=1),
        end_date=date(year=9999, month=12, day=31),
        is_hdhp=False,
    )
    category = ReimbursementRequestCategoryFactory.create(
        label="surrogacy", reimbursement_plan=plan
    )
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category=category,
        expense_type=ReimbursementRequestExpenseTypes.SURROGACY,
    )
    return category


@pytest.fixture(scope="function")
def cycle_based_category_association(
    cycle_dp_ros, cycle_based_category
) -> ReimbursementOrgSettingCategoryAssociation:
    category_association = ReimbursementOrgSettingCategoryAssociationFactory.create(
        benefit_type=BenefitTypes.CYCLE,
        reimbursement_organization_settings=cycle_dp_ros,
        reimbursement_request_category=cycle_based_category,
        reimbursement_request_category_maximum=None,
        currency_code=None,
        num_cycles=10,
    )
    return category_association


@pytest.fixture(scope="function")
def currency_based_category_association(
    currency_dp_ros, currency_based_category
) -> ReimbursementOrgSettingCategoryAssociation:
    category_association = ReimbursementOrgSettingCategoryAssociationFactory.create(
        benefit_type=BenefitTypes.CURRENCY,
        reimbursement_organization_settings=currency_dp_ros,
        reimbursement_request_category=currency_based_category,
        reimbursement_request_category_maximum=25_000_00,
        currency_code=DEFAULT_CURRENCY_CODE,
    )
    return category_association


@pytest.fixture(scope="function")
def cycle_shared_adoption_category_association(
    cycle_dp_ros, shared_adoption_category
) -> ReimbursementOrgSettingCategoryAssociation:
    category_association = ReimbursementOrgSettingCategoryAssociationFactory.create(
        benefit_type=BenefitTypes.CURRENCY,
        reimbursement_organization_settings=cycle_dp_ros,
        reimbursement_request_category=shared_adoption_category,
        reimbursement_request_category_maximum=10_000_00,
        currency_code=DEFAULT_CURRENCY_CODE,
    )
    return category_association


@pytest.fixture(scope="function")
def cycle_shared_surrogacy_category_association(
    cycle_dp_ros, shared_surrogacy_category
) -> ReimbursementOrgSettingCategoryAssociation:
    category_association = ReimbursementOrgSettingCategoryAssociationFactory.create(
        benefit_type=BenefitTypes.CURRENCY,
        reimbursement_organization_settings=cycle_dp_ros,
        reimbursement_request_category=shared_surrogacy_category,
        reimbursement_request_category_maximum=10_000_00,
        currency_code=DEFAULT_CURRENCY_CODE,
    )
    return category_association


@pytest.fixture(scope="function")
def currency_shared_adoption_category_association(
    currency_dp_ros, shared_adoption_category
) -> ReimbursementOrgSettingCategoryAssociation:
    category_association = ReimbursementOrgSettingCategoryAssociationFactory.create(
        benefit_type=BenefitTypes.CURRENCY,
        reimbursement_organization_settings=currency_dp_ros,
        reimbursement_request_category=shared_adoption_category,
        reimbursement_request_category_maximum=10_000_00,
        currency_code=DEFAULT_CURRENCY_CODE,
    )
    return category_association


@pytest.fixture(scope="function")
def currency_shared_surrogacy_category_association(
    currency_dp_ros, shared_surrogacy_category
) -> ReimbursementOrgSettingCategoryAssociation:
    category_association = ReimbursementOrgSettingCategoryAssociationFactory.create(
        benefit_type=BenefitTypes.CURRENCY,
        reimbursement_organization_settings=currency_dp_ros,
        reimbursement_request_category=shared_surrogacy_category,
        reimbursement_request_category_maximum=10_000_00,
        currency_code=DEFAULT_CURRENCY_CODE,
    )
    return category_association


@pytest.fixture(scope="function")
def another_non_dp_category_association(
    another_non_dp_ros, currency_based_category
) -> ReimbursementOrgSettingCategoryAssociation:
    category_association = ReimbursementOrgSettingCategoryAssociationFactory.create(
        benefit_type=BenefitTypes.CURRENCY,
        reimbursement_organization_settings=another_non_dp_ros,
        reimbursement_request_category=currency_based_category,
        reimbursement_request_category_maximum=10_000_00,
        currency_code=DEFAULT_CURRENCY_CODE,
    )
    return category_association


@pytest.fixture(scope="function")
def configured_dp_cycle_ros(
    cycle_dp_ros,
    cycle_based_category_association,
    cycle_shared_adoption_category_association,
    cycle_shared_surrogacy_category_association,
):
    return cycle_dp_ros


@pytest.fixture(scope="function")
def configured_dp_currency_ros(
    currency_dp_ros,
    currency_based_category_association,
    currency_shared_adoption_category_association,
    currency_shared_surrogacy_category_association,
):
    return currency_dp_ros


@pytest.fixture(scope="function")
def configured_another_non_dp_currency_ros(
    another_non_dp_ros, another_non_dp_category_association
):
    return another_non_dp_ros


@pytest.fixture(scope="function")
def non_dp_wallet(enterprise_user, non_dp_ros):
    wallet = ReimbursementWalletFactory.create(
        reimbursement_organization_settings=non_dp_ros,
        member=enterprise_user,
        state=WalletState.QUALIFIED,
    )
    _ = ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )
    return wallet


@pytest.fixture(scope="function")
def wallet_cycle_based(
    enterprise_user, configured_dp_cycle_ros, cycle_based_category_association
):
    wallet = ReimbursementWalletFactory.create(
        reimbursement_organization_settings=configured_dp_cycle_ros,
        member=enterprise_user,
        state=WalletState.QUALIFIED,
    )
    _ = ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )
    enterprise_user.member_profile.country_code = "US"

    cycle_credits = ReimbursementCycleCreditsFactory.create(
        reimbursement_wallet_id=wallet.id,
        reimbursement_organization_settings_allowed_category_id=cycle_based_category_association.id,
        amount=12,
    )

    ReimbursementCycleMemberCreditTransactionFactory.create(
        reimbursement_cycle_credits_id=cycle_credits.id,
        amount=12,
        notes="Initial Fund",
    )

    return wallet


@pytest.fixture(scope="function")
def wallet_currency_based(
    enterprise_user, configured_dp_currency_ros, currency_based_category_association
):
    wallet = ReimbursementWalletFactory.create(
        reimbursement_organization_settings=configured_dp_currency_ros,
        member=enterprise_user,
        state=WalletState.QUALIFIED,
    )
    _ = ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )
    enterprise_user.member_profile.country_code = "US"

    return wallet


@pytest.fixture(scope="function")
def cycle_based_reimbursed_reimbursement(
    wallet_cycle_based, cycle_based_category, expense_subtypes
):

    reimbursement = ReimbursementRequestFactory.create(
        state=ReimbursementRequestState.REIMBURSED,
        wallet=wallet_cycle_based,
        category=cycle_based_category,
        amount=1_000_00,
        benefit_currency_code=DEFAULT_CURRENCY_CODE,
        usd_amount=1_000_00,
        transaction_amount=1_000_00,
        transaction_currency_code=DEFAULT_CURRENCY_CODE,
        wallet_expense_subtype=expense_subtypes["FIVF"],
    )

    ReimbursementCycleMemberCreditTransactionFactory.create(
        reimbursement_cycle_credits=wallet_cycle_based.cycle_credits[0],
        reimbursement_request=reimbursement,
        amount=3,
    )

    return reimbursement


@pytest.fixture(scope="function")
def currency_based_reimbursed_reimbursement(
    wallet_currency_based, currency_based_category, expense_subtypes
):
    reimbursement = ReimbursementRequestFactory.create(
        state=ReimbursementRequestState.REIMBURSED,
        wallet=wallet_currency_based,
        category=currency_based_category,
        amount=1_000_00,
        benefit_currency_code=DEFAULT_CURRENCY_CODE,
        usd_amount=1_000_00,
        transaction_amount=1_000_00,
        transaction_currency_code=DEFAULT_CURRENCY_CODE,
        wallet_expense_subtype=expense_subtypes["FIVF"],
        reimbursement_type=ReimbursementRequestType.MANUAL,
    )

    return reimbursement


@pytest.fixture(scope="function")
def currency_based_pending_reimbursement(
    wallet_currency_based, currency_based_category, expense_subtypes
):
    reimbursement = ReimbursementRequestFactory.create(
        state=ReimbursementRequestState.PENDING,
        wallet=wallet_currency_based,
        category=currency_based_category,
        amount=1_000_00,
        benefit_currency_code=DEFAULT_CURRENCY_CODE,
        usd_amount=1_000_00,
        transaction_amount=1_000_00,
        transaction_currency_code=DEFAULT_CURRENCY_CODE,
        wallet_expense_subtype=expense_subtypes["FIVF"],
        reimbursement_type=ReimbursementRequestType.MANUAL,
    )

    return reimbursement


@pytest.fixture(scope="function")
def dp_currency_based_reimbursed_reimbursement(
    wallet_currency_based, currency_based_category, expense_subtypes
):
    reimbursement = ReimbursementRequestFactory.create(
        state=ReimbursementRequestState.REIMBURSED,
        wallet=wallet_currency_based,
        category=currency_based_category,
        amount=1_000_00,
        benefit_currency_code=DEFAULT_CURRENCY_CODE,
        usd_amount=1_000_00,
        transaction_amount=1_000_00,
        transaction_currency_code=DEFAULT_CURRENCY_CODE,
        reimbursement_type=ReimbursementRequestType.DIRECT_BILLING,
    )

    return reimbursement


@pytest.fixture(scope="function")
def dp_employer_currency_based_reimbursed_reimbursement(
    wallet_currency_based,
    currency_based_category,
    expense_subtypes,
    currency_based_scheduled_treatment_procedure,
    currency_based_cost_breakdown,
    dp_currency_based_reimbursed_reimbursement,
):
    ReimbursementRequestToCostBreakdownFactory.create(
        reimbursement_request_id=dp_currency_based_reimbursed_reimbursement.id,
        treatment_procedure_uuid=currency_based_cost_breakdown.treatment_procedure_uuid,
        cost_breakdown_id=currency_based_cost_breakdown.id,
        claim_type=ClaimType.EMPLOYER,
    )
    return dp_currency_based_reimbursed_reimbursement


@pytest.fixture(scope="function")
def currency_based_scheduled_treatment_procedure(
    wallet_currency_based, currency_based_category
):
    return TreatmentProcedureFactory.create(
        reimbursement_wallet_id=wallet_currency_based.id,
        reimbursement_request_category=currency_based_category,
        status=TreatmentProcedureStatus.SCHEDULED,
    )


@pytest.fixture(scope="function")
def currency_based_cancelled_treatment_procedure(
    wallet_currency_based, currency_based_category
):
    return TreatmentProcedureFactory.create(
        reimbursement_wallet_id=wallet_currency_based.id,
        reimbursement_request_category=currency_based_category,
        status=TreatmentProcedureStatus.CANCELLED,
    )


@pytest.fixture(scope="function")
def currency_based_cost_breakdown(
    wallet_currency_based, currency_based_scheduled_treatment_procedure
):
    return CostBreakdownFactory.create(
        wallet_id=wallet_currency_based.id,
        treatment_procedure_uuid=currency_based_scheduled_treatment_procedure.uuid,
    )


@pytest.fixture(scope="function")
def dp_employee_currency_based_reimbursed_reimbursement(
    wallet_currency_based,
    currency_based_category,
    expense_subtypes,
    currency_based_scheduled_treatment_procedure,
    currency_based_cost_breakdown,
    dp_currency_based_reimbursed_reimbursement,
):
    ReimbursementRequestToCostBreakdownFactory.create(
        reimbursement_request_id=dp_currency_based_reimbursed_reimbursement.id,
        treatment_procedure_uuid=currency_based_cost_breakdown.treatment_procedure_uuid,
        cost_breakdown_id=currency_based_cost_breakdown.id,
        claim_type=ClaimType.EMPLOYEE_DEDUCTIBLE,
    )
    return dp_currency_based_reimbursed_reimbursement


@pytest.fixture(scope="function")
def cycle_based_approved_reimbursement(
    wallet_cycle_based, cycle_based_category, expense_subtypes
):

    reimbursement = ReimbursementRequestFactory.create(
        state=ReimbursementRequestState.APPROVED,
        wallet=wallet_cycle_based,
        category=cycle_based_category,
        amount=1_000_00,
        benefit_currency_code=DEFAULT_CURRENCY_CODE,
        usd_amount=1_000_00,
        transaction_amount=1_000_00,
        transaction_currency_code=DEFAULT_CURRENCY_CODE,
        wallet_expense_subtype=expense_subtypes["FIVF"],
    )

    ReimbursementCycleMemberCreditTransactionFactory.create(
        reimbursement_cycle_credits=wallet_cycle_based.cycle_credits[0],
        reimbursement_request=reimbursement,
        amount=3,
    )

    return reimbursement


@pytest.fixture(scope="function")
def cycle_based_pending_reimbursement(
    wallet_cycle_based, cycle_based_category, expense_subtypes
):

    reimbursement = ReimbursementRequestFactory.create(
        state=ReimbursementRequestState.PENDING,
        wallet=wallet_cycle_based,
        category=cycle_based_category,
        amount=1_000_00,
        benefit_currency_code=DEFAULT_CURRENCY_CODE,
        usd_amount=1_000_00,
        transaction_amount=1_000_00,
        transaction_currency_code=DEFAULT_CURRENCY_CODE,
        wallet_expense_subtype=expense_subtypes["FIVF"],
    )

    ReimbursementCycleMemberCreditTransactionFactory.create(
        reimbursement_cycle_credits=wallet_cycle_based.cycle_credits[0],
        reimbursement_request=reimbursement,
        amount=3,
    )

    return reimbursement
