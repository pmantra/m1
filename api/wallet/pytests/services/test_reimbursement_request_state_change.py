from unittest.mock import patch

from requests import Response

from wallet.models.constants import ReimbursementRequestState
from wallet.models.reimbursement import ReimbursementClaim
from wallet.services.reimbursement_request_state_change import (
    handle_reimbursement_request_state_change,
    handle_upload_card_transaction_attachments_in_alegeus,
)


@patch(
    "wallet.services.reimbursement_request_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_handle_reimbursement_request_state_change__new_to_pending(
    wallet_with_pending_requests_no_claims,
):
    assert wallet_with_pending_requests_no_claims.reimbursement_requests
    reimbursement_request = (
        wallet_with_pending_requests_no_claims.reimbursement_requests[0]
    )

    assert reimbursement_request.state == ReimbursementRequestState.PENDING
    old_state = ReimbursementRequestState.NEW

    with patch(
        "wallet.services.reimbursement_request_state_change.create_claim_in_alegeus"
    ) as mock_create_claim_in_alegeus, patch(
        "wallet.services.reimbursement_request_state_change.upload_claim_attachments_to_alegeus"
    ) as mock_upload_claim_attachments_to_alegeus, patch(
        "utils.braze_events.braze.send_event"
    ) as mock_send_event:

        mock_create_claim_in_alegeus.return_value = (True, [], None)
        mock_upload_claim_attachments_to_alegeus.return_value = (True, [])

        handle_reimbursement_request_state_change(reimbursement_request, old_state)

        assert mock_create_claim_in_alegeus.call_count == 1
        assert mock_upload_claim_attachments_to_alegeus.call_count == 1
        assert mock_send_event.call_count == 2
        assert (
            mock_send_event.call_args_list[0].kwargs["event_name"]
            == "alegeus_claim_submitted"
        )
        assert (
            mock_send_event.call_args_list[1].kwargs["event_name"]
            == "alegeus_claim_attachments_submitted"
        )


@patch(
    "wallet.services.reimbursement_request_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_handle_reimbursement_request_state_change__new_to_pending_failure_submit_claim(
    wallet_with_pending_requests_no_claims,
):
    assert wallet_with_pending_requests_no_claims.reimbursement_requests
    reimbursement_request = (
        wallet_with_pending_requests_no_claims.reimbursement_requests[0]
    )

    assert reimbursement_request.state == ReimbursementRequestState.PENDING
    old_state = ReimbursementRequestState.NEW

    with patch(
        "wallet.services.reimbursement_request_state_change.create_claim_in_alegeus"
    ) as mock_create_claim_in_alegeus, patch(
        "wallet.services.reimbursement_request_state_change.upload_claim_attachments_to_alegeus"
    ) as mock_upload_claim_attachments_to_alegeus, patch(
        "utils.braze_events.braze.send_event"
    ) as mock_send_event:

        mock_create_claim_in_alegeus.return_value = (False, [], None)
        mock_upload_claim_attachments_to_alegeus.return_value = (True, [])

        handle_reimbursement_request_state_change(reimbursement_request, old_state)

        assert mock_create_claim_in_alegeus.call_count == 1

        # handler method should exit before upload method is called
        assert mock_upload_claim_attachments_to_alegeus.call_count == 0

        # no events should be sent
        assert mock_send_event.call_count == 0

        assert reimbursement_request.state == old_state


@patch(
    "wallet.services.reimbursement_request_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_handle_reimbursement_request_state_change__new_to_pending_failure_upload_attachments(
    wallet_with_pending_requests_no_claims,
):
    assert wallet_with_pending_requests_no_claims.reimbursement_requests
    reimbursement_request = (
        wallet_with_pending_requests_no_claims.reimbursement_requests[0]
    )

    assert reimbursement_request.state == ReimbursementRequestState.PENDING
    old_state = ReimbursementRequestState.NEW

    with patch(
        "wallet.services.reimbursement_request_state_change.create_claim_in_alegeus"
    ) as mock_create_claim_in_alegeus, patch(
        "wallet.services.reimbursement_request_state_change.upload_claim_attachments_to_alegeus"
    ) as mock_upload_claim_attachments_to_alegeus, patch(
        "utils.braze_events.braze.send_event"
    ) as mock_send_event:

        mock_create_claim_in_alegeus.return_value = (True, [], None)
        mock_upload_claim_attachments_to_alegeus.return_value = (False, [])

        handle_reimbursement_request_state_change(reimbursement_request, old_state)

        assert mock_create_claim_in_alegeus.call_count == 1

        # handler method should exit before upload method is called
        assert mock_upload_claim_attachments_to_alegeus.call_count == 1

        # only one event should be sent
        assert mock_send_event.call_count == 1
        assert (
            mock_send_event.call_args_list[0].kwargs["event_name"]
            == "alegeus_claim_submitted"
        )

        assert reimbursement_request.state == ReimbursementRequestState.NEW


@patch(
    "wallet.services.reimbursement_request_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_handle_reimbursement_request_state_change__sync_removes_claim(
    wallet_with_pending_requests_with_claims_and_attachments,
):
    """
    Test that when we have a ReimbursementRequest that has a ReimbursementClaim linked,
    that ReimbursementClaim is deleted if it does not exist in Alegeus

    A new ReimbursementClaim should be created and attached to the ReimbursementRequest
    The ReimbursementRequest should also have state == PENDING
    """
    claim_1_alegeus_id = "123abc"

    reimbursement_request = (
        wallet_with_pending_requests_with_claims_and_attachments.reimbursement_requests[
            0
        ]
    )

    reimbursement_claim = reimbursement_request.claims[0]

    assert reimbursement_claim.alegeus_claim_id == claim_1_alegeus_id

    assert reimbursement_request.state == ReimbursementRequestState.PENDING
    old_state = ReimbursementRequestState.NEW

    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: []

    with patch(
        "wallet.services.reimbursement_request_state_change.create_claim_in_alegeus"
    ) as mock_create_claim_in_alegeus, patch(
        "wallet.services.reimbursement_request_state_change.upload_claim_attachments_to_alegeus"
    ) as mock_upload_claim_attachments_to_alegeus, patch(
        "utils.braze_events.braze.send_event"
    ) as mock_send_event, patch(
        "wallet.alegeus_api.AlegeusApi.get_employee_activity"
    ) as mock_sync_request:

        mock_sync_request.return_value = mock_response

        mock_create_claim_in_alegeus.return_value = (True, [], None)
        mock_upload_claim_attachments_to_alegeus.return_value = (True, [])

        handle_reimbursement_request_state_change(reimbursement_request, old_state)

        # Note: not going to assert if a new ReimbursementClaim was created here since we would have to
        # mock more calls in create.py
        # Creating claims are covered in test_create.py

        assert not ReimbursementClaim.query.get(claim_1_alegeus_id)

        assert reimbursement_request.state == ReimbursementRequestState.PENDING

        assert mock_send_event.call_count == 2
        assert (
            mock_send_event.call_args_list[0].kwargs["event_name"]
            == "alegeus_claim_submitted"
        )
        assert (
            mock_send_event.call_args_list[1].kwargs["event_name"]
            == "alegeus_claim_attachments_submitted"
        )


def test_handle_reimbursement_request_state_change__pending_to_approved(
    valid_reimbursement_request,
):
    valid_reimbursement_request.state = ReimbursementRequestState.APPROVED
    old_state = ReimbursementRequestState.PENDING

    with patch("utils.braze_events.braze.send_event") as mock_send_event:

        handle_reimbursement_request_state_change(
            valid_reimbursement_request, old_state
        )

        assert mock_send_event.call_count == 1
        assert (
            mock_send_event.call_args.kwargs["event_name"]
            == "wallet_reimbursement_state_approved"
        )


def test_handle_reimbursement_request_state_change__approved_to_reimbursed(
    valid_reimbursement_request,
):
    valid_reimbursement_request.state = ReimbursementRequestState.REIMBURSED
    old_state = ReimbursementRequestState.APPROVED

    with patch("utils.braze_events.braze.send_event") as mock_send_event:

        handle_reimbursement_request_state_change(
            valid_reimbursement_request, old_state
        )

        assert mock_send_event.call_count == 1
        assert (
            mock_send_event.call_args.kwargs["event_name"]
            == "wallet_reimbursement_state_reimbursed"
        )


def test_handle_reimbursement_request_state_change__pending_to_denied(
    valid_reimbursement_request,
):
    valid_reimbursement_request.state = ReimbursementRequestState.DENIED
    old_state = ReimbursementRequestState.PENDING

    with patch("utils.braze_events.braze.send_event") as mock_send_event:

        handle_reimbursement_request_state_change(
            valid_reimbursement_request, old_state
        )

        assert mock_send_event.call_count == 1
        assert (
            mock_send_event.call_args.kwargs["event_name"]
            == "wallet_reimbursement_state_declined"
        )


def test_handle_upload_card_transaction_attachments_in_alegeus__success(
    wallet_with_pending_requests_with_transactions_and_attachments,
):
    assert (
        wallet_with_pending_requests_with_transactions_and_attachments.reimbursement_requests
    )
    reimbursement_request = wallet_with_pending_requests_with_transactions_and_attachments.reimbursement_requests[
        0
    ]

    reimbursement_request.state = ReimbursementRequestState.RECEIPT_SUBMITTED
    old_state = ReimbursementRequestState.NEEDS_RECEIPT

    with patch(
        "wallet.services.reimbursement_request_state_change.upload_card_transaction_attachments_to_alegeus"
    ) as mock_upload_card_transaction_attachments_to_alegeus, patch(
        "utils.braze_events.braze.send_event"
    ) as mock_send_event:

        mock_upload_card_transaction_attachments_to_alegeus.return_value = True

        messages = handle_upload_card_transaction_attachments_in_alegeus(
            wallet_with_pending_requests_with_transactions_and_attachments,
            reimbursement_request,
            old_state,
        )

        assert len(messages) == 0
        assert mock_upload_card_transaction_attachments_to_alegeus.call_count == 1
        assert mock_send_event.call_count == 1
        assert (
            mock_send_event.call_args.kwargs["event_name"]
            == "alegeus_card_transaction_attachments_submitted"
        )


def test_handle_upload_card_transaction_attachments_in_alegeus__failure(
    wallet_with_pending_requests_with_transactions_and_attachments,
):
    assert (
        wallet_with_pending_requests_with_transactions_and_attachments.reimbursement_requests
    )
    reimbursement_request = wallet_with_pending_requests_with_transactions_and_attachments.reimbursement_requests[
        0
    ]

    reimbursement_request.state = ReimbursementRequestState.RECEIPT_SUBMITTED
    old_state = ReimbursementRequestState.NEEDS_RECEIPT

    with patch(
        "wallet.services.reimbursement_request_state_change.upload_card_transaction_attachments_to_alegeus"
    ) as mock_upload_card_transaction_attachments_to_alegeus, patch(
        "utils.braze_events.braze.send_event"
    ) as mock_send_event:

        mock_upload_card_transaction_attachments_to_alegeus.return_value = False

        messages = handle_upload_card_transaction_attachments_in_alegeus(
            wallet_with_pending_requests_with_transactions_and_attachments,
            reimbursement_request,
            old_state,
        )

        assert len(messages) == 1
        assert mock_upload_card_transaction_attachments_to_alegeus.call_count == 1
        assert mock_send_event.call_count == 0
        assert reimbursement_request.state == old_state


def test_handle_upload_card_transaction_attachments_in_alegeus__exception(
    wallet_with_pending_requests_with_transactions_and_attachments,
):
    assert (
        wallet_with_pending_requests_with_transactions_and_attachments.reimbursement_requests
    )
    reimbursement_request = wallet_with_pending_requests_with_transactions_and_attachments.reimbursement_requests[
        0
    ]

    reimbursement_request.state = ReimbursementRequestState.RECEIPT_SUBMITTED
    old_state = ReimbursementRequestState.NEEDS_RECEIPT

    with patch(
        "wallet.services.reimbursement_request_state_change.upload_card_transaction_attachments_to_alegeus"
    ) as mock_upload_card_transaction_attachments_to_alegeus, patch(
        "utils.braze_events.braze.send_event"
    ) as mock_send_event:

        mock_upload_card_transaction_attachments_to_alegeus.side_effect = Exception

        messages = handle_upload_card_transaction_attachments_in_alegeus(
            wallet_with_pending_requests_with_transactions_and_attachments,
            reimbursement_request,
            old_state,
        )

        assert len(messages) == 1
        assert mock_upload_card_transaction_attachments_to_alegeus.call_count == 1
        assert mock_send_event.call_count == 0
        assert reimbursement_request.state == old_state
