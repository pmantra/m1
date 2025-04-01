from base64 import b64encode

from models.enterprise import Organization, UserAsset
from storage.connection import db
from wallet.models.constants import WalletState
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet


def download_user_asset_to_b64_str(user_asset: UserAsset) -> str:
    blob = user_asset.blob
    blob_bytes = blob.download_as_bytes()
    blob_bytes_b64_str = b64encode(blob_bytes).decode("ascii")
    return blob_bytes_b64_str


def get_all_alegeus_sync_claims_user_wallets() -> list:
    return (
        db.session.query(ReimbursementWallet)
        .join(ReimbursementWallet.reimbursement_organization_settings)
        .join(ReimbursementOrganizationSettings.organization)
        .filter(
            ReimbursementWallet.state.in_([WalletState.QUALIFIED, WalletState.RUNOUT]),
            ReimbursementWallet.alegeus_id.isnot(None),
            Organization.alegeus_employer_id.isnot(None),
        )
        .all()
    )
