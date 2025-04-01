from sqlalchemy import BigInteger, Column, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from models.base import TimeLoggedSnowflakeModelBase
from wallet.models.constants import WalletUserStatus, WalletUserType


class ReimbursementWalletUsers(TimeLoggedSnowflakeModelBase):
    __tablename__ = "reimbursement_wallet_users"

    reimbursement_wallet_id = Column(
        BigInteger,
        ForeignKey("reimbursement_wallet.id"),
        nullable=False,
        doc="Id of the reimbursement_wallet that this user is accessing.",
    )

    user_id = Column(
        Integer,
        ForeignKey("user.id"),
        unique=False,
        nullable=False,
    )

    member = relationship("User", backref="reimbursement_wallet_users")
    wallet = relationship("ReimbursementWallet")

    type = Column(
        Enum(WalletUserType),
        nullable=False,
        doc="Describes relationship between the Maven Clinic plan and this wallet user.",
    )

    status = Column(
        Enum(WalletUserStatus),
        nullable=False,
        doc="Describes the status of this user's access request to join the wallet.",
    )

    channel_id = Column(
        Integer,
        ForeignKey("channel.id"),
        nullable=True,
        doc="Associated Maven Wallet channel",
    )

    zendesk_ticket_id = Column(
        BigInteger,
        nullable=True,
        doc="Zendesk ticket id for the associated Maven Wallet channel",
    )

    alegeus_dependent_id = Column(String(30))

    def __repr__(self) -> str:
        return f"<ReimbursementWalletUser id={self.id}, reimbursement_wallet_id={self.reimbursement_wallet_id}"

    __str__ = __repr__
