import datetime
from unittest.mock import ANY, MagicMock, patch

import pytest
from maven import feature_flags

from cost_breakdown.constants import ENABLE_UNLIMITED_BENEFITS_FOR_CB, AmountType, Tier
from cost_breakdown.errors import TieredRTEError
from cost_breakdown.models.rte import EligibilityInfo
from cost_breakdown.pytests.factories import CostBreakdownFactory, RTETransactionFactory
from direct_payment.pharmacy.pytests.factories import HealthPlanYearToDateSpendFactory
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from pytests.factories import EnterpriseUserFactory
from wallet.models.constants import (
    FAMILY_PLANS,
    CostSharingCategory,
    FamilyPlanType,
    WalletState,
)
from wallet.models.reimbursement_organization_settings import EmployerHealthPlan
from wallet.models.reimbursement_wallet import MemberHealthPlan
from wallet.pytests.factories import (
    EmployerHealthPlanCoverageFactory,
    EmployerHealthPlanFactory,
    FertilityClinicLocationEmployerHealthPlanTierFactory,
    MemberHealthPlanFactory,
    ReimbursementPlanFactory,
    ReimbursementRequestFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
)
from wallet.repository.health_plan import (
    HEALTH_PLAN_YOY_FLAG,
    NEW_BEHAVIOR,
    OLD_BEHAVIOR,
)


@pytest.fixture(scope="function")
def rte_transaction_with_copay(member_health_plan):
    return RTETransactionFactory.create(
        id=1,
        response={
            "individual_oop": 150_000,
            "individual_oop_remaining": 10_000,
            "individual_deductible": 150_000,
            "individual_deductible_remaining": 2000,
            "copay": 4000,
        },
        response_code=200,
        request={},
        member_health_plan_id=member_health_plan.id,
    )


@pytest.fixture(scope="function")
def rte_transaction_with_high_deductible_remaining(member_health_plan):
    return RTETransactionFactory.create(
        id=1,
        response={
            "family_deductible": 150_000,
            "individual_oop": 150_000,
            "family_oop": 300_000,
            "individual_deductible_remaining": 100_000,
            "individual_deductible": 150_000,
            "coinsurance": 0.2,
            "family_deductible_remaining": 100_000,
            "individual_oop_remaining": 110_000,
            "family_oop_remaining": 229_309,
        },
        response_code=200,
        request={},
        member_health_plan_id=member_health_plan.id,
    )


@pytest.fixture(scope="function")
def rte_transaction_with_less_oop_than_deductible_remaining(member_health_plan):
    return RTETransactionFactory.create(
        id=1,
        response={
            "family_deductible": 150_000,
            "individual_oop": 150_000,
            "family_oop": 300_000,
            "individual_deductible_remaining": 100_000,
            "individual_deductible": 150_000,
            "copay": 2000,
            "family_deductible_remaining": 150_000,
            "individual_oop_remaining": 10_000,
            "family_oop_remaining": 10_000,
        },
        response_code=200,
        request={},
        member_health_plan_id=member_health_plan.id,
    )


@pytest.mark.parametrize(
    argnames=("procedure", "enable_is_unlimited"),
    argvalues=[
        ("treatment_procedure", False),
        ("rx_procedure", False),
        ("treatment_procedure", True),
        ("rx_procedure", True),
    ],
)
def test_no_deductible_accumulation_non_hdhp_cost_greater_than_balance(
    procedure, enable_is_unlimited, cost_breakdown_proc, wallet, request, ff_test_data
):
    ff_test_data.update(
        ff_test_data.flag(ENABLE_UNLIMITED_BENEFITS_FOR_CB).variation_for_all(
            enable_is_unlimited
        )
    )
    # _get_cost_breakdown_no_deductible_accumulation requires no deductible_accumulation_enabled + no member health plan
    wallet.reimbursement_organization_settings.deductible_accumulation_enabled = False
    wallet.reimbursement_organization_settings.first_dollar_coverage = True
    treatment_procedure = request.getfixturevalue(procedure)
    treatment_procedure.cost = 100_000
    with patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_treatment_cost_sharing_category",
        return_value=CostSharingCategory.GENERIC_PRESCRIPTIONS,
    ), patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor._get_member_health_plan",
        return_value=None,
    ):
        cost_breakdown = cost_breakdown_proc.get_cost_breakdown_for_treatment_procedure(
            wallet=wallet,
            treatment_procedure=treatment_procedure,
            wallet_balance=50_000,
        )
    assert cost_breakdown.total_member_responsibility == 50_000
    assert cost_breakdown.total_employer_responsibility == 50_000
    assert cost_breakdown.is_unlimited is False
    assert cost_breakdown.beginning_wallet_balance == 50_000
    assert cost_breakdown.ending_wallet_balance == 0
    assert cost_breakdown.overage_amount == 50_000
    assert (
        cost_breakdown.total_member_responsibility
        == cost_breakdown.deductible
        + cost_breakdown.coinsurance
        + cost_breakdown.overage_amount
        + cost_breakdown.copay
    )


@pytest.mark.parametrize(
    argnames=("procedure", "enable_is_unlimited"),
    argvalues=[
        ("treatment_procedure", False),
        ("rx_procedure", False),
        ("treatment_procedure", True),
        ("rx_procedure", True),
    ],
)
def test_no_deductible_accumulation_non_hdhp_cost_smaller_than_balance(
    procedure, enable_is_unlimited, cost_breakdown_proc, wallet, request, ff_test_data
):
    ff_test_data.update(
        ff_test_data.flag(ENABLE_UNLIMITED_BENEFITS_FOR_CB).variation_for_all(
            enable_is_unlimited
        )
    )
    # _get_cost_breakdown_no_deductible_accumulation requires no deductible_accumulation_enabled + no member health plan
    wallet.reimbursement_organization_settings.deductible_accumulation_enabled = False
    wallet.reimbursement_organization_settings.first_dollar_coverage = True
    treatment_procedure = request.getfixturevalue(procedure)
    treatment_procedure.cost = 50_000
    with patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_treatment_cost_sharing_category",
        return_value=CostSharingCategory.GENERIC_PRESCRIPTIONS,
    ), patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor._get_member_health_plan",
        return_value=None,
    ):
        cost_breakdown = cost_breakdown_proc.get_cost_breakdown_for_treatment_procedure(
            wallet=wallet,
            treatment_procedure=treatment_procedure,
            wallet_balance=100_000,
        )
    assert cost_breakdown.total_member_responsibility == 0
    assert cost_breakdown.total_employer_responsibility == 50_000
    assert cost_breakdown.is_unlimited is False
    assert cost_breakdown.beginning_wallet_balance == 100_000
    assert cost_breakdown.ending_wallet_balance == 50_000
    assert (
        cost_breakdown.total_member_responsibility
        == cost_breakdown.deductible
        + cost_breakdown.coinsurance
        + cost_breakdown.overage_amount
        + cost_breakdown.copay
    )


@pytest.mark.parametrize(
    argnames="procedure",
    argvalues=[
        "treatment_procedure",
        "rx_procedure",
    ],
)
def test_no_deductible_accumulation_non_hdhp_cost_smaller_than_balance_with_unlimited_category(
    procedure,
    cost_breakdown_proc,
    unlimited_direct_payment_wallet,
    request,
    ff_test_data,
):
    ff_test_data.update(
        ff_test_data.flag(ENABLE_UNLIMITED_BENEFITS_FOR_CB).variation_for_all(True)
    )
    unlimited_direct_payment_wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
        False
    )
    unlimited_direct_payment_wallet.reimbursement_organization_settings.first_dollar_coverage = (
        True
    )
    treatment_procedure = request.getfixturevalue(procedure)
    treatment_procedure.cost = 50_000
    treatment_procedure.reimbursement_request_category = (
        unlimited_direct_payment_wallet.get_direct_payment_category
    )
    with patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_treatment_cost_sharing_category",
        return_value=CostSharingCategory.GENERIC_PRESCRIPTIONS,
    ), patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor._get_member_health_plan",
        return_value=None,
    ):
        cost_breakdown = cost_breakdown_proc.get_cost_breakdown_for_treatment_procedure(
            wallet=unlimited_direct_payment_wallet,
            treatment_procedure=treatment_procedure,
            wallet_balance=None,
        )
    assert cost_breakdown.total_member_responsibility == 0
    assert cost_breakdown.total_employer_responsibility == 50_000
    assert cost_breakdown.is_unlimited is True
    assert cost_breakdown.beginning_wallet_balance == 0
    assert cost_breakdown.ending_wallet_balance == 0
    assert (
        cost_breakdown.total_member_responsibility
        == cost_breakdown.deductible
        + cost_breakdown.coinsurance
        + cost_breakdown.overage_amount
        + cost_breakdown.copay
    )


@pytest.mark.parametrize(
    argnames="enable_is_unlimited,cost,wallet_balance,plan_type,amount_type",
    argvalues=[
        (False, 50_000, 100_000, FamilyPlanType.INDIVIDUAL, AmountType.INDIVIDUAL),
        (
            False,
            50_000,
            1_000_000,
            FamilyPlanType.INDIVIDUAL,
            AmountType.INDIVIDUAL,
        ),
        (
            False,
            50_000,
            10_000_000,
            FamilyPlanType.INDIVIDUAL,
            AmountType.INDIVIDUAL,
        ),
        (
            False,
            100_000,
            100_000,
            FamilyPlanType.INDIVIDUAL,
            AmountType.INDIVIDUAL,
        ),
        (False, 50_000, 100_000, FamilyPlanType.FAMILY, AmountType.FAMILY),
        (False, 50_000, 1_000_000, FamilyPlanType.FAMILY, AmountType.FAMILY),
        (
            False,
            50_000,
            10_000_000,
            FamilyPlanType.FAMILY,
            AmountType.FAMILY,
        ),
        (False, 100_000, 100_000, FamilyPlanType.FAMILY, AmountType.FAMILY),
        (
            False,
            50_000,
            100_000,
            FamilyPlanType.FAMILY,
            AmountType.FAMILY,
        ),
        (
            False,
            50_000,
            1_000_000,
            FamilyPlanType.FAMILY,
            AmountType.FAMILY,
        ),
        (
            False,
            50_000,
            10_000_000,
            FamilyPlanType.FAMILY,
            AmountType.FAMILY,
        ),
        (
            False,
            100_000,
            100_000,
            FamilyPlanType.FAMILY,
            AmountType.FAMILY,
        ),
        (True, 50_000, 100_000, FamilyPlanType.INDIVIDUAL, AmountType.INDIVIDUAL),
        (
            True,
            50_000,
            1_000_000,
            FamilyPlanType.INDIVIDUAL,
            AmountType.INDIVIDUAL,
        ),
        (
            True,
            50_000,
            10_000_000,
            FamilyPlanType.INDIVIDUAL,
            AmountType.INDIVIDUAL,
        ),
        (
            True,
            100_000,
            100_000,
            FamilyPlanType.INDIVIDUAL,
            AmountType.INDIVIDUAL,
        ),
        (True, 50_000, 100_000, FamilyPlanType.FAMILY, AmountType.FAMILY),
        (True, 50_000, 1_000_000, FamilyPlanType.FAMILY, AmountType.FAMILY),
        (
            True,
            50_000,
            10_000_000,
            FamilyPlanType.FAMILY,
            AmountType.FAMILY,
        ),
        (True, 100_000, 100_000, FamilyPlanType.FAMILY, AmountType.FAMILY),
        (
            True,
            50_000,
            100_000,
            FamilyPlanType.FAMILY,
            AmountType.FAMILY,
        ),
        (
            True,
            50_000,
            1_000_000,
            FamilyPlanType.FAMILY,
            AmountType.FAMILY,
        ),
        (
            True,
            50_000,
            10_000_000,
            FamilyPlanType.FAMILY,
            AmountType.FAMILY,
        ),
        (
            True,
            100_000,
            100_000,
            FamilyPlanType.FAMILY,
            AmountType.FAMILY,
        ),
    ],
)
def test_deductible_accumulation_deductible_remaining_greater_than_cost(
    enable_is_unlimited,
    cost,
    wallet_balance,
    plan_type,
    amount_type,
    cost_breakdown_proc,
    rte_transaction_with_high_deductible_remaining,
    wallet,
    treatment_procedure,
    member_health_plan,
    ff_test_data,
):
    ff_test_data.update(
        ff_test_data.flag(ENABLE_UNLIMITED_BENEFITS_FOR_CB).variation_for_all(
            enable_is_unlimited
        )
    )
    wallet.reimbursement_organization_settings.deductible_accumulation_enabled = True
    member_health_plan.plan_type = plan_type
    treatment_procedure.cost = cost
    with patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_treatment_cost_sharing_category",
        return_value=CostSharingCategory.DIAGNOSTIC_MEDICAL,
    ), patch(
        "cost_breakdown.rte.pverify_api.PverifyAPI.get_real_time_eligibility_data",
        return_value=rte_transaction_with_high_deductible_remaining,
    ) as mock_rte, patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor._get_member_health_plan",
        return_value=member_health_plan,
    ):
        cost_breakdown = cost_breakdown_proc.get_cost_breakdown_for_treatment_procedure(
            wallet=wallet,
            treatment_procedure=treatment_procedure,
            wallet_balance=wallet_balance,
        )
        assert cost_breakdown.total_member_responsibility == cost
        assert cost_breakdown.total_employer_responsibility == 0
        assert cost_breakdown.is_unlimited is False
        assert cost_breakdown.beginning_wallet_balance == wallet_balance
        assert cost_breakdown.ending_wallet_balance == wallet_balance
        assert cost_breakdown.amount_type == amount_type
        assert (
            cost_breakdown.total_member_responsibility
            == cost_breakdown.deductible
            + cost_breakdown.coinsurance
            + cost_breakdown.overage_amount
            + cost_breakdown.copay
        )
        mock_rte.assert_called_once_with(
            plan=member_health_plan,
            cost_sharing_category=CostSharingCategory.DIAGNOSTIC_MEDICAL,
            member_first_name="alice",
            member_last_name="paul",
            is_second_tier=False,
            service_start_date=treatment_procedure.start_date,
            treatment_procedure_id=treatment_procedure.id,
            reimbursement_request_id=None,
        )

        if member_health_plan.is_family_plan:
            prev_ded_remaining = (
                rte_transaction_with_high_deductible_remaining.response[
                    "family_deductible_remaining"
                ]
            )
            deductible_remaining = cost_breakdown.family_deductible_remaining
        else:
            prev_ded_remaining = (
                rte_transaction_with_high_deductible_remaining.response[
                    "individual_deductible_remaining"
                ]
            )
            deductible_remaining = cost_breakdown.deductible_remaining
        assert cost_breakdown.deductible == cost
        assert deductible_remaining == prev_ded_remaining - cost

        if member_health_plan.is_family_plan:
            prev_oop_remaining = (
                rte_transaction_with_high_deductible_remaining.response[
                    "family_oop_remaining"
                ]
            )
            oop_remaining = cost_breakdown.family_oop_remaining
        else:
            prev_oop_remaining = (
                rte_transaction_with_high_deductible_remaining.response[
                    "individual_oop_remaining"
                ]
            )
            oop_remaining = cost_breakdown.oop_remaining
        assert cost_breakdown.oop_applied == cost
        assert oop_remaining == prev_oop_remaining - cost


@pytest.mark.parametrize(argnames="enable_is_unlimited", argvalues=[True, False])
def test_deductible_accumulation_oop_remaining_smaller_than_member_cost_with_enough_balance(
    enable_is_unlimited,
    cost_breakdown_proc,
    rte_transaction_with_oop_remaining,
    wallet,
    treatment_procedure,
    member_health_plan,
    ff_test_data,
):
    ff_test_data.update(
        ff_test_data.flag(ENABLE_UNLIMITED_BENEFITS_FOR_CB).variation_for_all(
            enable_is_unlimited
        )
    )
    wallet.reimbursement_organization_settings.deductible_accumulation_enabled = True
    treatment_procedure.cost = 80_000
    with patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_treatment_cost_sharing_category",
        return_value=CostSharingCategory.DIAGNOSTIC_MEDICAL,
    ), patch(
        "cost_breakdown.rte.pverify_api.PverifyAPI.get_real_time_eligibility_data",
        return_value=rte_transaction_with_oop_remaining,
    ), patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor._get_member_health_plan",
        return_value=member_health_plan,
    ):
        cost_breakdown = cost_breakdown_proc.get_cost_breakdown_for_treatment_procedure(
            wallet=wallet,
            treatment_procedure=treatment_procedure,
            wallet_balance=100_000,
        )
        assert cost_breakdown.total_member_responsibility == 10_000
        assert cost_breakdown.total_employer_responsibility == 70_000
        assert cost_breakdown.is_unlimited is False
        assert cost_breakdown.beginning_wallet_balance == 100_000
        assert cost_breakdown.ending_wallet_balance == 30_000
        assert cost_breakdown.deductible == 0
        assert cost_breakdown.deductible_remaining == 0
        assert cost_breakdown.coinsurance == 10_000
        assert cost_breakdown.amount_type == AmountType.INDIVIDUAL
        assert cost_breakdown.oop_applied == 10_000
        assert cost_breakdown.oop_remaining == 0
        assert (
            cost_breakdown.total_member_responsibility
            == cost_breakdown.deductible
            + cost_breakdown.coinsurance
            + cost_breakdown.overage_amount
            + cost_breakdown.copay
        )


def test_deductible_accumulation_oop_remaining_smaller_than_member_cost_with_unlimited_category(
    cost_breakdown_proc,
    rte_transaction_with_oop_remaining,
    unlimited_direct_payment_wallet,
    treatment_procedure,
    member_health_plan,
    ff_test_data,
):
    ff_test_data.update(
        ff_test_data.flag(ENABLE_UNLIMITED_BENEFITS_FOR_CB).variation_for_all(True)
    )
    unlimited_direct_payment_wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
        True
    )
    treatment_procedure.cost = 80_000
    treatment_procedure.reimbursement_request_category = (
        unlimited_direct_payment_wallet.get_direct_payment_category
    )
    with patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_treatment_cost_sharing_category",
        return_value=CostSharingCategory.DIAGNOSTIC_MEDICAL,
    ), patch(
        "cost_breakdown.rte.pverify_api.PverifyAPI.get_real_time_eligibility_data",
        return_value=rte_transaction_with_oop_remaining,
    ), patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor._get_member_health_plan",
        return_value=member_health_plan,
    ):
        cost_breakdown = cost_breakdown_proc.get_cost_breakdown_for_treatment_procedure(
            wallet=unlimited_direct_payment_wallet,
            treatment_procedure=treatment_procedure,
            wallet_balance=None,
        )
        assert cost_breakdown.total_member_responsibility == 10_000
        assert cost_breakdown.total_employer_responsibility == 70_000
        assert cost_breakdown.is_unlimited is True
        assert cost_breakdown.beginning_wallet_balance == 0
        assert cost_breakdown.ending_wallet_balance == 0
        assert cost_breakdown.deductible == 0
        assert cost_breakdown.deductible_remaining == 0
        assert cost_breakdown.coinsurance == 10_000
        assert cost_breakdown.amount_type == AmountType.INDIVIDUAL
        assert cost_breakdown.oop_applied == 10_000
        assert cost_breakdown.oop_remaining == 0
        assert (
            cost_breakdown.total_member_responsibility
            == cost_breakdown.deductible
            + cost_breakdown.coinsurance
            + cost_breakdown.overage_amount
            + cost_breakdown.copay
        )


@pytest.mark.parametrize(argnames="enable_is_unlimited", argvalues=[True, False])
def test_deductible_accumulation_oop_remaining_smaller_than_member_cost_with_not_enough_balance(
    enable_is_unlimited,
    cost_breakdown_proc,
    rte_transaction_with_oop_remaining,
    wallet,
    treatment_procedure,
    member_health_plan,
    ff_test_data,
):
    ff_test_data.update(
        ff_test_data.flag(ENABLE_UNLIMITED_BENEFITS_FOR_CB).variation_for_all(
            enable_is_unlimited
        )
    )
    wallet.reimbursement_organization_settings.deductible_accumulation_enabled = True
    treatment_procedure.cost = 80_000
    with patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_treatment_cost_sharing_category",
        return_value=CostSharingCategory.DIAGNOSTIC_MEDICAL,
    ), patch(
        "cost_breakdown.rte.pverify_api.PverifyAPI.get_real_time_eligibility_data",
        return_value=rte_transaction_with_oop_remaining,
    ), patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor._get_member_health_plan",
        return_value=member_health_plan,
    ):
        cost_breakdown = cost_breakdown_proc.get_cost_breakdown_for_treatment_procedure(
            wallet=wallet,
            treatment_procedure=treatment_procedure,
            wallet_balance=50_000,
        )
        assert cost_breakdown.total_member_responsibility == 30_000
        assert cost_breakdown.total_employer_responsibility == 50_000
        assert cost_breakdown.is_unlimited is False
        assert cost_breakdown.beginning_wallet_balance == 50_000
        assert cost_breakdown.ending_wallet_balance == 0
        assert cost_breakdown.deductible == 0
        assert cost_breakdown.deductible_remaining == 0
        assert cost_breakdown.coinsurance == 10_000
        assert cost_breakdown.amount_type == AmountType.INDIVIDUAL
        assert cost_breakdown.overage_amount == 20_000
        assert cost_breakdown.oop_applied == 10_000
        assert cost_breakdown.oop_remaining == 0
        assert (
            cost_breakdown.total_member_responsibility
            == cost_breakdown.deductible
            + cost_breakdown.coinsurance
            + cost_breakdown.overage_amount
            + cost_breakdown.copay
        )


@pytest.mark.parametrize(argnames="enable_is_unlimited", argvalues=[True, False])
def test_deductible_accumulation_hra_applied(
    enable_is_unlimited,
    cost_breakdown_proc,
    rte_transaction_with_hra_remaining,
    wallet,
    treatment_procedure,
    member_health_plan,
    ff_test_data,
):
    ff_test_data.update(
        ff_test_data.flag(ENABLE_UNLIMITED_BENEFITS_FOR_CB).variation_for_all(
            enable_is_unlimited
        )
    )
    wallet.reimbursement_organization_settings.deductible_accumulation_enabled = True
    member_health_plan.employer_health_plan.hra_enabled = True
    treatment_procedure.cost = 80_000
    with patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_treatment_cost_sharing_category",
        return_value=CostSharingCategory.DIAGNOSTIC_MEDICAL,
    ), patch(
        "cost_breakdown.rte.pverify_api.PverifyAPI.get_real_time_eligibility_data",
        return_value=rte_transaction_with_hra_remaining,
    ), patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor._get_member_health_plan",
        return_value=member_health_plan,
    ):
        cost_breakdown = cost_breakdown_proc.get_cost_breakdown_for_treatment_procedure(
            wallet=wallet,
            treatment_procedure=treatment_procedure,
            wallet_balance=50_000,
        )
        assert cost_breakdown.total_member_responsibility == 20_000
        assert cost_breakdown.total_employer_responsibility == 60_000
        assert cost_breakdown.is_unlimited is False
        assert cost_breakdown.beginning_wallet_balance == 50_000
        assert cost_breakdown.ending_wallet_balance == 0
        assert cost_breakdown.deductible == 0
        assert cost_breakdown.deductible_remaining == 0
        assert cost_breakdown.coinsurance == 10_000
        assert cost_breakdown.amount_type == AmountType.INDIVIDUAL
        assert cost_breakdown.overage_amount == 20_000
        assert cost_breakdown.oop_applied == 10_000
        assert cost_breakdown.hra_applied == 10_000
        assert cost_breakdown.oop_remaining == 0
        assert (
            cost_breakdown.total_member_responsibility
            == cost_breakdown.deductible
            + cost_breakdown.coinsurance
            + cost_breakdown.overage_amount
            + cost_breakdown.copay
            - cost_breakdown.hra_applied
        )


@pytest.mark.parametrize(argnames="enable_is_unlimited", argvalues=[True, False])
def test_deductible_accumulation_rx_not_integrated(
    enable_is_unlimited,
    cost_breakdown_proc,
    wallet,
    rx_procedure,
    member_health_plan_rx_not_included,
    ff_test_data,
):
    ff_test_data.update(
        ff_test_data.flag(ENABLE_UNLIMITED_BENEFITS_FOR_CB).variation_for_all(
            enable_is_unlimited
        )
    )
    wallet.reimbursement_organization_settings.deductible_accumulation_enabled = True
    rx_procedure.cost = 10000
    with patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_treatment_cost_sharing_category",
        return_value=CostSharingCategory.GENERIC_PRESCRIPTIONS,
    ), patch(
        "cost_breakdown.rte.rx_rte_processor.HealthPlanYearToDateSpendService.get_all_by_member",
        return_value=[
            HealthPlanYearToDateSpendFactory.create(
                policy_id="abcdefg",
                first_name="alice",
                last_name="paul",
                year=2023,
                source="MAVEN",
                deductible_applied_amount=200_000,
                # 1k less than employer_health_plan.rx_ind_oop_max_limit - 1k individual_oop_remaining
                oop_applied_amount=399_000,
            )
        ],
    ), patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor._get_member_health_plan",
        return_value=member_health_plan_rx_not_included,
    ):
        cost_breakdown = cost_breakdown_proc.get_cost_breakdown_for_treatment_procedure(
            wallet=wallet,
            treatment_procedure=rx_procedure,
            wallet_balance=20000,
        )
        assert cost_breakdown.total_member_responsibility == 1000
        assert cost_breakdown.total_employer_responsibility == 9000
        assert cost_breakdown.is_unlimited is False
        assert cost_breakdown.beginning_wallet_balance == 20000
        assert cost_breakdown.ending_wallet_balance == 11000
        assert cost_breakdown.deductible == 0
        assert cost_breakdown.coinsurance == 0
        assert cost_breakdown.copay == 1000
        assert cost_breakdown.amount_type == AmountType.INDIVIDUAL
        assert (
            cost_breakdown.total_member_responsibility
            == cost_breakdown.deductible
            + cost_breakdown.coinsurance
            + cost_breakdown.overage_amount
            + cost_breakdown.copay
        )


@pytest.mark.parametrize(
    argnames="enable_is_unlimited, rte_transaction_param, cost, wallet_balance, amount_type, "
    "member_resp, employer_resp, end_wallet_balance, irs_threshold, overage_amount",
    argvalues=[
        (
            False,
            "rte_irs_unmet",
            50_000,  # treatment cost
            100_000,  # wallet balance
            AmountType.INDIVIDUAL,  # is it an individual plan
            50_000,  # member responsibility
            0,  # employer responsibility
            100_000,  # end wallet balance
            150_000,  # irs threshold
            None,  # cost exceeding wallet balance
        ),  # individual irs unmet, member pays
        (
            False,
            "rte_irs_met",
            50_000,  # treatment cost
            0,  # wallet balance
            AmountType.INDIVIDUAL,  # is it an individual plan
            50_000,  # member responsibility
            0,  # employer responsibility
            0,  # end wallet balance
            150_000,  # irs threshold
            50_000,  # cost exceeding wallet balance
        ),  # individual irs met, no wallet -> member pays
        (
            False,
            "rte_irs_met",
            50_000,  # treatment cost
            0,  # wallet balance
            AmountType.FAMILY,  # is it an individual plan
            50_000,  # member responsibility
            0,  # employer responsibility
            0,  # end wallet balance
            300_000,  # irs threshold
            50_000,  # cost exceeding wallet balance
        ),  # family irs met, no wallet ->  member pays
        (
            False,
            "rte_irs_unmet",
            100_000,  # treatment cost
            100_000,  # wallet balance
            AmountType.FAMILY,  # is it an individual plan
            100_000,  # member responsibility
            0,  # employer responsibility
            100_000,  # end wallet balance
            300_000,  # irs threshold
            None,  # cost exceeding wallet balance
        ),  # family irs unmet -> member pays
        (
            False,
            "rte_irs_met",
            100_000,  # treatment cost
            1_000_000,  # wallet balance
            AmountType.INDIVIDUAL,  # is it an individual plan
            0,  # member responsibility
            100_000,  # employer responsibility
            900_000,  # end wallet balance
            150_000,  # irs threshold
            None,  # cost exceeding wallet balance
        ),  # ind irs met, wallet > cost -> employer $
        (
            False,
            "rte_irs_met",
            100_000,  # treatment cost
            1_000_000,  # wallet balance
            AmountType.FAMILY,  # is it an individual plan
            0,  # member responsibility
            100_000,  # employer responsibility
            900_000,  # end wallet balance
            300_000,  # irs threshold
            None,  # cost exceeding wallet balance
        ),  # fam irs met, wallet > cost -> employer $
        (
            False,
            "rte_irs_met",
            2_000_000,  # treatment cost
            1_000_000,  # wallet balance
            AmountType.INDIVIDUAL,  # is it an individual plan
            1_000_000,  # member responsibility
            1_000_000,  # employer responsibility
            0,  # end wallet balance
            150_000,  # irs threshold
            1_000_000,  # cost exceeding wallet balance
        ),  # ind irs met, wallet < cost -> both $
        (
            False,
            "rte_irs_met",
            2_000_000,  # treatment cost
            1_000_000,  # wallet balance
            AmountType.FAMILY,  # is it an individual plan
            1_000_000,  # member responsibility
            1_000_000,  # employer responsibility
            0,  # end wallet balance
            300_000,  # irs threshold
            1_000_000,  # cost exceeding wallet balance
        ),  # fam irs met, wallet < cost -> both $
        (
            False,
            "rte_irs_unmet",
            300_000,  # treatment cost
            1_000_000,  # wallet balance
            AmountType.INDIVIDUAL,  # is it an individual plan
            150_000,  # member responsibility
            150_000,  # employer responsibility
            850_000,  # end wallet balance
            150_000,  # irs threshold
            None,  # cost exceeding wallet balance
        ),  # ind irs unmet, both $
        (
            False,
            "rte_irs_unmet",
            400_000,  # treatment cost
            1_000_000,  # wallet balance
            AmountType.FAMILY,  # is it an individual plan
            300_000,  # member responsibility
            100_000,  # employer responsibility
            900_000,  # end wallet balance
            300_000,  # irs threshold
            None,  # cost exceeding wallet balance
        ),  # fam irs unmet, both $
        (
            False,
            "rte_irs_met",
            1_200_000,  # treatment cost
            1_000_000,  # wallet balance
            AmountType.INDIVIDUAL,  # is it an individual plan
            200_000,  # member responsibility
            1_000_000,  # employer responsibility
            0,  # end wallet balance
            150_000,  # irs threshold
            200_000,  # cost exceeding wallet balance
        ),  # ind irs met, cost > wallet -> both $
        (
            False,
            "rte_irs_met",
            1_200_000,  # treatment cost
            1_000_000,  # wallet balance
            AmountType.FAMILY,  # is it an individual plan
            200_000,  # member responsibility
            1_000_000,  # employer responsibility
            0,  # end wallet balance
            300_000,  # irs threshold
            200_000,  # cost exceeding wallet balance
        ),  # fam irs met, cost > wallet -> both $
        (
            False,
            "rte_irs_partial",
            1_100_000,  # treatment cost
            1_000_000,  # wallet balance
            AmountType.INDIVIDUAL,  # is it an individual plan
            100_000,  # member responsibility
            1_000_000,  # employer responsibility
            0,  # end wallet balance
            150_000,  # irs threshold
            None,  # cost exceeding wallet balance
        ),  # cost > wallet > remainder -> both $
        (
            False,
            "rte_irs_partial",
            900_000,  # treatment cost
            1_000_000,  # wallet balance
            AmountType.INDIVIDUAL,  # is it an individual plan
            100_000,  # member responsibility
            800_000,  # employer responsibility
            200_000,  # end wallet balance
            150_000,  # irs threshold
            None,  # cost exceeding wallet balance
        ),  # wallet > cost > remainder ->both$
        (
            False,
            "rte_irs_partial",
            1_100_000,  # treatment cost
            1_000_000,  # wallet balance
            AmountType.FAMILY,  # is it an individual plan
            100_000,  # member responsibility
            1_000_000,  # employer responsibility
            0,  # end wallet balance
            300_000,  # irs threshold
            None,  # cost exceeding wallet balance
        ),  # cost > wallet > remainder -> both $
        (
            False,
            "rte_irs_partial",
            900_000,  # treatment cost
            1_000_000,  # wallet balance
            AmountType.FAMILY,  # is it an individual plan
            100_000,  # member responsibility
            800_000,  # employer responsibility
            200_000,  # end wallet balance
            300_000,  # irs threshold
            None,  # cost exceeding wallet balance
        ),  # wallet > cost > remainder->both$
        (
            True,
            "rte_irs_unmet",
            50_000,  # treatment cost
            100_000,  # wallet balance
            AmountType.INDIVIDUAL,  # is it an individual plan
            50_000,  # member responsibility
            0,  # employer responsibility
            100_000,  # end wallet balance
            150_000,  # irs threshold
            None,  # cost exceeding wallet balance
        ),  # individual irs unmet, member pays
        (
            True,
            "rte_irs_met",
            50_000,  # treatment cost
            0,  # wallet balance
            AmountType.INDIVIDUAL,  # is it an individual plan
            50_000,  # member responsibility
            0,  # employer responsibility
            0,  # end wallet balance
            150_000,  # irs threshold
            50_000,  # cost exceeding wallet balance
        ),  # individual irs met, no wallet -> member pays
        (
            True,
            "rte_irs_met",
            50_000,  # treatment cost
            0,  # wallet balance
            AmountType.FAMILY,  # is it an individual plan
            50_000,  # member responsibility
            0,  # employer responsibility
            0,  # end wallet balance
            300_000,  # irs threshold
            50_000,  # cost exceeding wallet balance
        ),  # family irs met, no wallet ->  member pays
        (
            True,
            "rte_irs_unmet",
            100_000,  # treatment cost
            100_000,  # wallet balance
            AmountType.FAMILY,  # is it an individual plan
            100_000,  # member responsibility
            0,  # employer responsibility
            100_000,  # end wallet balance
            300_000,  # irs threshold
            None,  # cost exceeding wallet balance
        ),  # family irs unmet -> member pays
        (
            True,
            "rte_irs_met",
            100_000,  # treatment cost
            1_000_000,  # wallet balance
            AmountType.INDIVIDUAL,  # is it an individual plan
            0,  # member responsibility
            100_000,  # employer responsibility
            900_000,  # end wallet balance
            150_000,  # irs threshold
            None,  # cost exceeding wallet balance
        ),  # ind irs met, wallet > cost -> employer $
        (
            True,
            "rte_irs_met",
            100_000,  # treatment cost
            1_000_000,  # wallet balance
            AmountType.FAMILY,  # is it an individual plan
            0,  # member responsibility
            100_000,  # employer responsibility
            900_000,  # end wallet balance
            300_000,  # irs threshold
            None,  # cost exceeding wallet balance
        ),  # fam irs met, wallet > cost -> employer $
        (
            True,
            "rte_irs_met",
            2_000_000,  # treatment cost
            1_000_000,  # wallet balance
            AmountType.INDIVIDUAL,  # is it an individual plan
            1_000_000,  # member responsibility
            1_000_000,  # employer responsibility
            0,  # end wallet balance
            150_000,  # irs threshold
            1_000_000,  # cost exceeding wallet balance
        ),  # ind irs met, wallet < cost -> both $
        (
            True,
            "rte_irs_met",
            2_000_000,  # treatment cost
            1_000_000,  # wallet balance
            AmountType.FAMILY,  # is it an individual plan
            1_000_000,  # member responsibility
            1_000_000,  # employer responsibility
            0,  # end wallet balance
            300_000,  # irs threshold
            1_000_000,  # cost exceeding wallet balance
        ),  # fam irs met, wallet < cost -> both $
        (
            True,
            "rte_irs_unmet",
            300_000,  # treatment cost
            1_000_000,  # wallet balance
            AmountType.INDIVIDUAL,  # is it an individual plan
            150_000,  # member responsibility
            150_000,  # employer responsibility
            850_000,  # end wallet balance
            150_000,  # irs threshold
            None,  # cost exceeding wallet balance
        ),  # ind irs unmet, both $
        (
            True,
            "rte_irs_unmet",
            400_000,  # treatment cost
            1_000_000,  # wallet balance
            AmountType.FAMILY,  # is it an individual plan
            300_000,  # member responsibility
            100_000,  # employer responsibility
            900_000,  # end wallet balance
            300_000,  # irs threshold
            None,  # cost exceeding wallet balance
        ),  # fam irs unmet, both $
        (
            True,
            "rte_irs_met",
            1_200_000,  # treatment cost
            1_000_000,  # wallet balance
            AmountType.INDIVIDUAL,  # is it an individual plan
            200_000,  # member responsibility
            1_000_000,  # employer responsibility
            0,  # end wallet balance
            150_000,  # irs threshold
            200_000,  # cost exceeding wallet balance
        ),  # ind irs met, cost > wallet -> both $
        (
            True,
            "rte_irs_met",
            1_200_000,  # treatment cost
            1_000_000,  # wallet balance
            AmountType.FAMILY,  # is it an individual plan
            200_000,  # member responsibility
            1_000_000,  # employer responsibility
            0,  # end wallet balance
            300_000,  # irs threshold
            200_000,  # cost exceeding wallet balance
        ),  # fam irs met, cost > wallet -> both $
        (
            True,
            "rte_irs_partial",
            1_100_000,  # treatment cost
            1_000_000,  # wallet balance
            AmountType.INDIVIDUAL,  # is it an individual plan
            100_000,  # member responsibility
            1_000_000,  # employer responsibility
            0,  # end wallet balance
            150_000,  # irs threshold
            None,  # cost exceeding wallet balance
        ),  # cost > wallet > remainder -> both $
        (
            True,
            "rte_irs_partial",
            900_000,  # treatment cost
            1_000_000,  # wallet balance
            AmountType.INDIVIDUAL,  # is it an individual plan
            100_000,  # member responsibility
            800_000,  # employer responsibility
            200_000,  # end wallet balance
            150_000,  # irs threshold
            None,  # cost exceeding wallet balance
        ),  # wallet > cost > remainder ->both$
        (
            True,
            "rte_irs_partial",
            1_100_000,  # treatment cost
            1_000_000,  # wallet balance
            AmountType.FAMILY,  # is it an individual plan
            100_000,  # member responsibility
            1_000_000,  # employer responsibility
            0,  # end wallet balance
            300_000,  # irs threshold
            None,  # cost exceeding wallet balance
        ),  # cost > wallet > remainder -> both $
        (
            True,
            "rte_irs_partial",
            900_000,  # treatment cost
            1_000_000,  # wallet balance
            AmountType.FAMILY,  # is it an individual plan
            100_000,  # member responsibility
            800_000,  # employer responsibility
            200_000,  # end wallet balance
            300_000,  # irs threshold
            None,  # cost exceeding wallet balance
        ),  # wallet > cost > remainder->both$
    ],
)
def test_get_cost_breakdown_hdhp(
    enable_is_unlimited,
    rte_transaction_param,
    cost,
    wallet_balance,
    amount_type,
    member_resp,
    employer_resp,
    end_wallet_balance,
    irs_threshold,
    overage_amount,
    cost_breakdown_proc,
    member_hdhp_plan,
    wallet_hdhp_plan,
    request,
    treatment_procedure,
    ff_test_data,
):
    ff_test_data.update(
        ff_test_data.flag(ENABLE_UNLIMITED_BENEFITS_FOR_CB).variation_for_all(
            enable_is_unlimited
        )
    )
    rte = request.getfixturevalue(rte_transaction_param)
    member_hdhp_plan.plan_type = (
        FamilyPlanType.FAMILY
        if amount_type == AmountType.FAMILY
        else FamilyPlanType.INDIVIDUAL
    )
    treatment_procedure.cost = cost
    with patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_treatment_cost_sharing_category",
        return_value=CostSharingCategory.MEDICAL_CARE,
    ), patch(
        "cost_breakdown.rte.pverify_api.PverifyAPI.get_real_time_eligibility_data",
        return_value=rte,
    ) as mock_rte, patch(
        "cost_breakdown.cost_breakdown_data_service.get_irs_limit",
        return_value=irs_threshold,
    ), patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor._get_member_health_plan",
        return_value=member_hdhp_plan,
    ):
        cost_breakdown = cost_breakdown_proc.get_cost_breakdown_for_treatment_procedure(
            wallet=wallet_hdhp_plan,
            treatment_procedure=treatment_procedure,
            wallet_balance=wallet_balance,
            store_to_db=False,
        )
        assert cost_breakdown.ending_wallet_balance == end_wallet_balance
        assert cost_breakdown.total_member_responsibility == member_resp
        assert cost_breakdown.total_employer_responsibility == employer_resp
        assert cost_breakdown.is_unlimited is False
        assert cost_breakdown.beginning_wallet_balance == wallet_balance
        assert cost_breakdown.rte_transaction_id == 1
        assert cost_breakdown.treatment_procedure_uuid == treatment_procedure.uuid
        assert cost_breakdown.amount_type == amount_type
        if overage_amount:
            assert overage_amount == cost_breakdown.overage_amount
            assert (
                cost_breakdown.total_member_responsibility
                == (cost_breakdown.deductible or 0) + cost_breakdown.overage_amount
            )
        else:
            assert cost_breakdown.overage_amount == 0
            assert cost_breakdown.total_member_responsibility == (
                cost_breakdown.deductible or 0
            )
        mock_rte.assert_called_once_with(
            plan=member_hdhp_plan,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            member_first_name="alice",
            member_last_name="paul",
            is_second_tier=False,
            service_start_date=treatment_procedure.start_date,
            treatment_procedure_id=treatment_procedure.id,
            reimbursement_request_id=None,
        )


@pytest.mark.parametrize(
    argnames="rte_transaction_param, cost, amount_type, "
    "member_resp, employer_resp, irs_threshold",
    argvalues=[
        (
            "rte_irs_unmet",
            50_000,  # treatment cost
            AmountType.INDIVIDUAL,  # is it an individual plan
            50_000,  # member responsibility
            0,  # employer responsibility
            150_000,  # irs threshold
        ),
        (
            "rte_irs_met",
            50_000,  # treatment cost
            AmountType.INDIVIDUAL,  # is it an individual plan
            0,  # member responsibility
            50_000,  # employer responsibility
            150_000,  # irs threshold
        ),
        (
            "rte_irs_met",
            50_000,  # treatment cost
            AmountType.FAMILY,  # is it an individual plan
            0,  # member responsibility
            50_000,  # employer responsibility
            300_000,  # irs threshold
        ),
        (
            "rte_irs_unmet",
            100_000,  # treatment cost
            AmountType.FAMILY,  # is it an individual plan
            100_000,  # member responsibility
            0,  # employer responsibility
            300_000,  # irs threshold
        ),
        (
            "rte_irs_met",
            100_000,  # treatment cost
            AmountType.INDIVIDUAL,  # is it an individual plan
            0,  # member responsibility
            100_000,  # employer responsibility
            150_000,  # irs threshold
        ),
        (
            "rte_irs_met",
            100_000,  # treatment cost
            AmountType.FAMILY,  # is it an individual plan
            0,  # member responsibility
            100_000,  # employer responsibility
            300_000,  # irs threshold
        ),
        (
            "rte_irs_met",
            2_000_000,  # treatment cost
            AmountType.INDIVIDUAL,  # is it an individual plan
            0,  # member responsibility
            2_000_000,  # employer responsibility
            150_000,  # irs threshold
        ),
        (
            "rte_irs_met",
            2_000_000,  # treatment cost
            AmountType.FAMILY,  # is it an individual plan
            0,  # member responsibility
            2_000_000,  # employer responsibility
            300_000,  # irs threshold
        ),
        (
            "rte_irs_unmet",
            300_000,  # treatment cost
            AmountType.INDIVIDUAL,  # is it an individual plan
            150_000,  # member responsibility
            150_000,  # employer responsibility
            150_000,  # irs threshold
        ),
        (
            "rte_irs_unmet",
            400_000,  # treatment cost
            AmountType.FAMILY,  # is it an individual plan
            300_000,  # member responsibility
            100_000,  # employer responsibility
            300_000,  # irs threshold
        ),
        (
            "rte_irs_met",
            1_200_000,  # treatment cost
            AmountType.INDIVIDUAL,  # is it an individual plan
            0,  # member responsibility
            1_200_000,  # employer responsibility
            150_000,  # irs threshold
        ),
        (
            "rte_irs_met",
            1_200_000,  # treatment cost
            AmountType.FAMILY,  # is it an individual plan
            0,  # member responsibility
            1_200_000,  # employer responsibility
            300_000,  # irs threshold
        ),
        (
            "rte_irs_partial",
            1_100_000,  # treatment cost
            AmountType.INDIVIDUAL,  # is it an individual plan
            100_000,  # member responsibility
            1_000_000,  # employer responsibility
            150_000,  # irs threshold
        ),
        (
            "rte_irs_partial",
            900_000,  # treatment cost
            AmountType.INDIVIDUAL,  # is it an individual plan
            100_000,  # member responsibility
            800_000,  # employer responsibility
            150_000,  # irs threshold
        ),
        (
            "rte_irs_partial",
            1_100_000,  # treatment cost
            AmountType.FAMILY,  # is it an individual plan
            100_000,  # member responsibility
            1_000_000,  # employer responsibility
            300_000,  # irs threshold
        ),
        (
            "rte_irs_partial",
            900_000,  # treatment cost
            AmountType.FAMILY,  # is it an individual plan
            100_000,  # member responsibility
            800_000,  # employer responsibility
            300_000,  # irs threshold
        ),
        (
            "rte_irs_unmet",
            50_000,  # treatment cost
            AmountType.INDIVIDUAL,  # is it an individual plan
            50_000,  # member responsibility
            0,  # employer responsibility
            150_000,  # irs threshold
        ),
        (
            "rte_irs_met",
            50_000,  # treatment cost
            AmountType.INDIVIDUAL,  # is it an individual plan
            0,  # member responsibility
            50_000,  # employer responsibility
            150_000,  # irs threshold
        ),
        (
            "rte_irs_met",
            50_000,  # treatment cost
            AmountType.FAMILY,  # is it an individual plan
            0,  # member responsibility
            50_000,  # employer responsibility
            300_000,  # irs threshold
        ),
        (
            "rte_irs_unmet",
            100_000,  # treatment cost
            AmountType.FAMILY,  # is it an individual plan
            100_000,  # member responsibility
            0,  # employer responsibility
            300_000,  # irs threshold
        ),
        (
            "rte_irs_met",
            100_000,  # treatment cost
            AmountType.INDIVIDUAL,  # is it an individual plan
            0,  # member responsibility
            100_000,  # employer responsibility
            150_000,  # irs threshold
        ),
        (
            "rte_irs_met",
            100_000,  # treatment cost
            AmountType.FAMILY,  # is it an individual plan
            0,  # member responsibility
            100_000,  # employer responsibility
            300_000,  # irs threshold
        ),
        (
            "rte_irs_met",
            2_000_000,  # treatment cost
            AmountType.INDIVIDUAL,  # is it an individual plan
            0,  # member responsibility
            2_000_000,  # employer responsibility
            150_000,  # irs threshold
        ),
        (
            "rte_irs_met",
            2_000_000,  # treatment cost
            AmountType.FAMILY,  # is it an individual plan
            0,  # member responsibility
            2_000_000,  # employer responsibility
            300_000,  # irs threshold
        ),
        (
            "rte_irs_unmet",
            300_000,  # treatment cost
            AmountType.INDIVIDUAL,  # is it an individual plan
            150_000,  # member responsibility
            150_000,  # employer responsibility
            150_000,  # irs threshold
        ),
        (
            "rte_irs_unmet",
            400_000,  # treatment cost
            AmountType.FAMILY,  # is it an individual plan
            300_000,  # member responsibility
            100_000,  # employer responsibility
            300_000,  # irs threshold
        ),
        (
            "rte_irs_met",
            1_200_000,  # treatment cost
            AmountType.INDIVIDUAL,  # is it an individual plan
            0,  # member responsibility
            1_200_000,  # employer responsibility
            150_000,  # irs threshold
        ),
        (
            "rte_irs_met",
            1_200_000,  # treatment cost
            AmountType.FAMILY,  # is it an individual plan
            0,  # member responsibility
            1_200_000,  # employer responsibility
            300_000,  # irs threshold
        ),
        (
            "rte_irs_partial",
            1_100_000,  # treatment cost
            AmountType.INDIVIDUAL,  # is it an individual plan
            100_000,  # member responsibility
            1_000_000,  # employer responsibility
            150_000,  # irs threshold
        ),
        (
            "rte_irs_partial",
            900_000,  # treatment cost
            AmountType.INDIVIDUAL,  # is it an individual plan
            100_000,  # member responsibility
            800_000,  # employer responsibility
            150_000,  # irs threshold
        ),
        (
            "rte_irs_partial",
            1_100_000,  # treatment cost
            AmountType.FAMILY,  # is it an individual plan
            100_000,  # member responsibility
            1_000_000,  # employer responsibility
            300_000,  # irs threshold
        ),
        (
            "rte_irs_partial",
            900_000,  # treatment cost
            AmountType.FAMILY,  # is it an individual plan
            100_000,  # member responsibility
            800_000,  # employer responsibility
            300_000,  # irs threshold
        ),
    ],
)
def test_get_cost_breakdown_hdhp_with_unlimited_category(
    rte_transaction_param,
    cost,
    amount_type,
    member_resp,
    employer_resp,
    irs_threshold,
    cost_breakdown_proc,
    unlimited_member_hdhp_plan,
    unlimited_wallet_hdhp_plan,
    request,
    treatment_procedure,
    ff_test_data,
):
    ff_test_data.update(
        ff_test_data.flag(ENABLE_UNLIMITED_BENEFITS_FOR_CB).variation_for_all(True)
    )
    rte = request.getfixturevalue(rte_transaction_param)
    unlimited_member_hdhp_plan.plan_type = (
        FamilyPlanType.FAMILY
        if amount_type == AmountType.FAMILY
        else FamilyPlanType.INDIVIDUAL
    )
    treatment_procedure.cost = cost
    treatment_procedure.reimbursement_request_category = (
        unlimited_wallet_hdhp_plan.get_direct_payment_category
    )
    with patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_treatment_cost_sharing_category",
        return_value=CostSharingCategory.MEDICAL_CARE,
    ), patch(
        "cost_breakdown.rte.pverify_api.PverifyAPI.get_real_time_eligibility_data",
        return_value=rte,
    ) as mock_rte, patch(
        "cost_breakdown.cost_breakdown_data_service.get_irs_limit",
        return_value=irs_threshold,
    ), patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor._get_member_health_plan",
        return_value=unlimited_member_hdhp_plan,
    ):
        cost_breakdown = cost_breakdown_proc.get_cost_breakdown_for_treatment_procedure(
            wallet=unlimited_wallet_hdhp_plan,
            treatment_procedure=treatment_procedure,
            wallet_balance=None,
            store_to_db=False,
        )
        assert cost_breakdown.total_member_responsibility == member_resp
        assert cost_breakdown.total_employer_responsibility == employer_resp
        assert cost_breakdown.is_unlimited is True
        assert cost_breakdown.beginning_wallet_balance == 0
        assert cost_breakdown.ending_wallet_balance == 0
        assert cost_breakdown.rte_transaction_id == 1
        assert cost_breakdown.treatment_procedure_uuid == treatment_procedure.uuid
        assert cost_breakdown.amount_type == amount_type
        assert cost_breakdown.overage_amount == 0
        assert cost_breakdown.total_member_responsibility == (
            cost_breakdown.deductible or 0
        )
        mock_rte.assert_called_once_with(
            plan=unlimited_member_hdhp_plan,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            member_first_name="alice",
            member_last_name="paul",
            is_second_tier=False,
            service_start_date=treatment_procedure.start_date,
            treatment_procedure_id=treatment_procedure.id,
            reimbursement_request_id=None,
        )


# Test cases line up with scenarios outlined in second tab of spreadsheet:
# https://docs.google.com/spreadsheets/d/1w6RxSVAeqfoMJbD-VAXgTYO2FZC0bCFA8K1b2MGNxGQ/edit#gid=0
@pytest.mark.parametrize(
    argnames="enable_is_unlimited,"
    "plan_type,"
    "is_deductible_embedded,"
    "is_oop_embedded,"
    "coinsurance,"
    "member_responsibility,"
    "employer_responsibility,"
    "coinsurance_charge,"
    "overage_amount,"
    "individual_deductible_remaining, "
    "family_deductible_remaining,"
    "individual_oop_remaining,"
    "family_oop_remaining,"
    "expected_individual_deductible_remaining,"
    "expected_family_deductible_remaining,"
    "expected_individual_oop_remaining,"
    "expected_family_oop_remaining,"
    "expected_deductible_apply,"
    "expected_oop_apply,"
    "treatment_cost,"
    "wallet_balance",
    # fmt: off
    argvalues=[
        (False, FamilyPlanType.INDIVIDUAL, False, False, 0, 500, 0, 0, 0, 2500, None, 3425, None, 2000, None, 2925, None, 500, 500, 500, 5000),
        (False, FamilyPlanType.INDIVIDUAL, False, False, 0, 2000, 0, 0, 0, 2000, None, 2925, None, 0, None, 925, None, 2000, 2000, 2000, 5000),
        (False, FamilyPlanType.INDIVIDUAL, False, False, 0, 0, 100, 0, 0, 0, None, 925, None, 0, None, 925, None, 0, 0, 100, 5000),
        (False, FamilyPlanType.FAMILY, False, False, 0, 500, 0, 0, 0, None, 2500, None, 6850, None, 2000, None, 6350, 500, 500, 500, 5000),
        (False, FamilyPlanType.FAMILY, False, False, 0, 2000, 0, 0, 0, None, 2000, None, 6350, None, 0, None, 4350, 2000, 2000, 2000, 5000),
        (False, FamilyPlanType.FAMILY, False, False, 0, 0, 100, 0, 0, None, 0, None, 4350, None, 0, None, 4350, 0, 0, 100, 5000),
        (False, FamilyPlanType.INDIVIDUAL, True, True, 0, 500, 0, 0, 0, 2500, None, 3425, None, 2000, None, 2925, None, 500, 500, 500, 5000),
        (False, FamilyPlanType.INDIVIDUAL, True, True, 0, 2000, 0, 0, 0, 2000, None, 2925, None, 0, None, 925, None, 2000, 2000, 2000, 5000),
        (False, FamilyPlanType.INDIVIDUAL, True, True, 0, 0, 100, 0, 0, 0, None, 925, None, 0, None, 925, None, 0, 0, 100, 5000),
        (False, FamilyPlanType.FAMILY, True, True, 0.2, 500, 0, 0, 0, 1200, 2500, 3000, 7500, 700, 2000, 2500, 7000, 500, 500, 500, 5000),
        (False, FamilyPlanType.FAMILY, True, True, 0.2, 960, 1040, 260, 0, 700, 2000, 2500, 7000, 0, 1300, 1540, 6040, 700, 960, 2000, 5000),
        (False, FamilyPlanType.FAMILY, True, True, 0.2, 200, 800, 200, 0, 0, 1300, 1540, 6040, 0, 1300, 1340, 5840, 0, 200, 1000, 3960),
        (False, FamilyPlanType.FAMILY, True, True, 0.2, 1000, 0, 0, 0, 1200, 1300, 3000, 5840, 200, 300, 2000, 4840, 1000, 1000, 1000, 3160),
        (False, FamilyPlanType.FAMILY, True, True, 0.2, 280, 320, 80, 0, 200, 300, 2000, 4840, 0, 100, 1720, 4560, 200, 280, 600, 3160),
        (False, FamilyPlanType.FAMILY, True, True, 0.2, 200, 400, 100, 0, 1200, 100, 2000, 4560, 1100, 0, 1800, 4360, 100, 200, 600, 2840),
        (False, FamilyPlanType.FAMILY, True, True, 0.2, 20, 80, 20, 0, 1200, 0, 3000, 4360, 1200, 0, 2980, 4340, 0, 20, 100, 2440),
        (False, FamilyPlanType.INDIVIDUAL, True, False, 0, 500, 0, 0, 0, 2500, None, 3425, None, 2000, None, 2925, None, 500, 500, 500, 5000),
        (False, FamilyPlanType.INDIVIDUAL, True, False, 0, 2000, 0, 0, 0, 2000, None, 2925, None, 0, None, 925, None, 2000, 2000, 2000, 5000),
        (False, FamilyPlanType.INDIVIDUAL, True, False, 0, 0, 100, 0, 0, 0, None, 925, None, 0, None, 925, None, 0, 0, 100, 5000),
        (False, FamilyPlanType.FAMILY, True, False, 0.2, 1800, 3200, 800, 0, 1000, 2500, 2500, 5000, 0, 1500, None, 3200, 1000, 1800, 5000, 10_000),
        (False, FamilyPlanType.FAMILY, True, False, 0.2, 200, 800, 200, 0, 0, 1500, None, 3200, 0, 1500, None, 3000, 0, 200, 1000, 6800),
        (False, FamilyPlanType.FAMILY, True, False, 0.2, 1400, 1600, 400, 0, 1000, 1500, 2500, 3000, 0, 500, None, 1600, 1000, 1400, 3000, 6000),
        (False, FamilyPlanType.FAMILY, True, False, 0.2, 820, 1280, 320, 0, 1000, 500, 2500, 1600, 500, 0, None, 780, 500, 820, 2100, 4400),
        (False, FamilyPlanType.FAMILY, True, False, 0.2, 20, 80, 20, 0, 1000, 0, None, 780, 1000, 0, None, 760, 0, 20, 100, 3120),
        (False, FamilyPlanType.FAMILY, False, True, 0.2, 500, 0, 0, 0, None, 3600, 5000, 10_000, None, 3100, 4500, 9500, 500, 500, 500, 10_000),
        (False, FamilyPlanType.FAMILY, False, True, 0.2, 2000, 0, 0, 0, None, 3100, 4500, 9500, None, 1100, 2500, 7500, 2000, 2000, 2000, 10_000),
        (False, FamilyPlanType.FAMILY, False, True, 0.2, 1000, 0, 0, 0, None, 1100, 2500, 7500, None, 100, 1500, 6500, 1000, 1000, 1000, 10_000),
        (False, FamilyPlanType.FAMILY, False, True, 0.2, 280, 720, 180, 0, None, 100, 5000, 6500, None, 0, 4720, 6220, 100, 280, 1000, 10_000),
        (False, FamilyPlanType.FAMILY, False, True, 0.2, 120, 480, 120, 0, None, 0, 4720, 6220, None, 0, 4600, 6100, 0, 120, 600, 9280),
        (False, FamilyPlanType.FAMILY, False, True, 0.2, 2000, 8000, 2000, 0, None, 0, 5000, 6100, None, 0, 3000, 4100, 0, 2000, 10_000, 8800),
        (False, FamilyPlanType.FAMILY, False, True, 0.2, 184, 736, 184, 0, None, 0, 5000, 4100, None, 0, 4816, 3916, 0, 184, 920, 800),
        (False, FamilyPlanType.FAMILY, False, True, 0.2, 36, 64, 20, 16, None, 0, 4816, 3916, None, 0, 4780, 3880, 0, 36, 100, 64),
        (False, FamilyPlanType.FAMILY, False, True, 0.2, 2000, 0, 0, 0, None, 3600, 5000, 10_000, None, 1600, 3000, 8000, 2000, 2000, 2000, 10_000),
        (False, FamilyPlanType.FAMILY, False, True, 0.2, 1000, 0, 0, 0, None, 1600, 3000, 8000, None, 600, 2000, 7000, 1000, 1000, 1000, 10_000),
        (False, FamilyPlanType.FAMILY, False, True, 0.2, 880, 1120, 280, 0, None, 600, 5000, 7000, None, 0, 4120, 6120, 600, 880, 2000, 10_000),
        (False, FamilyPlanType.INDIVIDUAL, False, True, 0, 500, 0, 0, 0, 2500, None, 3425, None, 2000, None, 2925, None, 500, 500, 500, 5000),
        (False, FamilyPlanType.INDIVIDUAL, False, True, 0, 2000, 0, 0, 0, 2000, None, 2925, None, 0, None, 925, None, 2000, 2000, 2000, 5000),
        (False, FamilyPlanType.INDIVIDUAL, False, True, 0, 0, 100, 0, 0, 0, None, 925, None, 0, None, 925, None, 0, 0, 100, 5000),
        # Unlimited flag on below
        (True, FamilyPlanType.INDIVIDUAL, False, False, 0, 500, 0, 0, 0, 2500, None, 3425, None, 2000, None, 2925, None, 500, 500, 500, 5000),
        (True, FamilyPlanType.INDIVIDUAL, False, False, 0, 2000, 0, 0, 0, 2000, None, 2925, None, 0, None, 925, None, 2000, 2000, 2000, 5000),
        (True, FamilyPlanType.INDIVIDUAL, False, False, 0, 0, 100, 0, 0, 0, None, 925, None, 0, None, 925, None, 0, 0, 100, 5000),
        (True, FamilyPlanType.FAMILY, False, False, 0, 500, 0, 0, 0, None, 2500, None, 6850, None, 2000, None, 6350, 500, 500, 500, 5000),
        (True, FamilyPlanType.FAMILY, False, False, 0, 2000, 0, 0, 0, None, 2000, None, 6350, None, 0, None, 4350, 2000, 2000, 2000, 5000),
        (True, FamilyPlanType.FAMILY, False, False, 0, 0, 100, 0, 0, None, 0, None, 4350, None, 0, None, 4350, 0, 0, 100, 5000),
        (True, FamilyPlanType.INDIVIDUAL, True, True, 0, 500, 0, 0, 0, 2500, None, 3425, None, 2000, None, 2925, None, 500, 500, 500, 5000),
        (True, FamilyPlanType.INDIVIDUAL, True, True, 0, 2000, 0, 0, 0, 2000, None, 2925, None, 0, None, 925, None, 2000, 2000, 2000, 5000),
        (True, FamilyPlanType.INDIVIDUAL, True, True, 0, 0, 100, 0, 0, 0, None, 925, None, 0, None, 925, None, 0, 0, 100, 5000),
        (True, FamilyPlanType.FAMILY, True, True, 0.2, 500, 0, 0, 0, 1200, 2500, 3000, 7500, 700, 2000, 2500, 7000, 500, 500, 500, 5000),
        (True, FamilyPlanType.FAMILY, True, True, 0.2, 960, 1040, 260, 0, 700, 2000, 2500, 7000, 0, 1300, 1540, 6040, 700, 960, 2000, 5000),
        (True, FamilyPlanType.FAMILY, True, True, 0.2, 200, 800, 200, 0, 0, 1300, 1540, 6040, 0, 1300, 1340, 5840, 0, 200, 1000, 3960),
        (True, FamilyPlanType.FAMILY, True, True, 0.2, 1000, 0, 0, 0, 1200, 1300, 3000, 5840, 200, 300, 2000, 4840, 1000, 1000, 1000, 3160),
        (True, FamilyPlanType.FAMILY, True, True, 0.2, 280, 320, 80, 0, 200, 300, 2000, 4840, 0, 100, 1720, 4560, 200, 280, 600, 3160),
        (True, FamilyPlanType.FAMILY, True, True, 0.2, 200, 400, 100, 0, 1200, 100, 2000, 4560, 1100, 0, 1800, 4360, 100, 200, 600, 2840),
        (True, FamilyPlanType.FAMILY, True, True, 0.2, 20, 80, 20, 0, 1200, 0, 3000, 4360, 1200, 0, 2980, 4340, 0, 20, 100, 2440),
        (True, FamilyPlanType.INDIVIDUAL, True, False, 0, 500, 0, 0, 0, 2500, None, 3425, None, 2000, None, 2925, None, 500, 500, 500, 5000),
        (True, FamilyPlanType.INDIVIDUAL, True, False, 0, 2000, 0, 0, 0, 2000, None, 2925, None, 0, None, 925, None, 2000, 2000, 2000, 5000),
        (True, FamilyPlanType.INDIVIDUAL, True, False, 0, 0, 100, 0, 0, 0, None, 925, None, 0, None, 925, None, 0, 0, 100, 5000),
        (True, FamilyPlanType.FAMILY, True, False, 0.2, 1800, 3200, 800, 0, 1000, 2500, 2500, 5000, 0, 1500, None, 3200, 1000, 1800, 5000, 10_000),
        (True, FamilyPlanType.FAMILY, True, False, 0.2, 200, 800, 200, 0, 0, 1500, None, 3200, 0, 1500, None, 3000, 0, 200, 1000, 6800),
        (True, FamilyPlanType.FAMILY, True, False, 0.2, 1400, 1600, 400, 0, 1000, 1500, 2500, 3000, 0, 500, None, 1600, 1000, 1400, 3000, 6000),
        (True, FamilyPlanType.FAMILY, True, False, 0.2, 820, 1280, 320, 0, 1000, 500, 2500, 1600, 500, 0, None, 780, 500, 820, 2100, 4400),
        (True, FamilyPlanType.FAMILY, True, False, 0.2, 20, 80, 20, 0, 1000, 0, None, 780, 1000, 0, None, 760, 0, 20, 100, 3120),
        (True, FamilyPlanType.FAMILY, False, True, 0.2, 500, 0, 0, 0, None, 3600, 5000, 10_000, None, 3100, 4500, 9500, 500, 500, 500, 10_000),
        (True, FamilyPlanType.FAMILY, False, True, 0.2, 2000, 0, 0, 0, None, 3100, 4500, 9500, None, 1100, 2500, 7500, 2000, 2000, 2000, 10_000),
        (True, FamilyPlanType.FAMILY, False, True, 0.2, 1000, 0, 0, 0, None, 1100, 2500, 7500, None, 100, 1500, 6500, 1000, 1000, 1000, 10_000),
        (True, FamilyPlanType.FAMILY, False, True, 0.2, 280, 720, 180, 0, None, 100, 5000, 6500, None, 0, 4720, 6220, 100, 280, 1000, 10_000),
        (True, FamilyPlanType.FAMILY, False, True, 0.2, 120, 480, 120, 0, None, 0, 4720, 6220, None, 0, 4600, 6100, 0, 120, 600, 9280),
        (True, FamilyPlanType.FAMILY, False, True, 0.2, 2000, 8000, 2000, 0, None, 0, 5000, 6100, None, 0, 3000, 4100, 0, 2000, 10_000, 8800),
        (True, FamilyPlanType.FAMILY, False, True, 0.2, 184, 736, 184, 0, None, 0, 5000, 4100, None, 0, 4816, 3916, 0, 184, 920, 800),
        (True, FamilyPlanType.FAMILY, False, True, 0.2, 36, 64, 20, 16, None, 0, 4816, 3916, None, 0, 4780, 3880, 0, 36, 100, 64),
        (True, FamilyPlanType.FAMILY, False, True, 0.2, 2000, 0, 0, 0, None, 3600, 5000, 10_000, None, 1600, 3000, 8000, 2000, 2000, 2000, 10_000),
        (True, FamilyPlanType.FAMILY, False, True, 0.2, 1000, 0, 0, 0, None, 1600, 3000, 8000, None, 600, 2000, 7000, 1000, 1000, 1000, 10_000),
        (True, FamilyPlanType.FAMILY, False, True, 0.2, 880, 1120, 280, 0, None, 600, 5000, 7000, None, 0, 4120, 6120, 600, 880, 2000, 10_000),
        (True, FamilyPlanType.INDIVIDUAL, False, True, 0, 500, 0, 0, 0, 2500, None, 3425, None, 2000, None, 2925, None, 500, 500, 500, 5000),
        (True, FamilyPlanType.INDIVIDUAL, False, True, 0, 2000, 0, 0, 0, 2000, None, 2925, None, 0, None, 925, None, 2000, 2000, 2000, 5000),
        (True, FamilyPlanType.INDIVIDUAL, False, True, 0, 0, 100, 0, 0, 0, None, 925, None, 0, None, 925, None, 0, 0, 100, 5000),
    ],
    ids=[
        "unlimited-benefits-off - non-embedded individual first treatment",
        "unlimited-benefits-off - non-embedded individual second treatment",
        "unlimited-benefits-off - non-embedded individual third treatment",
        "unlimited-benefits-off - non-embedded family first treatment",
        "unlimited-benefits-off - non-embedded family second treatment",
        "unlimited-benefits-off - non-embedded family third treatment",
        "unlimited-benefits-off - fully embedded individual first treatment",
        "unlimited-benefits-off - fully embedded individual second treatment",
        "unlimited-benefits-off - fully embedded individual third treatment",
        "unlimited-benefits-off - fully embedded family member 1 treatment 1",
        "unlimited-benefits-off - fully embedded family member 1 treatment 2",
        "unlimited-benefits-off - fully embedded family member 1 treatment 3",
        "unlimited-benefits-off - fully embedded family member 2 treatment 1",
        "unlimited-benefits-off - fully embedded family member 2 treatment 2",
        "unlimited-benefits-off - fully embedded family member 3 treatment 1",
        "unlimited-benefits-off - fully embedded family member 4 treatment 1",
        "unlimited-benefits-off - embedded deductible individual first treatment",
        "unlimited-benefits-off - embedded deductible individual second treatment",
        "unlimited-benefits-off - embedded deductible individual third treatment",
        "unlimited-benefits-off - embedded deductible family member 1 treatment 1",
        "unlimited-benefits-off - embedded deductible family member 1 treatment 2",
        "unlimited-benefits-off - embedded deductible family member 2 treatment 1",
        "unlimited-benefits-off - embedded deductible family member 3 treatment 1",
        "unlimited-benefits-off - embedded deductible family member 4 treatment 1",
        "unlimited-benefits-off - embedded oop family 1 member 1 treatment 1",
        "unlimited-benefits-off - embedded oop family 1 member 1 treatment 2",
        "unlimited-benefits-off - embedded oop family 1 member 1 treatment 3",
        "unlimited-benefits-off - embedded oop family 1 member 2 treatment 1",
        "unlimited-benefits-off - embedded oop family 1 member 2 treatment 2",
        "unlimited-benefits-off - embedded oop family 1 member 3 treatment 1",
        "unlimited-benefits-off - embedded oop family 1 member 4 treatment 1",
        "unlimited-benefits-off - embedded oop family 1 member 4 treatment 2",
        "unlimited-benefits-off - embedded oop family 2 member 1 treatment 1",
        "unlimited-benefits-off - embedded oop family 2 member 1 treatment 2",
        "unlimited-benefits-off - embedded oop family 2 member 2 treatment 1",
        "unlimited-benefits-off - embedded oop individual first treatment",
        "unlimited-benefits-off - embedded oop individual second treatment",
        "unlimited-benefits-off - embedded oop individual third treatment",
        # Unlimited benefits flag on below
        "unlimited-benefits-on - non-embedded individual first treatment",
        "unlimited-benefits-on - non-embedded individual second treatment",
        "unlimited-benefits-on - non-embedded individual third treatment",
        "unlimited-benefits-on - non-embedded family first treatment",
        "unlimited-benefits-on - non-embedded family second treatment",
        "unlimited-benefits-on - non-embedded family third treatment",
        "unlimited-benefits-on - fully embedded individual first treatment",
        "unlimited-benefits-on - fully embedded individual second treatment",
        "unlimited-benefits-on - fully embedded individual third treatment",
        "unlimited-benefits-on - fully embedded family member 1 treatment 1",
        "unlimited-benefits-on - fully embedded family member 1 treatment 2",
        "unlimited-benefits-on - fully embedded family member 1 treatment 3",
        "unlimited-benefits-on - fully embedded family member 2 treatment 1",
        "unlimited-benefits-on - fully embedded family member 2 treatment 2",
        "unlimited-benefits-on - fully embedded family member 3 treatment 1",
        "unlimited-benefits-on - fully embedded family member 4 treatment 1",
        "unlimited-benefits-on - embedded deductible individual first treatment",
        "unlimited-benefits-on - embedded deductible individual second treatment",
        "unlimited-benefits-on - embedded deductible individual third treatment",
        "unlimited-benefits-on - embedded deductible family member 1 treatment 1",
        "unlimited-benefits-on - embedded deductible family member 1 treatment 2",
        "unlimited-benefits-on - embedded deductible family member 2 treatment 1",
        "unlimited-benefits-on - embedded deductible family member 3 treatment 1",
        "unlimited-benefits-on - embedded deductible family member 4 treatment 1",
        "unlimited-benefits-on - embedded oop family 1 member 1 treatment 1",
        "unlimited-benefits-on - embedded oop family 1 member 1 treatment 2",
        "unlimited-benefits-on - embedded oop family 1 member 1 treatment 3",
        "unlimited-benefits-on - embedded oop family 1 member 2 treatment 1",
        "unlimited-benefits-on - embedded oop family 1 member 2 treatment 2",
        "unlimited-benefits-on - embedded oop family 1 member 3 treatment 1",
        "unlimited-benefits-on - embedded oop family 1 member 4 treatment 1",
        "unlimited-benefits-on - embedded oop family 1 member 4 treatment 2",
        "unlimited-benefits-on - embedded oop family 2 member 1 treatment 1",
        "unlimited-benefits-on - embedded oop family 2 member 1 treatment 2",
        "unlimited-benefits-on - embedded oop family 2 member 2 treatment 1",
        "unlimited-benefits-on - embedded oop individual first treatment",
        "unlimited-benefits-on - embedded oop individual second treatment",
        "unlimited-benefits-on - embedded oop individual third treatment",
    ],
    # fmt: on
)
def test_cost_breakdown_embedded_non_embedded_coinsurance(
    enable_is_unlimited,
    plan_type,
    is_deductible_embedded,
    is_oop_embedded,
    coinsurance,
    member_responsibility,
    employer_responsibility,
    coinsurance_charge,
    overage_amount,
    individual_deductible_remaining,
    family_deductible_remaining,
    individual_oop_remaining,
    family_oop_remaining,
    expected_individual_deductible_remaining,
    expected_family_deductible_remaining,
    expected_individual_oop_remaining,
    expected_family_oop_remaining,
    expected_deductible_apply,
    expected_oop_apply,
    treatment_cost,
    wallet_balance,
    wallet,
    cost_breakdown_proc,
    treatment_procedure,
    rte_transaction_with_copay,
    ff_test_data,
):
    ff_test_data.update(
        ff_test_data.flag(ENABLE_UNLIMITED_BENEFITS_FOR_CB).variation_for_all(
            enable_is_unlimited
        )
    )
    member_health_plan = MemberHealthPlan(
        patient_first_name="Test",
        patient_last_name="Test",
        subscriber_first_name="Test2",
        subscriber_last_name="Test2",
        plan_type=plan_type,
        reimbursement_wallet_id=wallet.id,
        employer_health_plan=EmployerHealthPlan(),
    )
    eligibility_info = EligibilityInfo(
        copay=None,
        coinsurance=coinsurance,
        individual_deductible_remaining=individual_deductible_remaining,
        family_deductible_remaining=family_deductible_remaining,
        individual_oop_remaining=individual_oop_remaining,
        family_oop_remaining=family_oop_remaining,
        is_oop_embedded=is_oop_embedded,
        is_deductible_embedded=is_deductible_embedded,
    )
    wallet.reimbursement_organization_settings.deductible_accumulation_enabled = True
    treatment_procedure.cost = treatment_cost
    with patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_treatment_cost_sharing_category",
        return_value=CostSharingCategory.MEDICAL_CARE,
    ), patch(
        "cost_breakdown.cost_breakdown_data_service.CostBreakdownDataService.get_eligibility_info",
        return_value=(eligibility_info, 1),
    ), patch(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor._get_member_health_plan",
        return_value=member_health_plan,
    ):
        cost_breakdown = cost_breakdown_proc.get_cost_breakdown_for_treatment_procedure(
            wallet=wallet,
            treatment_procedure=treatment_procedure,
            wallet_balance=wallet_balance,
        )
    assert (
        expected_individual_deductible_remaining == cost_breakdown.deductible_remaining
    )
    assert expected_individual_oop_remaining == cost_breakdown.oop_remaining
    assert (
        expected_family_deductible_remaining
        == cost_breakdown.family_deductible_remaining
    )
    assert expected_family_oop_remaining == cost_breakdown.family_oop_remaining
    assert expected_deductible_apply == cost_breakdown.deductible
    assert expected_oop_apply == cost_breakdown.oop_applied
    assert overage_amount == cost_breakdown.overage_amount
    assert cost_breakdown.is_unlimited is False
    assert cost_breakdown.beginning_wallet_balance == wallet_balance
    assert (
        cost_breakdown.ending_wallet_balance == wallet_balance - employer_responsibility
    )
    assert member_responsibility == cost_breakdown.total_member_responsibility
    assert employer_responsibility == cost_breakdown.total_employer_responsibility
    assert coinsurance_charge == cost_breakdown.coinsurance
    assert (plan_type in FAMILY_PLANS) == cost_breakdown.calc_config[
        "health_plan_configuration"
    ]["is_family_plan"]


@pytest.mark.parametrize(argnames="enable_is_unlimited", argvalues=[True, False])
def test_health_plan_values_in_calc_config_audit(
    enable_is_unlimited,
    cost_breakdown_proc,
    treatment_procedure,
    member_health_plan,
    ff_test_data,
):
    ff_test_data.update(
        ff_test_data.flag(ENABLE_UNLIMITED_BENEFITS_FOR_CB).variation_for_all(
            enable_is_unlimited
        )
    )
    cost_breakdown = CostBreakdownFactory.create()
    with patch.multiple(
        "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor",
        get_treatment_cost_sharing_category=MagicMock(
            return_value=CostSharingCategory.DIAGNOSTIC_MEDICAL
        ),
        _get_member_health_plan=MagicMock(return_value=member_health_plan),
        _run_data_service=MagicMock(return_value=cost_breakdown),
    ):
        cost_breakdown = cost_breakdown_proc.get_cost_breakdown_for_treatment_procedure(
            wallet=member_health_plan.reimbursement_wallet,
            treatment_procedure=treatment_procedure,
            wallet_balance=0,
            store_to_db=False,
        )

    assert cost_breakdown.calc_config["member_health_plan_id"] == member_health_plan.id
    assert (
        cost_breakdown.calc_config["reimbursement_organization_settings_id"]
        == member_health_plan.reimbursement_wallet.reimbursement_organization_settings_id
    )


@pytest.mark.parametrize(
    argnames="feature_flag_variation", argvalues=[OLD_BEHAVIOR, NEW_BEHAVIOR]
)
def test_cost_breakdown_for_treatment_procedure_tier_determination(
    cost_breakdown_proc,
    treatment_procedure,
    member_health_plan,
    feature_flag_variation,
    ff_test_data,
):
    with feature_flags.test_data() as ff_test_data:
        ff_test_data.update(
            ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(feature_flag_variation)
        )
        employer_health_plan_coverage = EmployerHealthPlanCoverageFactory.create(tier=1)
        member_health_plan.plan_start_at = datetime.datetime(2024, 1, 1)
        member_health_plan.plan_end_at = datetime.datetime(2039, 1, 1)
        start_date = datetime.datetime.strptime("2024-03-15", "%Y-%m-%d").date()

        FertilityClinicLocationEmployerHealthPlanTierFactory.create(
            employer_health_plan=employer_health_plan_coverage.employer_health_plan,
            employer_health_plan_id=employer_health_plan_coverage.employer_health_plan.id,
            fertility_clinic_location=treatment_procedure.fertility_clinic_location,
            fertility_clinic_location_id=treatment_procedure.fertility_clinic_location.id,
        )
        member_health_plan.employer_health_plan = (
            employer_health_plan_coverage.employer_health_plan
        )
        member_health_plan.employer_health_plan_id = (
            employer_health_plan_coverage.employer_health_plan_id
        )
        member_health_plan.member_id = treatment_procedure.member_id
        treatment_procedure.start_date = start_date
        with patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_treatment_cost_sharing_category",
            return_value=CostSharingCategory.DIAGNOSTIC_MEDICAL,
        ), patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor._get_member_health_plan",
            return_value=member_health_plan,
        ), patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.cost_breakdown_data_service_from_treatment_procedure",
        ) as cost_breakdown_data_service_from_treatment_procedure:
            cost_breakdown_proc.get_cost_breakdown_for_treatment_procedure(
                wallet=member_health_plan.reimbursement_wallet,
                treatment_procedure=treatment_procedure,
                wallet_balance=0,
                store_to_db=False,
            )
            cost_breakdown_data_service_from_treatment_procedure.assert_called_once_with(
                cost=treatment_procedure.cost,
                member_id=treatment_procedure.member_id,
                wallet=member_health_plan.reimbursement_wallet,
                reimbursement_category=treatment_procedure.reimbursement_request_category,
                procedure_type=treatment_procedure.procedure_type,
                # type: ignore[arg-type] # Argument "procedure_type" to "cost_breakdown_data_service_from_treatment_procedure" of "CostBreakdownProcessor" has incompatible type "str"; expected "TreatmentProcedureType"
                before_this_date=ANY,
                asof_date=datetime.datetime.combine(start_date, datetime.time.min),
                global_procedure_id=treatment_procedure.global_procedure_id,
                wallet_balance_override=ANY,
                should_include_pending=ANY,
                tier=Tier.PREMIUM,
                fdc_hdhp_check=ANY,
                service_start_date=treatment_procedure.start_date,
                treatment_procedure_id=treatment_procedure.id,
            )


class TestReimbursementRequestCostBreakdown:
    @pytest.mark.parametrize(argnames="enable_is_unlimited", argvalues=[True, False])
    def test_data_service_from_reimbursement_request(
        self, enable_is_unlimited, cost_breakdown_proc, ff_test_data
    ):
        ff_test_data.update(
            ff_test_data.flag(ENABLE_UNLIMITED_BENEFITS_FOR_CB).variation_for_all(
                enable_is_unlimited
            )
        )
        # Note lack of member health plan!
        wallet = ReimbursementWalletFactory.create(state=WalletState.QUALIFIED)
        subscriber = wallet.member
        first_wallet_user = ReimbursementWalletUsersFactory.create(
            user_id=wallet.user_id, reimbursement_wallet_id=wallet.id
        )
        category_association = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ]
        )
        ReimbursementPlanFactory.create(
            category=category_association.reimbursement_request_category,
            start_date=datetime.date.today() - datetime.timedelta(days=100),
            end_date=datetime.date.today() + datetime.timedelta(days=100),
        )
        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=wallet,
            amount=580_00,
            reimbursement_request_category_id=category_association.reimbursement_request_category.id,
            procedure_type="MEDICAL",
        )
        expected_cost_sharing_category = CostSharingCategory.MEDICAL_CARE

        # When
        with patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_treatment_cost_sharing_category",
            return_value=CostSharingCategory.MEDICAL_CARE,
        ):
            data_service = cost_breakdown_proc.cost_breakdown_data_service_from_reimbursement_request(
                user_id=first_wallet_user.user_id,
                reimbursement_request=reimbursement_request,
                global_procedure_id="fake_uuid",
                asof_date=reimbursement_request.service_start_date,
            )

        # Then
        assert data_service.member_first_name == subscriber.first_name
        assert data_service.member_last_name == subscriber.last_name
        assert data_service.member_health_plan is None
        assert (
            data_service.wallet_balance
            == category_association.reimbursement_request_category_maximum
        )
        assert data_service.cost == reimbursement_request.amount
        assert data_service.procedure_type == TreatmentProcedureType.MEDICAL
        assert data_service.cost_sharing_category == expected_cost_sharing_category
        assert data_service.deductible_accumulation_enabled is False
        assert (
            data_service.sequential_deductible_accumulation_member_responsibilities
            is None
        )
        assert data_service.sequential_hdhp_responsibilities is None
        assert data_service.alegeus_ytd_spend == 0
        assert data_service.rx_ytd_spend is None
        assert data_service.tier is None

    @pytest.mark.parametrize(argnames="enable_is_unlimited", argvalues=[True, False])
    def test_data_service_from_reimbursement_request_for_dependent(
        self, enable_is_unlimited, cost_breakdown_proc, ff_test_data
    ):
        ff_test_data.update(
            ff_test_data.flag(ENABLE_UNLIMITED_BENEFITS_FOR_CB).variation_for_all(
                enable_is_unlimited
            )
        )
        wallet = ReimbursementWalletFactory.create(state=WalletState.QUALIFIED)
        ReimbursementWalletUsersFactory.create(
            user_id=wallet.user_id, reimbursement_wallet_id=wallet.id
        )
        subscriber = wallet.member
        dependent = EnterpriseUserFactory.create()
        second_wallet_user = ReimbursementWalletUsersFactory.create(
            user_id=dependent.id, reimbursement_wallet_id=wallet.id
        )
        # ensure the correct health plan is retrieved.
        employer_health_plan = EmployerHealthPlanFactory.create(
            reimbursement_organization_settings=wallet.reimbursement_organization_settings,
        )
        MemberHealthPlanFactory.create(
            reimbursement_wallet_id=wallet.id,
            reimbursement_wallet=wallet,
            employer_health_plan=employer_health_plan,
            member_id=subscriber.id,
            is_subscriber=True,
            subscriber_first_name=wallet.member.first_name,
            subscriber_last_name=wallet.member.last_name,
            patient_first_name=dependent.first_name,
            patient_last_name=dependent.last_name,
        )
        expected_member_health_plan = MemberHealthPlanFactory.create(
            reimbursement_wallet_id=wallet.id,
            reimbursement_wallet=wallet,
            employer_health_plan=employer_health_plan,
            member_id=dependent.id,
            is_subscriber=False,
            subscriber_first_name=subscriber.first_name,
            subscriber_last_name=subscriber.last_name,
            patient_first_name=dependent.first_name,
            patient_last_name=dependent.last_name,
        )
        category_association = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ]
        )
        ReimbursementPlanFactory.create(
            category=category_association.reimbursement_request_category,
            start_date=datetime.date.today() - datetime.timedelta(days=100),
            end_date=datetime.date.today() + datetime.timedelta(days=100),
        )
        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=wallet,
            amount=580_00,
            reimbursement_request_category_id=category_association.reimbursement_request_category.id,
            procedure_type="MEDICAL",
        )

        # When
        with patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_treatment_cost_sharing_category",
            return_value=CostSharingCategory.MEDICAL_CARE,
        ):
            data_service = cost_breakdown_proc.cost_breakdown_data_service_from_reimbursement_request(
                user_id=second_wallet_user.user_id,
                reimbursement_request=reimbursement_request,
                global_procedure_id="fake_uuid",
                tier=Tier.PREMIUM,
                asof_date=reimbursement_request.service_start_date,
            )

        assert data_service.member_first_name == dependent.first_name
        assert data_service.member_last_name == dependent.last_name
        assert data_service.member_health_plan == expected_member_health_plan
        assert data_service.tier == Tier.PREMIUM

    @pytest.mark.parametrize(argnames="enable_is_unlimited", argvalues=[True, False])
    def test_data_service_from_reimbursement_request_tiered_plan(
        self, enable_is_unlimited, cost_breakdown_proc, ff_test_data
    ):
        ff_test_data.update(
            ff_test_data.flag(ENABLE_UNLIMITED_BENEFITS_FOR_CB).variation_for_all(
                enable_is_unlimited
            )
        )
        wallet = ReimbursementWalletFactory.create(state=WalletState.QUALIFIED)
        coverage = EmployerHealthPlanCoverageFactory.create(tier=Tier.SECONDARY)
        MemberHealthPlanFactory.create(
            subscriber_first_name=wallet.member.first_name,
            subscriber_last_name=wallet.member.last_name,
            patient_first_name=wallet.member.first_name,
            patient_last_name=wallet.member.last_name,
            employer_health_plan=coverage.employer_health_plan,
            employer_health_plan_id=coverage.employer_health_plan.id,
            reimbursement_wallet=wallet,
            reimbursement_wallet_id=wallet.id,
        )
        first_wallet_user = ReimbursementWalletUsersFactory.create(
            user_id=wallet.user_id, reimbursement_wallet_id=wallet.id
        )
        category_association = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
                0
            ]
        )
        ReimbursementPlanFactory.create(
            category=category_association.reimbursement_request_category,
            start_date=datetime.date.today() - datetime.timedelta(days=100),
            end_date=datetime.date.today() + datetime.timedelta(days=100),
        )
        reimbursement_request = ReimbursementRequestFactory.create(
            wallet=wallet,
            amount=580_00,
            reimbursement_request_category_id=category_association.reimbursement_request_category.id,
            procedure_type="MEDICAL",
        )

        # When
        with patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_treatment_cost_sharing_category",
            return_value=CostSharingCategory.MEDICAL_CARE,
        ):
            data_service = cost_breakdown_proc.cost_breakdown_data_service_from_reimbursement_request(
                user_id=first_wallet_user.user_id,
                reimbursement_request=reimbursement_request,
                global_procedure_id="fake_uuid",
                asof_date=reimbursement_request.service_start_date,
            )
        assert data_service.tier is Tier.SECONDARY


class TestTieredCostBreakdown:
    @pytest.mark.parametrize(
        argnames="enable_is_unlimited,"
        "employer_health_plan,"
        "cost_share_category,"
        "treatment_procedure_type,"
        "plan_type,"
        "tier,"
        "treatment_cost,"
        "individual_deductible_remaining,"
        "family_deductible_remaining,"
        "individual_oop_remaining,"
        "family_oop_remaining,"
        "expected_member_cost,"
        "expected_employer_cost,"
        "expected_deductible_applied,"
        "expected_oop_applied",
        argvalues=[
            (
                False,
                "employer_health_plan_coverage_non_embedded",
                CostSharingCategory.CONSULTATION,  # cost_share_category
                TreatmentProcedureType.MEDICAL,  # treatment_procedure_type
                FamilyPlanType.INDIVIDUAL,  # plan_type
                Tier.PREMIUM,  # tier
                100_00,  # treatment_cost
                125_00,  # individual_deductible_remaining
                None,  # family_deductible_remaining
                900_000,  # individual_oop_remaining
                None,  # family_oop_remaining
                100_00,  # expected_member_cost
                0,  # expected_employer_cost
                100_00,  # expected_deductible_applied
                100_00,  # expected_oop_applied
            ),
            (
                False,
                "employer_health_plan_coverage_non_embedded",
                CostSharingCategory.CONSULTATION,  # cost_share_category
                TreatmentProcedureType.MEDICAL,  # treatment_procedure_type
                FamilyPlanType.INDIVIDUAL,  # plan_type
                Tier.SECONDARY,  # tier
                200_00,  # treatment_cost
                50_00,  # individual_deductible_remaining
                None,  # family_deductible_remaining
                900_000,  # individual_oop_remaining
                None,  # family_oop_remaining
                75_00,  # expected_member_cost
                125_00,  # expected_employer_cost
                50_00,  # expected_deductible_applied
                75_00,  # expected_oop_applied
            ),
            (
                False,
                "employer_health_plan_coverage_non_embedded",
                CostSharingCategory.GENERIC_PRESCRIPTIONS,  # cost_share_category
                TreatmentProcedureType.PHARMACY,  # treatment_procedure_type
                FamilyPlanType.INDIVIDUAL,  # plan_type
                Tier.PREMIUM,  # tier
                300_00,  # treatment_cost
                0,  # individual_deductible_remaining
                None,  # family_deductible_remaining
                700_00,  # individual_oop_remaining
                None,  # family_oop_remaining
                10_00,  # expected_member_cost
                290_00,  # expected_employer_cost
                0,  # expected_deductible_applied
                10_00,  # expected_oop_applied
            ),
            (
                False,
                "employer_health_plan_coverage_non_embedded",
                CostSharingCategory.SPECIALTY_PRESCRIPTIONS,  # cost_share_category
                TreatmentProcedureType.PHARMACY,  # treatment_procedure_type
                FamilyPlanType.INDIVIDUAL,  # plan_type
                Tier.PREMIUM,  # tier
                100_00,  # treatment_cost
                0,  # individual_deductible_remaining
                None,  # family_deductible_remaining
                690_00,  # individual_oop_remaining
                None,  # family_oop_remaining
                40_00,  # expected_member_cost
                60_00,  # expected_employer_cost
                0,  # expected_deductible_applied
                40_00,  # expected_oop_applied
            ),
            (
                False,
                "employer_health_plan_coverage_non_embedded",
                CostSharingCategory.MEDICAL_CARE,  # cost_share_category
                TreatmentProcedureType.MEDICAL,  # treatment_procedure_type
                FamilyPlanType.EMPLOYEE_PLUS,  # plan_type
                Tier.PREMIUM,  # tier
                100_00,  # treatment_cost
                None,  # individual_deductible_remaining
                200_00,  # family_deductible_remaining
                None,  # individual_oop_remaining
                1400_00,  # family_oop_remaining
                100_00,  # expected_member_cost
                0,  # expected_employer_cost
                100_00,  # expected_deductible_applied
                100_00,  # expected_oop_applied
            ),
            (
                False,
                "employer_health_plan_coverage_non_embedded",
                CostSharingCategory.DIAGNOSTIC_MEDICAL,  # cost_share_category
                TreatmentProcedureType.MEDICAL,  # treatment_procedure_type
                FamilyPlanType.EMPLOYEE_PLUS,  # plan_type
                Tier.SECONDARY,  # tier
                1500_00,  # treatment_cost
                None,  # individual_deductible_remaining
                125_00,  # family_deductible_remaining
                None,  # individual_oop_remaining
                1400_00,  # family_oop_remaining
                262_50,  # expected_member_cost
                123750,  # expected_employer_cost
                125_00,  # expected_deductible_applied
                262_50,  # expected_oop_applied
            ),
            (
                False,
                "employer_health_plan_coverage_non_embedded",
                CostSharingCategory.CONSULTATION,  # cost_share_category
                TreatmentProcedureType.MEDICAL,  # treatment_procedure_type
                FamilyPlanType.FAMILY,  # plan_type
                Tier.PREMIUM,  # tier
                800_00,  # treatment_cost
                None,  # individual_deductible_remaining
                0,  # family_deductible_remaining
                None,  # individual_oop_remaining
                1600_00,  # family_oop_remaining
                25_00,  # expected_member_cost
                775_00,  # expected_employer_cost
                0,  # expected_deductible_applied
                25_00,  # expected_oop_applied
            ),
            (
                False,
                "employer_health_plan_coverage_non_embedded",
                CostSharingCategory.DIAGNOSTIC_MEDICAL,  # cost_share_category
                TreatmentProcedureType.MEDICAL,  # treatment_procedure_type
                FamilyPlanType.FAMILY,  # plan_type
                Tier.SECONDARY,  # tier
                1500_00,  # treatment_cost
                None,  # individual_deductible_remaining
                0,  # family_deductible_remaining
                None,  # individual_oop_remaining
                1475_00,  # family_oop_remaining
                150_00,  # expected_member_cost
                1350_00,  # expected_employer_cost
                0,  # expected_deductible_applied
                150_00,  # expected_oop_applied
            ),
            (
                False,
                "employer_health_plan_coverage_mixed_embedded",
                CostSharingCategory.DIAGNOSTIC_MEDICAL,  # cost_share_category
                TreatmentProcedureType.MEDICAL,  # treatment_procedure_type
                FamilyPlanType.INDIVIDUAL,  # plan_type
                Tier.PREMIUM,  # tier
                600_00,  # treatment_cost
                2000_00,  # individual_deductible_remaining
                None,  # family_deductible_remaining
                4500_00,  # individual_oop_remaining
                None,  # family_oop_remaining
                600_00,  # expected_member_cost
                0,  # expected_employer_cost
                600_00,  # expected_deductible_applied
                600_00,  # expected_oop_applied
            ),
            (
                False,
                "employer_health_plan_coverage_mixed_embedded",
                CostSharingCategory.DIAGNOSTIC_MEDICAL,  # cost_share_category
                TreatmentProcedureType.MEDICAL,  # treatment_procedure_type
                FamilyPlanType.INDIVIDUAL,  # plan_type
                Tier.SECONDARY,  # tier
                1500_00,  # treatment_cost
                900_00,  # individual_deductible_remaining
                None,  # family_deductible_remaining
                3900_00,  # individual_oop_remaining
                None,  # family_oop_remaining
                1080_00,  # expected_member_cost
                420_00,  # expected_employer_cost
                900_00,  # expected_deductible_applied
                1080_00,  # expected_oop_applied
            ),
            (
                False,
                "employer_health_plan_coverage_mixed_embedded",
                CostSharingCategory.DIAGNOSTIC_MEDICAL,  # cost_share_category
                TreatmentProcedureType.MEDICAL,  # treatment_procedure_type
                FamilyPlanType.EMPLOYEE_PLUS,  # plan_type
                Tier.PREMIUM,  # tier
                1500_00,  # treatment_cost
                None,  # individual_deductible_remaining
                2500_00,  # family_deductible_remaining
                5150_00,  # individual_oop_remaining
                7750_00,  # family_oop_remaining
                1500_00,  # expected_member_cost
                0,  # expected_employer_cost
                1500_00,  # expected_deductible_applied
                1500_00,  # expected_oop_applied
            ),
            (
                False,
                "employer_health_plan_coverage_mixed_embedded",
                CostSharingCategory.DIAGNOSTIC_MEDICAL,  # cost_share_category
                TreatmentProcedureType.MEDICAL,  # treatment_procedure_type
                FamilyPlanType.EMPLOYEE_PLUS,  # plan_type
                Tier.SECONDARY,  # tier
                1500_00,  # treatment_cost
                None,  # individual_deductible_remaining
                50_00,  # family_deductible_remaining
                75_00,  # individual_oop_remaining
                7750_00,  # family_oop_remaining
                75_00,  # expected_member_cost
                1425_00,  # expected_employer_cost
                50_00,  # expected_deductible_applied
                75_00,  # expected_oop_applied
            ),
            (
                False,
                "employer_health_plan_coverage_mixed_embedded",
                CostSharingCategory.DIAGNOSTIC_MEDICAL,  # cost_share_category
                TreatmentProcedureType.MEDICAL,  # treatment_procedure_type
                FamilyPlanType.FAMILY,  # plan_type
                Tier.PREMIUM,  # tier
                1500_00,  # treatment_cost
                None,  # individual_deductible_remaining
                2500_00,  # family_deductible_remaining
                5150_00,  # individual_oop_remaining
                7750_00,  # family_oop_remaining
                1500_00,  # expected_member_cost
                0,  # expected_employer_cost
                1500_00,  # expected_deductible_applied
                1500_00,  # expected_oop_applied
            ),
            (
                False,
                "employer_health_plan_coverage_mixed_embedded",
                CostSharingCategory.DIAGNOSTIC_MEDICAL,  # cost_share_category
                TreatmentProcedureType.MEDICAL,  # treatment_procedure_type
                FamilyPlanType.FAMILY,  # plan_type
                Tier.SECONDARY,  # tier
                10_000_00,  # treatment_cost
                None,  # individual_deductible_remaining
                5400_00,  # family_deductible_remaining
                6550_00,  # individual_oop_remaining
                12_400_00,  # family_oop_remaining
                6550_00,  # expected_member_cost
                3450_00,  # expected_employer_cost
                5400_00,  # expected_deductible_applied
                6550_00,  # expected_oop_applied
            ),
            # Unlimited benefits flag on below
            (
                True,
                "employer_health_plan_coverage_non_embedded",
                CostSharingCategory.CONSULTATION,  # cost_share_category
                TreatmentProcedureType.MEDICAL,  # treatment_procedure_type
                FamilyPlanType.INDIVIDUAL,  # plan_type
                Tier.PREMIUM,  # tier
                100_00,  # treatment_cost
                125_00,  # individual_deductible_remaining
                None,  # family_deductible_remaining
                900_000,  # individual_oop_remaining
                None,  # family_oop_remaining
                100_00,  # expected_member_cost
                0,  # expected_employer_cost
                100_00,  # expected_deductible_applied
                100_00,  # expected_oop_applied
            ),
            (
                True,
                "employer_health_plan_coverage_non_embedded",
                CostSharingCategory.CONSULTATION,  # cost_share_category
                TreatmentProcedureType.MEDICAL,  # treatment_procedure_type
                FamilyPlanType.INDIVIDUAL,  # plan_type
                Tier.SECONDARY,  # tier
                200_00,  # treatment_cost
                50_00,  # individual_deductible_remaining
                None,  # family_deductible_remaining
                900_000,  # individual_oop_remaining
                None,  # family_oop_remaining
                75_00,  # expected_member_cost
                125_00,  # expected_employer_cost
                50_00,  # expected_deductible_applied
                75_00,  # expected_oop_applied
            ),
            (
                True,
                "employer_health_plan_coverage_non_embedded",
                CostSharingCategory.GENERIC_PRESCRIPTIONS,  # cost_share_category
                TreatmentProcedureType.PHARMACY,  # treatment_procedure_type
                FamilyPlanType.INDIVIDUAL,  # plan_type
                Tier.PREMIUM,  # tier
                300_00,  # treatment_cost
                0,  # individual_deductible_remaining
                None,  # family_deductible_remaining
                700_00,  # individual_oop_remaining
                None,  # family_oop_remaining
                10_00,  # expected_member_cost
                290_00,  # expected_employer_cost
                0,  # expected_deductible_applied
                10_00,  # expected_oop_applied
            ),
            (
                True,
                "employer_health_plan_coverage_non_embedded",
                CostSharingCategory.SPECIALTY_PRESCRIPTIONS,  # cost_share_category
                TreatmentProcedureType.PHARMACY,  # treatment_procedure_type
                FamilyPlanType.INDIVIDUAL,  # plan_type
                Tier.PREMIUM,  # tier
                100_00,  # treatment_cost
                0,  # individual_deductible_remaining
                None,  # family_deductible_remaining
                690_00,  # individual_oop_remaining
                None,  # family_oop_remaining
                40_00,  # expected_member_cost
                60_00,  # expected_employer_cost
                0,  # expected_deductible_applied
                40_00,  # expected_oop_applied
            ),
            (
                True,
                "employer_health_plan_coverage_non_embedded",
                CostSharingCategory.MEDICAL_CARE,  # cost_share_category
                TreatmentProcedureType.MEDICAL,  # treatment_procedure_type
                FamilyPlanType.EMPLOYEE_PLUS,  # plan_type
                Tier.PREMIUM,  # tier
                100_00,  # treatment_cost
                None,  # individual_deductible_remaining
                200_00,  # family_deductible_remaining
                None,  # individual_oop_remaining
                1400_00,  # family_oop_remaining
                100_00,  # expected_member_cost
                0,  # expected_employer_cost
                100_00,  # expected_deductible_applied
                100_00,  # expected_oop_applied
            ),
            (
                True,
                "employer_health_plan_coverage_non_embedded",
                CostSharingCategory.DIAGNOSTIC_MEDICAL,  # cost_share_category
                TreatmentProcedureType.MEDICAL,  # treatment_procedure_type
                FamilyPlanType.EMPLOYEE_PLUS,  # plan_type
                Tier.SECONDARY,  # tier
                1500_00,  # treatment_cost
                None,  # individual_deductible_remaining
                125_00,  # family_deductible_remaining
                None,  # individual_oop_remaining
                1400_00,  # family_oop_remaining
                262_50,  # expected_member_cost
                123750,  # expected_employer_cost
                125_00,  # expected_deductible_applied
                262_50,  # expected_oop_applied
            ),
            (
                True,
                "employer_health_plan_coverage_non_embedded",
                CostSharingCategory.CONSULTATION,  # cost_share_category
                TreatmentProcedureType.MEDICAL,  # treatment_procedure_type
                FamilyPlanType.FAMILY,  # plan_type
                Tier.PREMIUM,  # tier
                800_00,  # treatment_cost
                None,  # individual_deductible_remaining
                0,  # family_deductible_remaining
                None,  # individual_oop_remaining
                1600_00,  # family_oop_remaining
                25_00,  # expected_member_cost
                775_00,  # expected_employer_cost
                0,  # expected_deductible_applied
                25_00,  # expected_oop_applied
            ),
            (
                True,
                "employer_health_plan_coverage_non_embedded",
                CostSharingCategory.DIAGNOSTIC_MEDICAL,  # cost_share_category
                TreatmentProcedureType.MEDICAL,  # treatment_procedure_type
                FamilyPlanType.FAMILY,  # plan_type
                Tier.SECONDARY,  # tier
                1500_00,  # treatment_cost
                None,  # individual_deductible_remaining
                0,  # family_deductible_remaining
                None,  # individual_oop_remaining
                1475_00,  # family_oop_remaining
                150_00,  # expected_member_cost
                1350_00,  # expected_employer_cost
                0,  # expected_deductible_applied
                150_00,  # expected_oop_applied
            ),
            (
                True,
                "employer_health_plan_coverage_mixed_embedded",
                CostSharingCategory.DIAGNOSTIC_MEDICAL,  # cost_share_category
                TreatmentProcedureType.MEDICAL,  # treatment_procedure_type
                FamilyPlanType.INDIVIDUAL,  # plan_type
                Tier.PREMIUM,  # tier
                600_00,  # treatment_cost
                2000_00,  # individual_deductible_remaining
                None,  # family_deductible_remaining
                4500_00,  # individual_oop_remaining
                None,  # family_oop_remaining
                600_00,  # expected_member_cost
                0,  # expected_employer_cost
                600_00,  # expected_deductible_applied
                600_00,  # expected_oop_applied
            ),
            (
                True,
                "employer_health_plan_coverage_mixed_embedded",
                CostSharingCategory.DIAGNOSTIC_MEDICAL,  # cost_share_category
                TreatmentProcedureType.MEDICAL,  # treatment_procedure_type
                FamilyPlanType.INDIVIDUAL,  # plan_type
                Tier.SECONDARY,  # tier
                1500_00,  # treatment_cost
                900_00,  # individual_deductible_remaining
                None,  # family_deductible_remaining
                3900_00,  # individual_oop_remaining
                None,  # family_oop_remaining
                1080_00,  # expected_member_cost
                420_00,  # expected_employer_cost
                900_00,  # expected_deductible_applied
                1080_00,  # expected_oop_applied
            ),
            (
                True,
                "employer_health_plan_coverage_mixed_embedded",
                CostSharingCategory.DIAGNOSTIC_MEDICAL,  # cost_share_category
                TreatmentProcedureType.MEDICAL,  # treatment_procedure_type
                FamilyPlanType.EMPLOYEE_PLUS,  # plan_type
                Tier.PREMIUM,  # tier
                1500_00,  # treatment_cost
                None,  # individual_deductible_remaining
                2500_00,  # family_deductible_remaining
                5150_00,  # individual_oop_remaining
                7750_00,  # family_oop_remaining
                1500_00,  # expected_member_cost
                0,  # expected_employer_cost
                1500_00,  # expected_deductible_applied
                1500_00,  # expected_oop_applied
            ),
            (
                True,
                "employer_health_plan_coverage_mixed_embedded",
                CostSharingCategory.DIAGNOSTIC_MEDICAL,  # cost_share_category
                TreatmentProcedureType.MEDICAL,  # treatment_procedure_type
                FamilyPlanType.EMPLOYEE_PLUS,  # plan_type
                Tier.SECONDARY,  # tier
                1500_00,  # treatment_cost
                None,  # individual_deductible_remaining
                50_00,  # family_deductible_remaining
                75_00,  # individual_oop_remaining
                7750_00,  # family_oop_remaining
                75_00,  # expected_member_cost
                1425_00,  # expected_employer_cost
                50_00,  # expected_deductible_applied
                75_00,  # expected_oop_applied
            ),
            (
                True,
                "employer_health_plan_coverage_mixed_embedded",
                CostSharingCategory.DIAGNOSTIC_MEDICAL,  # cost_share_category
                TreatmentProcedureType.MEDICAL,  # treatment_procedure_type
                FamilyPlanType.FAMILY,  # plan_type
                Tier.PREMIUM,  # tier
                1500_00,  # treatment_cost
                None,  # individual_deductible_remaining
                2500_00,  # family_deductible_remaining
                5150_00,  # individual_oop_remaining
                7750_00,  # family_oop_remaining
                1500_00,  # expected_member_cost
                0,  # expected_employer_cost
                1500_00,  # expected_deductible_applied
                1500_00,  # expected_oop_applied
            ),
            (
                True,
                "employer_health_plan_coverage_mixed_embedded",
                CostSharingCategory.DIAGNOSTIC_MEDICAL,  # cost_share_category
                TreatmentProcedureType.MEDICAL,  # treatment_procedure_type
                FamilyPlanType.FAMILY,  # plan_type
                Tier.SECONDARY,  # tier
                10_000_00,  # treatment_cost
                None,  # individual_deductible_remaining
                5400_00,  # family_deductible_remaining
                6550_00,  # individual_oop_remaining
                12_400_00,  # family_oop_remaining
                6550_00,  # expected_member_cost
                3450_00,  # expected_employer_cost
                5400_00,  # expected_deductible_applied
                6550_00,  # expected_oop_applied
            ),
        ],
    )
    def test_tiered_cost_breakdown(
        self,
        enable_is_unlimited,
        employer_health_plan,
        cost_share_category,
        treatment_procedure_type,
        plan_type,
        tier,
        treatment_cost,
        individual_deductible_remaining,
        family_deductible_remaining,
        individual_oop_remaining,
        family_oop_remaining,
        expected_member_cost,
        expected_employer_cost,
        expected_deductible_applied,
        expected_oop_applied,
        wallet,
        cost_breakdown_proc,
        treatment_procedure,
        request,
        ff_test_data,
    ):
        ff_test_data.update(
            ff_test_data.flag(ENABLE_UNLIMITED_BENEFITS_FOR_CB).variation_for_all(
                enable_is_unlimited
            )
        )
        ehp = request.getfixturevalue(employer_health_plan)
        member_health_plan = MemberHealthPlanFactory.create(
            patient_first_name="Test",
            patient_last_name="Test",
            subscriber_first_name="Test2",
            subscriber_last_name="Test2",
            plan_type=plan_type,
            reimbursement_wallet_id=wallet.id,
            member_id=treatment_procedure.member_id,
            employer_health_plan=ehp,
            employer_health_plan_id=ehp.id,
        )
        rte_transaction = RTETransactionFactory.create(
            id=1,
            response={
                "individual_oop_remaining": individual_oop_remaining,
                "family_deductible_remaining": family_deductible_remaining,
                "family_oop_remaining": family_oop_remaining,
                "individual_deductible_remaining": individual_deductible_remaining,
            },
            response_code=200,
            request={},
            member_health_plan_id=member_health_plan.id,
        )
        wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
            True
        )
        treatment_procedure.cost = treatment_cost
        treatment_procedure.procedure_type = treatment_procedure_type
        if tier == Tier.PREMIUM:
            FertilityClinicLocationEmployerHealthPlanTierFactory.create(
                employer_health_plan=ehp,
                employer_health_plan_id=ehp.id,
                fertility_clinic_location=treatment_procedure.fertility_clinic_location,
                fertility_clinic_location_id=treatment_procedure.fertility_clinic_location.id,
            )
        with patch(
            "cost_breakdown.rte.pverify_api.PverifyAPI.get_real_time_eligibility_data",
            return_value=rte_transaction,
        ), patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor._get_member_health_plan",
            return_value=member_health_plan,
        ), patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_treatment_cost_sharing_category",
            return_value=cost_share_category,
        ):
            cost_breakdown = (
                cost_breakdown_proc.get_cost_breakdown_for_treatment_procedure(
                    wallet=wallet,
                    treatment_procedure=treatment_procedure,
                    wallet_balance=5000_00,
                )
            )
            assert cost_breakdown.total_member_responsibility == expected_member_cost
            assert (
                cost_breakdown.total_employer_responsibility == expected_employer_cost
            )
            assert cost_breakdown.deductible == expected_deductible_applied
            assert cost_breakdown.oop_applied == expected_oop_applied

    @pytest.mark.parametrize(argnames="enable_is_unlimited", argvalues=[True, False])
    def test_tiered_cost_breakdown_mismatched_rte_fails(
        self,
        enable_is_unlimited,
        employer_health_plan_coverage_non_embedded,
        wallet,
        cost_breakdown_proc,
        treatment_procedure,
        ff_test_data,
    ):
        ff_test_data.update(
            ff_test_data.flag(ENABLE_UNLIMITED_BENEFITS_FOR_CB).variation_for_all(
                enable_is_unlimited
            )
        )
        member_health_plan = MemberHealthPlanFactory.create(
            patient_first_name="Test",
            patient_last_name="Test",
            subscriber_first_name="Test2",
            subscriber_last_name="Test2",
            plan_type=FamilyPlanType.FAMILY,
            reimbursement_wallet_id=wallet.id,
            member_id=treatment_procedure.member_id,
            employer_health_plan=employer_health_plan_coverage_non_embedded,
            employer_health_plan_id=employer_health_plan_coverage_non_embedded.id,
        )
        rte_transaction = RTETransactionFactory.create(
            id=1,
            response={
                "individual_oop_remaining": 200,
                "family_deductible_remaining": 200,
                "family_oop_remaining": 400,
                "individual_deductible_remaining": 100,
                "individual_deductible": 400,
            },
            response_code=200,
            request={},
            member_health_plan_id=member_health_plan.id,
        )
        treatment_procedure.procedure_type = TreatmentProcedureType.MEDICAL
        wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
            True
        )
        with patch(
            "cost_breakdown.rte.pverify_api.PverifyAPI.get_real_time_eligibility_data",
            return_value=rte_transaction,
        ), patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor._get_member_health_plan",
            return_value=member_health_plan,
        ), patch(
            "cost_breakdown.cost_breakdown_processor.CostBreakdownProcessor.get_treatment_cost_sharing_category",
            return_value=CostSharingCategory.MEDICAL_CARE,
        ):
            with pytest.raises(TieredRTEError) as e:
                cost_breakdown_proc.get_cost_breakdown_for_treatment_procedure(
                    wallet=wallet,
                    treatment_procedure=treatment_procedure,
                    wallet_balance=5000_00,
                )
            assert (
                e.value.message
                == "RTE returned oop and deductible values that don't match the tier's Employer Health Plan coverage."
            )
