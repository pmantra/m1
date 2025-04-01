from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import NCHAR, BigInteger, Boolean, Column, Integer, String
from sqlalchemy.dialects import postgresql

from models.base import TimeLoggedModelBase

EXPIRATION_TIME = timedelta(days=3)


class WalletUserInvite(TimeLoggedModelBase):
    __tablename__ = "wallet_user_invite"

    id = Column(
        postgresql.UUID(as_uuid=True),
        default=uuid4,
        nullable=False,
        primary_key=True,
    )
    """This is a 36-character UUID."""

    created_by_user_id: int = Column(Integer, nullable=False)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[int]", variable has type "int")
    """
    user.id of the individual creating the invitation. Must be nullable
    in case we receive a data deletion request from the individual.
    CASCADE UPDATE and DELETE
    """

    reimbursement_wallet_id: int = Column(BigInteger, nullable=False)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[int]", variable has type "int")
    """
    reimbursement_wallet.id of the Maven Wallet that the recipient is being invited to.
    CASCADE UPDATE and DELETE
    """

    date_of_birth_provided: str = Column(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[str]", variable has type "str")
        NCHAR(10),
        nullable=False,
    )
    """Date of birth of the recipient, provided by the inviter, "YYYY-MM-DD" format"""

    email: str = Column(String(120), nullable=False)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[str]", variable has type "str")
    """Email address of the recipient, provided by the inviter."""

    claimed: bool = Column(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[bool]", variable has type "bool")
        Boolean,
        nullable=False,
        default=False,
    )
    """
    True if the recipient has accepted or declined the invitation,
    or if the invitation was voided or canceled.
    """

    has_info_mismatch: bool = Column(Boolean, nullable=False, default=False)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[bool]", variable has type "bool")
    """
    Flag for showing the inviting partner whether there was an
    information mismatch when the recipient tried to access the
    invitation.
    """

    def __repr__(self) -> str:
        return f"<WalletUserInvite from {self.created_by_user_id}>"

    __str__ = __repr__

    def is_expired(self) -> bool:
        """
        Returns whether the invitation is expired.
        The current policy is 3 days until expiration.
        """
        time_delta = datetime.now() - self.created_at
        return EXPIRATION_TIME <= time_delta
