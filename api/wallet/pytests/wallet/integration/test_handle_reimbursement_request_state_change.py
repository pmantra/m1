import datetime
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
import requests

from cost_breakdown.pytests.factories import CostBreakdownFactory
from payer_accumulator.common import TreatmentAccumulationStatus
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.pytests.factories import AccumulationTreatmentMappingFactory
from wallet.alegeus_api import ALEGEUS_WCP_URL
from wallet.models.constants import ReimbursementRequestState
from wallet.pytests.factories import (
    ReimbursementClaimFactory,
    ReimbursementRequestFactory,
)
from wallet.services.reimbursement_request_state_change import (
    handle_reimbursement_request_card_transaction_state_change,
    handle_reimbursement_request_state_change,
    handle_rx_auto_processed_reimbursement_request_state_change,
)
from wallet.utils.admin_helpers import FlashMessage, FlashMessageCategory


def test_handle_reimbursement_state_change__success_no_state_change(
    wallet_with_pending_requests_no_claims,
):
    """
    A reimbursement request with no state change should successfully complete.
    """

    reimbursement_request = (
        wallet_with_pending_requests_no_claims.reimbursement_requests[0]
    )

    old_state = ReimbursementRequestState.PENDING
    message = handle_reimbursement_request_state_change(
        reimbursement_request, old_state
    )

    assert len(reimbursement_request.claims) == 0
    assert message == []


@patch(
    "wallet.services.reimbursement_request_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_handle_reimbursement_state_change__success_new_claim(
    wallet_with_pending_requests_no_claims, post_claim_response
):
    """
    A wallet with no current reimbursement claims in Alegeus
    Should create a claim in Alegeus and send attachments.
    A ReimbursementClaim should be created and attached to the wallet.
    """

    def make_api_request_side_effect(
        url,
        data=None,
        params=None,
        api_version=None,
        extra_headers=None,
        method="GET",
        **kwargs,
    ):
        mock_response = requests.Response()
        key = f"{method}:{url}"

        # post_claim
        if key == f"POST:{ALEGEUS_WCP_URL}/participant/claims/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: post_claim_response(99)

        # upload_attachments
        elif (
            key == f"PUT:{ALEGEUS_WCP_URL}/participant/receipts/submitted/None/123/456"
        ):
            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored

        return mock_response

    mock_blob_instance = MagicMock()
    mock_blob_instance.download_as_bytes = lambda: b"testblob"

    reimbursement_request = (
        wallet_with_pending_requests_no_claims.reimbursement_requests[0]
    )
    assert len(reimbursement_request.claims) == 0
    old_state = ReimbursementRequestState.NEW.value

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ) as mock_api_request, patch(
        "models.enterprise.UserAsset.blob", new_callable=PropertyMock
    ) as mock_blob:
        mock_blob.return_value = mock_blob_instance

        handle_reimbursement_request_state_change(reimbursement_request, old_state)

        # Two reimbursement request sources(receipt/attachment) and one post claims
        assert mock_api_request.call_count == 3
        assert len(reimbursement_request.claims) == 1


@patch(
    "wallet.services.reimbursement_request_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_handle_reimbursement_state_change__success_existing_claim(
    wallet_with_pending_requests_with_claims_and_attachments,
    get_employee_activity_response,
):
    """
    A wallet with reimbursement claims in Alegeus
    Should GET existing claims from Alegeus and update reimbursement request claims with new info.
    """

    def make_api_request_side_effect(
        url,
        data=None,
        params=None,
        api_version=None,
        extra_headers=None,
        method="GET",
        **kwargs,
    ):
        mock_response = requests.Response()
        key = f"{method}:{url}"

        # get_claim
        if (
            key
            == f"GET:{ALEGEUS_WCP_URL}/participant/transactions/getemployeeactivity/None/123/456"
        ):
            mock_response.status_code = 200
            mock_response.json = lambda: get_employee_activity_response("123abc")

        return mock_response

    reimbursement_request = (
        wallet_with_pending_requests_with_claims_and_attachments.reimbursement_requests[
            0
        ]
    )

    assert len(reimbursement_request.claims) == 1
    assert reimbursement_request.claims[0].status == "pending"

    old_state = ReimbursementRequestState.NEW

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ) as mock_api_request:
        handle_reimbursement_request_state_change(reimbursement_request, old_state)

        assert mock_api_request.call_count == 1
        assert len(reimbursement_request.claims) == 1
        assert (
            reimbursement_request.claims[0].status
            == ReimbursementRequestState.APPROVED.value
        )


@patch(
    "wallet.services.reimbursement_request_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_handle_reimbursement_state_change__claim_status_returned_as_needs_receipt(
    wallet_with_pending_requests_with_claims_and_attachments,
    get_employee_activity_response,
):
    """
    A wallet with existing reimbursement claims but Claim Status returns 'NEEDS RECEIPT' in Alegeus
    Should upload claim attachments.
    """

    def make_api_request_side_effect(
        url,
        data=None,
        params=None,
        api_version=None,
        extra_headers=None,
        method="GET",
        **kwargs,
    ):
        mock_response = requests.Response()
        key = f"{method}:{url}"

        # upload_attachments
        if key == f"PUT:{ALEGEUS_WCP_URL}/participant/receipts/submitted/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored

        # get_claim
        elif (
            key
            == f"GET:{ALEGEUS_WCP_URL}/participant/transactions/getemployeeactivity/None/123/456"
        ):
            mock_response.status_code = 200
            mock_response.json = lambda: get_employee_activity_response(
                "123abc", "NEEDS RECEIPT"
            )

        return mock_response

    mock_blob_instance = MagicMock()
    mock_blob_instance.download_as_bytes = lambda: b"testblob"

    reimbursement_request = (
        wallet_with_pending_requests_with_claims_and_attachments.reimbursement_requests[
            0
        ]
    )

    old_state = ReimbursementRequestState.NEW

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ) as mock_api_request, patch(
        "models.enterprise.UserAsset.blob", new_callable=PropertyMock
    ) as mock_blob:
        mock_blob.return_value = mock_blob_instance

        handle_reimbursement_request_state_change(reimbursement_request, old_state)

    # Two reimbursement request sources(receipt/attachment) and one get claims
    assert mock_api_request.call_count == 3
    assert len(reimbursement_request.claims) == 1


@patch(
    "wallet.services.reimbursement_request_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_handle_reimbursement_state_change__failure_upload_attachments(
    wallet_with_pending_requests_no_claims, post_claim_response
):
    """
    A wallet with no current reimbursement claims in Alegeus
    Should create a claim in Alegeus and a ReimbursementClaim should be created and attached to the wallet.
    ReimbursementRequest state should set back to NEW
    """

    def make_api_request_side_effect(
        url,
        data=None,
        params=None,
        api_version=None,
        extra_headers=None,
        method="GET",
        **kwargs,
    ):
        mock_response = requests.Response()
        key = f"{method}:{url}"

        # post_claim
        if key == f"POST:{ALEGEUS_WCP_URL}/participant/claims/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: post_claim_response(99)

        # upload_attachments
        elif (
            key == f"PUT:{ALEGEUS_WCP_URL}/participant/receipts/submitted/None/123/456"
        ):
            mock_response.status_code = 400
            mock_response.headers["content-type"] = "image/jpeg"
            mock_response.json = lambda: {}  # response body is ignored

        return mock_response

    mock_blob_instance = MagicMock()
    mock_blob_instance.download_as_bytes = lambda: b"testblob"

    reimbursement_request = (
        wallet_with_pending_requests_no_claims.reimbursement_requests[0]
    )
    assert len(reimbursement_request.claims) == 0
    old_state = ReimbursementRequestState.NEW

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ) as mock_api_request, patch(
        "models.enterprise.UserAsset.blob", new_callable=PropertyMock
    ) as mock_blob:
        mock_blob.return_value = mock_blob_instance

        handle_reimbursement_request_state_change(reimbursement_request, old_state)

        # One reimbursement request sources(receipt/attachment) and one post claims
        assert mock_api_request.call_count == 2
        assert len(reimbursement_request.claims) == 1


@patch(
    "wallet.services.reimbursement_request_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_handle_reimbursement_state_change__failure_get_employee_activity(
    wallet_with_pending_requests_with_claims_and_attachments,
    get_employee_activity_response,
):
    """
    A wallet with existing claims.  Alegeus Get Claims fails - no changes made
    """

    def make_api_request_side_effect(
        url,
        data=None,
        params=None,
        api_version=None,
        extra_headers=None,
        method="GET",
        **kwargs,
    ):
        mock_response = requests.Response()
        key = f"{method}:{url}"

        # get_claim
        if (
            key
            == f"GET:{ALEGEUS_WCP_URL}/participant/transactions/getemployeeactivity/None/123/456"
        ):
            mock_response.status_code = 400
            mock_response.json = lambda: {}

        return mock_response

    reimbursement_request = (
        wallet_with_pending_requests_with_claims_and_attachments.reimbursement_requests[
            0
        ]
    )
    assert len(reimbursement_request.claims) == 1
    old_state = ReimbursementRequestState.NEW

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ) as mock_api_request:
        handle_reimbursement_request_state_change(reimbursement_request, old_state)

        # One get claims
        assert mock_api_request.call_count == 1
        assert len(reimbursement_request.claims) == 1


@patch(
    "wallet.services.reimbursement_request_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_handle_reimbursement_state_change__claim_deleted_in_alegeus(
    wallet_with_pending_requests_with_claims_and_attachments,
    get_employee_activity_response,
    post_claim_response,
):
    """
    A wallet with existing reimbursement claims but none in Alegeus
    Should create a claim in Alegeus and send attachments.
    A ReimbursementClaim should be created and attached to the wallet.
    """

    def make_api_request_side_effect(
        url,
        data=None,
        params=None,
        api_version=None,
        extra_headers=None,
        method="GET",
        **kwargs,
    ):
        mock_response = requests.Response()
        key = f"{method}:{url}"

        # post_claim
        if key == f"POST:{ALEGEUS_WCP_URL}/participant/claims/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: post_claim_response(88)

        # upload_attachments
        elif (
            key == f"PUT:{ALEGEUS_WCP_URL}/participant/receipts/submitted/None/123/456"
        ):
            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored

        # get_claim
        elif (
            key
            == f"GET:{ALEGEUS_WCP_URL}/participant/transactions/getemployeeactivity/None/123/456"
        ):
            mock_response.status_code = 200
            mock_response.json = lambda: get_employee_activity_response(
                "other_tracking"
            )

        return mock_response

    mock_blob_instance = MagicMock()
    mock_blob_instance.download_as_bytes = lambda: b"testblob"

    reimbursement_request = (
        wallet_with_pending_requests_with_claims_and_attachments.reimbursement_requests[
            0
        ]
    )

    old_claim_id = reimbursement_request.claims[0].alegeus_claim_id
    assert len(reimbursement_request.claims) == 1
    assert old_claim_id == "123abc"

    old_state = ReimbursementRequestState.NEW

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ) as mock_api_request, patch(
        "wallet.models.reimbursement.secrets.token_hex",
        return_value="OTHER_TRACKING",
    ), patch(
        "models.enterprise.UserAsset.blob", new_callable=PropertyMock
    ) as mock_blob:
        mock_blob.return_value = mock_blob_instance

        handle_reimbursement_request_state_change(reimbursement_request, old_state)

        # One get claim, one post claims and two reimbursement request sources(receipts/attachment)
        assert mock_api_request.call_count == 4
        assert len(reimbursement_request.claims) == 1
        assert reimbursement_request.claims[0].alegeus_claim_id != old_claim_id


@patch(
    "wallet.services.reimbursement_request_state_change.use_alegeus_for_reimbursements",
    lambda: True,
)
def test_handle_reimbursement_state_change__failure_post_claim(
    wallet_with_pending_requests_no_claims, post_claim_response
):
    """
    A wallet with no current reimbursement claims in Alegeus
    Should create a claim but set the reimbursement request back to New.
    """

    def make_api_request_side_effect(
        url,
        data=None,
        params=None,
        api_version=None,
        extra_headers=None,
        method="GET",
        **kwargs,
    ):
        mock_response = requests.Response()
        key = f"{method}:{url}"

        # post_claim
        if key == f"POST:{ALEGEUS_WCP_URL}/participant/claims/None/123/456":
            mock_response.status_code = 400
            mock_response.json = lambda: {}

        return mock_response

    reimbursement_request = (
        wallet_with_pending_requests_no_claims.reimbursement_requests[0]
    )
    assert len(reimbursement_request.claims) == 0
    assert reimbursement_request.state == ReimbursementRequestState.PENDING
    old_state = ReimbursementRequestState.NEW

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ) as mock_api_request:
        handle_reimbursement_request_state_change(reimbursement_request, old_state)

    # One post claim failure
    assert mock_api_request.call_count == 1
    assert len(reimbursement_request.claims) == 0
    assert reimbursement_request.state == ReimbursementRequestState.NEW


def test_handle_reimbursement_state_change__transaction_needs_receipt(
    wallet_with_pending_requests_with_transactions_and_attachments,
    get_employee_activity_response,
):
    """
    A wallet with existing reimbursement transaction in state 'NEEDS RECEIPT' should upload attachments.
    """

    def make_api_request_side_effect(
        url,
        data=None,
        params=None,
        api_version=None,
        extra_headers=None,
        method="GET",
        **kwargs,
    ):
        mock_response = requests.Response()
        key = f"{method}:{url}"

        # upload_attachments
        if key == f"PUT:{ALEGEUS_WCP_URL}/participant/receipts/pos/None/123/456":
            mock_response.status_code = 200
            mock_response.json = lambda: {}  # response body is ignored

        return mock_response

    mock_blob_instance = MagicMock()
    mock_blob_instance.download_as_bytes = lambda: b"testblob"

    reimbursement_request = wallet_with_pending_requests_with_transactions_and_attachments.reimbursement_requests[
        0
    ]
    reimbursement_request.state = ReimbursementRequestState.RECEIPT_SUBMITTED
    old_state = ReimbursementRequestState.NEEDS_RECEIPT

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=make_api_request_side_effect,
    ) as mock_api_request, patch(
        "models.enterprise.UserAsset.blob", new_callable=PropertyMock
    ) as mock_blob:
        mock_blob.return_value = mock_blob_instance

        handle_reimbursement_request_card_transaction_state_change(
            reimbursement_request.wallet, reimbursement_request, old_state
        )

    assert mock_api_request.call_count == 2
    assert mock_blob.call_count == 2


def test_handle_reimbursement_state_change__no_change(
    qualified_direct_payment_enabled_wallet,
):
    all_cats = (
        qualified_direct_payment_enabled_wallet.reimbursement_organization_settings.allowed_reimbursement_categories
    )
    category = all_cats[0].reimbursement_request_category
    reimbursement_request = ReimbursementRequestFactory.create(
        service_start_date=datetime.datetime(2024, 1, 1),
        service_end_date=datetime.datetime(2024, 2, 1),
        reimbursement_request_category_id=category.id,
        reimbursement_wallet_id=qualified_direct_payment_enabled_wallet.id,
        wallet=qualified_direct_payment_enabled_wallet,
        state=ReimbursementRequestState.NEW,
    )
    old_state = ReimbursementRequestState.PENDING
    messages = handle_reimbursement_request_card_transaction_state_change(
        qualified_direct_payment_enabled_wallet, reimbursement_request, old_state
    )
    assert messages == []


# Below is RX auto processed


def test_handle_rx_auto_processed_reimbursement_request_state_change__success_new_claim_hra(
    rx_reimbursement_request,
    qualified_direct_payment_enabled_wallet,
    mocked_auto_processed_claim_response,
):
    """
    A wallet with no current reimbursement claims in Alegeus
    A ReimbursementClaim should be created and attached to the wallet.
    """
    mock_response = mocked_auto_processed_claim_response(200, "Direct Deposit", 50)
    reimbursement_request = rx_reimbursement_request
    reimbursement_request.state = ReimbursementRequestState.PENDING
    CostBreakdownFactory.create(
        reimbursement_request_id=reimbursement_request.id,
        total_employer_responsibility=100,
        total_member_responsibility=100,
    )
    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        return_value=mock_response,
    ) as mock_request, patch(
        "braze.client.BrazeClient._make_request"
    ) as mock_send_event:
        handle_rx_auto_processed_reimbursement_request_state_change(
            reimbursement_request
        )
        assert mock_request.call_count == 1
        assert mock_send_event.call_count == 1
        assert len(reimbursement_request.claims) == 1
        assert reimbursement_request.state == ReimbursementRequestState.APPROVED


def test_handle_rx_auto_processed_reimbursement_request_state_change__success_new_claim_dtr(
    rx_reimbursement_request,
    qualified_direct_payment_enabled_wallet,
    mocked_auto_processed_claim_response,
    member_health_plan_for_wallet,
    valid_alegeus_account_hdhp,
    valid_alegeus_plan_hdhp,
):
    """
    An HDHP wallet with no current reimbursement claims in Alegeus
    A DTR ReimbursementClaim should be created and attached to the wallet.
    Reimbursement Request should be set to Denied
    """
    mock_response = mocked_auto_processed_claim_response(200, "Direct Deposit", 50)
    reimbursement_request = rx_reimbursement_request
    valid_alegeus_account_hdhp.wallet = qualified_direct_payment_enabled_wallet
    valid_alegeus_account_hdhp.plan = valid_alegeus_plan_hdhp
    qualified_direct_payment_enabled_wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
        False
    )
    member_health_plan_for_wallet.employer_health_plan.is_hdhp = True
    reimbursement_request.state = ReimbursementRequestState.PENDING
    CostBreakdownFactory.create(
        reimbursement_request_id=reimbursement_request.id,
        total_employer_responsibility=0,
        total_member_responsibility=reimbursement_request.amount,
        deductible=reimbursement_request.amount,
    )
    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        return_value=mock_response,
    ) as mock_request, patch(
        "braze.client.BrazeClient._make_request"
    ) as mock_send_event:
        handle_rx_auto_processed_reimbursement_request_state_change(
            reimbursement_request
        )
        assert mock_request.call_count == 1
        assert mock_send_event.call_count == 1
        assert len(reimbursement_request.claims) == 1
        assert reimbursement_request.state == ReimbursementRequestState.DENIED


def test_handle_rx_auto_processed_reimbursement_request_state_change__success_existing_hra_claim(
    rx_reimbursement_request,
    qualified_direct_payment_enabled_wallet,
    get_employee_activity_response,
    member_health_plan_for_wallet,
):
    """
    A wallet with reimbursement claims in Alegeus
    Should GET existing claims from Alegeus and update reimbursement request claims with new info.
    Direct Payment enabled - DA Enabled
    """
    mock_response = requests.Response()
    mock_response.status_code = 200
    mock_response.json = lambda: get_employee_activity_response("123abc")
    ReimbursementClaimFactory.create(
        alegeus_claim_id="123abc",
        alegeus_claim_key=1,
        status="pending",
        reimbursement_request=rx_reimbursement_request,
        amount=100,
    )
    reimbursement_request = rx_reimbursement_request
    qualified_direct_payment_enabled_wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
        True
    )
    CostBreakdownFactory.create(
        reimbursement_request_id=reimbursement_request.id,
        total_employer_responsibility=100,
        total_member_responsibility=100,
    )
    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        return_value=mock_response,
    ) as mock_request, patch(
        "braze.client.BrazeClient._make_request"
    ) as mock_send_event:
        handle_rx_auto_processed_reimbursement_request_state_change(
            reimbursement_request
        )
        assert mock_request.call_count == 1
        assert mock_send_event.call_count == 1
        assert len(reimbursement_request.claims) == 1
        assert reimbursement_request.state == ReimbursementRequestState.APPROVED


def test_handle_rx_auto_processed_reimbursement_request_state_change__success_existing_dtr_claim_creates_hra(
    rx_reimbursement_request,
    qualified_direct_payment_enabled_wallet,
    get_employee_activity_response,
    mocked_auto_processed_claim_response,
    member_health_plan_for_wallet,
):
    """
    A wallet with a DTR reimbursement claim in Alegeus
    Should GET existing claims from Alegeus and not update RR but instead submit the missing HRA.
    HDHP wallet
    """
    mock_activity_response = requests.Response()
    mock_activity_response.status_code = 200
    mock_activity_response.json = lambda: get_employee_activity_response(
        tracking_number="123abc", account_type_code="DTR"
    )
    ReimbursementClaimFactory.create(
        alegeus_claim_id="123abc",
        alegeus_claim_key=1,
        status="APPROVED",
        reimbursement_request=rx_reimbursement_request,
        amount=100,
    )
    mock_post_response = mocked_auto_processed_claim_response(
        200, "Direct Deposit", 100
    )
    reimbursement_request = rx_reimbursement_request
    qualified_direct_payment_enabled_wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
        False
    )
    member_health_plan_for_wallet.employer_health_plan.is_hdhp = True
    reimbursement_request.state = ReimbursementRequestState.PENDING
    CostBreakdownFactory.create(
        reimbursement_request_id=reimbursement_request.id,
        total_employer_responsibility=100,
        total_member_responsibility=100,
        deductible=100,
    )
    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=[mock_activity_response, mock_post_response],
    ) as mock_request, patch(
        "braze.client.BrazeClient._make_request"
    ) as mock_send_event:
        handle_rx_auto_processed_reimbursement_request_state_change(
            reimbursement_request
        )
        assert mock_request.call_count == 2
        assert mock_send_event.call_count == 1
        assert len(reimbursement_request.claims) == 2


def test_handle_rx_auto_processed_reimbursement_request_state_change__success_existing_claims(
    rx_reimbursement_request,
    qualified_direct_payment_enabled_wallet,
    get_employee_activity_response,
    member_health_plan_for_wallet,
):
    """
    An hdhp wallet with a DTR and HRA reimbursement claim in Alegeus
    Should GET existing claims from Alegeus does not submit but syncs and updates RR.
    """
    dtr = get_employee_activity_response(
        tracking_number="123abc", account_type_code="DTR"
    )
    hra = get_employee_activity_response(
        tracking_number="123def", account_type_code="HRA"
    )
    claims = dtr + hra
    mock_activity_response = requests.Response()
    mock_activity_response.status_code = 200
    mock_activity_response.json = lambda: claims

    qualified_direct_payment_enabled_wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
        False
    )
    member_health_plan_for_wallet.employer_health_plan.is_hdhp = True

    ReimbursementClaimFactory.create(
        alegeus_claim_id="123abc",
        alegeus_claim_key=1,
        status="APPROVED",
        reimbursement_request=rx_reimbursement_request,
        amount=100,
    )
    ReimbursementClaimFactory.create(
        alegeus_claim_id="123def",
        alegeus_claim_key=1,
        status="APPROVED",
        reimbursement_request=rx_reimbursement_request,
        amount=100,
    )
    reimbursement_request = rx_reimbursement_request
    reimbursement_request.state = ReimbursementRequestState.PENDING
    CostBreakdownFactory.create(
        reimbursement_request_id=reimbursement_request.id,
        total_employer_responsibility=100,
        total_member_responsibility=100,
        deductible=100,
    )
    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        return_value=mock_activity_response,
    ) as mock_request, patch(
        "braze.client.BrazeClient._make_request"
    ) as mock_send_event:
        handle_rx_auto_processed_reimbursement_request_state_change(
            reimbursement_request
        )
        assert mock_request.call_count == 1
        assert mock_send_event.call_count == 1
        assert len(reimbursement_request.claims) == 2
        assert reimbursement_request.state == ReimbursementRequestState.APPROVED


def test_handle_rx_auto_processed_reimbursement_request_state_change__failure_get_employee_activity(
    rx_reimbursement_request,
    qualified_direct_payment_enabled_wallet,
    get_employee_activity_response,
):
    """
    A wallet with existing claims.  Alegeus Get Claims fails - RR updates to Approved
    """
    mock_response = requests.Response()
    mock_response.status_code = 400
    mock_response.json = lambda: {}
    ReimbursementClaimFactory.create(
        alegeus_claim_id="123abc",
        alegeus_claim_key=1,
        status="pending",
        reimbursement_request=rx_reimbursement_request,
        amount=100,
    )
    reimbursement_request = rx_reimbursement_request
    reimbursement_request.state = ReimbursementRequestState.PENDING
    CostBreakdownFactory.create(
        reimbursement_request_id=reimbursement_request.id,
        total_employer_responsibility=100,
        total_member_responsibility=100,
    )
    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        return_value=mock_response,
    ) as mock_request, patch(
        "braze.client.BrazeClient._make_request"
    ) as mock_send_event:
        handle_rx_auto_processed_reimbursement_request_state_change(
            reimbursement_request
        )
        assert mock_request.call_count == 1
        assert mock_send_event.call_count == 1
        assert len(reimbursement_request.claims) == 1
        assert reimbursement_request.state == ReimbursementRequestState.APPROVED


def test_handle_rx_auto_processed_reimbursement_request_state_change__claim_deleted_in_alegeus(
    rx_reimbursement_request,
    qualified_direct_payment_enabled_wallet,
    get_employee_activity_response,
    mocked_auto_processed_claim_response,
):
    """
    A wallet with existing reimbursement claims but none in Alegeus
    Should create a claim in Alegeus
    A ReimbursementClaim should be created and attached to the wallet.
    """
    mock_activity_response = requests.Response()
    mock_activity_response.status_code = 200
    mock_activity_response.json = lambda: get_employee_activity_response(
        tracking_number="OTHER_TRACKING"
    )

    mock_post_response = mocked_auto_processed_claim_response(
        200, "Direct Deposit", 100
    )
    ReimbursementClaimFactory.create(
        alegeus_claim_id="123abc",
        alegeus_claim_key=1,
        status="pending",
        reimbursement_request=rx_reimbursement_request,
        amount=100,
    )
    reimbursement_request = rx_reimbursement_request
    reimbursement_request.state = ReimbursementRequestState.PENDING
    CostBreakdownFactory.create(
        reimbursement_request_id=reimbursement_request.id,
        total_employer_responsibility=100,
        total_member_responsibility=100,
    )
    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        side_effect=[mock_activity_response, mock_post_response],
    ) as mock_request, patch(
        "braze.client.BrazeClient._make_request"
    ) as mock_send_event:
        handle_rx_auto_processed_reimbursement_request_state_change(
            reimbursement_request
        )
        assert mock_request.call_count == 2
        assert mock_send_event.call_count == 1
        assert len(reimbursement_request.claims) == 1


def test_handle_rx_auto_processed_reimbursement_request_state_change__failure_post_claim(
    mocked_auto_processed_claim_response,
    rx_reimbursement_request,
):
    """
    A wallet with no current reimbursement claims in Alegeus
    Does not create a claim but set the reimbursement request back to New.
    """

    mock_response = mocked_auto_processed_claim_response(500, "Direct Deposit", 100)
    reimbursement_request = rx_reimbursement_request
    reimbursement_request.state = ReimbursementRequestState.PENDING
    CostBreakdownFactory.create(
        reimbursement_request_id=reimbursement_request.id,
        total_employer_responsibility=100,
        total_member_responsibility=100,
    )
    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        return_value=mock_response,
    ) as mock_request, patch(
        "braze.client.BrazeClient._make_request"
    ) as mock_send_event:
        handle_rx_auto_processed_reimbursement_request_state_change(
            reimbursement_request
        )
        assert mock_request.call_count == 1
        assert mock_send_event.call_count == 0
        assert len(reimbursement_request.claims) == 0
        assert reimbursement_request.state == ReimbursementRequestState.NEW


def test_handle_rx_auto_processed_reimbursement_request_state_change__failure_missing_cost_breakdown(
    mocked_auto_processed_claim_response,
    rx_reimbursement_request,
):
    """
    A wallet with no current reimbursement claims in Alegeus
    Does not create a claim but set the reimbursement request back to New.
    """

    mock_response = mocked_auto_processed_claim_response(500, "Direct Deposit", 100)
    reimbursement_request = rx_reimbursement_request
    reimbursement_request.state = ReimbursementRequestState.PENDING
    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        return_value=mock_response,
    ) as mock_request, patch(
        "braze.client.BrazeClient._make_request"
    ) as mock_send_event:
        handle_rx_auto_processed_reimbursement_request_state_change(
            reimbursement_request
        )
        assert mock_request.call_count == 0
        assert mock_send_event.call_count == 0
        assert len(reimbursement_request.claims) == 0
        assert reimbursement_request.state == ReimbursementRequestState.NEW


@pytest.mark.parametrize(
    "da_enabled, member_responsibility, accumulations",
    [(True, 100, 1), (True, 0, 0), (False, 100, 0)],
)
def test_handle_rx_auto_processed_reimbursement_request_state_change__creates_accumulation(
    rx_reimbursement_request,
    qualified_direct_payment_enabled_wallet,
    mocked_auto_processed_claim_response,
    member_health_plan_for_wallet,
    da_enabled,
    member_responsibility,
    accumulations,
):
    """
    A wallet with no current reimbursement claims in Alegeus
    A ReimbursementClaim should be created and attached to the wallet.
    """
    mock_response = mocked_auto_processed_claim_response(200, "Direct Deposit", 50)
    reimbursement_request = rx_reimbursement_request
    reimbursement_request.state = ReimbursementRequestState.PENDING
    reimbursement_request.wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
        da_enabled
    )
    CostBreakdownFactory.create(
        reimbursement_request_id=reimbursement_request.id,
        total_employer_responsibility=100,
        total_member_responsibility=member_responsibility,
    )
    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        return_value=mock_response,
    ) as mock_request, patch(
        "braze.client.BrazeClient._make_request"
    ) as mock_send_event:
        handle_rx_auto_processed_reimbursement_request_state_change(
            reimbursement_request
        )
        assert mock_request.call_count == 1
        assert mock_send_event.call_count == 1
        assert len(reimbursement_request.claims) == 1
        assert reimbursement_request.state == ReimbursementRequestState.APPROVED

        accumulation_mapping = AccumulationTreatmentMapping.query.filter_by(
            reimbursement_request_id=reimbursement_request.id
        ).all()
        assert len(accumulation_mapping) == accumulations


def test_handle_rx_auto_processed_reimbursement_request_state_change__existing_non_refunded_mappings(
    rx_reimbursement_request,
    qualified_direct_payment_enabled_wallet,
    mocked_auto_processed_claim_response,
):
    """
    Tests error handling when existing RX auto-processed accumulation mappings exist
    but are not all in REFUNDED status.
    """
    mock_response = mocked_auto_processed_claim_response(200, "Direct Deposit", 50)
    reimbursement_request = rx_reimbursement_request
    reimbursement_request.state = ReimbursementRequestState.PENDING
    reimbursement_request.wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
        True
    )

    # Create an existing mapping that is not in REFUNDED status
    AccumulationTreatmentMappingFactory.create(
        reimbursement_request_id=reimbursement_request.id,
        treatment_accumulation_status=TreatmentAccumulationStatus.PAID,
    )

    CostBreakdownFactory.create(
        reimbursement_request_id=reimbursement_request.id,
        total_employer_responsibility=100,
        total_member_responsibility=100,
    )

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        return_value=mock_response,
    ) as mock_request, patch(
        "braze.client.BrazeClient._make_request"
    ) as mock_send_event:
        messages = handle_rx_auto_processed_reimbursement_request_state_change(
            reimbursement_request
        )
        assert mock_request.call_count == 1
        assert mock_send_event.call_count == 1

        # Verify reimbursement request was still processed
        assert len(reimbursement_request.claims) == 1
        assert reimbursement_request.state == ReimbursementRequestState.APPROVED

        # Verify error message was returned
        assert isinstance(messages[-1], FlashMessage)
        assert messages[-1].category == FlashMessageCategory.ERROR
        assert "Failed to create an accumulation mapping record" in messages[-1].message

        # Verify no new accumulation mapping was created
        accumulation_mappings = AccumulationTreatmentMapping.query.filter_by(
            reimbursement_request_id=reimbursement_request.id
        ).all()
        assert len(accumulation_mappings) == 1
        assert (
            accumulation_mappings[0].treatment_accumulation_status
            == TreatmentAccumulationStatus.PAID
        )


def test_handle_rx_auto_processed_reimbursement_request_state_change__existing_refunded_mappings(
    rx_reimbursement_request,
    qualified_direct_payment_enabled_wallet,
    mocked_auto_processed_claim_response,
    member_health_plan_for_wallet,
):
    """
    Tests that when existing RX auto-processed accumulation mappings are all in REFUNDED status,
    a new mapping can be created successfully.
    """
    mock_response = mocked_auto_processed_claim_response(200, "Direct Deposit", 50)
    reimbursement_request = rx_reimbursement_request
    reimbursement_request.state = ReimbursementRequestState.PENDING
    reimbursement_request.wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
        True
    )

    # Create an existing mapping that is in REFUNDED status
    AccumulationTreatmentMappingFactory.create(
        reimbursement_request_id=reimbursement_request.id,
        treatment_accumulation_status=TreatmentAccumulationStatus.REFUNDED,
    )

    CostBreakdownFactory.create(
        reimbursement_request_id=reimbursement_request.id,
        total_employer_responsibility=100,
        total_member_responsibility=100,
    )

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
        return_value=mock_response,
    ) as mock_request, patch(
        "braze.client.BrazeClient._make_request"
    ) as mock_send_event:
        handle_rx_auto_processed_reimbursement_request_state_change(
            reimbursement_request
        )

        assert mock_request.call_count == 1
        assert mock_send_event.call_count == 1

        # Verify reimbursement request was still processed
        assert len(reimbursement_request.claims) == 1
        assert reimbursement_request.state == ReimbursementRequestState.APPROVED

        # Verify new accumulation mapping was created
        accumulation_mappings = AccumulationTreatmentMapping.query.filter_by(
            reimbursement_request_id=reimbursement_request.id
        ).all()
        assert len(accumulation_mappings) == 2

        statuses = [m.treatment_accumulation_status for m in accumulation_mappings]
        assert TreatmentAccumulationStatus.REFUNDED in statuses
        assert TreatmentAccumulationStatus.PAID in statuses
