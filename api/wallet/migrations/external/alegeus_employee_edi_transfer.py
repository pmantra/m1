from sqlalchemy import and_

from storage.connection import db
from wallet.models.constants import WalletState
from wallet.models.reimbursement_wallet import ReimbursementWallet


def get_all_user_wallets():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    all_user_wallets = (
        db.session.query(ReimbursementWallet)
        .filter(
            and_(
                ReimbursementWallet.state == WalletState.QUALIFIED,
                ReimbursementWallet.alegeus_id.isnot(None),
            )
        )
        .all()
    )
    return all_user_wallets


def get_all_alegeus_user_wallets():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    all_user_wallets = get_all_user_wallets()
    return [
        alegeus_wallet
        for alegeus_wallet in all_user_wallets
        if (
            hasattr(
                alegeus_wallet.reimbursement_organization_settings.organization,
                "alegeus_employer_id",
            )
            and alegeus_wallet.reimbursement_organization_settings.organization.alegeus_employer_id
            is not None
        )
    ]
