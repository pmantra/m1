from sqlalchemy import CHAR, Column, Date, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from models.base import TimeLoggedSnowflakeModelBase
from utils.braze_events import debit_card_lost_stolen, debit_card_temp_inactive
from utils.data import TinyIntEnum
from utils.log import logger
from wallet.models.constants import AlegeusCardStatus, CardStatus, CardStatusReason

log = logger(__name__)


class ReimbursementWalletDebitCard(TimeLoggedSnowflakeModelBase):
    __tablename__ = "reimbursement_wallet_debit_card"

    reimbursement_wallet_id = Column(
        Integer, ForeignKey("reimbursement_wallet.id"), nullable=False
    )

    reimbursement_wallet = relationship(
        "ReimbursementWallet",
        foreign_keys=reimbursement_wallet_id,
        backref="debit_cards",
    )

    card_proxy_number = Column(String, nullable=False)
    card_last_4_digits = Column(CHAR(4), nullable=False)
    card_status = Column(Enum(CardStatus), nullable=False, default=CardStatus.NEW)
    card_status_reason = Column(
        TinyIntEnum(CardStatusReason, unsigned=True),
        nullable=False,
        default=CardStatusReason.NONE,
    )

    created_date = Column(Date, default=None)
    issued_date = Column(Date, default=None)
    shipped_date = Column(Date, default=None)
    shipping_tracking_number = Column(String)

    def __repr__(self) -> str:
        return f"<ReimbursementWalletDebitCard {self.id} [x{self.card_last_4_digits}] [{self.card_status}]>"

    def update_status(self, card_status, card_status_reason=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self.card_status != card_status:
            self.card_status = card_status
            if card_status == CardStatus.INACTIVE:
                debit_card_temp_inactive(self)

        if card_status_reason and self.card_status_reason != card_status_reason:
            self.card_status_reason = card_status_reason
            if card_status_reason == CardStatusReason.LOST_STOLEN:
                debit_card_lost_stolen(self)


def map_alegeus_card_status_codes(alegeus_card_status_code):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if alegeus_card_status_code == AlegeusCardStatus.NEW:
        return CardStatus.NEW, CardStatusReason.NONE

    if alegeus_card_status_code == AlegeusCardStatus.ACTIVE:
        return CardStatus.ACTIVE, CardStatusReason.NONE

    if alegeus_card_status_code == AlegeusCardStatus.LOST_STOLEN:
        return CardStatus.CLOSED, CardStatusReason.LOST_STOLEN

    # These next two are likely to be expanded upon using the Alegeus card status reason code

    if alegeus_card_status_code == AlegeusCardStatus.TEMP_INACTIVE:
        return CardStatus.INACTIVE, CardStatusReason.NONE

    if alegeus_card_status_code == AlegeusCardStatus.PERM_INACTIVE:
        return CardStatus.CLOSED, CardStatusReason.NONE

    # The above code checks all known Alegeus status codes. If there is no match,
    # assume there is a problem and log in a monitorable way.
    log.warning("Unknown Code", AlegeusCardStatusCode=alegeus_card_status_code)
    return CardStatus.INACTIVE, CardStatusReason.NONE
