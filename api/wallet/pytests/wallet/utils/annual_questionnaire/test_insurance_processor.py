from __future__ import annotations

import json
from datetime import date, datetime, timezone
from unittest import mock

import pytest

from authn.models.user import User
from pytests.factories import HealthProfileFactory
from wallet.models.annual_insurance_questionnaire_response import (
    AnnualInsuranceQuestionnaireResponse,
)
from wallet.models.constants import AnnualQuestionnaireSyncStatus, QuestionnaireType
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.pytests.factories import (
    AnnualInsuranceQuestionnaireResponseFactory,
    EmployerHealthPlanFactory,
    MemberHealthPlanFactory,
)
from wallet.pytests.wallet.utils.annual_questionnaire.conftest import (
    DP_RESPONSE_DICT_NO_DEP_EMPLOYEE_PLUS,
    DP_RESPONSE_DICT_NO_DEP_EMPLOYEE_PLUS_AMAZON,
    DP_RESPONSE_DICT_YES_SELF_INDIVIDUAL,
    DP_RESPONSE_DICT_YES_SELF_INDIVIDUAL_NOT_HDHP,
    DP_RESPONSE_DICT_YES_SELF_INDIVIDUAL_OHIO,
    DP_RESPONSE_JSON_NO_DEP_EMPLOYEE_PLUS,
    DP_RESPONSE_JSON_NO_DEP_EMPLOYEE_PLUS_AMAZON,
    DP_RESPONSE_JSON_YES_SELF_INDIVIDUAL,
    DP_RESPONSE_JSON_YES_SELF_INDIVIDUAL_BAD_MHP,
    DP_RESPONSE_JSON_YES_SELF_INDIVIDUAL_NOT_HDHP,
    DP_RESPONSE_JSON_YES_SELF_INDIVIDUAL_OHIO,
)
from wallet.repository.health_plan import HEALTH_PLAN_YOY_FLAG, NEW_BEHAVIOR
from wallet.utils.annual_questionnaire.insurance_processor import (
    process_direct_payment_insurance_response,
)
from wallet.utils.annual_questionnaire.models import DirectPaymentSurveyFields
from wallet.utils.annual_questionnaire.processor import (
    process_direct_payment_survey_response_json,
)


@pytest.mark.parametrize(
    "inp_effective_date, inp_patient_dob, inp_patient_health_profile_json, inp_dp_response,inp_ehp_end_date,"
    "inp_ehp_start_date, subscriber_record_start_and_end, exp_plan_start_at, exp_plan_end_at, exp_is_subscriber, "
    "exp_patient_dob, exp_subscriber_info",
    [
        pytest.param(
            date(2024, 12, 31),  # inp_effective_date
            None,  # inp_patient_dob
            {},  # inp_patient_health_profile_json
            DP_RESPONSE_JSON_YES_SELF_INDIVIDUAL,  # inp_dp_response
            date(2025, 12, 31),  # inp_ehp_end_date
            date(2025, 1, 1),  # inp_ehp_start_date
            [],  # subscriber_record_start_and_end
            datetime(2025, 1, 1, 0, 0, 0, 0),  # exp_plan_start_at
            datetime(2025, 12, 31, 23, 59, 59, 0),  # exp_plan_end_at
            True,  # exp_is_subscriber
            None,  # exp_patient_dob
            DP_RESPONSE_DICT_YES_SELF_INDIVIDUAL,  # exp_subscriber_info
            id="1. Subscriber response - plan fully in the future. Unable to pull DOB",
        ),
        pytest.param(
            date(2025, 1, 31),  # inp_effective_date
            date(1995, 6, 15),  # inp_patient_dob
            {},  # inp_patient_health_profile_json
            DP_RESPONSE_JSON_NO_DEP_EMPLOYEE_PLUS,  # inp_dp_response
            date(2025, 12, 31),  # inp_ehp_end_date
            date(2025, 1, 1),  # inp_ehp_start_date
            [],  # subscriber_record_start_and_end
            datetime(2025, 1, 1, 0, 0, 0, 0),  # exp_plan_start_at
            datetime(2025, 12, 31, 23, 59, 59, 0),  # exp_plan_end_at
            False,  # exp_is_subscriber
            date(1995, 6, 15),  # exp_patient_dob
            DP_RESPONSE_DICT_NO_DEP_EMPLOYEE_PLUS,  # exp_subscriber_info
            id="2. Dependent Response, start date in the past, end date in the future. Bounded by ehp start date",
        ),
        pytest.param(
            date(2025, 10, 31),  # inp_effective_date
            date(2000, 1, 1),  # inp_patient_dob
            {},  # inp_patient_health_profile_json
            DP_RESPONSE_JSON_YES_SELF_INDIVIDUAL_NOT_HDHP,  # inp_dp_response
            date(2025, 12, 31),  # inp_ehp_end_date
            date(2025, 1, 1),  # inp_ehp_start_date
            [],  # subscriber_record_start_and_end
            datetime(2025, 5, 4, 0, 0, 0, 0),  # exp_plan_start_at
            datetime(2025, 12, 31, 23, 59, 59, 0),  # exp_plan_end_at
            True,  # exp_is_subscriber
            date(2000, 1, 1),  # exp_patient_dob
            DP_RESPONSE_DICT_YES_SELF_INDIVIDUAL_NOT_HDHP,  # exp_subscriber_info
            id="3. Subscriber response - start date in the past, end date in the future. Bounded by MAX_BACKDATE_DAYS",
        ),
        pytest.param(
            date(2026, 1, 31),  # inp_effective_date
            date(2000, 1, 1),  # inp_patient_dob
            {},  # inp_patient_health_profile_json
            DP_RESPONSE_JSON_YES_SELF_INDIVIDUAL_NOT_HDHP,  # inp_dp_response
            date(2025, 12, 31),  # inp_ehp_end_date
            date(2025, 1, 1),  # inp_ehp_start_date
            [],  # subscriber_record_start_and_end
            datetime(2025, 8, 4, 0, 0, 0, 0),  # exp_plan_start_at
            datetime(2025, 12, 31, 23, 59, 59, 0),  # exp_plan_end_at
            True,  # exp_is_subscriber
            date(2000, 1, 1),  # exp_patient_dob
            DP_RESPONSE_DICT_YES_SELF_INDIVIDUAL_NOT_HDHP,  # exp_subscriber_info
            id="4. Subscriber response - start date in the past, end date in the past. Bounded by MAX_BACKDATE_DAYS.",
        ),
        pytest.param(
            date(2026, 7, 31),  # inp_effective_date
            None,  # inp_patient_dob
            {
                "birthday": "2001-01-01",
            },  # inp_patient_health_profile_json
            DP_RESPONSE_JSON_YES_SELF_INDIVIDUAL_NOT_HDHP,  # inp_dp_response
            date(2025, 12, 31),  # inp_ehp_end_date
            date(2025, 1, 1),  # inp_ehp_start_date
            [],  # subscriber_record_start_and_end
            datetime(2025, 12, 31, 0, 0, 0, 0),  # exp_plan_start_at
            datetime(2025, 12, 31, 23, 59, 59, 0),  # exp_plan_end_at
            True,  # exp_is_subscriber
            date(2001, 1, 1),  # exp_patient_dob
            DP_RESPONSE_DICT_YES_SELF_INDIVIDUAL_NOT_HDHP,  # exp_subscriber_info
            id="5. Subscriber response - start date in the past, end date in the past. Bounded by ehp start date.",
        ),
        pytest.param(
            date(2025, 9, 30),  # inp_effective_date
            None,  # inp_patient_dob
            {"birthday": "2001-01-01"},  # inp_patient_health_profile_json
            DP_RESPONSE_JSON_NO_DEP_EMPLOYEE_PLUS,  # inp_dp_response
            date(2025, 12, 31),  # inp_ehp_end_date
            date(2025, 1, 1),  # inp_ehp_start_date
            [
                (
                    datetime(2025, 8, 30, 0, 0, 0, 0),
                    datetime(2025, 12, 31, 23, 59, 59, 0),
                )
            ],  # subscriber_record_start_and_end
            datetime(2025, 8, 30, 0, 0, 0, 0),  # exp_plan_start_at
            datetime(2025, 12, 31, 23, 59, 59, 0),  # exp_plan_end_at
            False,  # exp_is_subscriber
            date(2001, 1, 1),  # exp_patient_dob
            DP_RESPONSE_DICT_NO_DEP_EMPLOYEE_PLUS,  # exp_subscriber_info
            id="6. Dependent response - only start date in the past, subscriber record exists and  bounds new member.",
        ),
        pytest.param(
            date(2025, 9, 30),  # inp_effective_date
            date(2001, 1, 1),  # inp_patient_dob
            {"birthday": ""},  # inp_patient_health_profile_json
            DP_RESPONSE_JSON_NO_DEP_EMPLOYEE_PLUS,  # inp_dp_response
            date(2025, 12, 31),  # inp_ehp_end_date
            date(2025, 1, 1),  # inp_ehp_start_date
            [
                (
                    datetime(2025, 1, 1, 0, 0, 0, 0),
                    datetime(2025, 12, 31, 23, 59, 59, 0),
                )
            ],  # subscriber_record_start_and_end
            datetime(2025, 4, 3, 0, 0, 0, 0),  # exp_plan_start_at
            datetime(2025, 12, 31, 23, 59, 59, 0),  # exp_plan_end_at
            False,  # exp_is_subscriber
            date(2001, 1, 1),  # exp_patient_dob
            DP_RESPONSE_DICT_NO_DEP_EMPLOYEE_PLUS,  # exp_subscriber_info
            id="7. Dependent response - only start date in the past, subs rec exists but doesn't  bound new member.",
        ),
        pytest.param(
            date(2025, 9, 30),  # inp_effective_date
            date(2001, 1, 1),  # inp_patient_dob
            {"birthday": "2001-10-01"},  # inp_patient_health_profile_json
            DP_RESPONSE_JSON_NO_DEP_EMPLOYEE_PLUS,  # inp_dp_response
            date(2025, 12, 31),  # inp_ehp_end_date
            date(2025, 1, 1),  # inp_ehp_start_date
            [
                (
                    datetime(2025, 8, 30, 0, 0, 0, 0),
                    datetime(2025, 12, 31, 23, 59, 59, 0),
                ),
                (
                    datetime(2025, 7, 30, 0, 0, 0, 0),
                    datetime(2025, 12, 31, 23, 59, 59, 0),
                ),
            ],  # subscriber_record_start_and_end
            datetime(2025, 4, 3, 0, 0),  # exp_plan_start_at
            datetime(2025, 12, 31, 23, 59, 59, 0),  # exp_plan_end_at
            False,  # exp_is_subscriber
            date(2001, 1, 1),  # exp_patient_dob
            DP_RESPONSE_DICT_NO_DEP_EMPLOYEE_PLUS,  # exp_subscriber_info
            id="8. Dependent response - only start date in the past, multiple subs so ignored & don't bound new memb.",
        ),
        pytest.param(
            date(2025, 1, 31),  # inp_effective_date
            date(1995, 6, 15),  # inp_patient_dob
            {},  # inp_patient_health_profile_json
            DP_RESPONSE_JSON_NO_DEP_EMPLOYEE_PLUS_AMAZON,  # inp_dp_response
            date(2025, 12, 31),  # inp_ehp_end_date
            date(2025, 1, 1),  # inp_ehp_start_date
            [],  # subscriber_record_start_and_end
            datetime(2025, 1, 1, 0, 0, 0, 0),  # exp_plan_start_at
            datetime(2025, 12, 31, 23, 59, 59, 0),  # exp_plan_end_at
            False,  # exp_is_subscriber
            date(1995, 6, 15),  # exp_patient_dob
            DP_RESPONSE_DICT_NO_DEP_EMPLOYEE_PLUS_AMAZON,  # exp_subscriber_info
            id="9. Amazon Dependent Response, start date in the past, end dt in the future. Bounded by ehp start date",
        ),
        pytest.param(
            date(2024, 12, 31),  # inp_effective_date
            None,  # inp_patient_dob
            {},  # inp_patient_health_profile_json
            DP_RESPONSE_JSON_YES_SELF_INDIVIDUAL_OHIO,  # inp_dp_response
            date(2025, 12, 31),  # inp_ehp_end_date
            date(2025, 1, 1),  # inp_ehp_start_date
            [],  # subscriber_record_start_and_end
            datetime(2025, 1, 1, 0, 0, 0, 0),  # exp_plan_start_at
            datetime(2025, 12, 31, 23, 59, 59, 0),  # exp_plan_end_at
            True,  # exp_is_subscriber
            None,  # exp_patient_dob
            DP_RESPONSE_DICT_YES_SELF_INDIVIDUAL_OHIO,  # exp_subscriber_info
            id="10. Ohio Subscriber response - plan fully in the future. Unable to pull DOB",
        ),
    ],
)
def test_process_direct_payment_insurance_response(
    qualified_direct_payment_enabled_wallet: ReimbursementWallet,
    set_feature_flags,
    inp_effective_date: date,
    inp_patient_dob: date,
    inp_patient_health_profile_json: dict,
    inp_dp_response: dict,
    inp_ehp_end_date: date,
    inp_ehp_start_date: date,
    subscriber_record_start_and_end: list,
    exp_plan_start_at: datetime,
    exp_plan_end_at: datetime,
    exp_is_subscriber: bool,
    exp_patient_dob: date,
    exp_subscriber_info: dict,
):
    qdpe_wallet = qualified_direct_payment_enabled_wallet
    user = User.query.get(qdpe_wallet.user_id)
    HealthProfileFactory(
        user=user, date_of_birth=inp_patient_dob, json=inp_patient_health_profile_json
    )

    inp_resp = AnnualInsuranceQuestionnaireResponseFactory(
        wallet_id=qdpe_wallet.id,
        questionnaire_id=1436415308316467216,
        user_response_json=inp_dp_response,
        submitting_user_id=qdpe_wallet.user_id,
        sync_status=None,
        sync_attempt_at=None,
        survey_year=2025,
        questionnaire_type=QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE,
    )
    resp = process_direct_payment_survey_response_json(inp_resp.user_response_json)

    ehp = EmployerHealthPlanFactory.create(
        start_date=inp_ehp_start_date,
        end_date=inp_ehp_end_date,
        id=resp.employer_health_plan_id,
        reimbursement_org_settings_id=qdpe_wallet.reimbursement_organization_settings_id,
    )
    for s_and_e in subscriber_record_start_and_end:
        _ = MemberHealthPlanFactory.create(
            employer_health_plan=ehp,
            subscriber_insurance_id=resp.subscriber_insurance_id,
            plan_start_at=s_and_e[0],
            plan_end_at=s_and_e[1],
        )

    ehp.reimbursement_organization_settings = (
        qdpe_wallet.reimbursement_organization_settings
    )

    with mock.patch("braze.client.BrazeClient.track_users") as mock_track_users:
        res = process_direct_payment_insurance_response(inp_resp, inp_effective_date)
    assert res
    assert res.plan_start_at == exp_plan_start_at
    assert res.plan_end_at == exp_plan_end_at
    assert res.patient_date_of_birth == exp_patient_dob
    assert res.patient_first_name == user.first_name
    assert res.patient_last_name == user.last_name
    assert res.is_subscriber == exp_is_subscriber
    assert res.patient_sex == exp_subscriber_info[DirectPaymentSurveyFields.PATIENT_SEX]
    assert (
        res.subscriber_first_name
        == exp_subscriber_info[DirectPaymentSurveyFields.FIRST_NAME]
    )
    assert (
        res.subscriber_last_name
        == exp_subscriber_info[DirectPaymentSurveyFields.LAST_NAME]
    )
    assert res.subscriber_insurance_id == (
        exp_subscriber_info.get(DirectPaymentSurveyFields.INSURANCE_ID)
        or exp_subscriber_info.get(DirectPaymentSurveyFields.INSURANCE_ID_AMAZON)
    )
    assert res.subscriber_date_of_birth == date.fromisoformat(
        exp_subscriber_info[DirectPaymentSurveyFields.DOB]
    )
    assert res.patient_sex == exp_subscriber_info[DirectPaymentSurveyFields.PATIENT_SEX]
    updated_resp = AnnualInsuranceQuestionnaireResponse.query.get(inp_resp.id)
    assert (
        updated_resp.sync_status
        == AnnualQuestionnaireSyncStatus.MEMBER_HEALTH_PLAN_CREATION_SUCCESS
    )

    # test for user tracking
    assert mock_track_users.called
    res_user_att = mock_track_users.call_args.kwargs["user_attributes"][0]
    exp_user = User.query.get(qdpe_wallet.user_id)
    assert res_user_att.external_id == exp_user.esp_id
    assert len(res_user_att.attributes) == 1
    assert res_user_att.attributes["wallet_added_health_insurance_datetime"] is not None


def test_process_direct_payment_insurance_response_trim(
    qualified_direct_payment_enabled_wallet,
):
    inp_dp_response = DP_RESPONSE_DICT_YES_SELF_INDIVIDUAL.copy()
    inp_dp_response[DirectPaymentSurveyFields.INSURANCE_ID] = (
        " " + inp_dp_response[DirectPaymentSurveyFields.INSURANCE_ID] + " "
    )
    inp_dp_response[DirectPaymentSurveyFields.FIRST_NAME] = (
        " " + inp_dp_response[DirectPaymentSurveyFields.FIRST_NAME]
    )
    inp_dp_response[DirectPaymentSurveyFields.LAST_NAME] = (
        inp_dp_response[DirectPaymentSurveyFields.LAST_NAME] + "  "
    )

    user_response_json = json.dumps(inp_dp_response)
    resp = process_direct_payment_survey_response_json(user_response_json)

    assert (
        resp.subscriber_insurance_id
        == DP_RESPONSE_DICT_YES_SELF_INDIVIDUAL[DirectPaymentSurveyFields.INSURANCE_ID]
    )
    assert (
        resp.subscriber_first_name
        == DP_RESPONSE_DICT_YES_SELF_INDIVIDUAL[DirectPaymentSurveyFields.FIRST_NAME]
    )
    assert (
        resp.subscriber_last_name
        == DP_RESPONSE_DICT_YES_SELF_INDIVIDUAL[DirectPaymentSurveyFields.LAST_NAME]
    )


def test_process_direct_payment_insurance_response_no_ehp(
    qualified_direct_payment_enabled_wallet: ReimbursementWallet, set_feature_flags
):
    qdpe_wallet = qualified_direct_payment_enabled_wallet
    inp_resp = AnnualInsuranceQuestionnaireResponse(
        wallet_id=qdpe_wallet.id,
        questionnaire_id=1436415308316467216,
        user_response_json=DP_RESPONSE_JSON_NO_DEP_EMPLOYEE_PLUS,
        submitting_user_id=qdpe_wallet.user_id,
        sync_status=None,
        sync_attempt_at=None,
        survey_year=2025,
        questionnaire_type=QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE,
    )

    res = process_direct_payment_insurance_response(
        inp_resp, datetime.now(timezone.utc).date()
    )
    assert res is None


def test_process_direct_payment_insurance_response_bad_ehp(
    qualified_direct_payment_enabled_wallet: ReimbursementWallet, set_feature_flags
):
    qdpe_wallet = qualified_direct_payment_enabled_wallet
    inp_resp = AnnualInsuranceQuestionnaireResponse(
        wallet_id=qdpe_wallet.id,
        questionnaire_id=1436415308316467216,
        user_response_json=DP_RESPONSE_JSON_NO_DEP_EMPLOYEE_PLUS,
        submitting_user_id=qdpe_wallet.user_id,
        sync_status=None,
        sync_attempt_at=None,
        survey_year=2025,
        questionnaire_type=QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE,
    )

    _ = EmployerHealthPlanFactory.create(
        start_date=date(2025, 12, 31),
        end_date=date(2025, 1, 1),
        id=process_direct_payment_survey_response_json(
            inp_resp.user_response_json
        ).employer_health_plan_id,
        reimbursement_org_settings_id=qdpe_wallet.reimbursement_organization_settings_id,
    )
    with mock.patch("braze.client.BrazeClient.track_users") as mock_track_users:
        res = process_direct_payment_insurance_response(
            inp_resp, datetime.now(timezone.utc).date()
        )
    assert res is None
    assert mock_track_users.called is False


def test_process_direct_payment_insurance_response_bad_input(
    qualified_direct_payment_enabled_wallet: ReimbursementWallet, set_feature_flags
):
    qdpe_wallet = qualified_direct_payment_enabled_wallet
    inp_resp = AnnualInsuranceQuestionnaireResponse(
        wallet_id=qdpe_wallet.id,
        questionnaire_id=1436415308316467216,
        user_response_json=DP_RESPONSE_JSON_YES_SELF_INDIVIDUAL_BAD_MHP,
        submitting_user_id=qdpe_wallet.user_id,
        sync_status=None,
        sync_attempt_at=None,
        survey_year=2025,
        questionnaire_type=QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE,
    )

    _ = EmployerHealthPlanFactory.create(
        start_date=date(2025, 12, 31),
        end_date=date(2025, 1, 1),
        id=100,
        reimbursement_org_settings_id=qdpe_wallet.reimbursement_organization_settings_id,
    )
    with mock.patch("braze.client.BrazeClient.track_users") as mock_track_users:
        res = process_direct_payment_insurance_response(
            inp_resp, datetime.now(timezone.utc).date()
        )
    assert res is None
    assert mock_track_users.called is False


@pytest.fixture(scope="function")
def set_feature_flags(ff_test_data):
    ff_test_data.update(
        ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(NEW_BEHAVIOR)
    )
