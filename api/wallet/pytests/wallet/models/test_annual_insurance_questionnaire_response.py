import datetime

import pytest

from wallet.models.annual_insurance_questionnaire_response import (
    AnnualInsuranceQuestionnaireResponse,
)
from wallet.models.constants import AnnualQuestionnaireSyncStatus


@pytest.mark.parametrize(
    argnames="wallet_id, questionnaire_id, user_response_json, submitting_user_id, sync_status, sync_attempt_at",
    argvalues=(
        [1, "q1", '{"key1": "value1"}', 11, None, None],
        [
            2,
            "q2",
            '{"key2": "value2"}',
            11,
            AnnualQuestionnaireSyncStatus.ALEGEUS_SUCCESS,
            datetime.datetime.now(),
        ],
    ),
)
def test_annual_insurance_questionnaire_response(
    wallet_id,
    questionnaire_id,
    user_response_json,
    submitting_user_id,
    sync_status,
    sync_attempt_at,
):
    res = AnnualInsuranceQuestionnaireResponse(
        wallet_id=wallet_id,
        questionnaire_id=questionnaire_id,
        user_response_json=user_response_json,
        submitting_user_id=submitting_user_id,
        sync_status=sync_status,
        sync_attempt_at=sync_attempt_at,
    )
    assert res.wallet_id == wallet_id
    assert res.questionnaire_id == questionnaire_id
    assert res.user_response_json == user_response_json
    assert res.submitting_user_id == submitting_user_id
    assert res.sync_status == sync_status
    assert res.sync_attempt_at == sync_attempt_at
