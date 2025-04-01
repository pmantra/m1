from unittest.mock import patch

import pytest

from cost_breakdown.errors import NoPatientNameFoundError
from cost_breakdown.rte.rx_rte_processor import RxRteProcessor
from direct_payment.pharmacy.pytests.factories import HealthPlanYearToDateSpendFactory
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
    ReimbursementOrganizationSettingsFactory,
)


@pytest.fixture(scope="function")
def copay_cost_sharing():
    cost_sharing = [
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COPAY,
            cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS,
            absolute_amount=2000,
        ),
    ]
    return cost_sharing


@pytest.fixture(scope="function")
def coinsurance_cost_sharing():
    cost_sharing = [
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COINSURANCE,
            cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS,
            percent=0.05,
        ),
    ]
    return cost_sharing


@pytest.fixture(scope="function")
def coinsurance_cost_sharing_with_min_max():
    cost_sharing = [
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COINSURANCE,
            cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS,
            percent=0.05,
        ),
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COINSURANCE_MAX,
            cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS,
            absolute_amount=20000,
        ),
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COINSURANCE_MIN,
            cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS,
            absolute_amount=10000,
        ),
    ]
    return cost_sharing


@pytest.fixture(scope="function")
def individual_member_health_plan(
    wallet_deductible_accumulation, copay_cost_sharing, db
):
    member_health_plan = wallet_deductible_accumulation.member_health_plan[0]
    member_health_plan.plan_type = FamilyPlanType.INDIVIDUAL
    member_health_plan.is_subscriber = True
    ehp = member_health_plan.employer_health_plan

    # clear past cost sharings before adding new ones.
    for cost_sharing in ehp.cost_sharings:
        db.session.delete(cost_sharing)

    modified_rx_ehp = EmployerHealthPlanFactory.create(
        reimbursement_organization_settings=wallet_deductible_accumulation.reimbursement_organization_settings,
        cost_sharings=copay_cost_sharing,
        rx_integrated=False,
        coverage=[
            EmployerHealthPlanCoverageFactory.create(
                coverage_type=CoverageType.RX,
                individual_deductible=1000_00,
                individual_oop=2000_00,
            ),
        ],
    )
    member_health_plan.employer_health_plan = modified_rx_ehp
    wallet_deductible_accumulation.reimbursement_organization_settings.deductible_accumulation_enabled = (
        True
    )
    return member_health_plan


@pytest.fixture(scope="function")
def family_member_health_plan(wallet_deductible_accumulation, copay_cost_sharing, db):
    member_health_plan = wallet_deductible_accumulation.member_health_plan[0]
    member_health_plan.plan_type = FamilyPlanType.FAMILY
    member_health_plan.is_subscriber = True
    ehp = member_health_plan.employer_health_plan

    # clear past cost sharings before adding new ones.
    for cost_sharing in ehp.cost_sharings:
        db.session.delete(cost_sharing)

    modified_rx_ehp = EmployerHealthPlanFactory.create(
        reimbursement_organization_settings=wallet_deductible_accumulation.reimbursement_organization_settings,
        cost_sharings=copay_cost_sharing,
        rx_integrated=False,
        coverage=[
            EmployerHealthPlanCoverageFactory.create(
                coverage_type=CoverageType.RX,
                individual_deductible=1000_00,
                individual_oop=2000_00,
                family_deductible=2000_00,
                family_oop=3000_00,
                plan_type=FamilyPlanType.FAMILY,
            ),
        ],
    )
    member_health_plan.employer_health_plan = modified_rx_ehp

    return member_health_plan


@pytest.fixture(scope="function")
def rx_rte_proc():
    return RxRteProcessor()


@pytest.fixture
def multiple_ytd_spends():
    mocked_ytd_spends = [
        HealthPlanYearToDateSpendFactory.create(
            policy_id="policy1",
            first_name="paul",
            last_name="chris",
            year=2023,
            source="MAVEN",
            deductible_applied_amount=10000,
            oop_applied_amount=10000,
        ),
        HealthPlanYearToDateSpendFactory.create(
            policy_id="policy1",
            first_name="paul",
            last_name="chris",
            year=2023,
            source="MAVEN",
            deductible_applied_amount=15000,
            oop_applied_amount=15000,
        ),
        HealthPlanYearToDateSpendFactory.create(
            policy_id="policy1",
            first_name="paul",
            last_name="chris",
            year=2023,
            source="ESI",
            deductible_applied_amount=50000,
            oop_applied_amount=50000,
        ),
    ]
    return mocked_ytd_spends


class TestRxRteProcessor:
    def test_get_rte_individual_success(
        self,
        rx_rte_proc,
        rx_procedure,
        individual_member_health_plan,
        multiple_ytd_spends,
    ):
        with patch(
            "cost_breakdown.rte.rx_rte_processor.get_member_first_and_last_name",
            return_value=["firstname", "lastname"],
        ), patch(
            "cost_breakdown.rte.rx_rte_processor.HealthPlanYearToDateSpendService.get_all_by_member",
            return_value=multiple_ytd_spends,
        ):
            eligibility_info = rx_rte_proc.get_rte(
                treatment_procedure=rx_procedure,
                member_health_plan=individual_member_health_plan,
                cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS,
                tier=None,
            )
            assert eligibility_info.individual_deductible == 100000
            assert eligibility_info.individual_deductible_remaining == 25000
            assert eligibility_info.individual_oop == 200000
            assert eligibility_info.individual_oop_remaining == 125000
            assert eligibility_info.copay == 2000

    def test_get_rte_family_success(
        self, rx_rte_proc, rx_procedure, family_member_health_plan, multiple_ytd_spends
    ):
        with patch(
            "cost_breakdown.rte.rx_rte_processor.get_member_first_and_last_name",
            return_value=["firstname", "lastname"],
        ), patch(
            "cost_breakdown.rte.rx_rte_processor.HealthPlanYearToDateSpendService.get_all_by_policy",
            return_value=multiple_ytd_spends,
        ), patch(
            "cost_breakdown.rte.rx_rte_processor.HealthPlanYearToDateSpendService.get_all_by_member",
            return_value=multiple_ytd_spends,
        ):
            eligibility_info = rx_rte_proc.get_rte(
                treatment_procedure=rx_procedure,
                member_health_plan=family_member_health_plan,
                cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS,
                tier=None,
            )
            assert eligibility_info.family_deductible == 200000
            assert eligibility_info.family_deductible_remaining == 125000
            assert eligibility_info.family_oop == 300000
            assert eligibility_info.family_oop_remaining == 225000
            assert eligibility_info.copay == 2000
            assert eligibility_info.individual_deductible == 100000
            assert eligibility_info.individual_deductible_remaining == 25000
            assert eligibility_info.individual_oop == 200000
            assert eligibility_info.individual_oop_remaining == 125000

    def test_get_rte_individual_success_hit_deductible(
        self,
        rx_rte_proc,
        rx_procedure,
        copay_cost_sharing,
        wallet_deductible_accumulation,
        multiple_ytd_spends,
    ):
        org_settings = ReimbursementOrganizationSettingsFactory.create(
            organization_id=1,
            deductible_accumulation_enabled=True,
        )
        employer_health_plan = EmployerHealthPlanFactory.create(
            cost_sharings=copay_cost_sharing,
            reimbursement_organization_settings=org_settings,
            rx_integrated=False,
            coverage=[
                EmployerHealthPlanCoverageFactory(
                    coverage_type=CoverageType.RX,
                    individual_deductible=50000,
                    individual_oop=100000,
                ),
            ],
        )
        individual_member_health_plan = (
            wallet_deductible_accumulation.member_health_plan[0]
        )
        individual_member_health_plan.plan_type = FamilyPlanType.INDIVIDUAL
        individual_member_health_plan.is_subscriber = True
        individual_member_health_plan.employer_health_plan = employer_health_plan
        with patch(
            "cost_breakdown.rte.rx_rte_processor.get_member_first_and_last_name",
            return_value=["firstname", "lastname"],
        ), patch(
            "cost_breakdown.rte.rx_rte_processor.HealthPlanYearToDateSpendService.get_all_by_member",
            return_value=multiple_ytd_spends,
        ):
            eligibility_info = rx_rte_proc.get_rte(
                treatment_procedure=rx_procedure,
                member_health_plan=individual_member_health_plan,
                cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS,
                tier=None,
            )
            assert eligibility_info.individual_deductible == 500_00
            assert eligibility_info.individual_deductible_remaining == 0
            assert eligibility_info.individual_oop == 1000_00
            assert eligibility_info.individual_oop_remaining == 250_00
            assert eligibility_info.copay == 2000

    def test_get_rte_individual_success_hit_oop(
        self,
        rx_rte_proc,
        rx_procedure,
        copay_cost_sharing,
        wallet_deductible_accumulation,
        multiple_ytd_spends,
    ):
        org_settings = ReimbursementOrganizationSettingsFactory.create(
            organization_id=1,
            deductible_accumulation_enabled=True,
        )
        employer_health_plan = EmployerHealthPlanFactory.create(
            cost_sharings=copay_cost_sharing,
            reimbursement_organization_settings=org_settings,
            rx_integrated=False,
            rx_ind_deductible_limit=25000,
            rx_ind_oop_max_limit=50000,
            coverage=[
                EmployerHealthPlanCoverageFactory(
                    coverage_type=CoverageType.RX,
                    individual_deductible=25000,
                    individual_oop=50000,
                ),
            ],
        )
        individual_member_health_plan = (
            wallet_deductible_accumulation.member_health_plan[0]
        )
        individual_member_health_plan.plan_type = FamilyPlanType.INDIVIDUAL
        individual_member_health_plan.is_subscriber = True
        individual_member_health_plan.employer_health_plan = employer_health_plan
        with patch(
            "cost_breakdown.rte.rx_rte_processor.get_member_first_and_last_name",
            return_value=["firstname", "lastname"],
        ), patch(
            "cost_breakdown.rte.rx_rte_processor.HealthPlanYearToDateSpendService.get_all_by_member",
            return_value=multiple_ytd_spends,
        ):
            eligibility_info = rx_rte_proc.get_rte(
                treatment_procedure=rx_procedure,
                member_health_plan=individual_member_health_plan,
                cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS,
                tier=None,
            )
            assert eligibility_info.individual_deductible == 25000
            assert eligibility_info.individual_deductible_remaining == 0
            assert eligibility_info.individual_oop == 50000
            assert eligibility_info.individual_oop_remaining == 0
            assert eligibility_info.copay == 2000

    def test_get_rte_no_member_name(
        self, rx_rte_proc, rx_procedure, member_health_plan
    ):
        with patch(
            "cost_breakdown.rte.rx_rte_processor.get_member_first_and_last_name",
            return_value=[None, None],
        ), pytest.raises(NoPatientNameFoundError):
            rx_rte_proc.get_rte(
                treatment_procedure=rx_procedure,
                member_health_plan=member_health_plan,
                cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS,
                tier=None,
            )

    def test_get_rte_no_ytd_spend_returned(
        self, rx_rte_proc, rx_procedure, individual_member_health_plan
    ):
        with patch(
            "cost_breakdown.rte.rx_rte_processor.get_member_first_and_last_name",
            return_value=["firstname", "lastname"],
        ), patch(
            "cost_breakdown.rte.rx_rte_processor.HealthPlanYearToDateSpendService.get_all_by_member",
            return_value=[],
        ):
            eligibility_info = rx_rte_proc.get_rte(
                treatment_procedure=rx_procedure,
                member_health_plan=individual_member_health_plan,
                cost_sharing_category=CostSharingCategory.GENERIC_PRESCRIPTIONS,
                tier=None,
            )
            assert eligibility_info.individual_deductible == 100000
            assert eligibility_info.individual_deductible_remaining == 100000
            assert eligibility_info.individual_oop == 200000
            assert eligibility_info.individual_oop_remaining == 200000
            assert eligibility_info.copay == 2000
