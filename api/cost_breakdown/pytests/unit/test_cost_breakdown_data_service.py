import datetime
from unittest import mock
from unittest.mock import patch

import pytest

from cost_breakdown.constants import AmountType, CostBreakdownType
from cost_breakdown.cost_breakdown_data_service import CostBreakdownDataService
from cost_breakdown.errors import (
    NoCostSharingFoundError,
    NoFamilyDeductibleOopRemaining,
    NoIndividualDeductibleOopRemaining,
    PayerDisabledCostBreakdownException,
)
from cost_breakdown.models.cost_breakdown import (
    CostBreakdownData,
    DeductibleAccumulationYTDInfo,
    HDHPAccumulationYTDInfo,
)
from cost_breakdown.models.rte import EligibilityInfo
from cost_breakdown.pytests.factories import (
    CostBreakdownIrsMinimumDeductibleFactory,
    RTETransactionFactory,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from payer_accumulator.common import PayerName
from wallet.models.constants import CostSharingCategory, FamilyPlanType


@pytest.fixture(scope="function")
def cost_breakdown_irs_minimum_threshold():
    CostBreakdownIrsMinimumDeductibleFactory.create(
        individual_amount=20000,
        family_amount=30000,
    )


@pytest.fixture(scope="function")
def eligibility_info():
    return EligibilityInfo(
        individual_deductible=20000,
        individual_deductible_remaining=10000,
        individual_oop=40000,
        individual_oop_remaining=20000,
        is_deductible_embedded=False,
        is_oop_embedded=False,
    )


@pytest.fixture()
def cost_breakdown_data_service(member_health_plan):
    return CostBreakdownDataService(
        member_first_name="first name",
        member_last_name="last name",
        member_health_plan=member_health_plan,
        wallet_balance=100,
        cost=100,
        procedure_type=TreatmentProcedureType.MEDICAL,
        cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
        deductible_accumulation_enabled=True,
        sequential_deductible_accumulation_member_responsibilities=DeductibleAccumulationYTDInfo(
            individual_deductible_applied=0,
            individual_oop_applied=0,
            family_deductible_applied=0,
            family_oop_applied=0,
        ),
        sequential_hdhp_responsibilities=HDHPAccumulationYTDInfo(
            sequential_member_responsibilities=0, sequential_family_responsibilities=0
        ),
        alegeus_ytd_spend=0,
        rx_ytd_spend=None,
        service_start_date=datetime.date(year=2024, month=1, day=1),
    )


@pytest.mark.parametrize(
    argnames="deductible_accumulation_enabled,member_health_plan_fixture,expected_call,will_run_eligibility",
    argvalues=[
        (True, "member_health_plan", "get_deductible_accumulation_data", True),
        (False, "member_hdhp_plan", "get_hdhp_data", True),
        (False, "member_health_plan", "get_fully_covered_data", False),
    ],
    ids=["deductible_accumulation_enabled", "hdhp", "fully_covered"],
)
def test_get_cost_breakdown_data_conditionals(
    cost_breakdown_data_service,
    deductible_accumulation_enabled,
    member_health_plan_fixture,
    expected_call,
    will_run_eligibility,
    request,
):
    member_health_plan = request.getfixturevalue(member_health_plan_fixture)
    cost_breakdown_data_service.deductible_accumulation_enabled = (
        deductible_accumulation_enabled
    )
    cost_breakdown_data_service.member_health_plan = member_health_plan
    with mock.patch(
        f"cost_breakdown.cost_breakdown_data_service.CostBreakdownDataService.{expected_call}"
    ) as expected_called_function:
        cost_breakdown_data_service.get_cost_breakdown_data()
    assert expected_called_function.call_count == 1
    assert (
        cost_breakdown_data_service.will_run_eligibility_info(
            cost_breakdown_data_service.deductible_accumulation_enabled,
            cost_breakdown_data_service.member_health_plan,
        )
        == will_run_eligibility
    )


def test_get_cost_breakdown_data_negative_wallet_balance_family(
    cost_breakdown_data_service, request
):
    member_health_plan = request.getfixturevalue("member_health_plan")
    cost_breakdown_data_service.deductible_accumulation_enabled = True
    cost_breakdown_data_service.member_health_plan = member_health_plan
    cost_breakdown_data_service.cost = 100
    cb_data = CostBreakdownData(
        rte_transaction_id=123,
        beginning_wallet_balance=-500,
        ending_wallet_balance=0,
        total_member_responsibility=600,
        total_employer_responsibility=0,
        hra_applied=600,
        deductible_remaining=0,
        deductible=600,
        family_deductible_remaining=0,
        oop_applied=600,
        oop_remaining=200,
        family_oop_remaining=300,
        overage_amount=600,
        amount_type=AmountType.FAMILY,
        cost_breakdown_type=CostBreakdownType.DEDUCTIBLE_ACCUMULATION,
        copay=200,
    )
    expected_cb_data = CostBreakdownData(
        rte_transaction_id=123,
        beginning_wallet_balance=-500,
        ending_wallet_balance=-500,
        total_member_responsibility=100,
        total_employer_responsibility=0,
        hra_applied=100,
        deductible_remaining=500,
        deductible=100,
        family_deductible_remaining=500,
        oop_applied=100,
        oop_remaining=700,
        family_oop_remaining=800,
        overage_amount=100,
        amount_type=AmountType.FAMILY,
        cost_breakdown_type=CostBreakdownType.DEDUCTIBLE_ACCUMULATION,
        copay=100,
    )
    with mock.patch(
        "cost_breakdown.cost_breakdown_data_service.CostBreakdownDataService.get_deductible_accumulation_data",
        return_value=cb_data,
    ):
        result = cost_breakdown_data_service.get_cost_breakdown_data()
        assert result == expected_cb_data


def test_get_cost_breakdown_data_negative_wallet_balance_individual(
    cost_breakdown_data_service, request
):
    member_health_plan = request.getfixturevalue("member_health_plan")
    cost_breakdown_data_service.deductible_accumulation_enabled = True
    cost_breakdown_data_service.member_health_plan = member_health_plan
    cost_breakdown_data_service.cost = 100
    cb_data = CostBreakdownData(
        rte_transaction_id=123,
        beginning_wallet_balance=-500,
        ending_wallet_balance=0,
        total_member_responsibility=600,
        total_employer_responsibility=0,
        hra_applied=600,
        deductible_remaining=0,
        deductible=600,
        oop_applied=600,
        oop_remaining=200,
        overage_amount=600,
        amount_type=AmountType.INDIVIDUAL,
        cost_breakdown_type=CostBreakdownType.DEDUCTIBLE_ACCUMULATION,
        copay=200,
    )
    expected_cb_data = CostBreakdownData(
        rte_transaction_id=123,
        beginning_wallet_balance=-500,
        ending_wallet_balance=-500,
        total_member_responsibility=100,
        total_employer_responsibility=0,
        hra_applied=100,
        deductible_remaining=500,
        deductible=100,
        family_deductible_remaining=None,
        oop_applied=100,
        oop_remaining=700,
        family_oop_remaining=None,
        overage_amount=100,
        amount_type=AmountType.INDIVIDUAL,
        cost_breakdown_type=CostBreakdownType.DEDUCTIBLE_ACCUMULATION,
        copay=100,
    )
    with mock.patch(
        "cost_breakdown.cost_breakdown_data_service.CostBreakdownDataService.get_deductible_accumulation_data",
        return_value=cb_data,
    ):
        result = cost_breakdown_data_service.get_cost_breakdown_data()
        assert result == expected_cb_data


@pytest.mark.parametrize(
    argnames="procedure_type,rx_integrated,expected_call",
    argvalues=[
        (TreatmentProcedureType.MEDICAL, None, "_medical_or_rx_integrated_rte_request"),
        (
            TreatmentProcedureType.PHARMACY,
            True,
            "_medical_or_rx_integrated_rte_request",
        ),
        (TreatmentProcedureType.PHARMACY, False, "_rx_not_integrated_rte_request"),
    ],
    ids=["medical_procedure", "rx_enabled", "rx_not_enabled"],
)
def test_get_eligibility_info(
    cost_breakdown_data_service, procedure_type, rx_integrated, expected_call
):
    cost_breakdown_data_service.procedure_type = procedure_type
    cost_breakdown_data_service.member_health_plan.employer_health_plan.rx_integrated = (
        rx_integrated
    )
    with mock.patch(
        f"cost_breakdown.cost_breakdown_data_service.CostBreakdownDataService.{expected_call}"
    ) as expected_called_function:
        cost_breakdown_data_service.get_eligibility_info()
    assert expected_called_function.call_count == 1


@pytest.mark.parametrize(
    argnames="cost, balance, overage, member_resp, employer_resp, end_balance",
    argvalues=[
        (10_000, 5_000, 5_000, 5_000, 5_000, 0),
        (5_000, 10_000, 0, 5_000, 0, 5_000),
    ],
    ids=["cost_greater_than_balance", "cost_smaller_than_balance"],
)
def test_cost_breakdown_fully_covered(
    cost_breakdown_data_service,
    cost,
    balance,
    overage,
    member_resp,
    employer_resp,
    end_balance,
):
    cost_breakdown_data_service.cost = cost
    cost_breakdown_data_service.wallet_balance = balance

    data = cost_breakdown_data_service.get_fully_covered_data()

    assert data.overage_amount == overage
    assert data.total_employer_responsibility == member_resp
    assert data.total_member_responsibility == employer_resp
    assert data.beginning_wallet_balance == balance
    assert data.ending_wallet_balance == end_balance


@pytest.mark.parametrize(
    argnames="sequential_treatment_value, expected_individual_deductible, expected_oop_remaining",
    argvalues=[(0, 10_000, 20_000), (10_000, 0, 10_000)],
    ids=["no_past_treatments", "past_sequential_treatments"],
)
def test__add_sequential_responsibility_for_member_deductible_accumulation(
    cost_breakdown_data_service,
    sequential_treatment_value,
    expected_individual_deductible,
    expected_oop_remaining,
):
    eligibility_info = EligibilityInfo(
        individual_deductible=20000,
        individual_deductible_remaining=10000,
        individual_oop=40000,
        individual_oop_remaining=20000,
    )
    cost_breakdown_data_service.sequential_deductible_accumulation_member_responsibilities = DeductibleAccumulationYTDInfo(
        individual_deductible_applied=sequential_treatment_value,
        individual_oop_applied=sequential_treatment_value,
        family_deductible_applied=sequential_treatment_value,
        family_oop_applied=sequential_treatment_value,
    )

    updated_info = cost_breakdown_data_service._add_sequential_responsibility_for_deductible_accumulation(
        eligibility_info
    )

    assert (
        updated_info.individual_deductible_remaining == expected_individual_deductible
    )
    assert updated_info.individual_oop_remaining == expected_oop_remaining


def test_validate_real_time_eligibility_succeeds(
    cost_breakdown_data_service,
):
    eligibility_info = EligibilityInfo(
        individual_deductible_remaining=10000,
        individual_oop_remaining=20000,
    )
    rte = RTETransactionFactory.create()

    cost_breakdown_data_service._validate_real_time_eligibility_info(
        eligibility_info=eligibility_info, rte_transaction=rte
    )


@pytest.mark.parametrize(
    "plan_type,expected_exception",
    [
        (FamilyPlanType.FAMILY, NoFamilyDeductibleOopRemaining),
        (FamilyPlanType.INDIVIDUAL, NoIndividualDeductibleOopRemaining),
    ],
)
def test_validate_real_time_eligibility_fails(
    cost_breakdown_data_service, plan_type, expected_exception
):
    cost_breakdown_data_service.member_health_plan.plan_type = plan_type
    eligibility_info = EligibilityInfo(
        individual_deductible=20000,
        individual_oop=40000,
    )
    rte = RTETransactionFactory.create()

    with pytest.raises(expected_exception):
        cost_breakdown_data_service._validate_real_time_eligibility_info(
            eligibility_info=eligibility_info, rte_transaction=rte
        )


@pytest.mark.parametrize(
    "deductible_remaining,oop_remaining", [(10000, None), (None, 10000)]
)
def test_validate_real_time_eligibility_info_no_individual_ytd(
    cost_breakdown_data_service,
    deductible_remaining,
    oop_remaining,
):
    cost_breakdown_data_service.member_health_plan.plan_type = FamilyPlanType.FAMILY
    rte = RTETransactionFactory.create()

    eligibility_info = EligibilityInfo(
        family_deductible=20000,
        family_oop=40000,
        family_deductible_remaining=20000,
        family_oop_remaining=40000,
        individual_deductible_remaining=deductible_remaining,
        individual_oop_remaining=oop_remaining,
        is_oop_embedded=True if deductible_remaining else False,
        is_deductible_embedded=True if oop_remaining else False,
    )

    with pytest.raises(NoIndividualDeductibleOopRemaining):
        cost_breakdown_data_service._validate_real_time_eligibility_info(
            eligibility_info=eligibility_info, rte_transaction=rte
        )


class TestGetHdhpData:
    def test_fully_covered(
        self,
        cost_breakdown_data_service,
        cost_breakdown_irs_minimum_threshold,
        eligibility_info,
    ):
        eligibility_info.individual_oop_remaining = 0
        with patch(
            "cost_breakdown.cost_breakdown_data_service.CostBreakdownDataService.get_eligibility_info",
            return_value=(eligibility_info, 1),
        ):
            assert cost_breakdown_data_service.get_hdhp_data() == CostBreakdownData(
                rte_transaction_id=1,
                total_member_responsibility=0,
                total_employer_responsibility=100,
                beginning_wallet_balance=100,
                ending_wallet_balance=0,
                cost_breakdown_type=CostBreakdownType.FIRST_DOLLAR_COVERAGE,
                amount_type=AmountType.INDIVIDUAL,
                deductible=0,
                deductible_remaining=0,
            )

    def test_cost_under_irs_threshold(
        self,
        cost_breakdown_data_service,
        cost_breakdown_irs_minimum_threshold,
        eligibility_info,
    ):
        eligibility_info.individual_oop_remaining = 40000
        with patch(
            "cost_breakdown.cost_breakdown_data_service.CostBreakdownDataService.get_eligibility_info",
            return_value=(eligibility_info, 1),
        ):
            assert cost_breakdown_data_service.get_hdhp_data() == CostBreakdownData(
                rte_transaction_id=1,
                total_member_responsibility=100,
                total_employer_responsibility=0,
                beginning_wallet_balance=100,
                ending_wallet_balance=100,
                cost_breakdown_type=CostBreakdownType.HDHP,
                amount_type=AmountType.INDIVIDUAL,
                deductible=100,
                deductible_remaining=0,
            )

    def test_cost_not_under_irs_threshold_and_wallet_balance_enough(
        self,
        cost_breakdown_data_service,
        cost_breakdown_irs_minimum_threshold,
        eligibility_info,
    ):
        cost_breakdown_data_service.cost = 30000
        cost_breakdown_data_service.wallet_balance = 50000
        eligibility_info.individual_oop_remaining = 40000
        with patch(
            "cost_breakdown.cost_breakdown_data_service.CostBreakdownDataService.get_eligibility_info",
            return_value=(eligibility_info, 1),
        ):
            assert cost_breakdown_data_service.get_hdhp_data() == CostBreakdownData(
                rte_transaction_id=1,
                total_member_responsibility=20000,
                total_employer_responsibility=10000,
                beginning_wallet_balance=50000,
                ending_wallet_balance=40000,
                cost_breakdown_type=CostBreakdownType.HDHP,
                amount_type=AmountType.INDIVIDUAL,
                deductible=20000,
                deductible_remaining=0,
            )

    def test_cost_not_under_irs_threshold_and_wallet_balance_not_enough(
        self,
        cost_breakdown_data_service,
        cost_breakdown_irs_minimum_threshold,
        eligibility_info,
    ):
        cost_breakdown_data_service.cost = 30000
        cost_breakdown_data_service.wallet_balance = 5000
        eligibility_info.individual_oop_remaining = 40000
        with patch(
            "cost_breakdown.cost_breakdown_data_service.CostBreakdownDataService.get_eligibility_info",
            return_value=(eligibility_info, 1),
        ):
            assert cost_breakdown_data_service.get_hdhp_data() == CostBreakdownData(
                rte_transaction_id=1,
                total_member_responsibility=25000,
                total_employer_responsibility=5000,
                beginning_wallet_balance=5000,
                ending_wallet_balance=0,
                cost_breakdown_type=CostBreakdownType.HDHP,
                amount_type=AmountType.INDIVIDUAL,
                deductible=20000,
                overage_amount=5000,
                deductible_remaining=0,
            )


class TestGetDeductibleAccumulationData:
    def test_success(self, cost_breakdown_data_service, eligibility_info):
        with patch(
            "cost_breakdown.cost_breakdown_data_service.CostBreakdownDataService.get_eligibility_info",
            return_value=(eligibility_info, 1),
        ) as get_eligibility_info:
            cost_breakdown_data = (
                cost_breakdown_data_service.get_deductible_accumulation_data()
            )
            assert cost_breakdown_data == CostBreakdownData(
                rte_transaction_id=1,
                total_member_responsibility=100,
                total_employer_responsibility=0,
                beginning_wallet_balance=100,
                ending_wallet_balance=100,
                cost_breakdown_type=CostBreakdownType.DEDUCTIBLE_ACCUMULATION,
                amount_type=AmountType.INDIVIDUAL,
                deductible=100,
                deductible_remaining=9900,
                coinsurance=0,
                copay=0,
                overage_amount=0,
                oop_applied=100,
                oop_remaining=19900,
            )
            get_eligibility_info.assert_called_once()

    def test_payer_not_integrated_plan(self, cost_breakdown_data_service):
        eligibility_info = EligibilityInfo(
            individual_deductible=20000,
            individual_deductible_remaining=20000,
            family_deductible=40000,
            family_deductible_remaining=40000,
            individual_oop=40000,
            individual_oop_remaining=40000,
            family_oop=60000,
            family_oop_remaining=60000,
            coinsurance=None,
            copay=2000,
            is_deductible_embedded=False,
            is_oop_embedded=False,
        )
        cost_breakdown_data_service.member_health_plan.employer_health_plan.is_payer_not_integrated = (
            True
        )
        cost_breakdown_data_service.cost = 30000
        with patch(
            "cost_breakdown.cost_breakdown_data_service.CostBreakdownDataService.get_eligibility_info_payer_not_integrated_plan",
            return_value=eligibility_info,
        ) as get_eligibility_info_payer_not_integrated_plan:
            cost_breakdown_data = (
                cost_breakdown_data_service.get_deductible_accumulation_data()
            )
            get_eligibility_info_payer_not_integrated_plan.assert_called_once()
            assert cost_breakdown_data == CostBreakdownData(
                rte_transaction_id=None,
                total_member_responsibility=29900,
                total_employer_responsibility=100,
                beginning_wallet_balance=100,
                ending_wallet_balance=0,
                cost_breakdown_type=CostBreakdownType.DEDUCTIBLE_ACCUMULATION,
                amount_type=AmountType.INDIVIDUAL,
                deductible=20000,
                deductible_remaining=0,
                coinsurance=0,
                copay=2000,
                overage_amount=7900,
                oop_applied=29900,
                oop_remaining=10100,
            )

    def test_payer_not_integrated_plan_with_sequential_payments(
        self, cost_breakdown_data_service
    ):
        cost_breakdown_data_service.sequential_deductible_accumulation_member_responsibilities = DeductibleAccumulationYTDInfo(
            individual_deductible_applied=10000,
            individual_oop_applied=10000,
            family_deductible_applied=0,
            family_oop_applied=0,
        )
        eligibility_info = EligibilityInfo(
            individual_deductible=20000,
            individual_deductible_remaining=20000,
            family_deductible=40000,
            family_deductible_remaining=40000,
            individual_oop=40000,
            individual_oop_remaining=40000,
            family_oop=60000,
            family_oop_remaining=60000,
            coinsurance=None,
            copay=2000,
            is_oop_embedded=True,
            is_deductible_embedded=True,
        )
        cost_breakdown_data_service.member_health_plan.employer_health_plan.is_payer_not_integrated = (
            True
        )
        cost_breakdown_data_service.cost = 30000
        with patch(
            "cost_breakdown.cost_breakdown_data_service.CostBreakdownDataService.get_eligibility_info_payer_not_integrated_plan",
            return_value=eligibility_info,
        ) as get_eligibility_info_payer_not_integrated_plan:
            cost_breakdown_data = (
                cost_breakdown_data_service.get_deductible_accumulation_data()
            )
            get_eligibility_info_payer_not_integrated_plan.assert_called_once()
            assert cost_breakdown_data == CostBreakdownData(
                rte_transaction_id=None,
                total_member_responsibility=29900,
                total_employer_responsibility=100,
                beginning_wallet_balance=100,
                ending_wallet_balance=0,
                cost_breakdown_type=CostBreakdownType.DEDUCTIBLE_ACCUMULATION,
                amount_type=AmountType.INDIVIDUAL,
                deductible=10000,
                deductible_remaining=0,
                coinsurance=0,
                copay=2000,
                overage_amount=17900,
                oop_applied=29900,
                oop_remaining=100,
            )

    @pytest.mark.parametrize(
        argnames="hra_remaining,expected_hra_applied,expected_member_resp,expected_employer_resp,expected_ending_wallet_balance",
        argvalues=[
            (100, 100, 0, 100, 100),
            (90, 90, 10, 90, 100),
        ],
        ids=["hra >= member responsibility", "hra < member responsibility"],
    )
    def test_hra_applied(
        self,
        hra_remaining,
        expected_hra_applied,
        expected_member_resp,
        expected_employer_resp,
        expected_ending_wallet_balance,
        cost_breakdown_data_service,
        eligibility_info,
    ):
        cost_breakdown_data_service.member_health_plan.employer_health_plan.hra_enabled = (
            True
        )
        eligibility_info.hra_remaining = hra_remaining
        with patch(
            "cost_breakdown.cost_breakdown_data_service.CostBreakdownDataService.get_eligibility_info",
            return_value=(eligibility_info, 1),
        ) as get_eligibility_info:
            cost_breakdown_data = (
                cost_breakdown_data_service.get_deductible_accumulation_data()
            )
            assert cost_breakdown_data == CostBreakdownData(
                rte_transaction_id=1,
                total_member_responsibility=expected_member_resp,
                total_employer_responsibility=expected_employer_resp,
                beginning_wallet_balance=100,
                ending_wallet_balance=expected_ending_wallet_balance,
                cost_breakdown_type=CostBreakdownType.DEDUCTIBLE_ACCUMULATION,
                amount_type=AmountType.INDIVIDUAL,
                deductible=100,
                deductible_remaining=9900,
                coinsurance=0,
                copay=0,
                overage_amount=0,
                oop_applied=100,
                hra_applied=expected_hra_applied,
                oop_remaining=19900,
            )
            get_eligibility_info.assert_called_once()


class TestGetEligibilityInfoMavenManagedPlan:
    def test_success(self, cost_breakdown_data_service):
        eligibility_info = (
            cost_breakdown_data_service.get_eligibility_info_payer_not_integrated_plan()
        )
        assert eligibility_info == EligibilityInfo(
            individual_deductible=200000,
            individual_deductible_remaining=200000,
            family_deductible=400000,
            family_deductible_remaining=400000,
            individual_oop=400000,
            individual_oop_remaining=400000,
            family_oop=600000,
            family_oop_remaining=600000,
            coinsurance=None,
            copay=2000,
            is_oop_embedded=False,
            is_deductible_embedded=False,
        )

    def test_failure(self, cost_breakdown_data_service):
        cost_breakdown_data_service.member_health_plan.employer_health_plan.cost_sharings = (
            []
        )
        with pytest.raises(NoCostSharingFoundError):
            cost_breakdown_data_service.get_eligibility_info_payer_not_integrated_plan()


class TestWillRunEligibilityInfo:
    @pytest.mark.parametrize(
        "deductible_accumulation_enabled,is_hdhp,expected_result",
        [
            # Test deductible accumulation enabled
            (True, False, True),
            # Test HDHP plan
            (False, True, True),
            # Test neither deductible accumulation nor HDHP
            (False, False, False),
        ],
        ids=[
            "deductible_accumulation",
            "hdhp_plan",
            "neither_deductible_nor_hdhp",
        ],
    )
    def test_success(
        self,
        cost_breakdown_data_service,
        deductible_accumulation_enabled,
        is_hdhp,
        expected_result,
    ):
        # Setup
        cost_breakdown_data_service.deductible_accumulation_enabled = (
            deductible_accumulation_enabled
        )
        cost_breakdown_data_service.member_health_plan.employer_health_plan.is_hdhp = (
            is_hdhp
        )
        cost_breakdown_data_service.member_health_plan.employer_health_plan.benefits_payer.payer_name = (
            PayerName.Cigna
        )  # valid payer

        with patch(
            "cost_breakdown.cost_breakdown_data_service.feature_flags.json_variation",
            return_value={"disabled_payers": ["aetna"]},
        ):
            result = cost_breakdown_data_service.will_run_eligibility_info(
                deductible_accumulation_enabled,
                cost_breakdown_data_service.member_health_plan,
            )
            assert result == expected_result

    def test_exception(
        self,
        cost_breakdown_data_service,
    ):
        # Setup
        cost_breakdown_data_service.member_health_plan.employer_health_plan.benefits_payer.payer_name = (
            PayerName.AETNA
        )

        with patch(
            "cost_breakdown.cost_breakdown_data_service.feature_flags.json_variation",
            return_value={"disabled_payers": ["aetna"]},
        ):
            with pytest.raises(PayerDisabledCostBreakdownException) as exc:
                cost_breakdown_data_service.will_run_eligibility_info(
                    deductible_accumulation_enabled=True,
                    member_health_plan=cost_breakdown_data_service.member_health_plan,
                )
            assert str(exc.value) == "Cost breakdown disabled for payer aetna."

    def test_first_dollar_coverage(self, cost_breakdown_data_service):
        # Setup
        cost_breakdown_data_service.member_health_plan = None

        with patch(
            "cost_breakdown.cost_breakdown_data_service.feature_flags.json_variation",
            return_value={"disabled_payers": ["aetna"]},
        ):
            # Execute
            result = cost_breakdown_data_service.will_run_eligibility_info(
                deductible_accumulation_enabled=False,
                member_health_plan=cost_breakdown_data_service.member_health_plan,
            )

            # Verify - should not raise PayerDisabledCostBreakdownException
            assert result is False
