from typing import List

from models.profiles import Address
from utils.log import logger
from wallet import alegeus_api
from wallet.models.constants import WalletState
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.utils.alegeus.enrollments.enroll_wallet import update_employee_demographic

"""
This script is deprecated and should not be utilized. It references the deprecated ReimbursementWallet.user_id.
Instead, update the code to use ReimbursementWalletUsers if this functionality is required.
"""

log = logger(__name__)


def update_demographics_for_wallets_by_id(wallet_ids: List[int], dry_run: bool = True):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    count = 0
    api = alegeus_api.AlegeusApi()

    qualified_wallet_query = ReimbursementWallet.query.filter(
        ReimbursementWallet.state == WalletState.QUALIFIED,
        ReimbursementWallet.id.in_(wallet_ids),
    )
    wallet_count = qualified_wallet_query.count()
    log.info(f"Wallets to Update Found: {wallet_count}, Expected: {len(wallet_ids)}")
    all_wallets = qualified_wallet_query.all()

    # get addresses when possible
    addresses = (
        Address.query.join(
            ReimbursementWallet, ReimbursementWallet.user_id == Address.user_id
        )
        .filter(ReimbursementWallet.id.in_(wallet_ids))
        .all()
    )
    log.info(
        f"Addresses found for Wallet Users: {len(addresses)}, missing data will be passed as None."
    )
    address_dict = {address.user_id: address for address in addresses}

    # make updates
    failed_wallet_ids = []
    for wallet in all_wallets:
        log.info("Updating wallet", wallet_id=wallet.id)

        address = address_dict.get(ReimbursementWallet.user_id, None)
        if address is None:
            log.info("Wallet address not found.", wallet_id=wallet.id)

        if dry_run:
            log.info("DRY RUN: Did not update wallet.", wallet_id=wallet.id)
            continue
        else:
            try:
                update_employee_demographic(api, wallet, address)
                count += 1
                log.info("Updated wallet.", wallet_id=wallet.id)
            except Exception as e:
                failed_wallet_ids.append(wallet.id)
                log.error("Failed to update Wallet.", wallet_id=wallet.id, error=e)

    log.info(f"Wallets Updated: {count}, Expected: {len(wallet_ids)}")
    if failed_wallet_ids:
        log.debug(
            f"Failed Wallets: {len(failed_wallet_ids)}",
            failed_wallet_ids=failed_wallet_ids,
        )
