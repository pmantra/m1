import enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Enum,
    ForeignKey,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from models.base import TimeLoggedModelBase, TimeLoggedSnowflakeModelBase


class ReimbursementWalletDashboardType(enum.Enum):
    NONE = "NONE"
    PENDING = "PENDING"
    DISQUALIFIED = "DISQUALIFIED"


class ReimbursementWalletDashboard(TimeLoggedSnowflakeModelBase):
    __tablename__ = "reimbursement_wallet_dashboard"

    type = Column(
        Enum(ReimbursementWalletDashboardType),
        nullable=False,
    )
    cards = relationship("ReimbursementWalletDashboardCards")

    def __repr__(self) -> str:
        return f"<ReimbursementWalletDashboard {self.id} [{self.type}]>"


class ReimbursementWalletDashboardCard(TimeLoggedSnowflakeModelBase):
    __tablename__ = "reimbursement_wallet_dashboard_card"

    title = Column(String())
    body = Column(Text())
    img_url = Column(String())
    link_text = Column(String())
    link_url = Column(String())
    require_debit_eligible = Column(Boolean(), nullable=False)

    def __repr__(self) -> str:
        return f"<ReimbursementWalletDashboardCard {self.id} [{self.title}]>"


class ReimbursementWalletDashboardCards(TimeLoggedModelBase):
    __tablename__ = "reimbursement_wallet_dashboard_cards"

    reimbursement_wallet_dashboard_id = Column(
        BigInteger,
        ForeignKey("reimbursement_wallet_dashboard.id"),
        primary_key=True,
    )
    dashboard = relationship("ReimbursementWalletDashboard")

    reimbursement_wallet_dashboard_card_id = Column(
        BigInteger,
        ForeignKey("reimbursement_wallet_dashboard_card.id"),
        primary_key=True,
    )
    card = relationship("ReimbursementWalletDashboardCard")

    order = Column(SmallInteger, nullable=False)
