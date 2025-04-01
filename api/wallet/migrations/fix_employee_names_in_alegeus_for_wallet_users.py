from common.constants import Environment
from utils.log import logger
from wallet import alegeus_api
from wallet.models.constants import WalletState
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.utils.alegeus.enrollments.enroll_wallet import update_employee_demographic

log = logger(__name__)
DRY_RUN_USER_IDS = [322212, 331388]
QA_DRY_RUN_USER_IDS = [287684, 286883, 286266, 283071, 280618]


"""
This script is deprecated and should not be utilized. It references the deprecated ReimbursementWallet.user_id.
Instead, update the code to use ReimbursementWalletUsers if this functionality is required.
"""


def update_all_user_names_in_alegeus(dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    count = 0
    api = alegeus_api.AlegeusApi()
    try:
        query = ReimbursementWallet.query.filter(
            ReimbursementWallet.state == WalletState.QUALIFIED
        )
        if dry_run:
            if Environment.current() == Environment.PRODUCTION:
                query = query.filter(ReimbursementWallet.user_id.in_(DRY_RUN_USER_IDS))
            else:
                query = query.filter(
                    ReimbursementWallet.user_id.in_(QA_DRY_RUN_USER_IDS)
                )

        wallets = query.all()
        for wallet in wallets:
            try:
                update_employee_demographic(api, wallet)  # type: ignore[call-arg] # Missing positional argument "address" in call to "update_employee_demographic"
                count += 1
            except Exception as e:
                log.info(
                    f"There was an error updating wallet {wallet.id} due to error: {e}"
                )

        log.info(f"{count} users updated in alegeus successfully.")

    except Exception as e:
        log.info(f"There was an error updating wallet users in alegeus {e}")
