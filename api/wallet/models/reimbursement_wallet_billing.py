from sqlalchemy import BigInteger, Column, Enum, ForeignKey, SmallInteger, String
from sqlalchemy.orm import relationship

from models.base import TimeLoggedSnowflakeModelBase
from wallet.models.constants import BillingConsentAction


class ReimbursementWalletBillingConsent(TimeLoggedSnowflakeModelBase):
    __tablename__ = "reimbursement_wallet_billing_consent"

    reimbursement_wallet_id = Column(
        BigInteger,
        ForeignKey("reimbursement_wallet.id"),
        unique=False,
        nullable=False,
    )
    reimbursement_wallet = relationship(
        "ReimbursementWallet",
    )

    version = Column(SmallInteger, nullable=False)

    action = Column(
        Enum(BillingConsentAction), nullable=False, default=BillingConsentAction.CONSENT
    )

    acting_user_id = Column(BigInteger, nullable=True, default=None)

    ip_address = Column(String(39), nullable=True, default=None)

    def __repr__(self) -> str:
        return f"<ReimbursementWalletBillingConsent={self.id} ReimbursementWallet={self.reimbursement_wallet_id} Action={self.action}>"
