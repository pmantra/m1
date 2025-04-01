from airflow.utils import with_app_context
from storage.connection import db
from utils.log import logger
from wallet.models.constants import WalletState
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.services.reimbursement_wallet_e9y_service import WalletEligibilityService

log = logger(__name__)


@with_app_context(team_ns="benefits_experience", service_ns="wallet_e9y")
def wallet_e9y_job() -> None:
    wallets = (
        db.session.query(ReimbursementWallet)
        .filter(ReimbursementWallet.state == WalletState.QUALIFIED)
        .all()
    )
    service = WalletEligibilityService(db.session, dry_run=True, bypass_alegeus=True)

    for w in wallets:
        ret = service.process_wallet(w)
        if ret:
            log.info(f"For wallet: {w.id}, get metadata: {ret}")
    # todo: save result to db once migration is done
