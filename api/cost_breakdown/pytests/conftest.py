import datetime

import pytest

from cost_breakdown.cost_breakdown_processor import CostBreakdownProcessor
from cost_breakdown.models.cost_breakdown import CostBreakdown
from cost_breakdown.pytests.factories import CostBreakdownFactory, RTETransactionFactory
from direct_payment.clinic.pytests.factories import FeeScheduleGlobalProceduresFactory
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from payer_accumulator.common import PayerName
from payer_accumulator.pytests.factories import PayerFactory
from pytests.common.global_procedures.factories import GlobalProcedureFactory
from pytests.factories import DefaultUserFactory
from wallet.models.constants import (
    CategoryRuleAccessLevel,
    CategoryRuleAccessSource,
    CostSharingCategory,
    CostSharingType,
    CoverageType,
    FamilyPlanType,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
    WalletState,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.reimbursement_organization_settings import (
    EmployerHealthPlanCostSharing,
)
from wallet.pytests.conftest import SUPPORTED_CURRENCY_CODE_MINOR_UNIT
from wallet.pytests.factories import (
    CountryCurrencyCodeFactory,
    EmployerHealthPlanCoverageFactory,
    EmployerHealthPlanFactory,
    MemberHealthPlanFactory,
    ReimbursementAccountTypeFactory,
    ReimbursementCycleCreditsFactory,
    ReimbursementCycleMemberCreditTransactionFactory,
    ReimbursementOrganizationSettingsFactory,
    ReimbursementOrgSettingCategoryAssociationFactory,
    ReimbursementPlanFactory,
    ReimbursementRequestCategoryExpenseTypesFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementRequestFactory,
    ReimbursementWalletAllowedCategorySettingsFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
)

# import the new-style wallet fixtures
from wallet.pytests.fixtures import *  # noqa: F403,F401


@pytest.fixture(scope="function", autouse=True)
def supported_currency_codes():
    for currency_code, minor_unit in SUPPORTED_CURRENCY_CODE_MINOR_UNIT:
        CountryCurrencyCodeFactory.create(
            country_alpha_2=currency_code,
            currency_code=currency_code,
            minor_unit=minor_unit,
        )


@pytest.fixture(scope="function")
def cost_breakdown_proc():
    processor = CostBreakdownProcessor()
    return processor


@pytest.fixture(scope="function")
def treatment_procedure(wallet):
    category = ReimbursementRequestCategoryFactory.create(label="fertility")

    return TreatmentProcedureFactory.create(
        member_id=wallet.member.id,
        reimbursement_wallet_id=wallet.id,
        reimbursement_request_category=category,
        cost=34,
        start_date=datetime.date(year=2024, month=1, day=1),
        end_date=datetime.date(year=2024, month=1, day=2),
    )


@pytest.fixture(scope="function")
def treatment_procedure_cycle_based(
    global_procedure, wallet_cycle_based, enterprise_user
):
    fee_schedule_global_procedures = FeeScheduleGlobalProceduresFactory(
        cost=50_000, global_procedure_id=global_procedure["id"]
    )
    fee_schedule = fee_schedule_global_procedures.fee_schedule
    procedure_name = global_procedure["name"]

    return TreatmentProcedureFactory(
        member_id=enterprise_user.id,
        reimbursement_wallet_id=wallet_cycle_based.id,
        fee_schedule=fee_schedule,
        global_procedure_id=global_procedure["id"],
        procedure_name=procedure_name,
        cost=fee_schedule_global_procedures.cost,
        cost_credit=global_procedure["credits"],
        reimbursement_request_category=wallet_cycle_based.get_direct_payment_category,
    )


@pytest.fixture(scope="function")
def treatment_procedure_dependent(user_dependent):
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    return TreatmentProcedureFactory.create(
        member_id=user_dependent.id, reimbursement_request_category=category
    )


@pytest.fixture(scope="function")
def rx_procedure(enterprise_user):
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    return TreatmentProcedureFactory.create(
        member_id=enterprise_user.id,
        reimbursement_request_category=category,
        procedure_type=TreatmentProcedureType.PHARMACY,
    )


@pytest.fixture
def global_procedure():
    return GlobalProcedureFactory.create(credits=5)


@pytest.fixture(scope="function")
def user_dependent():
    user = DefaultUserFactory.create(first_name="fiona", last_name="fee")
    return user


@pytest.fixture(scope="function")
def employer_health_plan_cost_sharing():
    cost_sharing = [
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COINSURANCE,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            percent=0.05,
        ),
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COPAY,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            absolute_amount=2000,
        ),
    ]
    return cost_sharing


@pytest.fixture(scope="function")
def employer_health_plan_cost_sharing_tiered():
    cost_sharing = [
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COINSURANCE,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            percent=0.05,
        ),
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COPAY,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            absolute_amount=2000,
            second_tier_absolute_amount=4000,
        ),
    ]
    return cost_sharing


@pytest.fixture(scope="function")
def rx_employer_health_plan_cost_sharing():
    cost_sharing = [
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COINSURANCE,
            cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS,
            percent=0.05,
        ),
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COPAY,
            cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS,
            absolute_amount=2000,
        ),
    ]
    return cost_sharing


@pytest.fixture(scope="function")
def employer_health_plan(employer_health_plan_cost_sharing):
    org_settings = ReimbursementOrganizationSettingsFactory.create(
        organization_id=1,
        deductible_accumulation_enabled=True,
    )
    payer = PayerFactory.create(id=1, payer_name=PayerName.Cigna, payer_code="00001")
    return EmployerHealthPlanFactory.create(
        reimbursement_organization_settings=org_settings,
        cost_sharings=employer_health_plan_cost_sharing,
        benefits_payer_id=payer.id,
        coverage=[
            EmployerHealthPlanCoverageFactory.create(
                individual_deductible=200_000,
                individual_oop=400_000,
                family_deductible=400_000,
                family_oop=600_000,
            ),
            EmployerHealthPlanCoverageFactory.create(
                coverage_type=CoverageType.RX,
                individual_deductible=50000,
                individual_oop=100_000,
                family_deductible=100_000,
                family_oop=200_000,
            ),
            EmployerHealthPlanCoverageFactory.create(
                individual_deductible=200_000,
                individual_oop=400_000,
                family_deductible=400_000,
                family_oop=600_000,
                plan_type=FamilyPlanType.FAMILY,
            ),
            EmployerHealthPlanCoverageFactory.create(
                coverage_type=CoverageType.RX,
                individual_deductible=50000,
                individual_oop=100_000,
                family_deductible=100_000,
                family_oop=200_000,
                plan_type=FamilyPlanType.FAMILY,
            ),
        ],
    )


@pytest.fixture(scope="function")
def employer_health_plan_no_deductible_oop_max(employer_health_plan_cost_sharing):
    org_settings = ReimbursementOrganizationSettingsFactory.create(
        organization_id=1,
        deductible_accumulation_enabled=True,
    )
    return EmployerHealthPlanFactory.create(
        reimbursement_organization_settings=org_settings,
        cost_sharings=employer_health_plan_cost_sharing,
        coverage=[
            EmployerHealthPlanCoverageFactory.create(
                individual_deductible=0,
                individual_oop=0,
                family_deductible=0,
                family_oop=0,
                max_oop_per_covered_individual=100,
                plan_type=FamilyPlanType.FAMILY,
            ),
            EmployerHealthPlanCoverageFactory.create(
                individual_deductible=0,
                individual_oop=0,
                family_deductible=0,
                family_oop=0,
                max_oop_per_covered_individual=100,
                plan_type=FamilyPlanType.INDIVIDUAL,
            ),
        ],
    )


@pytest.fixture(scope="function")
def employer_health_plan_embedded(employer_health_plan_cost_sharing):
    org_settings = ReimbursementOrganizationSettingsFactory.create(
        organization_id=1,
        deductible_accumulation_enabled=True,
    )
    return EmployerHealthPlanFactory.create(
        reimbursement_organization_settings=org_settings,
        cost_sharings=employer_health_plan_cost_sharing,
        is_oop_embedded=True,
        is_deductible_embedded=True,
    )


@pytest.fixture(scope="function")
def member_health_plan(employer_health_plan, wallet, enterprise_user):
    plan = MemberHealthPlanFactory.create(
        reimbursement_wallet=wallet,
        reimbursement_wallet_id=wallet.id,
        employer_health_plan=employer_health_plan,
        plan_type=FamilyPlanType.INDIVIDUAL,
        is_subscriber=True,
        subscriber_insurance_id="W123456",
        subscriber_first_name="alice",
        subscriber_last_name="paul",
        member_id=enterprise_user.id,
    )
    return plan


@pytest.fixture(scope="function")
def member_health_plan_dependent(employer_health_plan, wallet):
    plan = MemberHealthPlanFactory.create(
        reimbursement_wallet=wallet,
        patient_date_of_birth=datetime.date(2010, 1, 1),
        employer_health_plan=employer_health_plan,
        plan_type=FamilyPlanType.FAMILY,
        is_subscriber=False,
    )
    return plan


@pytest.fixture(scope="function")
def member_health_plan_no_name(employer_health_plan, wallet):
    plan = MemberHealthPlanFactory.create(
        reimbursement_wallet=wallet,
        employer_health_plan=employer_health_plan,
        plan_type=FamilyPlanType.INDIVIDUAL,
        is_subscriber=True,
        subscriber_first_name=None,
        subscriber_last_name=None,
    )
    return plan


@pytest.fixture(scope="function")
def member_health_plan_dependent_no_name(employer_health_plan, wallet):
    plan = MemberHealthPlanFactory.create(
        reimbursement_wallet=wallet,
        employer_health_plan=employer_health_plan,
        plan_type=FamilyPlanType.INDIVIDUAL,
        is_subscriber=False,
        patient_first_name=None,
        patient_last_name=None,
    )
    return plan


@pytest.fixture(scope="function")
def member_health_plan_rx_not_included(
    wallet_deductible_accumulation,
    rx_employer_health_plan_cost_sharing,
    enterprise_user,
):
    org_settings = ReimbursementOrganizationSettingsFactory.create(
        organization_id=1,
        deductible_accumulation_enabled=True,
    )
    employer_health_plan = EmployerHealthPlanFactory.create(
        reimbursement_organization_settings=org_settings,
        cost_sharings=rx_employer_health_plan_cost_sharing,
        rx_integrated=False,
        coverage=[
            EmployerHealthPlanCoverageFactory.create(
                coverage_type=CoverageType.RX,
                plan_type=FamilyPlanType.FAMILY,
                individual_deductible=200_000,
                individual_oop=400_000,
                family_deductible=400_000,
                family_oop=600_000,
            ),
            EmployerHealthPlanCoverageFactory.create(
                coverage_type=CoverageType.RX,
                individual_deductible=200_000,
                individual_oop=400_000,
                family_deductible=400_000,
                family_oop=600_000,
            ),
        ],
    )
    return MemberHealthPlanFactory.create(
        reimbursement_wallet=wallet_deductible_accumulation,
        reimbursement_wallet_id=wallet_deductible_accumulation.id,
        employer_health_plan=employer_health_plan,
        plan_type=FamilyPlanType.INDIVIDUAL,
        is_subscriber=True,
        member_id=enterprise_user.id,
    )


@pytest.fixture(scope="function")
def member_health_plan_embedded_plan(
    employer_health_plan_embedded, wallet, enterprise_user
):
    plan = MemberHealthPlanFactory.create(
        reimbursement_wallet=wallet,
        reimbursement_wallet_id=wallet.id,
        employer_health_plan=employer_health_plan_embedded,
        plan_type=FamilyPlanType.FAMILY,
        is_subscriber=True,
        subscriber_insurance_id="W123456",
        subscriber_first_name="alice",
        subscriber_last_name="paul",
        member_id=enterprise_user.id,
    )
    return plan


@pytest.fixture(scope="function")
def wallet(enterprise_user):
    wallet = ReimbursementWalletFactory.create(state=WalletState.QUALIFIED)
    wallet_user = ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        status=WalletUserStatus.ACTIVE,
        type=WalletUserType.EMPLOYEE,
    )
    wallet_user.member.member_profile.country_code = "US"
    wallet.member.first_name = "Donna"
    wallet.member.last_name = "Williams"

    wallet.reimbursement_organization_settings.direct_payment_enabled = True
    category_association = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[0]
    )
    ReimbursementWalletAllowedCategorySettingsFactory.create(
        reimbursement_organization_settings_allowed_category_id=category_association.id,
        reimbursement_wallet_id=wallet.id,
        access_level=CategoryRuleAccessLevel.FULL_ACCESS,
        access_level_source=CategoryRuleAccessSource.NO_RULES,
    )
    category_association.is_direct_payment_eligible = True
    request_category = category_association.reimbursement_request_category
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category=request_category,
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
    )
    year = datetime.datetime.now().year
    ReimbursementPlanFactory.create(
        category=request_category,
        start_date=datetime.datetime(year, 1, 1).date(),
        end_date=datetime.datetime(year, 12, 31).date(),
    )
    return wallet


@pytest.fixture(scope="function")
def direct_payment_wallet(enterprise_user):
    plan = ReimbursementPlanFactory.create(
        reimbursement_account_type=ReimbursementAccountTypeFactory.create(
            alegeus_account_type="HRA"
        ),
        alegeus_plan_id="FAMILYFUND",
        start_date=datetime.date(year=2020, month=1, day=3),
        end_date=datetime.date(year=2199, month=12, day=31),
        is_hdhp=False,
        auto_renew=True,
        plan_type="ANNUAL",
    )
    wallet = ReimbursementWalletFactory.create(
        member=enterprise_user,
        state=WalletState.QUALIFIED,
        primary_expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
        payments_customer_id="00000000-0000-0000-0000-000000000000",
    )
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )
    org_settings = wallet.reimbursement_organization_settings
    org_settings.direct_payment_enabled = True

    category = ReimbursementRequestCategoryFactory.create(
        label="fertility", reimbursement_plan=plan
    )
    category_association = ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_organization_settings=org_settings,
        reimbursement_request_category=category,
        reimbursement_request_category_maximum=5000,
    )
    ReimbursementWalletAllowedCategorySettingsFactory.create(
        reimbursement_organization_settings_allowed_category_id=category_association.id,
        reimbursement_wallet_id=wallet.id,
        access_level=CategoryRuleAccessLevel.FULL_ACCESS,
        access_level_source=CategoryRuleAccessSource.NO_RULES,
    )
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
        reimbursement_request_category=category,
    )
    return wallet


@pytest.fixture(scope="function")
def wallet_category(wallet):
    return wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ].reimbursement_request_category


@pytest.fixture
def wallet_cycle_based(session, enterprise_user):
    org_settings = ReimbursementOrganizationSettingsFactory(
        organization_id=enterprise_user.organization.id,
        allowed_reimbursement_categories__cycle_based=True,
        direct_payment_enabled=True,
    )
    wallet = ReimbursementWalletFactory.create(
        reimbursement_organization_settings=org_settings,
        member=enterprise_user,
        state=WalletState.QUALIFIED,
    )
    wallet_user = ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        status=WalletUserStatus.ACTIVE,
        type=WalletUserType.EMPLOYEE,
    )
    wallet_user.member.member_profile.country_code = "US"
    category_association = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[0]
    )
    category_association.is_direct_payment_eligible = True
    request_category = category_association.reimbursement_request_category
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category=request_category,
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
    )
    year = datetime.datetime.utcnow().year
    request_category.reimbursement_plan = ReimbursementPlanFactory.create(
        reimbursement_account_type=ReimbursementAccountTypeFactory.create(
            alegeus_account_type="HRA"
        ),
        alegeus_plan_id="FERTILITY",
        start_date=datetime.date(year=year, month=1, day=1),
        end_date=datetime.date(year=year, month=12, day=31),
        is_hdhp=False,
    )
    credits = ReimbursementCycleCreditsFactory.create(
        reimbursement_wallet_id=wallet.id,
        reimbursement_organization_settings_allowed_category_id=category_association.id,
        amount=60,
    )
    ReimbursementCycleMemberCreditTransactionFactory.create(
        reimbursement_cycle_credits_id=credits.id,
        amount=60,
        notes="Initial Fund",
    )
    ReimbursementWalletAllowedCategorySettingsFactory.create(
        reimbursement_organization_settings_allowed_category_id=category_association.id,
        reimbursement_wallet_id=wallet.id,
        access_level=CategoryRuleAccessLevel.FULL_ACCESS,
        access_level_source=CategoryRuleAccessSource.NO_RULES,
    )
    return wallet


@pytest.fixture(scope="function")
def wallet_cycle_based_category(wallet_cycle_based):
    return wallet_cycle_based.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ].reimbursement_request_category


@pytest.fixture(scope="function")
def member_hdhp_plan(employer_health_plan, wallet):
    employer_health_plan.is_hdhp = True
    plan = MemberHealthPlanFactory.create(
        reimbursement_wallet=wallet,
        employer_health_plan=employer_health_plan,
        employer_health_plan_id=employer_health_plan.id,
        plan_type=FamilyPlanType.INDIVIDUAL,
        is_subscriber=True,
    )
    return plan


@pytest.fixture(scope="function")
def unlimited_member_hdhp_plan(employer_health_plan, unlimited_direct_payment_wallet):
    employer_health_plan.is_hdhp = True
    plan = MemberHealthPlanFactory.create(
        reimbursement_wallet=unlimited_direct_payment_wallet,
        employer_health_plan=employer_health_plan,
        employer_health_plan_id=employer_health_plan.id,
        plan_type=FamilyPlanType.INDIVIDUAL,
        is_subscriber=True,
    )
    return plan


@pytest.fixture(scope="function")
def wallet_hdhp_plan(member_hdhp_plan, wallet):
    wallet.member_health_plan = [member_hdhp_plan]
    return wallet


@pytest.fixture(scope="function")
def unlimited_wallet_hdhp_plan(
    unlimited_member_hdhp_plan, unlimited_direct_payment_wallet
):
    unlimited_direct_payment_wallet.member_health_plan = [unlimited_member_hdhp_plan]
    return unlimited_direct_payment_wallet


@pytest.fixture(scope="function")
def wallet_deductible_accumulation(treatment_procedure, employer_health_plan):
    labels_with_max_and_currency_code = [
        (treatment_procedure.reimbursement_request_category.label, 10_000, None)
    ]
    org_settings = ReimbursementOrganizationSettingsFactory.create(
        organization_id=1,
        deductible_accumulation_enabled=True,
        allowed_reimbursement_categories=labels_with_max_and_currency_code,
    )
    wallet = ReimbursementWalletFactory.create(
        reimbursement_organization_settings=org_settings,
        state=WalletState.QUALIFIED,
    )
    today = datetime.date.today()
    for (
        category_assoc
    ) in wallet.reimbursement_organization_settings.allowed_reimbursement_categories:
        category = category_assoc.reimbursement_request_category
        ReimbursementPlanFactory.create(
            category=category,
            start_date=today - datetime.timedelta(days=2),
            end_date=today + datetime.timedelta(days=2),
        )
        ReimbursementWalletAllowedCategorySettingsFactory.create(
            reimbursement_organization_settings_allowed_category_id=category_assoc.id,
            reimbursement_wallet_id=wallet.id,
            access_level=CategoryRuleAccessLevel.FULL_ACCESS,
            access_level_source=CategoryRuleAccessSource.NO_RULES,
        )

        ReimbursementRequestFactory.create(
            wallet=wallet,
            category=category,
            amount=100,
            state=ReimbursementRequestState.REIMBURSED,
        )

        ReimbursementRequestFactory.create(
            wallet=wallet,
            category=category,
            amount=100,
            state=ReimbursementRequestState.APPROVED,
        )
    plan = MemberHealthPlanFactory.create(
        reimbursement_wallet=wallet,
        plan_type=FamilyPlanType.INDIVIDUAL,
        employer_health_plan=employer_health_plan,
    )
    wallet.member_health_plan = [plan]
    return wallet


@pytest.fixture(scope="function")
def wallet_no_deductible_accumulation(treatment_procedure, employer_health_plan):
    labels_with_max = [
        [treatment_procedure.reimbursement_request_category.label, 10_000]
    ]
    org_settings = ReimbursementOrganizationSettingsFactory.create(
        organization_id=1,
        deductible_accumulation_enabled=False,
        allowed_reimbursement_categories=labels_with_max,
    )
    wallet = ReimbursementWalletFactory.create(
        reimbursement_organization_settings=org_settings,
        state=WalletState.QUALIFIED,
    )
    today = datetime.date.today()
    for (
        category_assoc
    ) in wallet.reimbursement_organization_settings.allowed_reimbursement_categories:
        category = category_assoc.reimbursement_request_category
        ReimbursementPlanFactory.create(
            category=category,
            start_date=today - datetime.timedelta(days=2),
            end_date=today + datetime.timedelta(days=2),
        )
        ReimbursementWalletAllowedCategorySettingsFactory.create(
            reimbursement_organization_settings_allowed_category_id=category_assoc.id,
            reimbursement_wallet_id=wallet.id,
            access_level=CategoryRuleAccessLevel.FULL_ACCESS,
            access_level_source=CategoryRuleAccessSource.NO_RULES,
        )
    plan = MemberHealthPlanFactory.create(
        reimbursement_wallet=wallet,
        plan_type=FamilyPlanType.INDIVIDUAL,
        employer_health_plan=employer_health_plan,
    )
    wallet.member_health_plan = [plan]
    return wallet


@pytest.fixture(scope="function")
def rte_irs_unmet():
    return RTETransactionFactory.create(
        id=1,
        response={
            "individual_deductible": 0,
            "individual_deductible_remaining": 0,
            "individual_oop": 300_000,
            "individual_oop_remaining": 300_000,
            "family_deductible": 0,
            "family_deductible_remaining": 0,
            "family_oop": 600_000,
            "family_oop_remaining": 600_000,
        },
    )


@pytest.fixture(scope="function")
def rte_irs_partial():
    return RTETransactionFactory.create(
        id=1,
        response={
            "individual_deductible": 0,
            "individual_deductible_remaining": 0,
            "individual_oop": 300_000,
            "individual_oop_remaining": 250_000,
            "family_deductible": 0,
            "family_deductible_remaining": 0,
            "family_oop": 600_000,
            "family_oop_remaining": 400_000,
        },
    )


@pytest.fixture(scope="function")
def rte_irs_met():
    return RTETransactionFactory.create(
        id=1,
        response={
            "individual_deductible": 0,
            "individual_deductible_remaining": 0,
            "individual_oop": 300_000,
            "individual_oop_remaining": 150_000,
            "family_deductible": 0,
            "family_deductible_remaining": 0,
            "family_oop": 600_000,
            "family_oop_remaining": 300_000,
        },
    )


@pytest.fixture(scope="function")
def rte_transaction_with_oop_remaining():
    return RTETransactionFactory.create(
        id=1,
        response={
            "family_deductible": 150_000,
            "individual_oop": 150_000,
            "family_oop": 300_000,
            "individual_deductible_remaining": 0,
            "individual_deductible": 150_000,
            "coinsurance": 0.2,
            "family_deductible_remaining": 10_000,
            "individual_oop_remaining": 10_000,
            "family_oop_remaining": 229_309,
        },
        response_code=200,
        request={},
    )


@pytest.fixture(scope="function")
def rte_transaction_with_hra_remaining():
    return RTETransactionFactory.create(
        id=1,
        response={
            "family_deductible": 150_000,
            "individual_oop": 150_000,
            "family_oop": 300_000,
            "individual_deductible_remaining": 0,
            "individual_deductible": 150_000,
            "coinsurance": 0.2,
            "family_deductible_remaining": 10_000,
            "individual_oop_remaining": 10_000,
            "family_oop_remaining": 229_309,
            "hra_remaining": 10_000,
        },
        response_code=200,
        request={},
    )


@pytest.fixture
def cost_breakdown():
    return CostBreakdownFactory.create(wallet_id=44444)


@pytest.fixture
def cost_breakdowns_in_one_treatment_procedure():
    first_cb: CostBreakdown = CostBreakdownFactory.create(wallet_id=44444)
    second_cb: CostBreakdown = CostBreakdownFactory.create(
        id=first_cb.id + 1,
        wallet_id=first_cb.wallet_id,
        treatment_procedure_uuid=first_cb.treatment_procedure_uuid,
    )
    third_cb: CostBreakdown = CostBreakdownFactory.create(
        id=second_cb.id + 1,
        wallet_id=first_cb.wallet_id,
        treatment_procedure_uuid=first_cb.treatment_procedure_uuid,
    )
    return [first_cb, second_cb, third_cb]


@pytest.fixture(scope="function")
def pending_cycle_reimbursement_request(wallet_cycle_based):
    category = wallet_cycle_based.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ].reimbursement_request_category
    return ReimbursementRequestFactory.create(
        id=1234,
        person_receiving_service_id=1,
        procedure_type=TreatmentProcedureType.MEDICAL.value,
        cost_sharing_category=CostSharingCategory.MEDICAL_CARE.value,
        state=ReimbursementRequestState.PENDING,
        cost_credit=5,
        wallet=wallet_cycle_based,
        category=category,
        amount=100,
    )


@pytest.fixture(scope="function")
def pending_currency_reimbursement_request(wallet):
    category = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
    )
    return ReimbursementRequestFactory.create(
        id=1235,
        person_receiving_service_id=1,
        procedure_type=TreatmentProcedureType.MEDICAL.value,
        cost_sharing_category=CostSharingCategory.MEDICAL_CARE.value,
        state=ReimbursementRequestState.PENDING,
        wallet=wallet,
        category=category,
        amount=100,
    )


@pytest.fixture(scope="function")
def member_health_plan_now(employer_health_plan, wallet, enterprise_user):
    plan = MemberHealthPlanFactory.create(
        employer_health_plan=employer_health_plan,
        is_subscriber=True,
        member_id=enterprise_user.id,
        reimbursement_wallet=wallet,
        plan_start_at=datetime.datetime.utcnow() - datetime.timedelta(days=90),
        plan_end_at=datetime.datetime.utcnow() + datetime.timedelta(days=395),
    )
    return plan


@pytest.fixture(scope="function")
def employer_health_plan_coverage_non_embedded():
    return EmployerHealthPlanFactory.create(
        rx_integrated=True,
        cost_sharings=[
            EmployerHealthPlanCostSharing(
                cost_sharing_type=CostSharingType.COPAY,
                cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
                absolute_amount=20_00,
                second_tier_absolute_amount=20_00,
            ),
            EmployerHealthPlanCostSharing(
                cost_sharing_type=CostSharingType.COINSURANCE,
                cost_sharing_category=CostSharingCategory.DIAGNOSTIC_MEDICAL,
                percent=0.1,
                second_tier_percent=0.1,
            ),
            EmployerHealthPlanCostSharing(
                cost_sharing_type=CostSharingType.COPAY,
                cost_sharing_category=CostSharingCategory.CONSULTATION,
                absolute_amount=25_00,
                second_tier_absolute_amount=25_00,
            ),
            EmployerHealthPlanCostSharing(
                cost_sharing_type=CostSharingType.COINSURANCE,
                cost_sharing_category=CostSharingCategory.SPECIALTY_PRESCRIPTIONS,
                percent=0.4,
            ),
            EmployerHealthPlanCostSharing(
                cost_sharing_type=CostSharingType.COPAY,
                cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS,
                absolute_amount=10_00,
            ),
        ],
        coverage=[
            EmployerHealthPlanCoverageFactory.create(
                tier=1,
                individual_deductible=125_00,
                individual_oop=900_00,
                family_deductible=200_00,
                family_oop=1400_00,
                plan_type=FamilyPlanType.EMPLOYEE_PLUS,
                is_deductible_embedded=False,
                is_oop_embedded=False,
            ),
            EmployerHealthPlanCoverageFactory.create(
                tier=2,
                individual_deductible=150_00,
                individual_oop=1000_00,
                family_deductible=225_00,
                family_oop=1500_00,
                plan_type=FamilyPlanType.EMPLOYEE_PLUS,
                is_deductible_embedded=False,
                is_oop_embedded=False,
            ),
            EmployerHealthPlanCoverageFactory.create(
                tier=1,
                individual_deductible=125_00,
                individual_oop=900_00,
                family_deductible=None,
                family_oop=None,
                plan_type=FamilyPlanType.INDIVIDUAL,
                is_deductible_embedded=False,
                is_oop_embedded=False,
            ),
            EmployerHealthPlanCoverageFactory.create(
                tier=2,
                individual_deductible=150_00,
                individual_oop=1000_00,
                family_deductible=None,
                family_oop=None,
                plan_type=FamilyPlanType.INDIVIDUAL,
                is_deductible_embedded=False,
                is_oop_embedded=False,
            ),
            EmployerHealthPlanCoverageFactory.create(
                tier=1,
                individual_deductible=125_00,
                individual_oop=900_00,
                family_deductible=275_00,
                family_oop=1900_00,
                plan_type=FamilyPlanType.FAMILY,
                is_deductible_embedded=False,
                is_oop_embedded=False,
            ),
            EmployerHealthPlanCoverageFactory.create(
                tier=2,
                individual_deductible=150_00,
                individual_oop=1000_00,
                family_deductible=300_00,
                family_oop=2000_00,
                plan_type=FamilyPlanType.FAMILY,
                is_deductible_embedded=False,
                is_oop_embedded=False,
            ),
        ],
    )


@pytest.fixture(scope="function")
def employer_health_plan_coverage_mixed_embedded():
    return EmployerHealthPlanFactory.create(
        rx_integrated=True,
        cost_sharings=[
            EmployerHealthPlanCostSharing(
                cost_sharing_type=CostSharingType.COINSURANCE,
                cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
                percent=0.1,
                second_tier_percent=0.3,
            ),
            EmployerHealthPlanCostSharing(
                cost_sharing_type=CostSharingType.COINSURANCE,
                cost_sharing_category=CostSharingCategory.DIAGNOSTIC_MEDICAL,
                percent=0.1,
                second_tier_percent=0.3,
            ),
        ],
        coverage=[
            EmployerHealthPlanCoverageFactory.create(
                tier=1,
                individual_deductible=2000_00,
                individual_oop=6750_00,
                family_deductible=3200_00,
                family_oop=6750_00,
                plan_type=FamilyPlanType.EMPLOYEE_PLUS,
                is_deductible_embedded=False,
                is_oop_embedded=True,
            ),
            EmployerHealthPlanCoverageFactory.create(
                tier=2,
                individual_deductible=3000_00,
                individual_oop=7150_00,
                family_deductible=4500_00,
                family_oop=9750_00,
                plan_type=FamilyPlanType.EMPLOYEE_PLUS,
                is_deductible_embedded=False,
                is_oop_embedded=True,
            ),
            EmployerHealthPlanCoverageFactory.create(
                tier=1,
                individual_deductible=2000_00,
                individual_oop=4500_00,
                family_deductible=None,
                family_oop=None,
                plan_type=FamilyPlanType.INDIVIDUAL,
                is_deductible_embedded=False,
                is_oop_embedded=False,
            ),
            EmployerHealthPlanCoverageFactory.create(
                tier=2,
                individual_deductible=3000_00,
                individual_oop=6500_00,
                family_deductible=None,
                family_oop=None,
                plan_type=FamilyPlanType.INDIVIDUAL,
                is_deductible_embedded=False,
                is_oop_embedded=False,
            ),
            EmployerHealthPlanCoverageFactory.create(
                tier=1,
                individual_deductible=2000_00,
                individual_oop=7150_00,
                family_deductible=4000_00,
                family_oop=9000_00,
                plan_type=FamilyPlanType.FAMILY,
                is_deductible_embedded=False,
                is_oop_embedded=True,
            ),
            EmployerHealthPlanCoverageFactory.create(
                tier=2,
                individual_deductible=3000_00,
                individual_oop=7150_00,
                family_deductible=6000_00,
                family_oop=13000_00,
                plan_type=FamilyPlanType.FAMILY,
                is_deductible_embedded=False,
                is_oop_embedded=True,
            ),
        ],
    )
