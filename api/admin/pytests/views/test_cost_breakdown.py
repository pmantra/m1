import datetime
from decimal import Decimal
from unittest.mock import ANY, patch

import pytest
from maven import feature_flags

from admin.common_cost_breakdown import CalculatorRTE, RTEOverride
from admin.views.models.cost_breakdown import CostBreakdownRecalculationView
from cost_breakdown.constants import AmountType, CostBreakdownType
from cost_breakdown.cost_breakdown_processor import CostBreakdownProcessor
from cost_breakdown.models.cost_breakdown import CostBreakdown, CostBreakdownData
from cost_breakdown.models.rte import EligibilityInfo
from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.billing.pytests.factories import BillFactory
from direct_payment.clinic.pytests.factories import (
    FeeScheduleFactory,
    FeeScheduleGlobalProceduresFactory,
    FertilityClinicFactory,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from wallet.models.constants import (
    CostSharingCategory,
    CostSharingType,
    CoverageType,
    FamilyPlanType,
)
from wallet.models.reimbursement_organization_settings import (
    EmployerHealthPlanCostSharing,
)
from wallet.pytests.factories import (
    EmployerHealthPlanCoverageFactory,
    EmployerHealthPlanFactory,
    MemberHealthPlanFactory,
    ReimbursementOrganizationSettingsFactory,
    ReimbursementRequestCategoryFactory,
)
from wallet.repository.health_plan import HEALTH_PLAN_YOY_FLAG, NEW_BEHAVIOR


@pytest.fixture
def cost_breakdown_processor() -> CostBreakdownProcessor:
    return CostBreakdownProcessor()


@pytest.fixture(scope="function")
def employer_health_plan_cost_sharing():
    cost_sharing = [
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COINSURANCE,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            percent=0.05,
        )
    ]
    return cost_sharing


@pytest.fixture(scope="function")
def employer_health_plan(employer_health_plan_cost_sharing):
    org_settings = ReimbursementOrganizationSettingsFactory.create(
        organization_id=1,
        deductible_accumulation_enabled=True,
    )
    return EmployerHealthPlanFactory.create(
        reimbursement_organization_settings=org_settings,
        cost_sharings=employer_health_plan_cost_sharing,
        coverage=[
            EmployerHealthPlanCoverageFactory(
                individual_deductible=200_000,
                individual_oop=400_000,
                family_deductible=400_000,
                family_oop=600_000,
                max_oop_per_covered_individual=200,
            ),
            EmployerHealthPlanCoverageFactory(
                individual_deductible=200_000,
                individual_oop=400_000,
                family_deductible=400_000,
                family_oop=600_000,
                plan_type=FamilyPlanType.FAMILY,
                max_oop_per_covered_individual=200,
            ),
            EmployerHealthPlanCoverageFactory(
                individual_deductible=50000,
                individual_oop=100_000,
                family_deductible=100_000,
                family_oop=200_000,
                coverage_type=CoverageType.RX,
            ),
            EmployerHealthPlanCoverageFactory(
                individual_deductible=50000,
                individual_oop=100_000,
                family_deductible=100_000,
                family_oop=200_000,
                plan_type=FamilyPlanType.FAMILY,
                coverage_type=CoverageType.RX,
            ),
        ],
    )


@pytest.fixture(scope="function")
def employer_health_plan_hdhp():
    org_settings = ReimbursementOrganizationSettingsFactory.create(
        organization_id=1,
        deductible_accumulation_enabled=True,
    )
    return EmployerHealthPlanFactory.create(
        reimbursement_organization_settings=org_settings,
        is_hdhp=True,
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
        coverage=[
            EmployerHealthPlanCoverageFactory(
                individual_deductible=200_000,
                individual_oop=400_000,
                family_deductible=400_000,
                family_oop=600_000,
                is_deductible_embedded=True,
                is_oop_embedded=True,
            ),
            EmployerHealthPlanCoverageFactory(
                individual_deductible=200_000,
                individual_oop=400_000,
                family_deductible=400_000,
                family_oop=600_000,
                plan_type=FamilyPlanType.FAMILY,
                is_deductible_embedded=True,
                is_oop_embedded=True,
            ),
            EmployerHealthPlanCoverageFactory(
                individual_deductible=50000,
                individual_oop=100_000,
                family_deductible=100_000,
                family_oop=200_000,
                coverage_type=CoverageType.RX,
                is_deductible_embedded=True,
                is_oop_embedded=True,
            ),
            EmployerHealthPlanCoverageFactory(
                individual_deductible=50000,
                individual_oop=100_000,
                family_deductible=100_000,
                family_oop=200_000,
                plan_type=FamilyPlanType.FAMILY,
                coverage_type=CoverageType.RX,
                is_deductible_embedded=True,
                is_oop_embedded=True,
            ),
        ],
    )


@pytest.fixture(scope="function")
def cost_breakdown_view():
    return CostBreakdownRecalculationView()


@pytest.fixture(scope="function")
def medical_procedure(enterprise_user, wallet):
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    return TreatmentProcedureFactory.create(
        member_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        reimbursement_request_category=category,
        procedure_type=TreatmentProcedureType.MEDICAL,
        start_date=datetime.date(year=2025, month=1, day=5),
    )


@pytest.fixture(scope="function")
def rx_procedure(enterprise_user, wallet):
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    return TreatmentProcedureFactory.create(
        member_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        reimbursement_request_category=category,
        procedure_type=TreatmentProcedureType.PHARMACY,
        start_date=datetime.date(year=2025, month=1, day=5),
    )


@pytest.fixture(scope="function")
def medical_procedure_cycle_based(enterprise_user, wallet_cycle_based):
    return TreatmentProcedureFactory.create(
        member_id=enterprise_user.id,
        reimbursement_request_category=wallet_cycle_based.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category,
        procedure_type=TreatmentProcedureType.MEDICAL,
        reimbursement_wallet_id=wallet_cycle_based.id,
        cost_credit=3,
        start_date=datetime.date(year=2025, month=1, day=5),
    )


@pytest.fixture(scope="function")
def member_health_plan(employer_health_plan, wallet, enterprise_user):
    plan = MemberHealthPlanFactory.create(
        employer_health_plan=employer_health_plan,
        is_subscriber=True,
        member_id=enterprise_user.id,
        reimbursement_wallet=wallet,
        plan_start_at=datetime.datetime(year=2025, month=1, day=1),
        plan_end_at=datetime.datetime(year=2026, month=1, day=1),
    )
    plan.reimbursement_wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
        True
    )
    return plan


@pytest.fixture(scope="function")
def member_health_plan_hdhp(employer_health_plan_hdhp, wallet, enterprise_user):
    plan = MemberHealthPlanFactory.create(
        employer_health_plan=employer_health_plan_hdhp,
        is_subscriber=True,
        member_id=enterprise_user.id,
        reimbursement_wallet=wallet,
        plan_start_at=datetime.datetime(year=2025, month=1, day=1),
        plan_end_at=datetime.datetime(year=2026, month=1, day=1),
    )
    return plan


@pytest.fixture(scope="function")
def member_health_plan_embedded(employer_health_plan_embedded, wallet, enterprise_user):
    plan = MemberHealthPlanFactory.create(
        employer_health_plan=employer_health_plan_embedded,
        is_subscriber=True,
        member_id=enterprise_user.id,
        reimbursement_wallet=wallet,
        plan_start_at=datetime.datetime(year=2025, month=1, day=1),
        plan_end_at=datetime.datetime(year=2026, month=1, day=1),
    )
    plan.reimbursement_wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
        True
    )
    return plan


@pytest.fixture(scope="function")
def member_health_plan_later(employer_health_plan, wallet, enterprise_user):
    new_ehp = EmployerHealthPlanFactory.create(
        reimbursement_organization_settings=employer_health_plan.reimbursement_organization_settings,
        cost_sharings=employer_health_plan.cost_sharings,
        coverage=employer_health_plan.coverage,
    )
    plan = MemberHealthPlanFactory.create(
        employer_health_plan=new_ehp,
        is_subscriber=True,
        member_id=enterprise_user.id,
        reimbursement_wallet=wallet,
        plan_start_at=datetime.datetime(year=2027, month=1, day=2),
        plan_end_at=datetime.datetime(year=2028, month=1, day=1),
    )
    return plan


@pytest.fixture(scope="function")
def medical_procedure_later(enterprise_user, wallet):
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    return TreatmentProcedureFactory.create(
        member_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
        reimbursement_request_category=category,
        procedure_type=TreatmentProcedureType.MEDICAL,
        start_date=datetime.date(year=2027, month=2, day=5),
    )


@pytest.fixture(scope="function")
def member_health_plan_cycle_based(
    employer_health_plan, wallet_cycle_based, enterprise_user
):
    plan = MemberHealthPlanFactory.create(
        employer_health_plan=employer_health_plan,
        plan_type=FamilyPlanType.INDIVIDUAL,
        is_subscriber=True,
        member_id=enterprise_user.id,
        reimbursement_wallet=wallet_cycle_based,
    )
    return plan


@pytest.fixture(scope="function")
def fee_schedule_global_procedure():
    fee_schedule = FeeScheduleFactory.create()
    FertilityClinicFactory.create(id=1, name="test_clinic", fee_schedule=fee_schedule)
    return FeeScheduleGlobalProceduresFactory.create(
        fee_schedule=fee_schedule, global_procedure_id="gp_id", cost=10000
    )


@pytest.fixture(scope="function")
def cost_breakdown_data():
    return CostBreakdownData(
        rte_transaction_id=1,
        total_member_responsibility=10000,
        total_employer_responsibility=20000,
        beginning_wallet_balance=100000,
        ending_wallet_balance=90000,
        cost_breakdown_type=CostBreakdownType.FIRST_DOLLAR_COVERAGE,
        amount_type=AmountType.INDIVIDUAL,
        deductible=1000,
        coinsurance=2000,
        oop_applied=3000,
    )


@pytest.fixture(scope="function")
def bill():
    return BillFactory.create()


class TestCalculatorRTE:
    def test_eligibility_info_override_individual_medical(
        self,
        member_health_plan,
        medical_procedure,
    ):
        rte_override_data = RTEOverride(
            ytd_ind_deductible="100",
            ytd_ind_oop="100",
        )
        eligibility_info = CalculatorRTE._eligibility_info_override(
            member_health_plan=member_health_plan,
            procedure_type=medical_procedure.procedure_type,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            rte_override_data=rte_override_data,
        )

        assert eligibility_info == EligibilityInfo(
            individual_deductible=200000,
            individual_deductible_remaining=190000,
            family_deductible=None,
            family_deductible_remaining=None,
            individual_oop=400000,
            individual_oop_remaining=390000,
            family_oop=None,
            family_oop_remaining=None,
            coinsurance=Decimal(0.05),
            coinsurance_min=None,
            coinsurance_max=None,
            copay=None,
            max_oop_per_covered_individual=200,
            is_deductible_embedded=False,
            is_oop_embedded=False,
        )

    def test_eligibility_info_override_family_medical(
        self,
        member_health_plan,
        medical_procedure,
    ):
        rte_override_data = RTEOverride(
            ytd_family_deductible="2000",
            ytd_family_oop="2000",
        )
        member_health_plan.plan_type = FamilyPlanType.FAMILY
        eligibility_info = CalculatorRTE._eligibility_info_override(
            member_health_plan=member_health_plan,
            procedure_type=medical_procedure.procedure_type,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            rte_override_data=rte_override_data,
        )

        assert eligibility_info == EligibilityInfo(
            individual_deductible=200000,
            individual_deductible_remaining=None,
            family_deductible=400000,
            family_deductible_remaining=200000,
            individual_oop=400000,
            individual_oop_remaining=None,
            family_oop=600000,
            family_oop_remaining=400000,
            coinsurance=Decimal(0.05),
            coinsurance_min=None,
            coinsurance_max=None,
            copay=None,
            is_deductible_embedded=False,
            is_oop_embedded=False,
            max_oop_per_covered_individual=200,
        )

    def test_eligibility_info_override_family_medical_embedded(
        self,
        member_health_plan_embedded,
        medical_procedure,
    ):
        rte_override_data = RTEOverride(
            ytd_ind_deductible="1000",
            ytd_ind_oop="1000",
            ytd_family_deductible="2000",
            ytd_family_oop="2000",
        )
        member_health_plan_embedded.plan_type = FamilyPlanType.FAMILY
        eligibility_info = CalculatorRTE._eligibility_info_override(
            member_health_plan=member_health_plan_embedded,
            procedure_type=medical_procedure.procedure_type,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            rte_override_data=rte_override_data,
        )

        assert eligibility_info == EligibilityInfo(
            individual_deductible=200000,
            individual_deductible_remaining=100000,
            family_deductible=400000,
            family_deductible_remaining=200000,
            individual_oop=400000,
            individual_oop_remaining=300000,
            family_oop=600000,
            family_oop_remaining=400000,
            coinsurance=Decimal(0.05),
            coinsurance_min=None,
            coinsurance_max=None,
            copay=None,
            is_deductible_embedded=True,
            is_oop_embedded=True,
        )

    def test_eligibility_info_override_rx_non_integrated_individual(
        self,
        member_health_plan,
        rx_procedure,
    ):
        rte_override_data = RTEOverride(
            ytd_ind_deductible="100",
            ytd_ind_oop="100",
        )
        member_health_plan.employer_health_plan.rx_integrated = False
        eligibility_info = CalculatorRTE._eligibility_info_override(
            member_health_plan=member_health_plan,
            procedure_type=rx_procedure.procedure_type,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            rte_override_data=rte_override_data,
        )

        assert eligibility_info == EligibilityInfo(
            individual_deductible=50000,
            individual_deductible_remaining=40000,
            family_deductible=None,
            family_deductible_remaining=None,
            individual_oop=100000,
            individual_oop_remaining=90000,
            family_oop=None,
            family_oop_remaining=None,
            coinsurance=Decimal(0.05),
            coinsurance_min=None,
            coinsurance_max=None,
            copay=None,
            is_deductible_embedded=False,
            is_oop_embedded=False,
        )

    def test_eligibility_info_override_rx_non_integrated_family(
        self,
        member_health_plan,
        rx_procedure,
    ):
        rte_override_data = RTEOverride(
            ytd_family_deductible="2000",
            ytd_family_oop="2000",
        )
        member_health_plan.plan_type = FamilyPlanType.FAMILY
        member_health_plan.employer_health_plan.rx_integrated = False
        eligibility_info = CalculatorRTE._eligibility_info_override(
            member_health_plan=member_health_plan,
            procedure_type=rx_procedure.procedure_type,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            rte_override_data=rte_override_data,
        )

        assert eligibility_info == EligibilityInfo(
            individual_deductible=50000,
            individual_deductible_remaining=None,
            family_deductible=100000,
            family_deductible_remaining=0,
            individual_oop=100000,
            individual_oop_remaining=None,
            family_oop=200000,
            family_oop_remaining=0,
            coinsurance=Decimal(0.05),
            coinsurance_min=None,
            coinsurance_max=None,
            copay=None,
            is_deductible_embedded=False,
            is_oop_embedded=False,
        )

    def test_eligibility_info_override_rx_non_integrated_family_embedded(
        self,
        member_health_plan_embedded,
        rx_procedure,
    ):
        rte_override_data = RTEOverride(
            ytd_ind_deductible="1000",
            ytd_ind_oop="1000",
            ytd_family_deductible="2000",
            ytd_family_oop="2000",
        )
        member_health_plan_embedded.plan_type = FamilyPlanType.FAMILY
        member_health_plan_embedded.employer_health_plan.rx_integrated = False
        eligibility_info = CalculatorRTE._eligibility_info_override(
            member_health_plan=member_health_plan_embedded,
            procedure_type=rx_procedure.procedure_type,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            rte_override_data=rte_override_data,
        )

        assert eligibility_info == EligibilityInfo(
            individual_deductible=50000,
            individual_deductible_remaining=0,
            family_deductible=100000,
            family_deductible_remaining=0,
            individual_oop=100000,
            individual_oop_remaining=0,
            family_oop=200000,
            family_oop_remaining=0,
            coinsurance=Decimal(0.05),
            coinsurance_min=None,
            coinsurance_max=None,
            copay=None,
            is_deductible_embedded=True,
            is_oop_embedded=True,
        )

    def test_eligibility_info_override_hra_remaining(
        self,
        member_health_plan,
        medical_procedure,
    ):
        rte_override_data = RTEOverride(hra_remaining="100")
        eligibility_info = CalculatorRTE._eligibility_info_override(
            member_health_plan=member_health_plan,
            procedure_type=medical_procedure.procedure_type,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            rte_override_data=rte_override_data,
        )

        assert eligibility_info == EligibilityInfo(
            individual_deductible=200000,
            individual_deductible_remaining=200000,
            family_deductible=None,
            family_deductible_remaining=None,
            individual_oop=400000,
            individual_oop_remaining=400000,
            family_oop=None,
            family_oop_remaining=None,
            coinsurance=Decimal(0.05),
            coinsurance_min=None,
            coinsurance_max=None,
            copay=None,
            max_oop_per_covered_individual=200,
            is_deductible_embedded=False,
            is_oop_embedded=False,
            hra_remaining=10000,
        )

    def test_eligibility_info_override_not_deductible_accumulation(
        self, member_health_plan, medical_procedure
    ):
        member_health_plan.reimbursement_wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
            False
        )
        with patch(
            "admin.common_cost_breakdown.set_db_copay_coinsurance_to_eligibility_info"
        ) as copay_coinsurance_call:
            CalculatorRTE._eligibility_info_override(
                member_health_plan=member_health_plan,
                procedure_type=medical_procedure.procedure_type,
                cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
                rte_override_data=RTEOverride(),
            )
        assert copay_coinsurance_call.call_count == 0

    def test_rte_override_includes_max_oop_per_covered_individual(
        self,
        member_health_plan,
        medical_procedure,
    ):
        rte_override_data = RTEOverride(
            ytd_ind_deductible="100",
            ytd_ind_oop="100",
        )
        expected_amount = 200
        eligibility_info = CalculatorRTE._eligibility_info_override(
            member_health_plan=member_health_plan,
            procedure_type=medical_procedure.procedure_type,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            rte_override_data=rte_override_data,
        )
        assert eligibility_info.individual_deductible_remaining == 190000
        assert eligibility_info.max_oop_per_covered_individual == expected_amount


class TestCostBreakdownRecalculationView:
    def test_format_cost_breakdown(self, cost_breakdown_view):
        cost_breakdown = CostBreakdown(
            rte_transaction_id=1,
            total_member_responsibility=1000,
            total_employer_responsibility=2000,
            is_unlimited=False,
            beginning_wallet_balance=3000,
            ending_wallet_balance=2000,
            cost_breakdown_type=CostBreakdownType.FIRST_DOLLAR_COVERAGE,
            amount_type=AmountType.INDIVIDUAL,
            calc_config={
                "eligibility_info": {
                    "coinsurance": 0.1,
                    "family_deductible": 300000,
                    "family_deductible_remaining": 300000,
                    "family_oop": 500000,
                    "family_oop_remaining": 500000,
                    "individual_deductible": 100000,
                    "individual_deductible_remaining": 100000,
                    "individual_oop": 200000,
                    "individual_oop_remaining": 200000,
                },
                "health_plan_configuration": {"is_family_plan": True},
                "trigger_object_status": "SCHEDULED",
            },
        )

        res = cost_breakdown_view._format_cost_breakdown(
            initial_cost=10000, cost_breakdown=cost_breakdown
        )
        assert res == {
            "cost": Decimal(100.0),
            "total_member_responsibility": Decimal(10.0),
            "total_employer_responsibility": Decimal(20.0),
            "is_unlimited": False,
            "beginning_wallet_balance": Decimal(30.0),
            "ending_wallet_balance": Decimal(20.0),
            "deductible": 0,
            "deductible_remaining": 0,
            "family_deductible_remaining": 0,
            "coinsurance": 0,
            "copay": 0,
            "oop_remaining": 0,
            "oop_applied": 0,
            "hra_applied": 0,
            "family_oop_remaining": 0,
            "overage_amount": 0,
            "amount_type": "INDIVIDUAL",
            "cost_breakdown_type": "FIRST_DOLLAR_COVERAGE",
            "rte_transaction_id": 1,
            "calc_config": '{"eligibility_info": {"coinsurance": 0.1, "family_deductible": 300000, "family_deductible_remaining": 300000, "family_oop": 500000, "family_oop_remaining": 500000, "individual_deductible": 100000, "individual_deductible_remaining": 100000, "individual_oop": 200000, "individual_oop_remaining": 200000}, '
            '"health_plan_configuration": {"is_family_plan": true}, '
            '"trigger_object_status": "SCHEDULED"}',
        }


class TestCostBreakdownRecalculator:
    def test_format_submit_cost_breakdowns(
        self,
        cost_breakdown_view,
        medical_procedure,
        rx_procedure,
        member_health_plan,
        enterprise_user,
    ):
        procedures = [medical_procedure, rx_procedure]
        cost_breakdowns = [
            CostBreakdownFactory.create(
                treatment_procedure_uuid=medical_procedure.uuid,
                total_member_responsibility=10000,
                total_employer_responsibility=10000,
            ),
            CostBreakdownFactory.create(
                treatment_procedure_uuid=rx_procedure.uuid,
                total_member_responsibility=10000,
                total_employer_responsibility=10000,
            ),
        ]
        res = cost_breakdown_view._format_submit_cost_breakdowns(
            treatment_procedures=procedures,
            cost_breakdowns=cost_breakdowns,
            member_health_plan=member_health_plan,
        )
        assert res == {
            "plan": {
                "member_id": enterprise_user.id,
                "plan_name": None,
                "rx_integrated": True,
                "is_family_plan": False,
                "member_health_plan_id": str(member_health_plan.id),
            },
            "breakdowns": [
                {
                    "cost": Decimal(100.0),
                    "total_member_responsibility": Decimal(100.0),
                    "total_employer_responsibility": Decimal(100.0),
                    "is_unlimited": False,
                    "beginning_wallet_balance": 0,
                    "ending_wallet_balance": 0,
                    "deductible": 0,
                    "deductible_remaining": 0,
                    "family_deductible_remaining": 0,
                    "coinsurance": 0,
                    "copay": 0,
                    "oop_remaining": 0,
                    "oop_applied": 0,
                    "hra_applied": 0,
                    "family_oop_remaining": 0,
                    "overage_amount": 0,
                    "amount_type": "INDIVIDUAL",
                    "cost_breakdown_type": None,
                    "rte_transaction_id": None,
                    "calc_config": None,
                    "treatment_id": medical_procedure.id,
                    "treatment_uuid": medical_procedure.uuid,
                    "treatment_type": "MEDICAL",
                    "treatment_cost_credit": None,
                },
                {
                    "cost": Decimal(100.0),
                    "total_member_responsibility": Decimal(100.0),
                    "total_employer_responsibility": Decimal(100.0),
                    "is_unlimited": False,
                    "beginning_wallet_balance": 0,
                    "ending_wallet_balance": 0,
                    "deductible": 0,
                    "deductible_remaining": 0,
                    "family_deductible_remaining": 0,
                    "coinsurance": 0,
                    "copay": 0,
                    "oop_remaining": 0,
                    "oop_applied": 0,
                    "hra_applied": 0,
                    "family_oop_remaining": 0,
                    "overage_amount": 0,
                    "amount_type": "INDIVIDUAL",
                    "cost_breakdown_type": None,
                    "rte_transaction_id": None,
                    "calc_config": None,
                    "treatment_id": rx_procedure.id,
                    "treatment_uuid": rx_procedure.uuid,
                    "treatment_type": "PHARMACY",
                    "treatment_cost_credit": None,
                },
            ],
        }

    def test_submit_cost_breakdown_procedure_not_integer(
        self, admin_client, enterprise_user
    ):
        res = admin_client.post(
            "/admin/cost_breakdown_calculator/submit",
            data={"treatment_ids": "abc"},
            headers={"Content-Type": "multipart/form-data"},
        )

        assert res.status_code == 400
        assert "abc is not a valid integer" in res.json["error"]

        res = admin_client.post(
            "/admin/cost_breakdown_calculator/submit",
            data={"treatment_ids": "1,abc"},
            headers={"Content-Type": "multipart/form-data"},
        )

        assert res.status_code == 400
        assert "abc is not a valid integer" in res.json["error"]

    def test_submit_cost_breakdown_procedure_not_found(
        self, admin_client, enterprise_user, medical_procedure
    ):
        res = admin_client.post(
            "/admin/cost_breakdown_calculator/submit",
            data={"treatment_ids": f"99,{medical_procedure.id}"},
            headers={"Content-Type": "multipart/form-data"},
        )

        assert res.status_code == 400
        assert (
            "Could not find all treatment procedures for the given ids. Missing: [99]"
            in res.json["error"]
        )

    def test_submit_cost_breakdown_procedure_not_for_single_user(
        self, admin_client, enterprise_user
    ):
        tp1 = TreatmentProcedureFactory.create(member_id=1)
        tp2 = TreatmentProcedureFactory.create(member_id=2)
        res = admin_client.post(
            "/admin/cost_breakdown_calculator/submit",
            data={"treatment_ids": f"{tp1.id}, {tp2.id}"},
            headers={"Content-Type": "multipart/form-data"},
        )

        assert res.status_code == 400
        assert (
            "Treatments don't belong to the same user, found multiple users"
            in res.json["error"]
        )

    def test_submit_cost_breakdown_procedure_not_for_multiple_health_plans(
        self,
        admin_client,
        enterprise_user,
        wallet,
        medical_procedure,
        medical_procedure_later,
        member_health_plan,
        member_health_plan_later,
    ):
        with feature_flags.test_data() as ff_test_data:
            ff_test_data.update(
                ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(NEW_BEHAVIOR)
            )
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/submit",
                data={
                    "treatment_ids": f"{medical_procedure.id},{medical_procedure_later.id}"
                },
                headers={"Content-Type": "multipart/form-data"},
            )
        assert res.status_code == 400
        assert (
            "Treatments don't belong to the same health plan, found multiple relevant member health plans."
            in res.json["error"]
        ), res.json

    def test_submit_cost_breakdown_cannot_override_rte(
        self, admin_client, enterprise_user, medical_procedure, wallet
    ):
        res = admin_client.post(
            "/admin/cost_breakdown_calculator/submit",
            data={
                "treatment_ids": f"{medical_procedure.id}",
                "ind_deductible": "100",
                "ind_oop": "100",
                "family_deductible": "100",
                "family_oop": "100",
            },
            headers={"Content-Type": "multipart/form-data"},
        )

        assert res.status_code == 400
        assert (
            "Cannot override RTE for a procedure without a member health plan"
            in res.json["error"]
        )

    def test_submit_cost_breakdown_currency_based(
        self,
        admin_client,
        enterprise_user,
        wallet,
        medical_procedure,
        member_health_plan,
    ):
        with patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_cost_breakdown_for_treatment_procedure",
            return_value=CostBreakdownFactory.create(
                treatment_procedure_uuid=medical_procedure.uuid,
                total_member_responsibility=10000,
                total_employer_responsibility=10000,
            ),
        ) as get_cost_breakdown_for_treatment_procedure:
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/submit",
                data={
                    "treatment_ids": f"{medical_procedure.id}",
                    "ind_deductible": "",
                    "ind_oop": "",
                    "family_deductible": "",
                    "family_oop": "",
                    "hra_remaining": "",
                },
                headers={"Content-Type": "multipart/form-data"},
            )

        assert res.status_code == 200
        get_cost_breakdown_for_treatment_procedure.assert_called_with(
            wallet=wallet,
            treatment_procedure=medical_procedure,
            store_to_db=False,
            override_rte_result=None,
            wallet_balance=None,
        )
        assert res.json == {
            "breakdowns": [
                {
                    "amount_type": "INDIVIDUAL",
                    "beginning_wallet_balance": 0,
                    "calc_config": None,
                    "coinsurance": 0,
                    "copay": 0,
                    "cost": "100",
                    "cost_breakdown_type": None,
                    "deductible": 0,
                    "deductible_remaining": 0,
                    "ending_wallet_balance": 0,
                    "family_deductible_remaining": 0,
                    "family_oop_remaining": 0,
                    "oop_applied": 0,
                    "hra_applied": 0,
                    "is_unlimited": False,
                    "oop_remaining": 0,
                    "overage_amount": 0,
                    "rte_transaction_id": None,
                    "total_employer_responsibility": "100",
                    "total_member_responsibility": "100",
                    "treatment_cost_credit": None,
                    "treatment_id": medical_procedure.id,
                    "treatment_type": "MEDICAL",
                    "treatment_uuid": medical_procedure.uuid,
                }
            ],
            "plan": {
                "is_family_plan": False,
                "member_health_plan_id": str(member_health_plan.id),
                "member_id": enterprise_user.id,
                "plan_name": None,
                "rx_integrated": True,
            },
        }

    def test_submit_cost_breakdown_currency_based_multiple_procedures(
        self,
        admin_client,
        enterprise_user,
        wallet,
        medical_procedure,
        rx_procedure,
        member_health_plan,
    ):
        with patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_cost_breakdown_for_treatment_procedure",
            return_value=CostBreakdownFactory.create(
                treatment_procedure_uuid=medical_procedure.uuid,
                total_member_responsibility=10000,
                total_employer_responsibility=10000,
            ),
        ) as get_cost_breakdown_for_treatment_procedure:
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/submit",
                data={
                    "treatment_ids": f"     {medical_procedure.id},    {rx_procedure.id}     ",
                    "ind_deductible": "",
                    "ind_oop": "",
                    "family_deductible": "",
                    "family_oop": "",
                    "hra_remaining": "",
                },
                headers={"Content-Type": "multipart/form-data"},
            )

        assert res.status_code == 200
        assert res.json == {
            "breakdowns": [
                {
                    "amount_type": "INDIVIDUAL",
                    "beginning_wallet_balance": 0,
                    "calc_config": None,
                    "coinsurance": 0,
                    "copay": 0,
                    "cost": "100",
                    "cost_breakdown_type": None,
                    "deductible": 0,
                    "deductible_remaining": 0,
                    "ending_wallet_balance": 0,
                    "family_deductible_remaining": 0,
                    "family_oop_remaining": 0,
                    "oop_applied": 0,
                    "hra_applied": 0,
                    "is_unlimited": False,
                    "oop_remaining": 0,
                    "overage_amount": 0,
                    "rte_transaction_id": None,
                    "total_employer_responsibility": "100",
                    "total_member_responsibility": "100",
                    "treatment_cost_credit": None,
                    "treatment_id": medical_procedure.id,
                    "treatment_type": "MEDICAL",
                    "treatment_uuid": medical_procedure.uuid,
                },
                {
                    "amount_type": "INDIVIDUAL",
                    "beginning_wallet_balance": 0,
                    "calc_config": None,
                    "coinsurance": 0,
                    "copay": 0,
                    "cost": "100",
                    "cost_breakdown_type": None,
                    "deductible": 0,
                    "deductible_remaining": 0,
                    "ending_wallet_balance": 0,
                    "family_deductible_remaining": 0,
                    "family_oop_remaining": 0,
                    "oop_applied": 0,
                    "hra_applied": 0,
                    "is_unlimited": False,
                    "oop_remaining": 0,
                    "overage_amount": 0,
                    "rte_transaction_id": None,
                    "total_employer_responsibility": "100",
                    "total_member_responsibility": "100",
                    "treatment_cost_credit": None,
                    "treatment_id": rx_procedure.id,
                    "treatment_type": "PHARMACY",
                    "treatment_uuid": rx_procedure.uuid,
                },
            ],
            "plan": {
                "is_family_plan": False,
                "member_health_plan_id": str(member_health_plan.id),
                "member_id": enterprise_user.id,
                "plan_name": None,
                "rx_integrated": True,
            },
        }
        get_cost_breakdown_for_treatment_procedure.assert_called_with(
            wallet=wallet,
            treatment_procedure=rx_procedure,
            store_to_db=False,
            override_rte_result=None,
            wallet_balance=None,
        )

    def test_submit_cost_breakdown_currency_based_override_rte(
        self,
        admin_client,
        enterprise_user,
        wallet,
        medical_procedure,
        member_health_plan,
    ):
        with patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_cost_breakdown_for_treatment_procedure",
            return_value=CostBreakdownFactory.create(
                treatment_procedure_uuid=medical_procedure.uuid,
                total_member_responsibility=10000,
                total_employer_responsibility=10000,
            ),
        ) as get_cost_breakdown_for_treatment_procedure, patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_treatment_cost_sharing_category",
            return_value=CostSharingCategory.MEDICAL_CARE,
        ):
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/submit",
                data={
                    "treatment_ids": f"{medical_procedure.id}",
                    "ind_deductible": "1000",
                    "ind_oop": "1000",
                    "family_deductible": "1000",
                    "family_oop": "1000",
                    "hra_remaining": "",
                },
                headers={"Content-Type": "multipart/form-data"},
            )
        assert res.status_code == 200
        get_cost_breakdown_for_treatment_procedure.assert_called_with(
            wallet=wallet,
            treatment_procedure=medical_procedure,
            store_to_db=False,
            override_rte_result=EligibilityInfo(
                individual_deductible=200000,
                individual_deductible_remaining=100000,
                family_deductible=None,
                family_deductible_remaining=None,
                individual_oop=400000,
                individual_oop_remaining=300000,
                family_oop=None,
                family_oop_remaining=None,
                coinsurance=Decimal(0.05),
                coinsurance_min=None,
                coinsurance_max=None,
                copay=None,
                is_oop_embedded=False,
                is_deductible_embedded=False,
                max_oop_per_covered_individual=200,
            ),
            wallet_balance=None,
        )
        assert res.json == {
            "breakdowns": [
                {
                    "amount_type": "INDIVIDUAL",
                    "beginning_wallet_balance": 0,
                    "calc_config": None,
                    "coinsurance": 0,
                    "copay": 0,
                    "cost": "100",
                    "cost_breakdown_type": None,
                    "deductible": 0,
                    "deductible_remaining": 0,
                    "ending_wallet_balance": 0,
                    "family_deductible_remaining": 0,
                    "family_oop_remaining": 0,
                    "oop_applied": 0,
                    "hra_applied": 0,
                    "is_unlimited": False,
                    "oop_remaining": 0,
                    "overage_amount": 0,
                    "rte_transaction_id": None,
                    "total_employer_responsibility": "100",
                    "total_member_responsibility": "100",
                    "treatment_cost_credit": None,
                    "treatment_id": medical_procedure.id,
                    "treatment_type": "MEDICAL",
                    "treatment_uuid": medical_procedure.uuid,
                }
            ],
            "plan": {
                "is_family_plan": False,
                "member_health_plan_id": str(member_health_plan.id),
                "member_id": enterprise_user.id,
                "plan_name": None,
                "rx_integrated": True,
            },
        }

    def test_submit_cost_breakdown_hdhp_based_override_rte_success(
        self,
        admin_client,
        enterprise_user,
        wallet,
        medical_procedure,
        member_health_plan_hdhp,
    ):
        with patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_cost_breakdown_for_treatment_procedure",
            return_value=CostBreakdownFactory.create(
                treatment_procedure_uuid=medical_procedure.uuid,
                total_member_responsibility=10000,
                total_employer_responsibility=10000,
            ),
        ) as get_cost_breakdown_for_treatment_procedure, patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_treatment_cost_sharing_category",
            return_value=CostSharingCategory.MEDICAL_CARE,
        ):
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/submit",
                data={
                    "treatment_ids": f"{medical_procedure.id}",
                    "ind_deductible": "",
                    "ind_oop": "1000",
                    "family_deductible": "",
                    "family_oop": "",
                    "hra_remaining": "",
                    "ind_oop_limit": "1000",
                    "family_oop_limit": "",
                },
                headers={"Content-Type": "multipart/form-data"},
            )
        assert res.status_code == 200
        get_cost_breakdown_for_treatment_procedure.assert_called_with(
            wallet=wallet,
            treatment_procedure=medical_procedure,
            store_to_db=False,
            override_rte_result=EligibilityInfo(
                individual_deductible=None,
                individual_deductible_remaining=None,
                family_deductible=None,
                family_deductible_remaining=None,
                individual_oop=100000,
                individual_oop_remaining=0,
                family_oop=None,
                family_oop_remaining=None,
                coinsurance=None,
                coinsurance_min=None,
                coinsurance_max=None,
                copay=None,
                is_oop_embedded=None,
                is_deductible_embedded=None,
                max_oop_per_covered_individual=None,
            ),
            wallet_balance=None,
        )
        assert res.json == {
            "breakdowns": [
                {
                    "amount_type": "INDIVIDUAL",
                    "beginning_wallet_balance": 0,
                    "calc_config": None,
                    "coinsurance": 0,
                    "copay": 0,
                    "cost": "100",
                    "cost_breakdown_type": None,
                    "deductible": 0,
                    "deductible_remaining": 0,
                    "ending_wallet_balance": 0,
                    "family_deductible_remaining": 0,
                    "family_oop_remaining": 0,
                    "oop_applied": 0,
                    "hra_applied": 0,
                    "is_unlimited": False,
                    "oop_remaining": 0,
                    "overage_amount": 0,
                    "rte_transaction_id": None,
                    "total_employer_responsibility": "100",
                    "total_member_responsibility": "100",
                    "treatment_cost_credit": None,
                    "treatment_id": medical_procedure.id,
                    "treatment_type": "MEDICAL",
                    "treatment_uuid": medical_procedure.uuid,
                }
            ],
            "plan": {
                "is_family_plan": False,
                "member_health_plan_id": str(member_health_plan_hdhp.id),
                "member_id": enterprise_user.id,
                "plan_name": None,
                "rx_integrated": True,
            },
        }

    def test_submit_cost_breakdown_hdhp_override_rte_failure(
        self,
        admin_client,
        enterprise_user,
        wallet,
        medical_procedure,
        member_health_plan_hdhp,
    ):
        with patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_treatment_cost_sharing_category",
            return_value=CostSharingCategory.MEDICAL_CARE,
        ):
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/submit",
                data={
                    "treatment_ids": f"{medical_procedure.id}",
                    "ind_deductible": "",
                    "ind_oop": "",
                    "family_deductible": "",
                    "family_oop": "",
                    "hra_remaining": "",
                    "ind_oop_limit": "0",
                    "family_oop_limit": "",
                },
                headers={"Content-Type": "multipart/form-data"},
            )
            assert res.status_code == 400

    def test_submit_cost_breakdown_cycle_based(
        self,
        admin_client,
        enterprise_user,
        wallet_cycle_based,
        medical_procedure_cycle_based,
        member_health_plan_cycle_based,
    ):
        with patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_cost_breakdown_for_treatment_procedure",
            return_value=CostBreakdownFactory.create(
                treatment_procedure_uuid=medical_procedure_cycle_based.uuid,
                total_member_responsibility=10000,
                total_employer_responsibility=10000,
            ),
        ) as get_cost_breakdown_for_treatment_procedure:
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/submit",
                data={
                    "treatment_ids": f"{medical_procedure_cycle_based.id}",
                    "ind_deductible": "",
                    "ind_oop": "",
                    "family_deductible": "",
                    "family_oop": "",
                    "hra_remaining": "",
                },
                headers={"Content-Type": "multipart/form-data"},
            )

        assert res.status_code == 200
        get_cost_breakdown_for_treatment_procedure.assert_called_with(
            wallet=wallet_cycle_based,
            treatment_procedure=medical_procedure_cycle_based,
            store_to_db=False,
            override_rte_result=None,
            wallet_balance=10000,
        )
        assert res.json == {
            "breakdowns": [
                {
                    "amount_type": "INDIVIDUAL",
                    "beginning_wallet_balance": 0,
                    "calc_config": None,
                    "coinsurance": 0,
                    "copay": 0,
                    "cost": "100",
                    "cost_breakdown_type": None,
                    "deductible": 0,
                    "deductible_remaining": 0,
                    "ending_wallet_balance": 0,
                    "family_deductible_remaining": 0,
                    "family_oop_remaining": 0,
                    "oop_applied": 0,
                    "hra_applied": 0,
                    "is_unlimited": False,
                    "oop_remaining": 0,
                    "overage_amount": 0,
                    "rte_transaction_id": None,
                    "total_employer_responsibility": "100",
                    "total_member_responsibility": "100",
                    "treatment_cost_credit": 3,
                    "treatment_id": medical_procedure_cycle_based.id,
                    "treatment_type": "MEDICAL",
                    "treatment_uuid": medical_procedure_cycle_based.uuid,
                }
            ],
            "plan": {
                "is_family_plan": False,
                "member_health_plan_id": str(member_health_plan_cycle_based.id),
                "member_id": enterprise_user.id,
                "plan_name": None,
                "rx_integrated": True,
            },
        }

    def test_submit_cost_breakdown_cycle_based_no_credit(
        self,
        admin_client,
        enterprise_user,
        wallet_cycle_based,
        medical_procedure_cycle_based,
        member_health_plan_cycle_based,
    ):
        medical_procedure_cycle_based.cost_credit = None
        with patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_cost_breakdown_for_treatment_procedure",
            return_value=CostBreakdownFactory.create(
                treatment_procedure_uuid=medical_procedure_cycle_based.uuid,
                total_member_responsibility=10000,
                total_employer_responsibility=10000,
            ),
        ):
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/submit",
                data={
                    "treatment_ids": f"{medical_procedure_cycle_based.id}",
                    "ind_deductible": "",
                    "ind_oop": "",
                    "family_deductible": "",
                    "family_oop": "",
                    "hra_remaining": "",
                },
                headers={"Content-Type": "multipart/form-data"},
            )

            assert res.status_code == 400
            assert (
                "Cycle wallet balance failed. Make sure there is a cost credit value saved."
                in res.json["error"]
            )

    def test_confirm_cost_breakdown_no_breakdowns(
        self,
        admin_client,
    ):
        res = admin_client.post(
            "/admin/cost_breakdown_calculator/confirm",
            json={
                "breakdowns": [],
            },
            headers={"Content-Type": "application/json"},
        )
        assert res.status_code == 200
        assert res.json == {"bills": []}

    def test_confirm_cost_breakdown_scheduled_tp(
        self, admin_client, medical_procedure, wallet, bill
    ):
        with patch(
            "admin.views.models.cost_breakdown.create_member_bill"
        ) as create_member_bill, patch(
            "admin.views.models.cost_breakdown.deduct_balance"
        ) as deduct_balance, patch(
            "admin.views.models.cost_breakdown.BillRepository.get_by_cost_breakdown_ids",
            return_value=[bill],
        ):
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/confirm",
                json={
                    "breakdowns": [
                        {
                            "treatment_id": medical_procedure.id,
                            "treatment_uuid": medical_procedure.uuid,
                            "treatment_type": medical_procedure.procedure_type.value,
                            "treatment_cost_credit": medical_procedure.cost_credit,
                            "cost": "100",
                            "total_member_responsibility": "100",
                            "total_employer_responsibility": "200",
                            "is_unlimited": False,
                            "beginning_wallet_balance": "300",
                            "ending_wallet_balance": "100",
                            "deductible": "50",
                            "deductible_remaining": "0",
                            "family_deductible_remaining": "0",
                            "coinsurance": "50",
                            "copay": "0",
                            "oop_remaining": "300",
                            "oop_applied": "100",
                            "hra_applied": 0,
                            "family_oop_remaining": "300",
                            "overage_amount": "0",
                            "amount_type": "INDIVIDUAL",
                            "cost_breakdown_type": "DEDUCTIBLE_ACCUMULATION",
                            "rte_transaction_id": None,
                            "calc_config": {},
                        }
                    ],
                },
                headers={"Content-Type": "application/json"},
            )

        assert res.status_code == 200
        create_member_bill.assert_called_once_with(
            treatment_procedure_id=medical_procedure.id,
            cost_breakdown_id=ANY,
            wallet_id=wallet.id,
            treatment_procedure_status=TreatmentProcedureStatus.SCHEDULED,
        )
        deduct_balance.assert_called_once_with(
            treatment_procedure=medical_procedure, cost_breakdown=ANY, wallet=wallet
        )
        assert res.json == {
            "bills": [
                {
                    "cost_breakdown_uuid": ANY,
                    "bill_id": bill.id,
                    "bill_amount": bill.amount / 100,
                    "bill_payer_type": "MEMBER",
                    "treatment_id": bill.procedure_id,
                }
            ]
        }

    def test_confirm_cost_breakdown_completed_tp(
        self, admin_client, medical_procedure, wallet, bill
    ):
        medical_procedure.status = TreatmentProcedureStatus.COMPLETED
        with patch(
            "admin.views.models.cost_breakdown.create_member_and_employer_bill"
        ) as create_member_and_employer_bill, patch(
            "admin.views.models.cost_breakdown.deduct_balance"
        ) as deduct_balance, patch(
            "admin.views.models.cost_breakdown.BillRepository.get_by_cost_breakdown_ids",
            return_value=[bill],
        ):
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/confirm",
                json={
                    "breakdowns": [
                        {
                            "treatment_id": medical_procedure.id,
                            "treatment_uuid": medical_procedure.uuid,
                            "treatment_type": medical_procedure.procedure_type.value,
                            "treatment_cost_credit": medical_procedure.cost_credit,
                            "cost": 100.0,
                            "total_member_responsibility": 100.0,
                            "total_employer_responsibility": 200.0,
                            "is_unlimited": False,
                            "beginning_wallet_balance": 300.0,
                            "ending_wallet_balance": 100.0,
                            "deductible": 50.0,
                            "deductible_remaining": 0.0,
                            "family_deductible_remaining": 0.0,
                            "coinsurance": 50.0,
                            "copay": 0.0,
                            "oop_remaining": 300.0,
                            "oop_applied": 100.0,
                            "hra_applied": 0,
                            "family_oop_remaining": 300.0,
                            "overage_amount": 0.0,
                            "amount_type": "INDIVIDUAL",
                            "cost_breakdown_type": "DEDUCTIBLE_ACCUMULATION",
                            "rte_transaction_id": None,
                            "calc_config": {},
                        }
                    ],
                },
                headers={"Content-Type": "application/json"},
            )
        assert res.status_code == 200
        create_member_and_employer_bill.assert_called_once_with(
            treatment_procedure_id=medical_procedure.id,
            cost_breakdown_id=ANY,
            wallet_id=wallet.id,
            treatment_procedure_status=TreatmentProcedureStatus.COMPLETED,
        )
        deduct_balance.assert_called_once_with(
            treatment_procedure=medical_procedure, cost_breakdown=ANY, wallet=wallet
        )
        assert res.json == {
            "bills": [
                {
                    "cost_breakdown_uuid": ANY,
                    "bill_id": bill.id,
                    "bill_amount": bill.amount / 100,
                    "bill_payer_type": "MEMBER",
                    "treatment_id": bill.procedure_id,
                }
            ]
        }

    def test_confirm_cost_breakdown_error_trigger_billing(
        self, admin_client, medical_procedure, wallet, bill
    ):
        medical_procedure.status = TreatmentProcedureStatus.COMPLETED
        with patch(
            "admin.views.models.cost_breakdown.create_member_and_employer_bill"
        ) as create_member_and_employer_bill:
            create_member_and_employer_bill.side_effect = Exception(
                "Failed to trigger billing and deduct balance from wallet"
            )
            res = admin_client.post(
                "/admin/cost_breakdown_calculator/confirm",
                json={
                    "breakdowns": [
                        {
                            "treatment_id": medical_procedure.id,
                            "treatment_uuid": medical_procedure.uuid,
                            "treatment_type": medical_procedure.procedure_type.value,
                            "treatment_cost_credit": medical_procedure.cost_credit,
                            "cost": 100.0,
                            "total_member_responsibility": 100.0,
                            "total_employer_responsibility": 200.0,
                            "is_unlimited": False,
                            "beginning_wallet_balance": 300.0,
                            "ending_wallet_balance": 100.0,
                            "deductible": 50.0,
                            "deductible_remaining": 0.0,
                            "family_deductible_remaining": 0.0,
                            "coinsurance": 50.0,
                            "copay": 0.0,
                            "oop_remaining": 300.0,
                            "oop_applied": 100.0,
                            "hra_applied": 0,
                            "family_oop_remaining": 300.0,
                            "overage_amount": 0.0,
                            "amount_type": "INDIVIDUAL",
                            "cost_breakdown_type": "DEDUCTIBLE_ACCUMULATION",
                            "rte_transaction_id": None,
                            "calc_config": {},
                        }
                    ],
                },
                headers={"Content-Type": "application/json"},
            )
        assert res.status_code == 400
        create_member_and_employer_bill.assert_called_once_with(
            treatment_procedure_id=medical_procedure.id,
            cost_breakdown_id=ANY,
            wallet_id=wallet.id,
            treatment_procedure_status=TreatmentProcedureStatus.COMPLETED,
        )
        assert (
            res.json["error"]
            == "An unexpected error has occurred. Please reach out to @payments-platform-oncall and provide the following message: Failed to trigger billing and deduct balance from wallet"
        )
