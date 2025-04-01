from __future__ import annotations

from itertools import islice
from typing import List

from flask import request
from flask_restful import abort

from common.services.api import InternalServiceResource
from storage.connection import db
from utils.log import logger
from wallet.constants import WHS_LEDGER_SEARCH_BATCH_SIZE
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.schemas.wallet_historical_spend import WalletHistoricalSpendPostRequest
from wallet.services.wallet_historical_spend import (
    get_historical_spend_wallet_ids,
    process_historical_spend_wallets_job,
)

log = logger(__name__)


def batch_iterator(wallet_ids: List, batch_size: int) -> List:
    """
    Yields successive batches of wallet ids.
    """
    iterator = iter(wallet_ids)
    while batch := list(islice(iterator, batch_size)):
        yield batch


class WalletHistoricalSpendResource(InternalServiceResource):
    @staticmethod
    def post() -> tuple[str, int]:
        """
        Enqueues batched jobs to process historical spend records for all qualified/runout wallets for a given ROS id.
        """
        try:
            post_request = WalletHistoricalSpendPostRequest.from_dict(
                request.json if request.is_json else None
            )
        except TypeError as e:
            log.error("Failed to process file. Missing required field", error=e)
            abort(400, message="Failed to process file. Missing required field.")

        reimbursement_organization_settings: ReimbursementOrganizationSettings | None = db.session.query(
            ReimbursementOrganizationSettings
        ).get(
            post_request.reimbursement_organization_settings_id
        )

        if not reimbursement_organization_settings:
            abort(
                400,
                message="Failed to process file. Reimbursement Organization Settings not found.",
            )
        historical_spend_wallet_ids = get_historical_spend_wallet_ids(
            reimbursement_org_settings_id=reimbursement_organization_settings.id
        )
        # Process wallets in batches of 20
        for wallet_ids_batch in batch_iterator(
            historical_spend_wallet_ids, WHS_LEDGER_SEARCH_BATCH_SIZE
        ):
            process_historical_spend_wallets_job.delay(
                file_id=post_request.file_id,
                reimbursement_organization_settings_id=reimbursement_organization_settings.id,
                wallet_ids=wallet_ids_batch,
            )
            log.info(
                "Wallet Historical Spend batches enqueued",
                file_id=post_request.file_id,
                reimbursement_organization_settings_id=str(
                    reimbursement_organization_settings.id
                ),
                batch_size=len(wallet_ids_batch),
            )
        return "Payload received", 201
