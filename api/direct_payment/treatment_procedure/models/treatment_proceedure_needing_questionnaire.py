from sqlalchemy import BigInteger, Column, ForeignKey, Integer

from models.base import TimeLoggedModelBase


class TreatmentProceduresNeedingQuestionnaires(TimeLoggedModelBase):
    __tablename__ = "treatment_procedures_needing_questionnaires"

    id = Column(
        Integer,
        nullable=False,
        primary_key=True,
    )
    treatment_procedure_id = Column(
        BigInteger, ForeignKey("treatment_procedure.id"), nullable=False
    )
