from __future__ import annotations

from storage.connection import db
from wallet.models.annual_insurance_questionnaire_response import (
    AnnualInsuranceQuestionnaireResponse,
)


class AnnualInsuranceResponseRepository:
    __slots__ = ["_session"]

    def __init__(self, session: db.session):  # type: ignore[name-defined] # Name "db.Session" is not defined
        self._session = session

    def get_response_for_id(
        self, id_: int
    ) -> AnnualInsuranceQuestionnaireResponse | None:
        return (
            self._session.query(AnnualInsuranceQuestionnaireResponse)
            .filter(AnnualInsuranceQuestionnaireResponse.id == id_)
            .one_or_none()
        )

    def get_response_for_wallet_id_member_id_year(
        self, wallet_id: int, user_id: int, plan_year: int
    ) -> AnnualInsuranceQuestionnaireResponse | None:
        return (
            self._session.query(AnnualInsuranceQuestionnaireResponse)
            .filter(
                AnnualInsuranceQuestionnaireResponse.wallet_id == wallet_id,
                AnnualInsuranceQuestionnaireResponse.survey_year == plan_year,
                AnnualInsuranceQuestionnaireResponse.submitting_user_id == user_id,
            )
            .one_or_none()
        )
