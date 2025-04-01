import sqlalchemy.orm
from httpproblem import Problem

from authn.models.user import User
from direct_payment.billing import models
from utils.log import logger
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers

log = logger(__name__)


class BillResourceMixin:
    def _user_has_access_to_bill_or_403(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, accessing_user: User, bill: models.Bill, session: sqlalchemy.orm.Session
    ):
        if bill.payor_type == models.PayorType.MEMBER:
            wallet_users = (
                session.query(ReimbursementWalletUsers)
                .filter(
                    ReimbursementWalletUsers.reimbursement_wallet_id == bill.payor_id
                )
                .all()
            )
            if not (
                # a user may retry their own bill
                accessing_user.id
                in [wallet_user.user_id for wallet_user in wallet_users]
                # note: we may want to amend this to a more specific permission for ops
                or accessing_user.is_care_coordinator
                # note: we do not allow any practitioners to modify bills unlike _user_has_access_to_user_or_403
            ):
                self._throw_invalid_access_error(accessing_user, bill)
        else:
            # only ops may retry employer and clinic bills through this endpoint
            if not accessing_user.is_care_coordinator:
                self._throw_invalid_access_error(accessing_user, bill)

    @staticmethod
    def _throw_invalid_access_error(accessing_user: User, bill: models.Bill):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        log.info(
            "Invalid bill access attempt.",
            bill_id=bill.id,
            accessing_user_id=accessing_user.id,
        )
        raise Problem(403, detail="You do not have access to that bill information.")
