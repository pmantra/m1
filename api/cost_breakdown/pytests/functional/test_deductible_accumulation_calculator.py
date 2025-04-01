import math

import pytest

from cost_breakdown.deductible_accumulation_calculator import (
    DeductibleAccumulationCalculator,
)
from cost_breakdown.models.rte import EligibilityInfo
from wallet.models.constants import FamilyPlanType
from wallet.models.reimbursement_organization_settings import EmployerHealthPlan
from wallet.models.reimbursement_wallet import MemberHealthPlan
from wallet.pytests.factories import EmployerHealthPlanCoverageFactory


@pytest.mark.parametrize(
    argnames="treatment_cost,deductible_remaining,oop_remaining,copay,coinsurance,coinsurance_min,coinsurance_max,expected_charge,expected_coinsurance,expected_copay",
    # fmt: off
    argvalues=[
        (50, 30, 70, 50, None, None, None, 50, 0, 50),
        (100, 30, 70, 50, None, None, None, 70, 0, 50),
        (100, 30, 70, 20, None, None, None, 50, 0, 20),
        (100, 30, 70, None, 0.4, None, None, 58, 28, 0),
        (100, 30, 70, None, 0.4, 40, 60, 70, 40, 0),
        (100, 30, 70, None, 0.4, 20, 40, 58, 28, 0),
        (100, 30, 70, None, 0.4, 0, 20, 50, 20, 0),
        (100, 30, 70, None, 0.4, 40, None, 70, 40, 0),
        (100, 30, 70, None, 0.4, None, 20, 50, 20, 0),
    ],
    # fmt: on
    ids=[
        "treatment cost less than oop remaining and deductible remaining plus copay",
        "oop remaining > deductible remaining but < deductible remaining + copay",
        "copay and deductible remaining less than oop remaining and treatment cost",
        "coinsurance without min/max",
        "coinsurance with min/max and coinsurance < min",
        "coinsurance with min/max and min < coinsurance < max",
        "coinsurance with min/max and coinsurance > max",
        "coinsurance with min only",
        "coinsurance with max only",
    ],
)
def test_calc_base_member_charge(
    treatment_cost,
    deductible_remaining,
    oop_remaining,
    copay,
    coinsurance,
    coinsurance_max,
    coinsurance_min,
    expected_charge,
    expected_coinsurance,
    expected_copay,
):
    calculated_member_charge = (
        DeductibleAccumulationCalculator._calc_base_member_charge(
            treatment_cost=treatment_cost,
            deductible_remaining=deductible_remaining,
            oop_remaining=oop_remaining,
            copay=copay,
            coinsurance=coinsurance,
            coinsurance_max=coinsurance_max,
            coinsurance_min=coinsurance_min,
        )
    )
    assert expected_charge == calculated_member_charge.member_responsibility
    assert expected_coinsurance == calculated_member_charge.coinsurance
    assert expected_copay == calculated_member_charge.copay


@pytest.mark.parametrize(
    argnames="is_unlimited,"
    "treatment_cost,"
    "deductible_remaining,"
    "oop_remaining,"
    "copay,"
    "coinsurance,"
    "wallet_balance, "
    "expected_charge,"
    "expected_copay,"
    "expected_coinsurance,"
    "expected_overage,",
    # fmt: off
    argvalues=[
        (False, 900_000, 299_011, 499_011, None, 0.3, 2_000_000, 479_308, 0, 180_297, 0),
        (False, 50, 30, 70, 50, None, 80, 50, 50, 0, 0),  # base member charge in (see case above) is 50
        (False, 100, 30, 70, 50, None, 150, 70, 50, 0, 0),  # base member charge in (see case above) is 70
        (False, 100, 30, 70, 20, None, 10, 90, 20, 0, 40),  # base member charge in (see case above) is 50
        (True, 100, 30, 70, 20, None, math.inf, 50, 20, 0, 0),  # No overage with unlimited benefit
    ],
    # fmt: on
    ids=[
        "limited benefit - member pays coinsurance and wallet covers rest",
        "limited benefit - member pays treatment cost",
        "limited benefit - member pays oop remaining and wallet covers rest",
        "limited benefit - member pays copay and deductible remaining with overage after wallet exhausted",
        "unlimited benefit - member pays copay and deductible remaining",
    ],
)
def test_calc_total_member_charge(
    is_unlimited,
    treatment_cost,
    deductible_remaining,
    oop_remaining,
    copay,
    coinsurance,
    wallet_balance,
    expected_charge,
    expected_copay,
    expected_coinsurance,
    expected_overage,
):
    total_calculated = (
        DeductibleAccumulationCalculator()._calculate_member_total_charge(
            treatment_cost=treatment_cost,
            deductible_remaining=deductible_remaining,
            oop_remaining=oop_remaining,
            copay=copay,
            coinsurance=coinsurance,
            is_unlimited=is_unlimited,
            wallet_balance=wallet_balance,
            coinsurance_min=None,
            coinsurance_max=None,
        )
    )
    assert expected_charge == total_calculated.member_responsibility
    assert expected_copay == total_calculated.copay
    assert expected_coinsurance == expected_coinsurance
    assert expected_overage == total_calculated.overage_amount


@pytest.mark.parametrize(
    argnames="is_individual,is_embedded,individual_remaining, family_remaining, expected_choice",
    # fmt: off
    argvalues=[
        (True, True, 500, 200, 500),
        (True, False, 500, 200, 500),
        (False, True, 500, 200, 200),
        (False, True, 200, 500, 200),
        (False, False, 200, 500, 500),
    ],
    # fmt: on
    ids=[
        "embedded individual picks individual amount",
        "non-embedded individual picks individual amount",
        "embedded family picks lesser of individual or family amount where family is less",
        "embedded family picks lesser of individual or family amount where individual is less",
        "non-embedded family picks family",
    ],
)
def test_choose_remaining(
    is_individual,
    is_embedded,
    individual_remaining,
    family_remaining,
    expected_choice,
):
    remaining_amount = DeductibleAccumulationCalculator._choose_remaining(
        is_individual=is_individual,
        is_embedded=is_embedded,
        individual_remaining=individual_remaining,
        family_remaining=family_remaining,
    )
    assert expected_choice == remaining_amount


@pytest.mark.parametrize(
    argnames="is_individual,"
    "is_embedded,"
    "individual_remaining,"
    "family_remaining, "
    "member_charge,"
    "expected_apply,"
    "expected_individual,"
    "expected_family",
    # fmt: off
    argvalues=[
        (True, True, 1000, 2000, 500, 500, 500, None),
        (True, False, 1000, 2000, 500, 500, 500, None),
        (True, True, 500, 2000, 1000, 500, 0, None),
        (True, False, 500, 2000, 1000, 500, 0, None),
        (False, True, 500, 2000, 1000, 500, 0, 1500),
        (False, True, 1000, 2000, 500, 500, 500, 1500),
        (False, False, None, 2000, 500, 500, None, 1500),
        (False, False, 500, 2000, 2500, 2000, None, 0),
    ],
    # fmt: on
    ids=[
        "embedded individual contributes member charge to individual value only",
        "non-embedded individual contributes member charge to individual value only",
        "embedded individual contributes individual remaining to individual value only",
        "non-embedded individual contributes individual remaining to individual value only",
        "embedded family member contributes individual remaining to family remaining",
        "embedded family member contributes member charge to individual and family remaining",
        "non-embedded family member contributes member charge to family remaining",
        "non-embedded family member contributes member charge greater than remaining to family remaining",
    ],
)
def test_apply_charge_to_individual_family_limit(
    is_individual,
    is_embedded,
    individual_remaining,
    family_remaining,
    member_charge,
    expected_apply,
    expected_individual,
    expected_family,
):
    (
        apply,
        individual_remaining,
        family_remaining,
    ) = DeductibleAccumulationCalculator._apply_charge_to_individual_family_limit(
        is_individual=is_individual,
        is_embedded=is_embedded,
        individual_remaining=individual_remaining,
        family_remaining=family_remaining,
        member_charge=member_charge,
    )
    assert expected_apply == apply
    assert expected_individual == individual_remaining
    assert expected_family == family_remaining


# Test cases line up with scenarios outlined in spreadsheet:
# https://docs.google.com/spreadsheets/d/1w6RxSVAeqfoMJbD-VAXgTYO2FZC0bCFA8K1b2MGNxGQ/edit#gid=0


@pytest.mark.parametrize(
    argnames="is_unlimited,"
    "plan_type,"
    "is_deductible_embedded,"
    "is_oop_embedded,"
    "member_charge,"
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
    "wallet_balance,"
    "ignore_deductible",
    # fmt: off
    argvalues=[
        (False, FamilyPlanType.INDIVIDUAL, False, False, 500, 1000, None, 2000, None, 500, None, 1500, None, 500, 500, 500, 5000, False),
        (False, FamilyPlanType.INDIVIDUAL, False, False, 540, 500, None, 1500, None, 0, None, 960, None, 500, 540, 2000, 5000, False),
        (False, FamilyPlanType.INDIVIDUAL, False, False, 40, 0, None, 960, None, 0, None, 920, None, 0, 40, 100, 3540, False),
        (False, FamilyPlanType.FAMILY, False, False, 500, 1000, 2500, 2000, 5000, None, 2000, None, 4500, 500, 500, 500, 5000, False),
        (False, FamilyPlanType.FAMILY, False, False, 2000, 500, 2000, 1500, 4500, None, 0, None, 2500, 2000, 2000, 2000, 5000, False),
        (False, FamilyPlanType.FAMILY, False, False, 40, 0, 0, 0, 2500, None, 0, None, 2460, 0, 40, 100, 5000, False),
        (False, FamilyPlanType.FAMILY, True, True, 500, 1000, 2500, 2000, 5000, 500, 2000, 1500, 4500, 500, 500, 500, 5000, False),
        (False, FamilyPlanType.FAMILY, True, True, 540, 500, 2000, 1500, 4500, 0, 1500, 960, 3960, 500, 540, 2000, 5000, False),
        (False, FamilyPlanType.FAMILY, True, True, 40, 0, 1500, 960, 3960, 0, 1500, 920, 3920, 0, 40, 100, 3540, False),
        (False, FamilyPlanType.FAMILY, True, True, 1000, 1000, 1500, 2000, 3920, 0, 500, 1000, 2920, 1000, 1000, 1000, 2580, False),
        (False, FamilyPlanType.FAMILY, True, True, 40, 0, 500, 1000, 2920, 0, 500, 960, 2880, 0, 40, 600, 2580, False),
        (False, FamilyPlanType.FAMILY, True, True, 540, 1000, 500, 2000, 2880, 500, 0, 1460, 2340, 500, 540, 600, 2020, False),
        (False, FamilyPlanType.FAMILY, True, True, 40, 1000, 0, 2000, 2340, 1000, 0, 1960, 2300, 0, 40, 100, 1960, False),
        (False, FamilyPlanType.FAMILY, True, False, 1040, 1000, 2500, 2000, 5000, 0, 1500, None, 3960, 1000, 1040, 5000, 10_000, False),
        (False, FamilyPlanType.FAMILY, True, False, 40, 0, 1500, 960, 3960, 0, 1500, None, 3920, 0, 40, 1000, 6040, False),
        (False, FamilyPlanType.FAMILY, True, False, 1040, 1000, 1500, 2000, 3920, 0, 500, None, 2880, 1000, 1040, 3000, 5080, False),
        (False, FamilyPlanType.FAMILY, True, False, 540, 1000, 500, 2000, 2880, 500, 0, None, 2340, 500, 540, 2100, 3120, False),
        (False, FamilyPlanType.FAMILY, True, False, 40, 1000, 0, 2000, 2340, 1000, 0, None, 2300, 0, 40, 100, 1560, False),
        (False, FamilyPlanType.FAMILY, False, True, 0, 500, 0, 0, 3000, None, 0, 0, 3000, 0, 0, 1000, 10_000, False),
        (False, FamilyPlanType.FAMILY, False, True, 40, 1000, 0, 2000, 3000, None, 0, 1960, 2960, 0, 40, 1000, 9000, False),
        (False, FamilyPlanType.FAMILY, False, True, 40, 1000, 0, 1960, 2960, None, 0, 1920, 2920, 0, 40, 600, 8040, False),
        (False, FamilyPlanType.FAMILY, False, True, 2520, 1000, 0, 2000, 2920, None, 0, 0, 920, 0, 2000, 10_000, 7480, False),
        (False, FamilyPlanType.FAMILY, False, True, 920, 1000, 0, 2000, 920, None, 0, 1080, 0, 0, 920, 920, 0, False),
        (False, FamilyPlanType.FAMILY, False, True, 100, 1000, 0, 1080, 0, None, 0, 1080, 0, 0, 0, 100, 0, False),
        (False, FamilyPlanType.FAMILY, False, True, 540, 1000, 500, 2000, 3000, None, 0, 1460, 2460, 500, 540, 2000, 9000, False),
        (False, FamilyPlanType.INDIVIDUAL, True, True, 500, 1000, None, 2000, None, 500, None, 1500, None, 500, 500, 500, 5000, False),
        (False, FamilyPlanType.INDIVIDUAL, True, True, 540, 500, None, 1500, None, 0, None, 960, None, 500, 540, 2000, 5000, False),
        (False, FamilyPlanType.INDIVIDUAL, True, True, 40, 0, None, 960, None, 0, None, 920, None, 0, 40, 100, 3540, False),
        (False, FamilyPlanType.INDIVIDUAL, True, False, 500, 1000, None, 2000, None, 500, None, 1500, None, 500, 500, 500, 5000, False),
        (False, FamilyPlanType.INDIVIDUAL, True, False, 540, 500, None, 1500, None, 0, None, 960, None, 500, 540, 2000, 5000, False),
        (False, FamilyPlanType.INDIVIDUAL, True, False, 40, 0, None, 960, None, 0, None, 920, None, 0, 40, 100, 3540, False),
        (False, FamilyPlanType.INDIVIDUAL, False, True, 500, 1000, None, 2000, None, 500, None, 1500, None, 500, 500, 500, 5000, False),
        (False, FamilyPlanType.INDIVIDUAL, False, True, 540, 500, None, 1500, None, 0, None, 960, None, 500, 540, 2000, 5000, False),
        (False, FamilyPlanType.INDIVIDUAL, False, True, 40, 0, None, 960, None, 0, None, 920, None, 0, 40, 100, 3540, False),
        (False, FamilyPlanType.INDIVIDUAL, False, False, 40, 1000, None, 2000, None, 1000, None, 1960, None, 0, 40, 500, 5000, True),
        (False, FamilyPlanType.FAMILY, False, False, 40, None, 1000, None, 2000, None, 1000, None, 1960, 0, 40, 500, 5000, True),
        # Tests unlimited benefits
        (True, FamilyPlanType.FAMILY, False, True, 40, 1000, 0, 2000, 2990, None, 0, 1960, 2950, 0, 40, 10_000, math.inf, False),
        (True, FamilyPlanType.FAMILY, False, True, 40, 1000, 0, 2000, 920, None, 0, 1960, 880, 0, 40, 920, math.inf, False),
        (True, FamilyPlanType.FAMILY, False, True, 0, 1000, 0, 1080, 0, None, 0, 1080, 0, 0, 0, 100, math.inf, False),
    ],
    # fmt: on
    ids=[
        "limited benefits - non-embedded individual first treatment",
        "limited benefits - non-embedded individual second treatment",
        "limited benefits - non-embedded individual third treatment",
        "limited benefits - non-embedded family first treatment",
        "limited benefits - non-embedded family second treatment",
        "limited benefits - non-embedded family third treatment",
        "limited benefits - fully embedded family member 1 treatment 1",
        "limited benefits - fully embedded family member 1 treatment 2",
        "limited benefits - fully embedded family member 1 treatment 3",
        "limited benefits - fully embedded family member 2 treatment 1",
        "limited benefits - fully embedded family member 2 treatment 2",
        "limited benefits - fully embedded family member 3 treatment 1",
        "limited benefits - fully embedded family member 4 treatment 1",
        "limited benefits - embedded deductible family member 1 treatment 1",
        "limited benefits - embedded deductible family member 1 treatment 2",
        "limited benefits - embedded deductible family member 2 treatment 1",
        "limited benefits - embedded deductible family member 3 treatment 1",
        "limited benefits - embedded deductible family member 4 treatment 1",
        "limited benefits - embedded oop family 1 member 1 treatment 3",
        "limited benefits - embedded oop family 1 member 2 treatment 1",
        "limited benefits - embedded oop family 1 member 2 treatment 2",
        "limited benefits - embedded oop family 1 member 3 treatment 1",
        "limited benefits - embedded oop family 1 member 4 treatment 1",
        "limited benefits - embedded oop family 1 member 4 treatment 2",
        "limited benefits - embedded oop family 2 member 2 treatment 1",
        "limited benefits - fully embedded individual first treatment",
        "limited benefits - fully embedded individual second treatment",
        "limited benefits - fully embedded individual third treatment",
        "limited benefits - embedded deductible individual first treatment",
        "limited benefits - embedded deductible individual second treatment",
        "limited benefits - embedded deductible individual third treatment",
        "limited benefits - embedded oop individual first treatment",
        "limited benefits - embedded oop individual second treatment",
        "limited benefits - embedded oop individual third treatment",
        "limited benefits - deductible ignored set to True for individual plan",
        "limited benefits - deductible ignored set to True for family plan",
        "unlimited benefits - embedded oop family 1 member 3 treatment 1",
        "unlimited benefits - embedded oop family 1 member 4 treatment 1",
        "unlimited benefits - embedded oop family 1 member 4 treatment 2",
    ],
)
def test_calculate_accumulation_values_with_copay(
    is_unlimited,
    plan_type,
    is_deductible_embedded,
    is_oop_embedded,
    member_charge,
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
    ignore_deductible,
):
    member_health_plan = MemberHealthPlan(
        plan_type=plan_type,
    )
    eligibility_info = EligibilityInfo(
        copay=40,
        individual_deductible_remaining=individual_deductible_remaining,
        family_deductible_remaining=family_deductible_remaining,
        individual_oop_remaining=individual_oop_remaining,
        family_oop_remaining=family_oop_remaining,
        is_deductible_embedded=is_deductible_embedded,
        is_oop_embedded=is_oop_embedded,
        ignore_deductible=ignore_deductible,
    )
    member_charge_object = (
        DeductibleAccumulationCalculator().calculate_member_cost_breakdown(
            treatment_cost=treatment_cost,
            is_unlimited=is_unlimited,
            wallet_balance=wallet_balance,
            member_health_plan=member_health_plan,
            eligibility_info=eligibility_info,
        )
    )
    assert member_charge_object.member_responsibility == member_charge
    accumulator_results = (
        DeductibleAccumulationCalculator().calculate_accumulation_values(
            member_health_plan=member_health_plan,
            eligibility_info=eligibility_info,
            member_charge=member_charge,
        )
    )
    assert (
        expected_individual_deductible_remaining
        == accumulator_results.individual_deductible_remaining
    )
    assert (
        expected_individual_oop_remaining
        == accumulator_results.individual_oop_remaining
    )
    assert (
        expected_family_deductible_remaining
        == accumulator_results.family_deductible_remaining
    )
    assert expected_family_oop_remaining == accumulator_results.family_oop_remaining
    assert expected_deductible_apply == accumulator_results.deductible_apply
    assert expected_oop_apply == accumulator_results.oop_apply


@pytest.mark.parametrize("max_oop_per_individual", [150, 149])
def test_calculate_accumulation_values_with_max_oop_per_covered_individual(
    max_oop_per_individual,
):
    member_health_plan = MemberHealthPlan(
        plan_type=FamilyPlanType.FAMILY,
        employer_health_plan=EmployerHealthPlan(
            coverage=[
                EmployerHealthPlanCoverageFactory(
                    max_oop_per_covered_individual=150,
                    plan_type=FamilyPlanType.FAMILY,
                )
            ]
        ),
    )
    eligibility_info = EligibilityInfo(
        copay=50,
        family_deductible_remaining=140,
        family_oop_remaining=500,
        max_oop_per_covered_individual=max_oop_per_individual,
        is_oop_embedded=False,
        is_deductible_embedded=False,
    )
    # of the two above, the oop remaining should be 2000
    member_charge_object = (
        DeductibleAccumulationCalculator().calculate_member_cost_breakdown(
            treatment_cost=250,
            wallet_balance=250,
            member_health_plan=member_health_plan,
            eligibility_info=eligibility_info,
            is_unlimited=False,
        )
    )
    # base_member_charge.member_responsibility = min(
    #   max_oop_per_covered_individual, family_oop_remaining, treatment_cost
    # )  # should be 150
    # cost_without_deductible = treatment_cost - base_member_charge.member_responsibility
    # fair_member_charge = min(member_charge, oop_remaining, treatment_cost)
    # with no cost remainder
    assert member_charge_object.member_responsibility == max_oop_per_individual
