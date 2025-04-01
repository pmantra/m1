from dataclasses import dataclass
from typing import Optional

from flask_restful import abort
from sqlalchemy.orm.exc import NoResultFound

from authn.models.user import User
from storage.connection import db
from utils.log import logger
from wallet.models.constants import WalletUserStatus
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers

log = logger(__name__)


class WalletResourceMixin:
    def _wallet_or_404(self, user: User, wallet_id: int) -> ReimbursementWallet:  # type: ignore[return] # Missing return statement
        """
        Retrieve a `ReimbursementWallet` with the provided wallet_id making sure the wallet is connected to the
        specified user.
        If the user is not associated with a wallet with `wallet_id` or if no wallet with `wallet_id` is found,
        throw and log an exception.
        @param user: the `User` who is associated with the wallet to retrieve
        @param wallet_id: the ID of the wallet to retrieve
        @return: `ReimbursementWallet`
        """
        try:
            wallet = (
                db.session.query(ReimbursementWallet)
                .join(
                    ReimbursementWalletUsers,
                    ReimbursementWalletUsers.reimbursement_wallet_id
                    == ReimbursementWallet.id,
                )
                .filter(
                    ReimbursementWallet.id == wallet_id,
                    ReimbursementWalletUsers.user_id == user.id,
                    ReimbursementWalletUsers.status == WalletUserStatus.ACTIVE,
                )
                .one()
            )
            return wallet
        except NoResultFound:
            log.error(
                f"Could not find associated wallet with ID={wallet_id} and User ID={user.id}"
            )
            self._throw_invalid_wallet_id_error(wallet_id)

    @staticmethod
    def _throw_invalid_wallet_id_error(wallet_id: int) -> None:
        abort(404, message=f"ReimbursementWallet {wallet_id} is invalid.")


@dataclass(frozen=True)
class PaymentBlock:
    __slots__ = ("variant", "show_benefit_amount", "num_errors")
    variant: str
    show_benefit_amount: bool
    num_errors: int


@dataclass(frozen=True)
class TreatmentBlock:
    variant: str
    clinic: str = ""
    clinic_location: str = ""


@dataclass(frozen=True)
class ReimbursementRequestBlock:
    has_cost_breakdown_available: bool
    total: int
    title: Optional[str] = None
    reimbursement_text: Optional[str] = None
    expected_reimbursement_amount: Optional[str] = None
    original_claim_text: Optional[str] = None
    original_claim_amount: Optional[str] = None
    reimbursement_request_uuid: Optional[str] = None
    details_text: Optional[str] = None
