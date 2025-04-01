import pytest

from payer_accumulator import helper_functions
from payer_accumulator.common import TreatmentAccumulationStatus
from payer_accumulator.helper_functions import _verify_status_to_update
from wallet.models.constants import MemberHealthPlanPatientRelationship
from wallet.models.reimbursement_wallet import MemberHealthPlan


def test_get_payer_id_success(uhc_payer):
    payer_id = helper_functions.get_payer_id(payer_name=uhc_payer.payer_name)
    assert payer_id == uhc_payer.id


@pytest.mark.parametrize(
    argnames="treatment_procedure_status,current_treatment_procedure_status,evaluates",
    argvalues=[
        (
            TreatmentAccumulationStatus.ROW_ERROR,
            TreatmentAccumulationStatus.ROW_ERROR,
            True,
        ),
        (
            TreatmentAccumulationStatus.ROW_ERROR,
            TreatmentAccumulationStatus.PROCESSED,
            True,
        ),
        (
            TreatmentAccumulationStatus.SUBMITTED,
            TreatmentAccumulationStatus.ROW_ERROR,
            False,
        ),
        (
            TreatmentAccumulationStatus.SUBMITTED,
            TreatmentAccumulationStatus.PROCESSED,
            True,
        ),
    ],
    ids=[
        "failed on failure",
        "failed on success",
        "succeeded on failure",
        "succeeded on success",
    ],
)
def test_verify_status_to_update_failure(
    treatment_procedure_status,
    current_treatment_procedure_status,
    evaluates,
):
    result = _verify_status_to_update(
        treatment_procedure_status,
        current_treatment_procedure_status,
    )

    assert result == evaluates


def test_get_patient_first_name():
    member_health_plan = MemberHealthPlan()
    member_health_plan.subscriber_first_name = "Alice"
    member_health_plan.patient_first_name = "Bob"

    member_health_plan.patient_relationship = (
        MemberHealthPlanPatientRelationship.CARDHOLDER
    )
    assert helper_functions.get_patient_first_name(member_health_plan) == "Alice"

    member_health_plan.patient_relationship = MemberHealthPlanPatientRelationship.SPOUSE
    assert helper_functions.get_patient_first_name(member_health_plan) == "Bob"


def test_get_patient_last_name():
    member_health_plan = MemberHealthPlan()
    member_health_plan.subscriber_last_name = "Johnson"
    member_health_plan.patient_last_name = "Stevens"

    member_health_plan.patient_relationship = (
        MemberHealthPlanPatientRelationship.CARDHOLDER
    )
    assert helper_functions.get_patient_last_name(member_health_plan) == "Johnson"

    member_health_plan.patient_relationship = MemberHealthPlanPatientRelationship.SPOUSE
    assert helper_functions.get_patient_last_name(member_health_plan) == "Stevens"
