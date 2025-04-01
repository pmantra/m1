from storage.connection import db
from utils.log import logger
from wallet.models.constants import WalletState
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_benefit import ReimbursementWalletBenefit
from wallet.services.reimbursement_benefits import assign_benefit_id

log = logger(__name__)


def get_all_wallets_needing_benefit_id():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    all_wallets_needing_benefit_id = (
        db.session.query(ReimbursementWallet)
        .outerjoin(ReimbursementWalletBenefit)
        .filter(
            ReimbursementWallet.state == WalletState.QUALIFIED,
            ReimbursementWalletBenefit.reimbursement_wallet_id.is_(None),
        )
        .all()
    )
    return all_wallets_needing_benefit_id


def backfill():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from app import create_app

    with create_app(task_instance=True).app_context():
        wallets = get_all_wallets_needing_benefit_id()
        assigned = 0
        errors = 0
        for wallet in wallets:
            try:
                assign_benefit_id(wallet)
                assigned += 1
            except Exception as e:
                log.exception("Failed to assign Benefit ID", error=e, wallet=wallet)
                errors += 1

        log.info(f"Finished. Total={len(wallets)} Assigned={assigned} Errors={errors}")


if __name__ == "__main__":
    backfill()
