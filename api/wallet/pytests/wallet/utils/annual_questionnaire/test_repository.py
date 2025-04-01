import pytest

from storage import connection
from wallet.models.constants import QuestionnaireType
from wallet.pytests.factories import AnnualInsuranceQuestionnaireResponseFactory
from wallet.utils.annual_questionnaire.repository import (
    AnnualInsuranceResponseRepository,
)


class TestAnnualInsuranceResponseRepository:
    def test_get_response_for_wallet_id_member_id_year(
        self, questionnaire_wallet_user, repository
    ):
        exp = AnnualInsuranceQuestionnaireResponseFactory(
            wallet_id=questionnaire_wallet_user.wallet.id,
            submitting_user_id=questionnaire_wallet_user.id,
            survey_year=2024,
            user_response_json="""{"test": "response"}""",
            questionnaire_type=QuestionnaireType.DIRECT_PAYMENT_HDHP,
        )
        resp = repository.get_response_for_wallet_id_member_id_year(
            questionnaire_wallet_user.wallet.id, questionnaire_wallet_user.id, 2024
        )
        assert resp is not None
        assert resp.survey_year == exp.survey_year
        assert resp.wallet_id == questionnaire_wallet_user.wallet.id
        assert resp.submitting_user_id == questionnaire_wallet_user.id

        assert (
            repository.get_response_for_wallet_id_member_id_year(
                questionnaire_wallet_user.wallet.id + 1,
                questionnaire_wallet_user.id,
                2024,
            )
            is None
        )
        assert (
            repository.get_response_for_wallet_id_member_id_year(
                questionnaire_wallet_user.wallet.id,
                questionnaire_wallet_user.id + 2,
                2024,
            )
            is None
        )
        assert (
            repository.get_response_for_wallet_id_member_id_year(
                questionnaire_wallet_user.wallet.id, questionnaire_wallet_user.id, 2027
            )
            is None
        )

    def test_get_response_for_id(self, questionnaire_wallet_user, repository):
        exp = AnnualInsuranceQuestionnaireResponseFactory(
            wallet_id=questionnaire_wallet_user.wallet.id,
            submitting_user_id=questionnaire_wallet_user.id,
            survey_year=2024,
            user_response_json="""{"test": "response"}""",
            questionnaire_type=QuestionnaireType.DIRECT_PAYMENT_HDHP,
        )

        res = repository.get_response_for_id(exp.id)
        assert res is not None

        res = repository.get_response_for_id(exp.id + 1)
        assert res is None


@pytest.fixture
def repository():
    return AnnualInsuranceResponseRepository(connection.db.session)
