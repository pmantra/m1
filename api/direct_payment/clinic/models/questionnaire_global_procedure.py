from sqlalchemy import BigInteger, Column, ForeignKey, String
from sqlalchemy.orm import relationship

from models.base import ModelBase


class QuestionnaireGlobalProcedure(ModelBase):
    __tablename__ = "questionnaire_global_procedure"

    id = Column(BigInteger, primary_key=True)
    questionnaire_id = Column(
        BigInteger, ForeignKey("questionnaire.id"), nullable=False
    )
    global_procedure_id = Column(String(36), nullable=False)

    questionnaire = relationship("Questionnaire")

    def __repr__(self) -> str:
        return f"Link questionnaire {self.questionnaire_id} to global procedure {self.global_procedure_id}"
