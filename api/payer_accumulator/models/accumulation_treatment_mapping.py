from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    event,
)
from sqlalchemy.orm import relationship

from models.base import TimeLoggedModelBase
from payer_accumulator.common import TreatmentAccumulationStatus


class AccumulationTreatmentMapping(TimeLoggedModelBase):
    __tablename__ = "accumulation_treatment_mapping"

    id = Column(BigInteger, primary_key=True)
    accumulation_unique_id = Column(String(128), nullable=True, unique=True)
    accumulation_transaction_id = Column(String(255), nullable=True)
    treatment_procedure_uuid = Column(String(36), nullable=True)
    reimbursement_request_id = Column(BigInteger(), nullable=True)
    treatment_accumulation_status = Column(
        Enum(TreatmentAccumulationStatus), nullable=True
    )
    deductible = Column(
        Integer, nullable=True, doc="Amount applied to deductible in cents"
    )
    oop_applied = Column(Integer, nullable=True, doc="Amount applied to oop in cents")
    hra_applied = Column(Integer, nullable=True, doc="Amount applied to hra in cents")
    # NOTE: The FK definition here is for admin. It does not (currently) correspond to a FK in the table definition.
    report_id = Column(
        BigInteger, ForeignKey("payer_accumulation_reports.id"), nullable=True
    )
    completed_at = Column(DateTime, nullable=True)
    payer_id = Column(BigInteger, nullable=False)

    report = relationship(
        "PayerAccumulationReports", back_populates="treatment_mappings"
    )
    is_refund = Column(Boolean, nullable=False, default=False)
    response_code = Column(String(255), nullable=True)
    row_error_reason = Column(String(1024), nullable=True)


# TODO: Enforce the following validation in the DB via CHECK constraint when in mysql >8.0.16 or postgres
@event.listens_for(AccumulationTreatmentMapping, "before_insert")
def mapping_before_insert(mapper, connection, target) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if (
        target.treatment_procedure_uuid is None
        and target.reimbursement_request_id is None
    ):
        raise ValueError(
            "AccumulationTreatmentMapping may not have a null reimbursement_request_id "
            "and a null treatment_procedure_uuid."
        )


@event.listens_for(AccumulationTreatmentMapping, "before_update")
def mapping_before_update(mapper, connection, target):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if (
        target.treatment_procedure_uuid is None
        and target.reimbursement_request_id is None
    ):
        raise ValueError(
            "AccumulationTreatmentMapping may not have a null reimbursement_request_id "
            "and a null treatment_procedure_uuid."
        )
