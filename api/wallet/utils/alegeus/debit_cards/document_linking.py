from typing import Optional

from common import stats
from utils.log import logger
from wallet.alegeus_api import AlegeusApi, is_request_successful
from wallet.models.reimbursement import ReimbursementRequest
from wallet.utils.alegeus.common import download_user_asset_to_b64_str

metric_prefix = "api.wallet.utils.alegeus.debit_cards.document_linking"

log = logger(__name__)


def upload_card_transaction_attachments_to_alegeus(
    reimbursement_request: ReimbursementRequest, source_ids: Optional[list] = None
) -> bool:
    """
    Upload all attachments for a Pending ReimbursementRequest / card transaction to Alegeus
    Limit upload to optional list of source_ids if we don't want to upload all associated assets.
    """

    def tag_successful(
        successful: bool,
        reason: Optional[str] = None,
        content_type: Optional[str] = None,
        end_point: Optional[str] = None,
    ) -> None:
        metric_name = f"{metric_prefix}.upload_debit_attachments"
        if successful:
            tags = ["success:true"]
        else:
            tags = [
                "error:true",
                f"content_type:{content_type}",
                f"reason:{reason}",
                f"end_point:{end_point}",
            ]
            metric_name += ".error"

        stats.increment(
            metric_name=metric_name,
            pod_name=stats.PodNames.PAYMENTS_POD,
            tags=tags,
        )

    api = AlegeusApi()
    wallet = reimbursement_request.wallet
    reimbursement_transaction = (
        reimbursement_request.transactions and reimbursement_request.transactions[0]
    )
    if not wallet or not reimbursement_transaction:
        log.info(
            f"Reimbursement Request ID: {reimbursement_request.id} does not have an associated wallet or reimbursement transaction"
        )
        return False

    transaction_id = reimbursement_transaction.alegeus_transaction_key
    settlement_date = reimbursement_transaction.settlement_date.strftime("%Y%m%d")
    sequence_number = reimbursement_transaction.sequence_number

    if not all([transaction_id, settlement_date, sequence_number]):
        log.info(
            f"Transaction ID: {reimbursement_transaction.id} does not have transaction_id, settlement_date, or sequence_number"
        )
        tag_successful(False)
        return False

    sources = reimbursement_request.sources
    if not sources:
        log.info(
            f"Transaction ID: {reimbursement_transaction.id} does not have any sources"
        )
        tag_successful(False)
        return False

    for source in sources:
        if source_ids and source.id not in source_ids:
            continue
        try:
            user_asset = source.user_asset
            blob_bytes_b64_str = download_user_asset_to_b64_str(user_asset)
        except Exception as e:
            message = f"Could not download attachment for ReimbursementRequestSource ID: {source.id} as bytes"
            log.exception(message, error=e)
            tag_successful(False)
            return False
        else:
            try:
                response = api.upload_attachment_for_card_transaction(
                    wallet,
                    source.user_asset,
                    transaction_id,
                    settlement_date,
                    sequence_number,
                    blob_bytes_b64_str,
                )
                if is_request_successful(response):
                    log.info(
                        f"Successfully uploaded attachment for transaction: {reimbursement_transaction.id}"
                        f"Source ID: {source.id}, "
                        f"UserAsset ID: {user_asset.id}"
                    )
                    tag_successful(True)
                else:
                    log.info(
                        f"Could not upload attachment for transaction: {reimbursement_transaction.id}"
                        f"Source ID: {source.id}, "
                        f"UserAsset ID: {user_asset.id}"
                    )
                    tag_successful(
                        False,
                        reason="alegeus_api_failure",
                        content_type=response.headers["content-type"],
                        end_point="upload_attachment_for_card_transaction",
                    )
                    return False

            except Exception as e:
                message = f"Could not upload attachment for transaction: {reimbursement_transaction.id}"
                log.exception(message, error=e)
                tag_successful(
                    False,
                    reason="exception",
                    end_point="upload_attachment_for_card_transaction",
                )

    return True
