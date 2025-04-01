from sqlalchemy import BigInteger, Column, ForeignKey, Integer

from models.base import TimeLoggedModelBase


class TreatmentProcedureRecordedAnswerSet(TimeLoggedModelBase):
    __tablename__ = "treatment_procedure_recorded_answer_set"

    id = Column(BigInteger, primary_key=True)
    treatment_procedure_id: int = Column(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[int]", variable has type "int")
        BigInteger,
        ForeignKey("treatment_procedure.id"),
        nullable=False,
    )
    recorded_answer_set_id: int = Column(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[int]", variable has type "int")
        BigInteger,
        ForeignKey("recorded_answer_set.id"),
        nullable=False,
    )
    questionnaire_id: int = Column(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[int]", variable has type "int")
        BigInteger,
        ForeignKey("questionnaire.id"),
        nullable=False,
    )
    user_id: int = Column(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[int]", variable has type "int")
        Integer,
        ForeignKey("user.id"),
        nullable=False,
    )
    fertility_clinic_id: int = Column(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[int]", variable has type "int")
        BigInteger,
        ForeignKey("fertility_clinic.id"),
        nullable=False,
    )
