from sqlalchemy import BigInteger, Column, ForeignKey, Integer, SmallInteger, String
from sqlalchemy.orm import backref, relationship

from models.base import TimeLoggedModelBase
from utils.log import logger

log = logger(__name__)


class ReimbursementWalletBenefit(TimeLoggedModelBase):
    __tablename__ = "reimbursement_wallet_benefit"

    incremental_id = Column(Integer, primary_key=True)
    rand = Column(SmallInteger)
    checksum = Column(SmallInteger)

    maven_benefit_id = Column(
        String(),
        unique=True,
        nullable=True,
        doc="Member-facing Benefit ID for billing.",
    )

    reimbursement_wallet_id = Column(
        BigInteger,
        ForeignKey("reimbursement_wallet.id"),
        unique=True,
        nullable=True,
        doc="Reimbursement Wallet associated with this Benefit ID.",
    )

    reimbursement_wallet = relationship(
        "ReimbursementWallet",
        backref=backref("reimbursement_wallet_benefit", uselist=False),
    )

    def __repr__(self) -> str:
        return f"<ReimbursementWalletBenefit={self.maven_benefit_id} ReimbursementWallet={self.reimbursement_wallet_id}>"
