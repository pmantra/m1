from unittest.mock import patch

import pytest

from cost_breakdown.constants import Tier
from cost_breakdown.errors import (
    NoIndividualDeductibleOopRemaining,
    PverifyHttpCallError,
    TieredRTEError,
)
from cost_breakdown.models.rte import EligibilityInfo, RTETransaction
from cost_breakdown.rte.rte_processor import (
    RTEProcessor,
    get_member_first_and_last_name,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from wallet.models.constants import CostSharingCategory, CostSharingType, FamilyPlanType
from wallet.models.reimbursement_organization_settings import (
    EmployerHealthPlanCostSharing,
)
from wallet.pytests.factories import EmployerHealthPlanCoverageFactory


@pytest.fixture(scope="function")
def rte_proc():
    return RTEProcessor()


@pytest.fixture(scope="function")
def rte_all_zeros():
    return RTETransaction(
        id=1,
        response={
            "individual_deductible": 0,
            "individual_deductible_remaining": 0,
            "family_deductible": 0,
            "family_deductible_remaining": 0,
            "individual_oop": 0,
            "individual_oop_remaining": 0,
            "family_oop": 0,
            "family_oop_remaining": 0,
            "coinsurance": 0.0,
            "copay": 0,
        },
    )


@pytest.fixture(scope="function")
def rte_transaction_empty():
    return RTETransaction(
        id=1,
        response={},
    )


@pytest.fixture(scope="function")
def rte_missing_deductible_ytd_spend():
    return RTETransaction(
        id=1,
        response={
            "family_deductible": None,
            "individual_oop": 300_000,
            "family_oop": 600_000,
            "individual_deductible_remaining": None,
            "individual_deductible": None,
            "coinsurance": 0,
            "copay": 4_000,
            "family_deductible_remaining": None,
            "individual_oop_remaining": 248_274,
            "family_oop_remaining": 540_242,
        },
    )


@pytest.fixture(scope="function")
def rte_missing_oop_and_deductible_ytd_spend():
    return RTETransaction(
        id=1,
        response={
            "family_deductible": None,
            "individual_oop": None,
            "family_oop": None,
            "individual_deductible_remaining": None,
            "individual_deductible": None,
            "coinsurance": 0,
            "copay": 4_000,
            "family_deductible_remaining": None,
            "individual_oop_remaining": None,
            "family_oop_remaining": None,
        },
    )


def test_default_copay_coinsurance(
    employer_health_plan_cost_sharing, rte_proc, rte_transaction_empty
):
    eligibility_info = EligibilityInfo(**rte_transaction_empty.response)
    eligibility_info = rte_proc._get_copay_coinsurance(
        eligibility_info,
        employer_health_plan_cost_sharing,
        CostSharingCategory.MEDICAL_CARE,
        TreatmentProcedureType.MEDICAL,
        tier=None,
    )
    assert eligibility_info.copay == 2000
    assert eligibility_info.coinsurance is None


def test_default_copay_coinsurance_second_tier(
    employer_health_plan_cost_sharing_tiered, rte_proc, rte_transaction_empty
):
    eligibility_info = EligibilityInfo(**rte_transaction_empty.response)
    eligibility_info = rte_proc._get_copay_coinsurance(
        eligibility_info,
        employer_health_plan_cost_sharing_tiered,
        CostSharingCategory.MEDICAL_CARE,
        TreatmentProcedureType.MEDICAL,
        tier=Tier.PREMIUM,
    )
    assert eligibility_info.copay == 2000
    assert eligibility_info.coinsurance is None
    eligibility_info = EligibilityInfo(**rte_transaction_empty.response)
    eligibility_info = rte_proc._get_copay_coinsurance(
        eligibility_info,
        employer_health_plan_cost_sharing_tiered,
        CostSharingCategory.MEDICAL_CARE,
        TreatmentProcedureType.MEDICAL,
        tier=Tier.SECONDARY,
    )
    assert eligibility_info.copay == 4000
    assert eligibility_info.coinsurance is None


def test_default_copay_coinsurance_tiered(employer_health_plan_cost_sharing, rte_proc):
    rte_transaction = RTETransaction(
        id=1,
        response={
            "copay": 1000,
        },
    )
    eligibility_info = EligibilityInfo(**rte_transaction.response)
    eligibility_info = rte_proc._get_copay_coinsurance(
        eligibility_info,
        employer_health_plan_cost_sharing,
        CostSharingCategory.MEDICAL_CARE,
        TreatmentProcedureType.MEDICAL,
        tier=Tier.PREMIUM,
    )
    assert eligibility_info.copay == 2000
    assert eligibility_info.coinsurance is None


def test_default_copay_coinsurance_with_both_copay_coinsurance_returned(
    employer_health_plan_cost_sharing, rte_proc
):
    rte_transaction = RTETransaction(
        id=1,
        response={
            "copay": 1000,
            "coinsurance": 0.2,
        },
    )
    eligibility_info = EligibilityInfo(**rte_transaction.response)
    eligibility_info = rte_proc._get_copay_coinsurance(
        eligibility_info,
        employer_health_plan_cost_sharing,
        CostSharingCategory.MEDICAL_CARE,
        TreatmentProcedureType.MEDICAL,
        tier=None,
    )
    assert eligibility_info.copay == 2000
    assert eligibility_info.coinsurance is None


def test_default_copay_coinsurance_with_pharmacy_treatment(
    employer_health_plan_cost_sharing, rte_proc
):
    rte_transaction = RTETransaction(
        id=1,
        response={
            "coinsurance": 0.2,
        },
    )
    eligibility_info = EligibilityInfo(**rte_transaction.response)
    eligibility_info = rte_proc._get_copay_coinsurance(
        eligibility_info,
        employer_health_plan_cost_sharing,
        CostSharingCategory.MEDICAL_CARE,
        TreatmentProcedureType.PHARMACY,
        tier=None,
    )
    assert eligibility_info.copay == 2000
    assert eligibility_info.coinsurance is None


def test_default_copay_coinsurance_valid_coinsurance(rte_proc):
    rte_transaction = RTETransaction(
        id=1,
        response={},
    )
    eligibility_info = EligibilityInfo(**rte_transaction.response)
    cost_sharing = [
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COINSURANCE,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            percent=0.05,
        ),
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COINSURANCE_MIN,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            absolute_amount=10000,
        ),
        EmployerHealthPlanCostSharing(
            cost_sharing_type=CostSharingType.COINSURANCE_MAX,
            cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
            absolute_amount=20000,
        ),
    ]
    eligibility_info = rte_proc._get_copay_coinsurance(
        eligibility_info,
        cost_sharing,
        CostSharingCategory.MEDICAL_CARE,
        TreatmentProcedureType.MEDICAL,
        tier=None,
    )
    assert eligibility_info.copay is None
    assert eligibility_info.coinsurance == 0.05
    assert eligibility_info.coinsurance_min == 10000
    assert eligibility_info.coinsurance_max == 20000


def test_default_deductible_oop(rte_transaction_empty, employer_health_plan, rte_proc):
    eligibility_info = rte_proc._get_deductible_oop(
        rte_transaction=rte_transaction_empty,
        employer_health_plan=employer_health_plan,
        plan_size=FamilyPlanType.FAMILY,
        tier=None,
    )
    assert eligibility_info.individual_deductible == 200_000
    assert eligibility_info.individual_oop == 400_000
    assert eligibility_info.family_deductible == 400_000
    assert eligibility_info.family_oop == 600_000


def test_default_tiered_error(rte_proc, rte_transaction_empty, employer_health_plan):
    rte_transaction_empty.response = {"individual_deductible": 200_000}
    employer_health_plan.coverage = [
        EmployerHealthPlanCoverageFactory.create(
            tier=Tier.PREMIUM.value,
            individual_deductible=150_00,
            plan_type=FamilyPlanType.FAMILY,
        )
    ]
    with pytest.raises(TieredRTEError) as e:
        rte_proc._get_deductible_oop(
            rte_transaction=rte_transaction_empty,
            employer_health_plan=employer_health_plan,
            plan_size=FamilyPlanType.FAMILY,
            tier=Tier.PREMIUM,
        )
    assert (
        str(e.value)
        == "Need Ops Action: RTE returned oop and deductible values that don't match the tier's Employer Health Plan coverage."
    )


def test_default_deductible_missing_oop_present(
    rte_missing_deductible_ytd_spend,
    employer_health_plan_no_deductible_oop_max,
    rte_proc,
):
    eligibility_info = rte_proc._get_deductible_oop(
        rte_missing_deductible_ytd_spend,
        employer_health_plan_no_deductible_oop_max,
        plan_size=FamilyPlanType.FAMILY,
        tier=None,
    )
    assert eligibility_info.individual_deductible_remaining == 0
    assert eligibility_info.individual_oop_remaining == 248_274
    assert eligibility_info.family_deductible_remaining == 0
    assert eligibility_info.family_oop_remaining == 540_242


def test_default_deductible_missing_oop_missing(
    rte_missing_oop_and_deductible_ytd_spend,
    employer_health_plan_no_deductible_oop_max,
    rte_proc,
):
    eligibility_info = rte_proc._get_deductible_oop(
        rte_missing_oop_and_deductible_ytd_spend,
        employer_health_plan_no_deductible_oop_max,
        plan_size=FamilyPlanType.FAMILY,
        tier=None,
    )
    assert eligibility_info.individual_deductible_remaining == 0
    assert eligibility_info.individual_oop_remaining == 0
    assert eligibility_info.family_deductible_remaining == 0
    assert eligibility_info.family_oop_remaining == 0


def test_max_oop_per_covered_individual_in_rte(
    employer_health_plan_no_deductible_oop_max, rte_proc
):
    rte_transaction = RTETransaction(
        id=1,
        response={
            "family_deductible": None,
            "individual_oop": None,
            "family_oop": None,
            "individual_deductible_remaining": None,
            "individual_deductible": None,
            "coinsurance": 0,
            "copay": 0,
            "family_deductible_remaining": None,
            "individual_oop_remaining": None,
            "family_oop_remaining": None,
        },
    )
    ehp = employer_health_plan_no_deductible_oop_max
    ehp.max_oop_per_covered_individual = 100
    eligibility_info = rte_proc._get_deductible_oop(
        rte_transaction,
        ehp,
        plan_size=FamilyPlanType.INDIVIDUAL,
        tier=None,
    )
    assert eligibility_info.max_oop_per_covered_individual == 100


def test_get_rte_empty_rte_response(
    rte_transaction_empty,
    rte_proc,
    treatment_procedure,
    member_health_plan,
):
    with patch(
        "cost_breakdown.rte.pverify_api.PverifyAPI.get_real_time_eligibility_data",
        return_value=rte_transaction_empty,
    ), pytest.raises(NoIndividualDeductibleOopRemaining):
        rte_proc.get_rte(
            treatment_procedure,
            member_health_plan,
            CostSharingCategory.MEDICAL_CARE,
            tier=None,
        )


def test_get_rte_all_zeros_default(
    rte_all_zeros, member_health_plan, rte_proc, treatment_procedure
):
    with patch(
        "cost_breakdown.rte.pverify_api.PverifyAPI.get_real_time_eligibility_data",
        return_value=rte_all_zeros,
    ):
        eligibility_info, rte_id = rte_proc.get_rte(
            treatment_procedure,
            member_health_plan,
            CostSharingCategory.MEDICAL_CARE,
            tier=None,
        )
        assert eligibility_info.individual_deductible == 200_000
        assert eligibility_info.individual_deductible_remaining == 0
        assert eligibility_info.individual_oop == 400_000
        assert eligibility_info.individual_oop_remaining == 0
        assert eligibility_info.family_deductible == 400_000
        assert eligibility_info.family_deductible_remaining == 0
        assert eligibility_info.family_oop == 600_000
        assert eligibility_info.family_oop_remaining == 0
        assert eligibility_info.copay == 0
        assert eligibility_info.coinsurance == 0.0
        assert rte_id == 1


def test_get_rte_no_defaulting(
    rte_transaction_with_oop_remaining,
    rte_proc,
    treatment_procedure,
    member_health_plan,
):
    with patch(
        "cost_breakdown.rte.pverify_api.PverifyAPI.get_real_time_eligibility_data",
        return_value=rte_transaction_with_oop_remaining,
    ):
        eligibility_info, rte_id = rte_proc.get_rte(
            treatment_procedure,
            member_health_plan,
            CostSharingCategory.MEDICAL_CARE,
            tier=None,
        )
        assert eligibility_info.family_deductible == 150_000
        assert eligibility_info.individual_oop == 150_000
        assert eligibility_info.family_oop == 300_000
        assert eligibility_info.individual_deductible_remaining == 0
        assert eligibility_info.individual_deductible == 150_000
        assert eligibility_info.coinsurance == 0.2
        assert eligibility_info.family_deductible_remaining == 10_000
        assert eligibility_info.individual_oop_remaining == 10_000
        assert eligibility_info.family_oop_remaining == 229_309
        assert rte_id == 1


def test_get_rte_failure(rte_proc, treatment_procedure, member_health_plan):
    with patch(
        "cost_breakdown.rte.pverify_api.PverifyAPI.get_real_time_eligibility_data",
        side_effect=PverifyHttpCallError(message="Test Failure", http_status=500),
    ), pytest.raises(PverifyHttpCallError) as e:
        rte_proc.get_rte(
            treatment_procedure,
            member_health_plan,
            CostSharingCategory.MEDICAL_CARE,
            tier=None,
        )
    assert (
        str(e.value.get_internal_message())
        == "The request to Pverify failed with an unexpected error. Please reach out to @payments-platform-oncall to see if Pverify is down."
    )


@pytest.mark.parametrize(
    argnames="member_health_plan_fixture,expected_first_name,expected_last_name",
    argvalues=[
        ("member_health_plan_dependent", "lucia", "paul"),
        ("member_health_plan_no_name", "Donna", "Williams"),
        (
            "member_health_plan_dependent_no_name",
            "Donna",
            "Williams",
        ),
    ],
)
def test_get_patient_first_and_last_name_self(
    treatment_procedure,
    member_health_plan_fixture,
    expected_first_name,
    expected_last_name,
    request,
):
    member_health_plan = request.getfixturevalue(member_health_plan_fixture)
    first_name, last_name = get_member_first_and_last_name(
        user_id=treatment_procedure.member_id,
        member_health_plan=member_health_plan,
    )
    assert first_name == expected_first_name
    assert last_name == expected_last_name
