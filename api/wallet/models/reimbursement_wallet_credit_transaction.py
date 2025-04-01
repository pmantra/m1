import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from models.base import ModelBase
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_wallet_global_procedures import (
    ReimbursementWalletGlobalProcedures,
)


class ReimbursementCycleMemberCreditTransaction(ModelBase):
    __tablename__ = "reimbursement_cycle_member_credit_transactions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    reimbursement_cycle_credits_id = Column(
        BigInteger,
        ForeignKey("reimbursement_cycle_credits.id"),
        nullable=False,
    )

    reimbursement_request_id = Column(
        BigInteger,
        ForeignKey("reimbursement_request.id"),
        nullable=True,
    )

    reimbursement_wallet_global_procedures_id = Column(
        BigInteger,
        ForeignKey("reimbursement_wallet_global_procedures.id"),
        nullable=True,
    )

    amount = Column(Integer, nullable=False)

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.datetime.now())

    reimbursement_cycle_credits = relationship("ReimbursementCycleCredits")
    reimbursement_request = relationship(ReimbursementRequest)
    reimbursement_wallet_global_procedure = relationship(
        ReimbursementWalletGlobalProcedures
    )

    def __repr__(self) -> str:
        return f"<ReimbursementCycleMemberCreditTransaction, created_at={self.created_at}, amount={self.amount}"
