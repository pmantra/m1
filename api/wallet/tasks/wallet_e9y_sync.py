from sqlalchemy import func

from common import stats
from storage.connection import db
from tasks.queues import job
from utils.log import logger
from wallet.models.constants import WalletState
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.services.reimbursement_wallet_e9y_service import (
    BASE_METRIC_NAME,
    WalletEligibilityService,
)

log = logger(__name__)


@job(service_ns="wallet_e9y", team_ns="benefits_experience")
def wallet_e9y_job() -> None:
    total_count = (
        db.session.query(func.count(ReimbursementWallet.id))
        .filter(ReimbursementWallet.state == WalletState.QUALIFIED)
        .scalar()
    )
    service = WalletEligibilityService(db, dry_run=False, bypass_alegeus=False)
    log.info(f"Got total: {total_count} qualified wallets to process")
    stats.increment(
        metric_name=f"{BASE_METRIC_NAME}.wallet_e9y_job.expected_wallet_count",
        pod_name=stats.PodNames.BENEFITS_EXP,
        metric_value=float(total_count),
    )
    batch_size = 1000
    processed = 0
    while True:
        with service._fresh_session() as session:
            batch = (
                session.query(ReimbursementWallet)
                .filter(ReimbursementWallet.state == WalletState.QUALIFIED)
                .order_by(ReimbursementWallet.id)
                .limit(batch_size)
                .offset(processed)
                .all()
            )

            if not batch:
                break

            wallet_ids = [w.id for w in batch]

        # Process each wallet independently with its own session
        for wallet_id in wallet_ids:
            try:
                ret = service.process_wallet(wallet_id)
                if ret:
                    log.info(f"For wallet: {wallet_id}, get metadata: {ret}")

            except Exception as e:
                # Catch errors for individual wallets but continue processing others
                log.exception(f"Failed to process wallet {wallet_id}", exc=e)
                continue

        processed += len(wallet_ids)
        log.info(f"Processed {processed}/{total_count} wallets")

    stats.increment(
        metric_name=f"{BASE_METRIC_NAME}.wallet_e9y_job.processed_wallet_count",
        pod_name=stats.PodNames.BENEFITS_EXP,
        metric_value=float(processed),
    )
    log.info(f"Final processed count: {processed}")
