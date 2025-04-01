from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

from authn.models.user import User
from storage.connection import db
from utils.log import logger
from wallet.models.reimbursement_wallet import ReimbursementWallet

log = logger(__name__)


def get_user_from_wallet_or_payor_id(
    inp_id: int,
) -> Iterable[User]:
    """
    Returns The active user objects mapped to the supplied wallet id (synonymous with payor id).
    :param inp_id:
    :return: Iterable of user objects.
    """
    to_return = []
    try:
        wallet = (
            db.session.query(ReimbursementWallet)
            .filter(ReimbursementWallet.id == inp_id)
            .one()
        )
        to_return = wallet.all_active_users
    except (NoResultFound, MultipleResultsFound):
        log.warn("Unable to load wallet for.", inp_id=inp_id)
    return to_return
