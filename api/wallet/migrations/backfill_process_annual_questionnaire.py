import json
from typing import List

from app import create_app
from storage.connection import db
from utils.log import logger
from wallet.models.annual_insurance_questionnaire_response import (
    AnnualInsuranceQuestionnaireResponse,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.services.annual_questionnaire_lib import _insurance_integration

log = logger(__name__)

BACKFILL_DATE = "2024-01-10"


def get_survey_response_list() -> List[AnnualInsuranceQuestionnaireResponse]:
    responses: List[AnnualInsuranceQuestionnaireResponse] = (
        db.session.query(AnnualInsuranceQuestionnaireResponse)
        .filter(
            AnnualInsuranceQuestionnaireResponse.sync_attempt_at == None,
            AnnualInsuranceQuestionnaireResponse.created_at > BACKFILL_DATE,
        )
        .all()
    )
    return responses


def queue_jobs():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    responses: List[AnnualInsuranceQuestionnaireResponse] = get_survey_response_list()
    for r in responses:
        wallet: ReimbursementWallet = db.session.query(ReimbursementWallet).get(
            r.wallet_id
        )
        answers: dict = json.loads(r.user_response_json)
        _insurance_integration(wallet=wallet, questionnaire_resp=r, answers=answers)


if __name__ == "__main__":
    with create_app().app_context():
        queue_jobs()
