from datetime import timedelta, timezone

import snowflake

from storage.connection import db
from utils.log import logger
from wallet.models.reimbursement_wallet import ReimbursementWallet

log = logger(__name__)

"""
This script is deprecated and should not be utilized. It references the deprecated ReimbursementWallet.user_id.
Instead, update the code to use ReimbursementWalletUsers if this functionality is required.
"""


def fix_user_and_wallet_id(action, force):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.info(
        "Fixing change_wallet_status action user_id and wallet_id.", action_id=action.id
    )
    if action.user_id is not None and action.data.get("wallet_id"):
        log.info("Action Okay.")
        return

    a_created_at = action.created_at.replace(tzinfo=timezone.utc)
    lower_bound = snowflake.lower_bound_for_datetime(
        a_created_at - timedelta(seconds=2)
    )
    upper_bound = snowflake.upper_bound_for_datetime(
        a_created_at + timedelta(seconds=2)
    )
    ww = ReimbursementWallet.query.filter(
        ReimbursementWallet.id >= lower_bound, ReimbursementWallet.id <= upper_bound
    ).all()

    if len(ww) != 1:
        log.error(
            "Could not determine wallet associated with action.",
            wallet_ids=",".join(str(w.id) for w in ww),
            action_id=action.id,
            action_created_at=action.created_at,
        )
        return

    w = ww[0]
    log.info(
        "Found wallet for wallet status action.",
        action_id=action.id,
        wallet_id=w.id,
        user_id=w.user_id,
    )
    if force:
        action.user_id = w.user_id
        action.data = {
            k: w.id if k == "wallet_id" else v for k, v in action.data.items()
        }
        db.session.commit()
