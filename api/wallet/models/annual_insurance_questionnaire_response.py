from sqlalchemy import BigInteger, Column, DateTime, Enum, Integer, String, Text

from models.base import TimeLoggedExternalUuidModelBase
from wallet.models.constants import AnnualQuestionnaireSyncStatus, QuestionnaireType


class AnnualInsuranceQuestionnaireResponse(TimeLoggedExternalUuidModelBase):
    __tablename__ = "annual_insurance_questionnaire_response"

    wallet_id = Column(
        BigInteger,
        nullable=False,
        default=None,
        doc="The wallet id linked to this response - survey is delivered per user, but stored per wallet",
    )
    questionnaire_id = Column(
        String(256),
        nullable=False,
        default=None,
        doc="The questionnaire id - maps to the questionnaire slug as provided by contentful.",
    )
    user_response_json = Column(
        Text,
        nullable=False,
        default=None,
        doc="User response to the questionnaire, stored as JSON.",
    )
    submitting_user_id = Column(
        BigInteger,
        nullable=False,
        default=None,
        doc="Id of the user that submitted the questionnaire",
    )

    sync_status = Column(
        Enum(AnnualQuestionnaireSyncStatus),
        nullable=True,
        default=None,
        doc="The status of the Alegeus synch status.",
    )

    sync_attempt_at = Column(
        DateTime,
        nullable=True,
        default=None,
        doc="The time at which we attempted to synch this record with alegeus.",
    )

    survey_year = Column(
        Integer,
        nullable=False,
        default=None,
        doc="The year for which this survey is being submitted.",
    )

    questionnaire_type = Column(
        Enum(QuestionnaireType),
        nullable=False,
        default=QuestionnaireType.LEGACY,
        doc="The type of the questionnaire.",
    )

    def __repr__(self) -> str:
        return (
            f"<AnnualInsuranceQuestionnaireResponse uuid={self.uuid} wallet_id={self.wallet_id} "
            f"questionnaire_id={self.questionnaire_id} submitting_user_id={self.submitting_user_id}>"
        )
