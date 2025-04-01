from __future__ import annotations

from sqlalchemy import BigInteger, Column, Enum, Integer, String

from models.base import TimeLoggedModelBase
from wallet.models.constants import ConsentOperation


class WalletUserConsent(TimeLoggedModelBase):
    __tablename__ = "wallet_user_consent"

    id: int = Column(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[int]", variable has type "int")
        Integer,
        nullable=False,
        primary_key=True,
        autoincrement=True,
    )

    consent_giver_id: int | None = Column(Integer, nullable=True)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[Optional[int]]", variable has type "Optional[int]")
    """
    user.id of the individual giving consent. Must be nullable in case
    we receive a data deletion request from the individual
    """

    consent_recipient_id: int | None = Column(Integer, nullable=True, default=None)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[Optional[int]]", variable has type "Optional[int]")
    """
    user.id of the individual giving consent. When the recipient is not
    currently a member, we write it as None and populate the recipient_email
    in order to make a contemperaneous record. When the recipient
    decides to accept the invitation, then we backfill the consent_recipient_id
    with the user_id of the recipient, who had to make a Maven account in order
    to accept the invitation.
    """

    recipient_email: str | None = Column(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[Optional[str]]", variable has type "Optional[str]")
        String(120),
        nullable=True,
    )
    """Will be set to NULL if we receive a data deletion request from the recipient."""

    reimbursement_wallet_id: int = Column(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[int]", variable has type "int")
        BigInteger,
        nullable=False,
    )
    """Refers to reimbursement_wallet.id, no foreign key constraint."""

    operation: ConsentOperation = Column(Enum(ConsentOperation), nullable=False)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[str]", variable has type "ConsentOperation")
    """Give or revoke consent."""

    def __repr__(self) -> str:
        return f"<{self.operation.value} from {self.consent_giver_id} to {self.recipient_email}>"

    __str__ = __repr__
