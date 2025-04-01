from __future__ import annotations

import enum
from typing import List

from sqlalchemy import BigInteger, Column, Date, Enum, String
from sqlalchemy.orm import relationship

from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
)
from models.base import TimeLoggedModelBase
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.models.payer_list import Payer
from wallet.models.reimbursement import ReimbursementRequest


class PayerReportStatus(enum.Enum):
    NEW = "NEW"
    SUBMITTED = "SUBMITTED"
    FAILURE = "FAILURE"


class PayerAccumulationReports(TimeLoggedModelBase):
    __tablename__ = "payer_accumulation_reports"

    id = Column("id", BigInteger, primary_key=True)
    payer_id = Column(BigInteger, nullable=False)
    filename = Column(String(255), nullable=False)
    report_date = Column(Date, nullable=False)
    status = Column(Enum(PayerReportStatus, nullable=False))

    treatment_mappings = relationship(
        "AccumulationTreatmentMapping", back_populates="report"
    )

    def treatment_procedures(self) -> List[TreatmentProcedure]:
        return (
            TreatmentProcedure.query.join(
                AccumulationTreatmentMapping,
                AccumulationTreatmentMapping.treatment_procedure_uuid
                == TreatmentProcedure.uuid,
            )
            .filter(AccumulationTreatmentMapping.report_id == self.id)
            .all()
        )

    def reimbursement_requests(self) -> List[ReimbursementRequest]:
        return (
            ReimbursementRequest.query.join(
                AccumulationTreatmentMapping,
                AccumulationTreatmentMapping.reimbursement_request_id
                == ReimbursementRequest.id,
            )
            .filter(AccumulationTreatmentMapping.report_id == self.id)
            .all()
        )

    def file_path(self) -> str:
        date_prefix = self.created_at.strftime("%Y/%m/%d")
        return f"{self.payer_name.value}/{date_prefix}/{self.filename}"

    @property
    def payer_name(self) -> Payer:
        payer_name = (
            Payer.query.with_entities(Payer.payer_name)
            .filter(Payer.id == self.payer_id)
            .one()
        )
        return payer_name[0]
