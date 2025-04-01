from datetime import date

import pytest

from wallet.models.constants import (
    FamilyPlanType,
    MemberHealthPlanPatientRelationship,
    MemberHealthPlanPatientSex,
)
from wallet.pytests.wallet.utils.annual_questionnaire.conftest import (
    DP_RESPONSE_JSON_NO_DEP_EMPLOYEE_PLUS,
    DP_RESPONSE_JSON_NO_DEP_EMPLOYEE_PLUS_AMAZON,
    DP_RESPONSE_JSON_YES_SELF_INDIVIDUAL,
    DP_RESPONSE_JSON_YES_SELF_INDIVIDUAL_OHIO,
    HDHP_SURVEY_RESPONSE_JSON_ONE_HDHP,
)
from wallet.utils.annual_questionnaire.models import (
    DirectPaymentAnnualSurveyResponse,
    EmployerPlanCoverage,
    HDHPAnnualSurveyResponse,
)
from wallet.utils.annual_questionnaire.processor import (
    process_direct_payment_survey_response_json,
    process_traditional_survey_response_json,
)


@pytest.mark.parametrize(
    argnames="inp_json, is_hdhp, family_plan_type, employer_health_plan_id, insurance_id, "
    "member_health_plan_patient_relationship,first_name, last_name, dob, patient_sex",
    argvalues=[
        pytest.param(
            DP_RESPONSE_JSON_YES_SELF_INDIVIDUAL,
            True,
            FamilyPlanType.INDIVIDUAL,
            12345654321,
            "1234568",
            MemberHealthPlanPatientRelationship.CARDHOLDER,
            "Dara",
            "O'Brien",
            date(2000, 1, 1),
            MemberHealthPlanPatientSex.MALE,
        ),
        pytest.param(
            DP_RESPONSE_JSON_NO_DEP_EMPLOYEE_PLUS,
            False,
            FamilyPlanType.EMPLOYEE_PLUS,
            9009009,
            "12A34568G",
            MemberHealthPlanPatientRelationship.SPOUSE,
            "Fern",
            "Brady",
            date(1990, 2, 3),
            MemberHealthPlanPatientSex.FEMALE,
        ),
        pytest.param(
            DP_RESPONSE_JSON_YES_SELF_INDIVIDUAL_OHIO,
            True,
            FamilyPlanType.INDIVIDUAL,
            12345654321,
            "1234568",
            MemberHealthPlanPatientRelationship.CARDHOLDER,
            "Munya",
            "Chawawa",
            date(2000, 1, 1),
            MemberHealthPlanPatientSex.MALE,
        ),
        pytest.param(
            DP_RESPONSE_JSON_NO_DEP_EMPLOYEE_PLUS_AMAZON,
            False,
            FamilyPlanType.EMPLOYEE_PLUS,
            9009009,
            "12A34568G",
            MemberHealthPlanPatientRelationship.SPOUSE,
            "Sarah",
            "Millican",
            date(1990, 2, 3),
            MemberHealthPlanPatientSex.FEMALE,
        ),
    ],
)
def test_process_direct_payment_survey_response_json(
    inp_json,
    is_hdhp,
    family_plan_type,
    employer_health_plan_id,
    insurance_id,
    member_health_plan_patient_relationship,
    first_name,
    last_name,
    dob,
    patient_sex,
):
    res = process_direct_payment_survey_response_json(inp_json)
    exp = DirectPaymentAnnualSurveyResponse(
        is_hdhp=is_hdhp,
        family_plan_type=family_plan_type,
        employer_health_plan_id=employer_health_plan_id,
        subscriber_insurance_id=insurance_id,
        member_health_plan_patient_relationship=member_health_plan_patient_relationship,
        subscriber_first_name=first_name,
        subscriber_last_name=last_name,
        subscriber_date_of_birth=dob,
        patient_sex=patient_sex,
    )
    assert res == exp


def test_process_traditional_survey_response_json():
    inp_json = HDHP_SURVEY_RESPONSE_JSON_ONE_HDHP
    exp = HDHPAnnualSurveyResponse(
        self_hdhp=True,
        partner_hdhp=False,
        employer_plan_coverage=EmployerPlanCoverage.BOTH,
    )
    res = process_traditional_survey_response_json(inp_json)
    assert res == exp
