from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from models.base import TimeLoggedSnowflakeModelBase


class ReimbursementWalletBlacklist(TimeLoggedSnowflakeModelBase):
    __tablename__ = "reimbursement_wallet_eligibility_blacklist"

    reimbursement_wallet_id = Column(
        BigInteger, ForeignKey("reimbursement_wallet.id"), nullable=False
    )

    creator_id = Column(Integer, ForeignKey("user.id"), nullable=False)

    reason = Column(
        String(1024), nullable=True, doc="Reason for blacklisting this user"
    )
    deleted_at = Column(
        DateTime,
        nullable=True,
        doc="When this blacklist entry was soft deleted, if applicable",
    )
    creator = relationship("User")
    reimbursement_wallet = relationship("ReimbursementWallet")

    @property
    def is_active(self) -> bool:
        """Returns True if this blacklist entry is currently active (not deleted)."""
        return self.deleted_at is None

    def __repr__(self) -> str:
        """String representation of the blacklist entry."""
        status = "active" if self.is_active else "deleted"
        return f"<ReimbursementWalletEligibilityBlacklist {self.id} [{status}] for wallet {self.reimbursement_wallet_id}>"
