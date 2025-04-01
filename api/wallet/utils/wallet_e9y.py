from __future__ import annotations

from storage.connection import db
from utils.log import logger
from wallet.models.constants import WalletState
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.services.reimbursement_wallet_e9y_service import WalletEligibilityService

log = logger(__name__)


def undo_set_to_runout(
    ros_id: int | None = None, wallet_id: int | None = None, dry_run: bool = True
) -> None:
    if not ros_id and not wallet_id:
        raise Exception("ros_id or wallet_id must be specified")

    query = (
        db.session.query(ReimbursementWallet)
        .join(ReimbursementOrganizationSettings)
        .filter(
            ReimbursementWallet.state == WalletState.RUNOUT,
        )
    )

    if ros_id:
        query = query.filter(ReimbursementOrganizationSettings.id == ros_id)

    if wallet_id:
        query = query.filter(ReimbursementWallet.id == wallet_id)

    wallets = query.all()

    service = WalletEligibilityService(
        db.session, dry_run=dry_run, bypass_alegeus=dry_run
    )

    success_count, failure_count = 0, 0

    try:
        for wallet in wallets:
            result = service.undo_set_wallet_to_runout(
                wallet=wallet, session=db.session
            )
            if result is True:
                log.info(
                    "Wallet was successfully set back to QUALIFIED",
                    wallet_id=str(wallet.id),
                )
                success_count += 1
            else:
                log.warn(
                    "Failed to set wallet back to QUALIFIED", wallet_id=str(wallet.id)
                )
                failure_count += 1
    except Exception as e:
        log.exception(
            "Exception encountered while processing wallets",
            error=str(e),
            ros_id=ros_id,
        )
        db.session.rollback()
    else:
        if dry_run:
            db.session.rollback()
        else:
            db.session.commit()

    log.info(
        "Processing completed",
        count=len(wallets),
        success=str(success_count),
        failure=str(failure_count),
    )
