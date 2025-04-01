from __future__ import annotations

import json
import re
from typing import Any

from dateutil.parser import isoparse

from common import stats
from wallet.models.constants import (
    FamilyPlanType,
    MemberHealthPlanPatientRelationship,
    MemberHealthPlanPatientSex,
)
from wallet.utils.annual_questionnaire.models import (
    DirectPaymentAnnualSurveyResponse,
    DirectPaymentSurveyFields,
    EmployerPlanCoverage,
    HDHPAnnualSurveyResponse,
    TraditionalWalletFieldKeys,
)


def process_traditional_survey_response_json(
    input_json: str,
) -> HDHPAnnualSurveyResponse:
    data: dict[str, Any] = json.loads(input_json)
    for field in TraditionalWalletFieldKeys:
        if data.get(field) is None:
            raise ValueError(f"Field {field} cannot be null or blank")
        if isinstance(data[field], str) and not data[field].strip():
            raise ValueError(f"Field {field} cannot be empty")

    try:
        return HDHPAnnualSurveyResponse(
            self_hdhp=data[TraditionalWalletFieldKeys.SELF_HDHP].lower() == "yes",
            partner_hdhp=data[TraditionalWalletFieldKeys.PARTNER_HDHP].lower() == "yes",
            employer_plan_coverage=EmployerPlanCoverage(
                data[TraditionalWalletFieldKeys.EMPLOYER_PLAN].lower()
            ),
        )
    except Exception as e:
        raise ValueError(f"Failed to process survey data: {str(e)}")


def process_direct_payment_survey_response_json(
    input_json: str,
) -> DirectPaymentAnnualSurveyResponse:
    data: dict[str, Any] = json.loads(input_json)

    for field in DirectPaymentSurveyFields:
        if field in data:
            if data[field] is None:
                raise ValueError(f"Field {field} cannot be null.")
            if isinstance(data[field], str) and not data[field].strip():
                raise ValueError(f"Field {field} cannot be empty.")

    try:
        raw_subscriber_insurance_id = str(
            data.get(DirectPaymentSurveyFields.INSURANCE_ID)
            or data.get(DirectPaymentSurveyFields.INSURANCE_ID_AMAZON)
        )
        subscriber_insurance_id = re.sub(
            r"[^a-zA-Z0-9]", "", raw_subscriber_insurance_id
        )
        if not subscriber_insurance_id:
            raise ValueError("After clean-up, the subscriber_insurance_id was empty.")

        stats.increment(
            metric_name="wallet.utils.annual_questionnaire.processor.process_direct_payment_survey_response_json_input_subscriber_insurance_id_mutated",
            pod_name=stats.PodNames.BENEFITS_EXP,
            tags=[f"modified:{raw_subscriber_insurance_id != subscriber_insurance_id}"],
        )

        return DirectPaymentAnnualSurveyResponse(
            is_hdhp=data[DirectPaymentSurveyFields.IS_HDHP].lower() == "yes",
            family_plan_type=FamilyPlanType(
                data.get(DirectPaymentSurveyFields.COVERED_MEMBERS)
                or data.get(DirectPaymentSurveyFields.COVERED_MEMBERS_AMAZON)
                or data.get(DirectPaymentSurveyFields.COVERED_MEMBERS_OHIO)
            ),
            employer_health_plan_id=int(
                data[DirectPaymentSurveyFields.PAYER_PLAN_NAME]
            ),
            subscriber_insurance_id=subscriber_insurance_id.strip(),
            member_health_plan_patient_relationship=MemberHealthPlanPatientRelationship(
                data[DirectPaymentSurveyFields.MEMBER_HEALTH_PLAN_PATIENT_RELATIONSHIP]
            ),
            subscriber_first_name=str(
                data[DirectPaymentSurveyFields.FIRST_NAME]
            ).strip(),
            subscriber_last_name=str(data[DirectPaymentSurveyFields.LAST_NAME]).strip(),
            subscriber_date_of_birth=isoparse(
                data[DirectPaymentSurveyFields.DOB].replace("Z", "+00:00")
            ).date(),
            patient_sex=MemberHealthPlanPatientSex(
                data.get(DirectPaymentSurveyFields.PATIENT_SEX)
            ),
        )
    except Exception as e:
        raise ValueError(f"Failed to process survey data: {str(e)}")
