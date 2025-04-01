import decimal
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from cost_breakdown.constants import AmountType, PlanCoverage, Tier
from cost_breakdown.errors import (
    NoCostSharingFoundError,
    NoIrsDeductibleFoundError,
    TieredConfigurationError,
)
from cost_breakdown.models.rte import EligibilityInfo
from cost_breakdown.pytests.factories import (
    CostBreakdownFactory,
    CostBreakdownIrsMinimumDeductibleFactory,
)
from cost_breakdown.utils.helpers import (
    get_amount_type,
    get_calculation_tier,
    get_cycle_based_wallet_balance_from_credit,
    get_effective_date_from_cost_breakdown,
    get_irs_limit,
    get_medical_coverage,
    get_rx_coverage,
    get_scheduled_procedure_costs,
    get_scheduled_procedure_costs_for_clinic_portal,
    get_scheduled_tp_and_pending_rr_costs,
    is_plan_tiered,
    set_db_copay_coinsurance_to_eligibility_info,
)
from direct_payment.clinic.pytests.factories import FertilityClinicLocationFactory
from direct_payment.treatment_procedure.models.treatment_procedure import (
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
    ReimbursementRequestState,
    WalletState,
)
from wallet.models.reimbursement_organization_settings import (
    EmployerHealthPlanCostSharing,
)
from wallet.pytests.factories import (
    EmployerHealthPlanCoverageFactory,
    EmployerHealthPlanFactory,
    FertilityClinicLocationEmployerHealthPlanTierFactory,
    ReimbursementRequestFactory,
)
from wallet.repository.health_plan import HEALTH_PLAN_YOY_FLAG, NEW_BEHAVIOR
from wallet.utils.common import get_pending_reimbursement_requests_costs


@pytest.fixture()
def enable_health_plan_feature(ff_test_data):
    ff_test_data.update(
        ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(NEW_BEHAVIOR)
    )


@pytest.fixture(scope="function")
def cost_breakdown_irs_minimum_threshold():
    CostBreakdownIrsMinimumDeductibleFactory.create(
        individual_amount=150_000,
        family_amount=300_000,
    )


@pytest.fixture(scope="function")
def cost_sharings():
    cost_sharings = [
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
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COINSURANCE_MAX,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            absolute_amount=2000,
        ),
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COINSURANCE_MIN,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            absolute_amount=1000,
        ),
    ]
    return cost_sharings


@pytest.mark.parametrize(
    argnames="is_individual,expected", argvalues=[(True, 150_000), (False, 300_000)]
)
def test_get_irs_limit(is_individual, expected, cost_breakdown_irs_minimum_threshold):
    assert get_irs_limit(is_individual) == expected


def test_get_irs_limit_no_row_found():
    with pytest.raises(NoIrsDeductibleFoundError):
        get_irs_limit(True)


@pytest.mark.parametrize(
    argnames="plan_type, expected_type",
    argvalues=[
        (FamilyPlanType.INDIVIDUAL, AmountType.INDIVIDUAL),
        (FamilyPlanType.FAMILY, AmountType.FAMILY),
    ],
)
def test_get_amount_type(
    plan_type,
    expected_type,
    member_health_plan,
):
    member_health_plan.plan_type = plan_type
    amount_type = get_amount_type(member_health_plan)
    assert amount_type == expected_type


class TestCreditWalletBalance:
    def test_get_credit_wallet_balance_for_non_credit_wallet(
        self, wallet, wallet_category
    ):
        balance = get_cycle_based_wallet_balance_from_credit(
            wallet=wallet, category_id=wallet_category.id, cost_credit=0, cost=100
        )
        assert balance is None

    @pytest.mark.parametrize(
        "cycle_credits,cost_credits,cost,expected_balance",
        [
            (60, 1, 100, 100),
            (0, 1, 100, 0),
            (0, 0, 100, 100),
            (4, 5, 100, 80),
        ],
    )
    def test_get_credit_wallet_balance(
        self,
        wallet_cycle_based,
        wallet_cycle_based_category,
        cycle_credits,
        cost_credits,
        cost,
        expected_balance,
    ):
        wallet_cycle_based.cycle_credits[0].amount = cycle_credits
        balance = get_cycle_based_wallet_balance_from_credit(
            wallet=wallet_cycle_based,
            category_id=wallet_cycle_based_category.id,
            cost_credit=cost_credits,
            cost=cost,
        )
        assert balance == expected_balance


class TestPendingScheduleCosts:
    def test_get_pending_reimbursement_requests_costs_cycle_wallet(
        self, wallet_cycle_based, pending_cycle_reimbursement_request
    ):
        # Given
        wallet_cycle_based.state = WalletState.QUALIFIED
        pending_cycle_reimbursement_request.cost_credit = 5
        pending_credits = get_pending_reimbursement_requests_costs(
            wallet=wallet_cycle_based, remaining_balance=20
        )
        assert pending_credits == pending_cycle_reimbursement_request.cost_credit

    def test_get_pending_reimbursement_requests_costs_null(self, wallet_cycle_based):
        scheduled_costs = get_scheduled_procedure_costs(
            wallet_cycle_based, remaining_balance=4
        )
        assert scheduled_costs == 0

    def test_get_pending_reimbursement_requests_costs_cycle_wallet_overage(
        self, pending_cycle_reimbursement_request, wallet_cycle_based
    ):
        pending_cycle_reimbursement_request.cost_credit = 5
        scheduled_costs = get_pending_reimbursement_requests_costs(
            wallet_cycle_based, remaining_balance=4
        )
        assert scheduled_costs == 4

    def test_get_pending_reimbursement_requests_costs_wallet(
        self, pending_currency_reimbursement_request, wallet
    ):
        scheduled_costs = get_pending_reimbursement_requests_costs(
            wallet, remaining_balance=300
        )
        assert scheduled_costs == pending_currency_reimbursement_request.amount

    def test_get_pending_reimbursement_requests_costs_non_dp_wallet(
        self, wallet, pending_currency_reimbursement_request
    ):
        wallet.reimbursement_organization_settings.direct_payment_enabled = False

        scheduled_costs = get_pending_reimbursement_requests_costs(
            wallet, remaining_balance=300
        )
        assert scheduled_costs == 0

    def test_get_pending_reimbursement_requests_costs_wallet_multiple(
        self, pending_currency_reimbursement_request, wallet
    ):
        reimbursement_request_1 = pending_currency_reimbursement_request
        category = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ].reimbursement_request_category
        )
        reimbursement_request_2 = ReimbursementRequestFactory.create(
            id=12,
            person_receiving_service_id=1,
            procedure_type=TreatmentProcedureType.MEDICAL.value,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE.value,
            state=ReimbursementRequestState.PENDING,
            wallet=wallet,
            category=category,
            amount=100,
        )
        scheduled_costs = get_pending_reimbursement_requests_costs(
            wallet, remaining_balance=50
        )
        assert (
            scheduled_costs
            == reimbursement_request_1.amount + reimbursement_request_2.amount
        )

    def test_get_scheduled_costs_currency_wallet(self, treatment_procedure, wallet):
        cost_breakdown = CostBreakdownFactory.create(
            treatment_procedure_uuid=treatment_procedure.uuid,
            wallet_id=wallet.id,
            total_employer_responsibility=10,
        )
        treatment_procedure.cost_breakdown_id = cost_breakdown.id

        scheduled_costs = get_scheduled_procedure_costs(wallet, remaining_balance=50)
        assert scheduled_costs == 10

    def test_get_scheduled_costs_cost_breakdown_not_included(
        self, treatment_procedure, wallet
    ):
        treatment_procedure.cost_breakdown_id = None
        scheduled_costs = get_scheduled_procedure_costs(wallet, remaining_balance=4)
        assert scheduled_costs == 0

    def test_get_scheduled_costs_cost_breakdown_not_found(
        self, treatment_procedure, wallet
    ):
        treatment_procedure.cost_breakdown_id = 99
        scheduled_costs = get_scheduled_procedure_costs(wallet, remaining_balance=4)
        assert scheduled_costs == 0

    def test_get_scheduled_costs_currency_wallet_multi_procedure(
        self, treatment_procedure, treatment_procedure_cycle_based, wallet
    ):
        treatment_procedure_cycle_based.reimbursement_wallet_id = wallet.id
        cost_breakdown = CostBreakdownFactory.create(
            treatment_procedure_uuid=treatment_procedure.uuid,
            wallet_id=wallet.id,
            total_employer_responsibility=10,
        )
        treatment_procedure.cost_breakdown_id = cost_breakdown.id

        cost_breakdown_2 = CostBreakdownFactory.create(
            treatment_procedure_uuid=treatment_procedure_cycle_based.uuid,
            wallet_id=wallet.id,
            total_employer_responsibility=11,
        )
        treatment_procedure_cycle_based.cost_breakdown_id = cost_breakdown_2.id

        scheduled_costs = get_scheduled_procedure_costs(wallet, remaining_balance=50)
        assert scheduled_costs == 21

    def test_get_scheduled_costs_cycle_wallet(
        self, treatment_procedure_cycle_based, wallet_cycle_based
    ):
        cost_breakdown = CostBreakdownFactory.create(
            treatment_procedure_uuid=treatment_procedure_cycle_based.uuid,
            wallet_id=wallet_cycle_based.id,
            total_employer_responsibility=10,
        )
        treatment_procedure_cycle_based.cost_breakdown_id = cost_breakdown.id
        treatment_procedure_cycle_based.cost_credit = 5

        scheduled_costs = get_scheduled_procedure_costs(
            wallet_cycle_based, remaining_balance=50
        )
        assert scheduled_costs == 5

    def test_get_scheduled_costs_cycle_wallet_overage(
        self, treatment_procedure_cycle_based, wallet_cycle_based
    ):
        cost_breakdown = CostBreakdownFactory.create(
            treatment_procedure_uuid=treatment_procedure_cycle_based.uuid,
            wallet_id=wallet_cycle_based.id,
            total_employer_responsibility=10,
        )
        treatment_procedure_cycle_based.cost_breakdown_id = cost_breakdown.id
        treatment_procedure_cycle_based.cost_credit = 5

        scheduled_costs = get_scheduled_procedure_costs(
            wallet_cycle_based, remaining_balance=4
        )
        assert scheduled_costs == 4

    def test_get_scheduled_costs_tp_cost_breakdown_null(
        self, treatment_procedure_cycle_based, wallet_cycle_based
    ):
        scheduled_costs = get_scheduled_procedure_costs(
            wallet_cycle_based, remaining_balance=4
        )
        assert scheduled_costs == 0

    @pytest.mark.parametrize(
        argnames="remaining_balance, exp",
        argvalues=[
            pytest.param(4, 4, id="credit balance less than TP cost"),
            pytest.param(5, 5, id="credit balance equal to TP cost"),
            pytest.param(9, 5, id="credit balance greater than TP cost"),
            pytest.param(0, 0, id="credit balance zero"),
        ],
    )
    def test_get_scheduled_costs_cycle_for_clinic_portal_wallet_overage(
        self,
        treatment_procedure_cycle_based,
        wallet_cycle_based,
        remaining_balance,
        exp,
    ):
        cost_breakdown = CostBreakdownFactory.create(
            treatment_procedure_uuid=treatment_procedure_cycle_based.uuid,
            wallet_id=wallet_cycle_based.id,
            total_employer_responsibility=10,
        )
        treatment_procedure_cycle_based.cost_breakdown_id = cost_breakdown.id
        treatment_procedure_cycle_based.cost_credit = 5

        scheduled_costs = get_scheduled_procedure_costs_for_clinic_portal(
            wallet_cycle_based, remaining_balance=remaining_balance
        )
        assert scheduled_costs == exp

    @pytest.mark.parametrize(
        argnames="remaining_balance, exp",
        argvalues=[
            pytest.param(4, 4, id="credit balance less than TP cost"),
            pytest.param(5, 5, id="credit balance equal to TP cost"),
            pytest.param(9, 5, id="credit balance greater than TP cost"),
            pytest.param(0, 0, id="credit balance zero"),
        ],
    )
    def test_get_scheduled_costs_cycle_for_clinic_portal_tp_cost_breakdown_null(
        self,
        treatment_procedure_cycle_based,
        wallet_cycle_based,
        remaining_balance,
        exp,
    ):
        scheduled_costs = get_scheduled_procedure_costs_for_clinic_portal(
            wallet_cycle_based, remaining_balance=remaining_balance
        )
        assert scheduled_costs == exp

    @pytest.mark.parametrize(
        argnames="remaining_balance, exp",
        argvalues=[
            pytest.param(30, 30, id="wallet balance less than TP cost"),
            pytest.param(34, 34, id="wallet balance equal to TP cost"),
            pytest.param(99, 34, id="wallet balance greater than TP cost"),
            pytest.param(0, 0, id="wallet balance zero"),
        ],
    )
    def test_get_scheduled_costs_for_clinic_portal_tp_cost_breakdown_null(
        self,
        treatment_procedure,
        wallet,
        remaining_balance,
        exp,
    ):
        scheduled_costs = get_scheduled_procedure_costs_for_clinic_portal(
            wallet, remaining_balance=remaining_balance
        )
        assert scheduled_costs == exp

    @pytest.mark.parametrize(
        argnames="cb_exists,remaining_balance, emp_resp_1, emp_resp_2, exp",
        argvalues=[
            pytest.param(
                True, 50, 10, 11, 11, id="All cbs exist. Credit balance > total TP cost"
            ),
            pytest.param(
                True,
                50,
                0,
                0,
                0,
                id="All cbs exist. All emp resp is 0 in cb. Credit balance < total cost",
            ),
            pytest.param(
                True,
                50,
                10,
                0,
                6,
                id="All cbs exist. One emp resp is 0 in cb. Credit balance > total TP cost",
            ),
            pytest.param(
                False,
                50,
                10,
                None,
                11,
                id="One cb exists. Credit balance > total TP cost",
            ),
            pytest.param(
                True,
                5,
                10,
                0,
                5,
                id="All cbs exist. One emp resp is 0 in cb. Credit balance < total cost",
            ),
            pytest.param(
                False,
                9,
                10,
                None,
                9,
                id="One cb exists. Credit balance < total TP cost",
            ),
        ],
    )
    def test_get_scheduled_costs_cycle_for_clinic_portal_multi_procedure(
        self,
        treatment_procedure,
        treatment_procedure_cycle_based,
        wallet_cycle_based,
        cb_exists,
        remaining_balance,
        emp_resp_1,
        emp_resp_2,
        exp,
    ):
        treatment_procedure.reimbursement_wallet_id = wallet_cycle_based.id
        treatment_procedure.reimbursement_request_category_id = (
            treatment_procedure_cycle_based.reimbursement_request_category_id
        )
        treatment_procedure.cost_credit = 6
        cost_breakdown = CostBreakdownFactory.create(
            treatment_procedure_uuid=treatment_procedure.uuid,
            wallet_id=wallet_cycle_based.id,
            total_employer_responsibility=emp_resp_1,
        )
        treatment_procedure.cost_breakdown_id = cost_breakdown.id
        if cb_exists:
            cost_breakdown_2 = CostBreakdownFactory.create(
                treatment_procedure_uuid=treatment_procedure_cycle_based.uuid,
                wallet_id=wallet_cycle_based.id,
                total_employer_responsibility=emp_resp_2,
            )
            treatment_procedure_cycle_based.cost_breakdown_id = cost_breakdown_2.id

        scheduled_costs = get_scheduled_procedure_costs_for_clinic_portal(
            wallet_cycle_based, remaining_balance=remaining_balance
        )
        assert scheduled_costs == exp

    @pytest.mark.parametrize(
        argnames="cb_exists,remaining_balance, emp_resp_1, emp_resp_2, exp",
        argvalues=[
            pytest.param(
                True,
                500,
                60,
                30,
                90,
                id="All cbs exist. Wallet balance > total TP cost",
            ),
            pytest.param(
                True,
                500,
                0,
                0,
                0,
                id="All cbs exist. All emp resp is 0 in cb. Wallet balance irrelevant.",
            ),
            pytest.param(
                True,
                500,
                60,
                0,
                60,
                id="All cbs exist. One emp resp is 0 in cb. Wallet balance < total cost.",
            ),
            pytest.param(
                False,
                160_000,
                100_000,
                None,
                150_000,
                id="One cb exists. Wallet balance > total TP cost",
            ),
            pytest.param(
                True,
                5_000,
                5_000,
                0,
                5_000,
                id="All cbs exist. One emp resp is 0 in cb. Wallet balance eq. total cost",
            ),
            pytest.param(
                False,
                90,
                100,
                None,
                90,
                id="One cb exists. Wallet balance < total TP cost",
            ),
        ],
    )
    def test_get_scheduled_costs_for_clinic_portal_multi_procedure(
        self,
        treatment_procedure,
        treatment_procedure_cycle_based,
        wallet,
        cb_exists,
        remaining_balance,
        emp_resp_1,
        emp_resp_2,
        exp,
    ):
        treatment_procedure_cycle_based.reimbursement_wallet_id = wallet.id
        treatment_procedure.reimbursement_request_category_id = (
            treatment_procedure_cycle_based.reimbursement_request_category_id
        )
        treatment_procedure.cost = emp_resp_1
        cost_breakdown = CostBreakdownFactory.create(
            treatment_procedure_uuid=treatment_procedure.uuid,
            wallet_id=wallet.id,
            total_employer_responsibility=emp_resp_1,
        )
        treatment_procedure.cost_breakdown_id = cost_breakdown.id
        if cb_exists:
            treatment_procedure_cycle_based.cost = emp_resp_2
            cost_breakdown_2 = CostBreakdownFactory.create(
                treatment_procedure_uuid=treatment_procedure_cycle_based.uuid,
                wallet_id=wallet.id,
                total_employer_responsibility=emp_resp_2,
            )
            treatment_procedure_cycle_based.cost_breakdown_id = cost_breakdown_2.id

        scheduled_costs = get_scheduled_procedure_costs_for_clinic_portal(
            wallet, remaining_balance=remaining_balance
        )
        assert scheduled_costs == exp

    def test_get_scheduled_and_pending_costs_with_cycle_wallet_overage(
        self,
        treatment_procedure_cycle_based,
        wallet_cycle_based,
        pending_cycle_reimbursement_request,
    ):
        cost_breakdown = CostBreakdownFactory.create(
            treatment_procedure_uuid=treatment_procedure_cycle_based.uuid,
            wallet_id=wallet_cycle_based.id,
            total_employer_responsibility=10,
        )
        treatment_procedure_cycle_based.cost_breakdown_id = cost_breakdown.id
        treatment_procedure_cycle_based.cost_credit = 5
        pending_cycle_reimbursement_request.cost_credit = 8
        scheduled_and_pending_cost = get_scheduled_tp_and_pending_rr_costs(
            wallet=wallet_cycle_based, remaining_balance=10
        )
        assert scheduled_and_pending_cost == 10

    def test_get_scheduled_and_pending_costs_cycle_wallet(
        self,
        treatment_procedure_cycle_based,
        wallet_cycle_based,
        pending_cycle_reimbursement_request,
    ):
        cost_breakdown = CostBreakdownFactory.create(
            treatment_procedure_uuid=treatment_procedure_cycle_based.uuid,
            wallet_id=wallet_cycle_based.id,
            total_employer_responsibility=10,
        )
        treatment_procedure_cycle_based.cost_breakdown_id = cost_breakdown.id
        treatment_procedure_cycle_based.cost_credit = 5
        pending_cycle_reimbursement_request.cost_credit = 4
        scheduled_and_pending_cost = get_scheduled_tp_and_pending_rr_costs(
            wallet=wallet_cycle_based, remaining_balance=10
        )
        assert scheduled_and_pending_cost == 9

    def test_get_scheduled_and_pending_costs_currency_wallet(
        self, treatment_procedure, pending_currency_reimbursement_request, wallet
    ):
        cost_breakdown = CostBreakdownFactory.create(
            treatment_procedure_uuid=treatment_procedure.uuid,
            wallet_id=wallet.id,
            total_employer_responsibility=10,
        )
        treatment_procedure.cost_breakdown_id = cost_breakdown.id

        scheduled_costs = get_scheduled_tp_and_pending_rr_costs(
            wallet, remaining_balance=300
        )
        assert scheduled_costs == 110

    def test_get_scheduled_and_pending_costs_currency_wallet_overage(
        self, treatment_procedure, pending_currency_reimbursement_request, wallet
    ):
        cost_breakdown = CostBreakdownFactory.create(
            treatment_procedure_uuid=treatment_procedure.uuid,
            wallet_id=wallet.id,
            total_employer_responsibility=10,
        )
        treatment_procedure.cost_breakdown_id = cost_breakdown.id

        scheduled_costs = get_scheduled_tp_and_pending_rr_costs(
            wallet, remaining_balance=100
        )
        assert scheduled_costs == 110


class TestTieredCostSharingHelpers:
    @pytest.fixture(scope="function")
    def employer_health_plan_deprecated_config(self):
        return EmployerHealthPlanFactory.create(
            ind_deductible_limit=200_000,
            ind_oop_max_limit=400_000,
            fam_deductible_limit=400_000,
            fam_oop_max_limit=600_000,
            rx_ind_deductible_limit=50000,
            rx_ind_oop_max_limit=100_000,
            rx_fam_deductible_limit=100_000,
            rx_fam_oop_max_limit=200_000,
            is_oop_embedded=False,
            is_deductible_embedded=False,
            cost_sharings=[
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
            ],
        )

    @pytest.fixture(scope="function")
    def employer_health_plan_coverage_config_non_tiered(self):
        return EmployerHealthPlanFactory.create(
            cost_sharings=[
                EmployerHealthPlanCostSharing(
                    cost_sharing_type=CostSharingType.COINSURANCE,
                    cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
                    percent=0.05,
                    second_tier_percent=0.07,
                ),
                EmployerHealthPlanCostSharing(
                    cost_sharing_type=CostSharingType.COPAY,
                    cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
                    absolute_amount=2000,
                    second_tier_absolute_amount=3000,
                ),
            ],
            coverage=[
                EmployerHealthPlanCoverageFactory.create(),
                EmployerHealthPlanCoverageFactory.create(
                    plan_type=FamilyPlanType.EMPLOYEE_PLUS,
                    individual_deductible=150_000,
                    individual_oop=250_000,
                    family_deductible=350_000,
                    family_oop=550_000,
                    max_oop_per_covered_individual=400_000,
                    is_deductible_embedded=True,
                    is_oop_embedded=True,
                ),
                EmployerHealthPlanCoverageFactory.create(
                    plan_type=FamilyPlanType.FAMILY,
                    individual_deductible=200_000,
                    individual_oop=300_000,
                    family_deductible=400_000,
                    family_oop=600_000,
                ),
                EmployerHealthPlanCoverageFactory.create(
                    coverage_type=CoverageType.RX,
                    individual_deductible=10_000,
                    individual_oop=50_000,
                    family_deductible=60_000,
                    family_oop=100_000,
                ),
                EmployerHealthPlanCoverageFactory.create(
                    plan_type=FamilyPlanType.FAMILY,
                    coverage_type=CoverageType.RX,
                    individual_deductible=20_000,
                    individual_oop=70_000,
                    family_deductible=80_000,
                    family_oop=120_000,
                ),
                EmployerHealthPlanCoverageFactory.create(
                    plan_type=FamilyPlanType.EMPLOYEE_PLUS,
                    coverage_type=CoverageType.RX,
                    individual_deductible=15_000,
                    individual_oop=60_000,
                    family_deductible=70_000,
                    family_oop=110_000,
                ),
            ],
        )

    @pytest.fixture(scope="function")
    def employer_health_plan_coverage_config_tiered(self):
        return EmployerHealthPlanFactory.create(
            cost_sharings=[
                EmployerHealthPlanCostSharing(
                    cost_sharing_type=CostSharingType.COINSURANCE,
                    cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
                    percent=0.05,
                    second_tier_percent=0.07,
                ),
                EmployerHealthPlanCostSharing(
                    cost_sharing_type=CostSharingType.COPAY,
                    cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
                    absolute_amount=2000,
                    second_tier_absolute_amount=3000,
                ),
            ],
            coverage=[
                EmployerHealthPlanCoverageFactory.create(
                    tier=1,
                ),
                EmployerHealthPlanCoverageFactory.create(
                    plan_type=FamilyPlanType.EMPLOYEE_PLUS,
                    tier=1,
                    is_deductible_embedded=True,
                    is_oop_embedded=True,
                ),
                EmployerHealthPlanCoverageFactory.create(
                    plan_type=FamilyPlanType.FAMILY,
                    tier=1,
                ),
                EmployerHealthPlanCoverageFactory.create(
                    coverage_type=CoverageType.RX,
                    tier=1,
                ),
                EmployerHealthPlanCoverageFactory.create(
                    plan_type=FamilyPlanType.FAMILY,
                    coverage_type=CoverageType.RX,
                    tier=1,
                ),
                EmployerHealthPlanCoverageFactory.create(
                    plan_type=FamilyPlanType.EMPLOYEE_PLUS,
                    coverage_type=CoverageType.RX,
                    tier=1,
                ),
                EmployerHealthPlanCoverageFactory.create(
                    individual_deductible=125_000,
                    individual_oop=225_000,
                    family_deductible=325_000,
                    family_oop=525_000,
                    tier=2,
                ),
                EmployerHealthPlanCoverageFactory.create(
                    plan_type=FamilyPlanType.EMPLOYEE_PLUS,
                    individual_deductible=150_000,
                    individual_oop=250_000,
                    family_deductible=350_000,
                    family_oop=550_000,
                    tier=2,
                    is_deductible_embedded=True,
                    is_oop_embedded=True,
                ),
                EmployerHealthPlanCoverageFactory.create(
                    plan_type=FamilyPlanType.FAMILY,
                    individual_deductible=200_000,
                    individual_oop=300_000,
                    family_deductible=400_000,
                    family_oop=600_000,
                    tier=2,
                ),
                EmployerHealthPlanCoverageFactory.create(
                    coverage_type=CoverageType.RX,
                    individual_deductible=11_000,
                    individual_oop=51_000,
                    family_deductible=61_000,
                    family_oop=101_000,
                    tier=2,
                ),
                EmployerHealthPlanCoverageFactory.create(
                    plan_type=FamilyPlanType.FAMILY,
                    coverage_type=CoverageType.RX,
                    individual_deductible=22_000,
                    individual_oop=72_000,
                    family_deductible=82_000,
                    family_oop=122_000,
                    tier=2,
                ),
                EmployerHealthPlanCoverageFactory.create(
                    plan_type=FamilyPlanType.EMPLOYEE_PLUS,
                    coverage_type=CoverageType.RX,
                    individual_deductible=17_000,
                    individual_oop=61_000,
                    family_deductible=71_000,
                    family_oop=111_000,
                    tier=2,
                ),
            ],
        )

    def test_is_plan_tiered(
        self,
        employer_health_plan_deprecated_config,
        employer_health_plan_coverage_config_non_tiered,
        employer_health_plan_coverage_config_tiered,
    ):
        employer_health_plan_deprecated_config.created_at = datetime.strptime(
            "23/10/2024 00:01", "%d/%m/%Y %H:%M"
        )
        employer_health_plan_coverage_config_non_tiered.created_at = datetime.strptime(
            "24/10/2024 00:01", "%d/%m/%Y %H:%M"
        )
        employer_health_plan_coverage_config_tiered.created_at = datetime.strptime(
            "24/10/2024 00:01", "%d/%m/%Y %H:%M"
        )
        assert is_plan_tiered(employer_health_plan_coverage_config_tiered) is True
        assert is_plan_tiered(employer_health_plan_deprecated_config) is False
        assert is_plan_tiered(employer_health_plan_coverage_config_non_tiered) is False

    def test_get_cost_breakdown_tier(self, employer_health_plan_coverage_config_tiered):
        procedure_date = datetime.strptime("2024-06-15", "%Y-%m-%d").date()
        procedure_date_outside_range = datetime.strptime(
            "2024-12-16", "%Y-%m-%d"
        ).date()
        employer_health_plan_coverage_config_tiered.created_at = datetime.strptime(
            "24/10/2024 00:01", "%d/%m/%Y %H:%M"
        )
        fertility_clinic_location = FertilityClinicLocationFactory.create()
        fertility_clinic_location_not_tiered = FertilityClinicLocationFactory.create()
        assert (
            get_calculation_tier(
                fertility_clinic_location=fertility_clinic_location,
                ehp=employer_health_plan_coverage_config_tiered,
                treatment_procedure_start=procedure_date,
            )
            == Tier.SECONDARY
        )
        tier = FertilityClinicLocationEmployerHealthPlanTierFactory.create(
            employer_health_plan=employer_health_plan_coverage_config_tiered,
            employer_health_plan_id=employer_health_plan_coverage_config_tiered.id,
            fertility_clinic_location=fertility_clinic_location,
            fertility_clinic_location_id=fertility_clinic_location.id,
        )
        employer_health_plan_coverage_config_tiered.tiers = [tier]
        assert (
            get_calculation_tier(
                fertility_clinic_location=fertility_clinic_location,
                ehp=employer_health_plan_coverage_config_tiered,
                treatment_procedure_start=procedure_date,
            )
            == Tier.PREMIUM
        )
        assert (
            get_calculation_tier(
                fertility_clinic_location=fertility_clinic_location,
                ehp=employer_health_plan_coverage_config_tiered,
                treatment_procedure_start=procedure_date_outside_range,
            )
            == Tier.SECONDARY
        )
        assert (
            get_calculation_tier(
                fertility_clinic_location=fertility_clinic_location_not_tiered,
                ehp=employer_health_plan_coverage_config_tiered,
                treatment_procedure_start=procedure_date,
            )
            == Tier.SECONDARY
        )

    @pytest.mark.parametrize(
        argnames="employer_health_plan, created_at, plan_size, tier, expected_ind_deductible, expected_ind_oop, expected_family_deductible, expected_family_oop, expected_max_oop_per_covered_individual, expected_is_deductible_embedded, expected_is_oop_embedded",
        argvalues=[
            (
                "employer_health_plan_deprecated_config",
                "23/10/2024 00:00",
                FamilyPlanType.INDIVIDUAL,
                None,
                200_000,
                400_000,
                400_000,
                600_000,
                None,
                False,
                False,
            ),
            (
                "employer_health_plan_coverage_config_non_tiered",
                "24/10/2024 00:01",
                FamilyPlanType.INDIVIDUAL,
                None,
                100_000,
                200_000,
                300_000,
                500_000,
                None,
                False,
                False,
            ),
            (
                "employer_health_plan_coverage_config_non_tiered",
                "24/10/2024 00:01",
                FamilyPlanType.EMPLOYEE_PLUS,
                None,
                150_000,
                250_000,
                350_000,
                550_000,
                400_000,
                True,
                True,
            ),
            (
                "employer_health_plan_coverage_config_non_tiered",
                "24/10/2024 00:01",
                FamilyPlanType.FAMILY,
                None,
                200_000,
                300_000,
                400_000,
                600_000,
                None,
                False,
                False,
            ),
            (
                "employer_health_plan_coverage_config_tiered",
                "24/10/2024 00:01",
                FamilyPlanType.INDIVIDUAL,
                Tier.PREMIUM,
                100_000,
                200_000,
                300_000,
                500_000,
                None,
                False,
                False,
            ),
            (
                "employer_health_plan_coverage_config_tiered",
                "24/10/2024 00:01",
                FamilyPlanType.EMPLOYEE_PLUS,
                Tier.PREMIUM,
                100_000,
                200_000,
                300_000,
                500_000,
                None,
                True,
                True,
            ),
            (
                "employer_health_plan_coverage_config_tiered",
                "24/10/2024 00:01",
                FamilyPlanType.FAMILY,
                Tier.PREMIUM,
                100_000,
                200_000,
                300_000,
                500_000,
                None,
                False,
                False,
            ),
            (
                "employer_health_plan_coverage_config_tiered",
                "24/10/2024 00:01",
                FamilyPlanType.INDIVIDUAL,
                Tier.SECONDARY,
                125_000,
                225_000,
                325_000,
                525_000,
                None,
                False,
                False,
            ),
            (
                "employer_health_plan_coverage_config_tiered",
                "24/10/2024 00:01",
                FamilyPlanType.EMPLOYEE_PLUS,
                Tier.SECONDARY,
                150_000,
                250_000,
                350_000,
                550_000,
                None,
                True,
                True,
            ),
            (
                "employer_health_plan_coverage_config_tiered",
                "24/10/2024 00:01",
                FamilyPlanType.FAMILY,
                Tier.SECONDARY,
                200_000,
                300_000,
                400_000,
                600_000,
                None,
                False,
                False,
            ),
        ],
    )
    def test_get_medical_coverage(
        self,
        employer_health_plan,
        created_at,
        plan_size,
        tier,
        expected_ind_deductible,
        expected_ind_oop,
        expected_family_deductible,
        expected_family_oop,
        expected_max_oop_per_covered_individual,
        expected_is_deductible_embedded,
        expected_is_oop_embedded,
        request,
    ):
        ehp = request.getfixturevalue(employer_health_plan)
        ehp.created_at = datetime.strptime(created_at, "%d/%m/%Y %H:%M")
        coverage_fetched = get_medical_coverage(ehp=ehp, plan_size=plan_size, tier=tier)
        assert coverage_fetched == PlanCoverage(
            individual_deductible=expected_ind_deductible,
            individual_oop=expected_ind_oop,
            family_deductible=expected_family_deductible,
            family_oop=expected_family_oop,
            max_oop_per_covered_individual=expected_max_oop_per_covered_individual,
            is_deductible_embedded=expected_is_deductible_embedded,
            is_oop_embedded=expected_is_oop_embedded,
        )

    @pytest.mark.parametrize(
        argnames="employer_health_plan, created_at, plan_size, tier, expected_ind_deductible, expected_ind_oop, expected_family_deductible, expected_family_oop, expected_max_oop_per_covered_individual, expected_is_deductible_embedded, expected_is_oop_embedded",
        argvalues=[
            (
                "employer_health_plan_deprecated_config",
                "23/10/2024 00:00",
                FamilyPlanType.INDIVIDUAL,
                None,
                50_000,
                100_000,
                100_000,
                200_000,
                None,
                False,
                False,
            ),
            (
                "employer_health_plan_coverage_config_non_tiered",
                "24/10/2024 00:01",
                FamilyPlanType.INDIVIDUAL,
                None,
                10_000,
                50_000,
                60_000,
                100_000,
                None,
                False,
                False,
            ),
            (
                "employer_health_plan_coverage_config_non_tiered",
                "24/10/2024 00:01",
                FamilyPlanType.EMPLOYEE_PLUS,
                None,
                15_000,
                60_000,
                70_000,
                110_000,
                None,
                False,
                False,
            ),
            (
                "employer_health_plan_coverage_config_non_tiered",
                "24/10/2024 00:01",
                FamilyPlanType.FAMILY,
                None,
                20_000,
                70_000,
                80_000,
                120_000,
                None,
                False,
                False,
            ),
            (
                "employer_health_plan_coverage_config_tiered",
                "24/10/2024 00:01",
                FamilyPlanType.INDIVIDUAL,
                Tier.PREMIUM,
                100_000,
                200_000,
                300_000,
                500_000,
                None,
                False,
                False,
            ),
            (
                "employer_health_plan_coverage_config_tiered",
                "24/10/2024 00:01",
                FamilyPlanType.EMPLOYEE_PLUS,
                Tier.PREMIUM,
                100_000,
                200_000,
                300_000,
                500_000,
                None,
                False,
                False,
            ),
            (
                "employer_health_plan_coverage_config_tiered",
                "24/10/2024 00:01",
                FamilyPlanType.FAMILY,
                Tier.PREMIUM,
                100_000,
                200_000,
                300_000,
                500_000,
                None,
                False,
                False,
            ),
            (
                "employer_health_plan_coverage_config_tiered",
                "24/10/2024 00:01",
                FamilyPlanType.INDIVIDUAL,
                Tier.SECONDARY,
                11_000,
                51_000,
                61_000,
                101_000,
                None,
                False,
                False,
            ),
            (
                "employer_health_plan_coverage_config_tiered",
                "24/10/2024 00:01",
                FamilyPlanType.EMPLOYEE_PLUS,
                Tier.SECONDARY,
                17_000,
                61_000,
                71_000,
                111_000,
                None,
                False,
                False,
            ),
            (
                "employer_health_plan_coverage_config_tiered",
                "24/10/2024 00:01",
                FamilyPlanType.FAMILY,
                Tier.SECONDARY,
                22_000,
                72_000,
                82_000,
                122_000,
                None,
                False,
                False,
            ),
        ],
    )
    def test_get_rx_coverage(
        self,
        employer_health_plan,
        created_at,
        plan_size,
        tier,
        expected_ind_deductible,
        expected_ind_oop,
        expected_family_deductible,
        expected_family_oop,
        expected_max_oop_per_covered_individual,
        expected_is_deductible_embedded,
        expected_is_oop_embedded,
        request,
    ):
        ehp = request.getfixturevalue(employer_health_plan)
        ehp.created_at = datetime.strptime(created_at, "%d/%m/%Y %H:%M")
        coverage_fetched = get_rx_coverage(ehp=ehp, plan_size=plan_size, tier=tier)
        assert coverage_fetched == PlanCoverage(
            individual_deductible=expected_ind_deductible,
            individual_oop=expected_ind_oop,
            family_deductible=expected_family_deductible,
            family_oop=expected_family_oop,
            max_oop_per_covered_individual=expected_max_oop_per_covered_individual,
            is_deductible_embedded=expected_is_deductible_embedded,
            is_oop_embedded=expected_is_oop_embedded,
        )

    @pytest.mark.parametrize(
        argnames="feature_flag_value,expected_ind_deductible,expected_ind_oop,expected_family_deductible,expected_family_oop,expected_is_deductible_embedded,expected_is_oop_embedded",
        argvalues=[
            (
                False,  # feature_flag_value
                200_000,  # expected_ind_deductible
                400_000,  # expected_ind_oop
                400_000,  # expected_family_deductible
                600_000,  # expected_family_oop
                False,  # expected_is_deductible_embedded
                False,  # expected_is_oop_embedded
            ),
            (
                True,  # feature_flag_value
                150_000,  # expected_ind_deductible
                250_000,  # expected_ind_oop
                350_000,  # expected_family_deductible
                550_000,  # expected_family_oop
                True,  # expected_is_deductible_embedded
                True,  # expected_is_oop_embedded
            ),
        ],
    )
    def test_coverage_feature_flag_on(
        self,
        feature_flag_value,
        expected_ind_deductible,
        expected_ind_oop,
        expected_family_deductible,
        expected_family_oop,
        expected_is_deductible_embedded,
        expected_is_oop_embedded,
    ):
        ehp = EmployerHealthPlanFactory.create(
            ind_deductible_limit=200_000,
            ind_oop_max_limit=400_000,
            fam_deductible_limit=400_000,
            fam_oop_max_limit=600_000,
            rx_ind_deductible_limit=50000,
            rx_ind_oop_max_limit=100_000,
            rx_fam_deductible_limit=100_000,
            rx_fam_oop_max_limit=200_000,
            is_oop_embedded=False,
            is_deductible_embedded=False,
            coverage=[
                EmployerHealthPlanCoverageFactory.create(),
                EmployerHealthPlanCoverageFactory.create(
                    plan_type=FamilyPlanType.EMPLOYEE_PLUS,
                    individual_deductible=150_000,
                    individual_oop=250_000,
                    family_deductible=350_000,
                    family_oop=550_000,
                    is_deductible_embedded=True,
                    is_oop_embedded=True,
                ),
            ],
        )
        ehp.created_at = datetime.strptime("23/10/2024 00:00", "%d/%m/%Y %H:%M")
        with patch(
            "cost_breakdown.cost_breakdown_processor.feature_flags.bool_variation",
            return_value=feature_flag_value,
        ):
            coverage = get_medical_coverage(
                ehp=ehp, plan_size=FamilyPlanType.EMPLOYEE_PLUS
            )
            assert coverage.individual_deductible == expected_ind_deductible
            assert coverage.individual_oop == expected_ind_oop
            assert coverage.family_deductible == expected_family_deductible
            assert coverage.family_oop == expected_family_oop
            assert coverage.is_deductible_embedded == expected_is_deductible_embedded
            assert coverage.is_oop_embedded == expected_is_oop_embedded

    @pytest.mark.parametrize("wrong_number_of_plans", [0, 2])
    def test_coverage_errors(self, employer_health_plan, wrong_number_of_plans):
        employer_health_plan.coverage = EmployerHealthPlanCoverageFactory.create_batch(
            size=wrong_number_of_plans,
            plan_type=FamilyPlanType.EMPLOYEE_PLUS,
            coverage_type=CoverageType.MEDICAL,
        )
        with pytest.raises(TieredConfigurationError):
            get_medical_coverage(
                ehp=employer_health_plan, plan_size=FamilyPlanType.EMPLOYEE_PLUS
            )


class TestGetEffectiveDate:
    def test_date_from_procedure(self):
        # Note Treatment Procedure start_dates are dates, not datetimes.
        # The resulting effective dates will always be at 0:00:00
        expected_date = datetime(year=2026, month=7, day=21, hour=0, minute=0, second=0)
        procedure = TreatmentProcedureFactory.create(start_date=expected_date.date())
        cost_breakdown = CostBreakdownFactory.create(
            treatment_procedure_uuid=procedure.uuid
        )
        procedure.cost_breakdown_id = cost_breakdown.id

        assert get_effective_date_from_cost_breakdown(cost_breakdown) == expected_date

    def test_date_from_reimbursement(self, wallet, db):
        category = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ].reimbursement_request_category
        )
        reimbursement = ReimbursementRequestFactory.create(
            service_start_date=datetime.now(timezone.utc),
            wallet=wallet,
            category=category,
        )
        db.session.expire(reimbursement)
        cost_breakdown = CostBreakdownFactory.create(
            reimbursement_request_id=reimbursement.id, treatment_procedure_uuid=None
        )

        assert (
            get_effective_date_from_cost_breakdown(cost_breakdown)
            == reimbursement.service_start_date
        )


class TestSetCopayCoinsuranceToEligibilityInfo:
    def test_both_copay_coinsurance_exist(self, cost_sharings):
        eligibility_info = EligibilityInfo()
        eligibility_info = set_db_copay_coinsurance_to_eligibility_info(
            eligibility_info=eligibility_info,
            cost_sharings=cost_sharings,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            tier=None,
        )
        assert eligibility_info == EligibilityInfo(
            copay=2000,
        )

    def test_only_coinsurance(self):
        eligibility_info = EligibilityInfo()
        cost_sharings = [
            EmployerHealthPlanCostSharing(
                cost_sharing_type=CostSharingType.COINSURANCE,
                cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
                percent=0.05,
            )
        ]
        eligibility_info = set_db_copay_coinsurance_to_eligibility_info(
            eligibility_info=eligibility_info,
            cost_sharings=cost_sharings,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            tier=None,
        )
        assert eligibility_info == EligibilityInfo(
            coinsurance=decimal.Decimal(0.05),
        )

    def test_no_cost_sharing(self):
        eligibility_info = EligibilityInfo()
        with pytest.raises(NoCostSharingFoundError):
            set_db_copay_coinsurance_to_eligibility_info(
                eligibility_info=eligibility_info,
                cost_sharings=[],
                cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
                tier=None,
            )

    def test_ignore_deductible(self):
        eligibility_info = EligibilityInfo()
        cost_sharings = [
            EmployerHealthPlanCostSharing(
                cost_sharing_type=CostSharingType.COINSURANCE_NO_DEDUCTIBLE,
                cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
                percent=0.05,
            )
        ]
        eligibility_info = set_db_copay_coinsurance_to_eligibility_info(
            eligibility_info=eligibility_info,
            cost_sharings=cost_sharings,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
        )
        assert eligibility_info == EligibilityInfo(
            coinsurance=decimal.Decimal(0.05), ignore_deductible=True
        )
