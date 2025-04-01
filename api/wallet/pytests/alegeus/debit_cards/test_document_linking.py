from unittest.mock import MagicMock, PropertyMock, patch

from requests import Response

from wallet.pytests.factories import ReimbursementTransactionFactory
from wallet.utils.alegeus.debit_cards.document_linking import (
    upload_card_transaction_attachments_to_alegeus,
)


def test_upload_claim_attachments_to_alegeus__successful(
    wallet_with_pending_requests_no_claims,
):
    reimbursement_request = (
        wallet_with_pending_requests_no_claims.reimbursement_requests[0]
    )

    ReimbursementTransactionFactory.create(reimbursement_request=reimbursement_request)

    mock_response_1 = Response()
    mock_response_1.status_code = 200
    mock_response_1.json = lambda: {}

    mock_response_2 = Response()
    mock_response_2.status_code = 200
    mock_response_2.json = lambda: {}

    mock_blob_instance = MagicMock()
    mock_blob_instance.download_as_bytes = lambda: b"pizza"

    with patch(
        "wallet.utils.alegeus.debit_cards.document_linking.AlegeusApi.upload_attachment_for_card_transaction"
    ) as mock_request, patch(
        "models.enterprise.UserAsset.blob", new_callable=PropertyMock
    ) as mock_blob:
        mock_request.side_effect = [mock_response_1, mock_response_2]
        mock_blob.return_value = mock_blob_instance

        was_successful = upload_card_transaction_attachments_to_alegeus(
            reimbursement_request,
        )

        assert was_successful is True
        assert mock_request.call_count == 2


def test_upload_claim_attachments_to_alegeus__failure_upload_attachments(
    wallet_with_pending_requests_with_claims_and_attachments,
):
    reimbursement_request = (
        wallet_with_pending_requests_with_claims_and_attachments.reimbursement_requests[
            0
        ]
    )
    ReimbursementTransactionFactory.create(reimbursement_request=reimbursement_request)

    mock_response_1 = Response()
    mock_response_1.status_code = 418
    mock_response_1.headers["content-type"] = "image/jpeg"
    mock_response_1.json = lambda: {}

    mock_blob_instance = MagicMock()
    mock_blob_instance.download_as_bytes = lambda: b"empanada"

    with patch(
        "wallet.utils.alegeus.debit_cards.document_linking.AlegeusApi.upload_attachment_for_card_transaction"
    ) as mock_request, patch(
        "models.enterprise.UserAsset.blob", new_callable=PropertyMock
    ) as mock_blob:
        mock_request.side_effect = [mock_response_1]
        mock_blob.return_value = mock_blob_instance

        was_successful = upload_card_transaction_attachments_to_alegeus(
            reimbursement_request,
        )

        assert was_successful is False
        assert mock_request.call_count == 1


def test_upload_claim_attachments_to_alegeus__failure_could_not_upload_all_attachments(
    wallet_with_pending_requests_with_claims_and_attachments,
):
    reimbursement_request = (
        wallet_with_pending_requests_with_claims_and_attachments.reimbursement_requests[
            0
        ]
    )
    ReimbursementTransactionFactory.create(reimbursement_request=reimbursement_request)

    mock_response_1 = Response()
    mock_response_1.status_code = 200
    mock_response_1.json = lambda: {}

    mock_response_2 = Response()
    mock_response_2.status_code = 418
    mock_response_2.headers["content-type"] = "image/jpeg"
    mock_response_2.json = lambda: {}

    mock_blob_instance = MagicMock()
    mock_blob_instance.download_as_bytes = lambda: b"pizza"

    with patch(
        "wallet.utils.alegeus.debit_cards.document_linking.AlegeusApi.upload_attachment_for_card_transaction"
    ) as mock_request, patch(
        "models.enterprise.UserAsset.blob", new_callable=PropertyMock
    ) as mock_blob:
        mock_request.side_effect = [mock_response_1, mock_response_2]
        mock_blob.return_value = mock_blob_instance

        was_successful = upload_card_transaction_attachments_to_alegeus(
            reimbursement_request,
        )

        assert was_successful is False
        assert mock_request.call_count == 2
