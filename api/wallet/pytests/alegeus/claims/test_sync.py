import datetime
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from requests import Response

from cost_breakdown.pytests.factories import CostBreakdownFactory
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from utils.payments import convert_dollars_to_cents
from utils.random_string import generate_random_string
from wallet.alegeus_api import format_date_from_string_to_datetime
from wallet.models.constants import (
    AlegeusAccountType,
    AlegeusClaimStatus,
    CategoryRuleAccessLevel,
    CategoryRuleAccessSource,
    CostSharingCategory,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
    ReimbursementRequestType,
    WalletState,
)
from wallet.models.reimbursement import (
    ReimbursementAccount,
    ReimbursementClaim,
    ReimbursementPlan,
)
from wallet.models.reimbursement_wallet_credit import ReimbursementCycleCredits
from wallet.pytests.factories import (
    ReimbursementAccountFactory,
    ReimbursementClaimFactory,
    ReimbursementRequestFactory,
    ReimbursementWalletAllowedCategorySettingsFactory,
    ReimbursementWalletFactory,
)
from wallet.utils.alegeus.claims.sync import (
    WalletClaims,
    _add_back_hra_to_alegeus_wallet_balance,
    _should_deduct_credits,
    get_account_type_code,
    get_wallets_with_pending_claims,
    sync_pending_claims,
)
from wallet.utils.alegeus.common import get_all_alegeus_sync_claims_user_wallets
from wallet.utils.payment_ops import SyncAccountSccPaymentOpsZendeskTicket


@pytest.fixture(scope="module")
def feature_flag_on():
    with patch(
        "wallet.utils.alegeus.claims.sync.bool_variation", return_value=True
    ) as feature_flag:
        yield feature_flag


@pytest.fixture(scope="function")
def wallet_with_pending_claims(qualified_alegeus_wallet_hra):
    # Note, ReimbursementRequests with state as either PENDING or APPROVED will still need to be synced with alegeus
    # and fall under what is meant in the method signature as a "pending" claim
    # There are 4 cases for which a request / claim counts as pending based on:
    #     the ReimbursementRequest state and the claim status we get back from alegeus.

    category = qualified_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories[
        1  # first is the default, second is the one created by pending_alegeus_wallet_hra
    ].reimbursement_request_category

    # case 1 of a pending claim:
    # ReimbursementRequest.state = PENDING,
    # ReimbursementClaim.status = "needs receipt"
    request_1 = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hra,
        category=category,
        state=ReimbursementRequestState.PENDING,
        amount=100_00,
    )
    ReimbursementClaimFactory.create(
        alegeus_claim_id="123abc",
        status=AlegeusClaimStatus.NEEDS_RECEIPT.value,
        reimbursement_request=request_1,
        alegeus_claim_key=1,
        amount=100.00,
    )

    # case 2 of a pending claim:
    # ReimbursementRequest.state = PENDING,
    # ReimbursementClaim.status = "submitted - under review"
    request_2 = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hra,
        category=category,
        state=ReimbursementRequestState.PENDING,
        amount=250_20,
    )
    ReimbursementClaimFactory.create(
        alegeus_claim_id="456def",
        status=AlegeusClaimStatus.SUBMITTED_UNDER_REVIEW.value,
        reimbursement_request=request_2,
        alegeus_claim_key=2,
        amount=250.20,
    )

    # case 3 of a pending claim:
    # ReimbursementRequest.state = APPROVED,
    # ReimbursementClaim.status = "approved"
    request_3 = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hra,
        category=category,
        state=ReimbursementRequestState.APPROVED,
        amount=500_00,
    )
    ReimbursementClaimFactory.create(
        alegeus_claim_id="789ghi",
        status=AlegeusClaimStatus.APPROVED.value,
        reimbursement_request=request_3,
        alegeus_claim_key=3,
        amount=500.00,
    )

    # case 4 of a pending claim:
    # ReimbursementRequest.state = APPROVED,
    # ReimbursementClaim.status = "partially approved"
    request_4 = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hra,
        category=category,
        state=ReimbursementRequestState.APPROVED,
    )
    ReimbursementClaimFactory.create(
        alegeus_claim_id="bibidi",
        status=AlegeusClaimStatus.PARTIALLY_APPROVED.value,
        reimbursement_request=request_4,
        alegeus_claim_key=4,
    )

    # case 5 of a pending claim:
    # ReimbursementRequest.state = APPROVED,
    # ReimbursementClaim.status = "partially approved"
    request_5 = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hra,
        category=category,
        state=ReimbursementRequestState.APPROVED,
    )
    ReimbursementClaimFactory.create(
        alegeus_claim_id="bobidi",
        status=AlegeusClaimStatus.PARTIALLY_APPROVED.value,
        reimbursement_request=request_5,
        alegeus_claim_key=4,
    )

    # case 6 of a pending claim:
    # ReimbursementRequest.state = APPROVED,
    # ReimbursementClaim.status = "partially approved"
    request_6 = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hra,
        category=category,
        state=ReimbursementRequestState.APPROVED,
    )
    ReimbursementClaimFactory.create(
        alegeus_claim_id="boo",
        status=AlegeusClaimStatus.PARTIALLY_APPROVED.value,
        reimbursement_request=request_6,
        alegeus_claim_key=6,
    )

    # case 7 of a pending claim:
    # ReimbursementRequest.state = PENDING,
    # ReimbursementRequest.type = DIRECT_BILLING,
    # ReimbursementClaim.status = "needs receipt"
    request_7 = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hra,
        category=category,
        state=ReimbursementRequestState.PENDING,
        reimbursement_type=ReimbursementRequestType.DIRECT_BILLING,
    )

    ReimbursementClaimFactory.create(
        alegeus_claim_id=generate_random_string(8),
        status=AlegeusClaimStatus.NEEDS_RECEIPT.value,
        reimbursement_request=request_7,
        alegeus_claim_key=7,
        amount=100.00,
    )

    # case 8 of a pending claim:
    # ReimbursementRequest.state = APPROVED,
    # ReimbursementRequest.type = DIRECT_BILLING,
    # ReimbursementClaim.status = "partially approved"
    request_8 = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hra,
        category=category,
        state=ReimbursementRequestState.APPROVED,
    )
    ReimbursementClaimFactory.create(
        alegeus_claim_id=generate_random_string(8),
        status=AlegeusClaimStatus.PARTIALLY_APPROVED.value,
        reimbursement_request=request_8,
        alegeus_claim_key=8,
    )

    return qualified_alegeus_wallet_hra


@pytest.fixture(scope="function")
def wallet_with_no_pending_claims(qualified_alegeus_wallet_hra):
    # Note, ReimbursementRequests with state as either NEW, DENIED, FAILED, or REIMBURSED will NOT sync with alegeus

    category = qualified_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories[
        1  # first is the default, second is the one created by pending_alegeus_wallet_hra
    ].reimbursement_request_category

    # case 1 of a NOT pending claim:
    # ReimbursementRequest.state = NEW,
    # No ReimbursementClaim should exist since it's only created when a ReimbursementRequest is changed to PENDING"
    ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hra,
        category=category,
        state=ReimbursementRequestState.NEW,
    )

    # case 2 of a NOT pending claim:
    # ReimbursementRequest.state = REIMBURSED,
    # ReimbursementClaim.status = "paid"
    request_2 = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hra,
        category=category,
        state=ReimbursementRequestState.REIMBURSED,
    )
    ReimbursementClaimFactory.create(
        alegeus_claim_id="456def",
        status=AlegeusClaimStatus.PAID.value,
        reimbursement_request=request_2,
    )

    # case 3 of a NOT pending claim:
    # ReimbursementRequest.state = DENIED,
    # ReimbursementClaim.status = "denied"
    request_3 = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hra,
        category=category,
        state=ReimbursementRequestState.DENIED,
    )
    ReimbursementClaimFactory.create(
        alegeus_claim_id="789ghi",
        status=AlegeusClaimStatus.DENIED.value,
        reimbursement_request=request_3,
    )

    # case 4 of a NOT pending claim:
    # ReimbursementRequest.state = FAILED,
    # No ReimbursementClaim needed here, as this request state is determined manually by the Operations team
    ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hra,
        category=category,
        state=ReimbursementRequestState.FAILED,
    )

    return qualified_alegeus_wallet_hra


def test_sync_pending_claims__status_flow(wallet_with_pending_claims):
    """
    Testing syncing of reimbursement requests / claims
    All of these are valid for a sync
    """
    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: [
        {
            "Status": "Submitted - Under Review",
            "StatusCode": 2,
            "TrackingNumber": "123abc",
        },
        {
            "Status": "Approved",
            "StatusCode": 2,
            "TrackingNumber": "456def",
        },
        {
            "Status": "Paid",
            "StatusCode": 2,
            "TrackingNumber": "789ghi",
        },
        {
            "Status": "Paid",
            "StatusCode": 2,
            "TrackingNumber": "bibidi",
        },
        {
            "Status": "Claim Adjusted-Overpayment",
            "StatusCode": 2,
            "TrackingNumber": "bobidi",
        },
        {
            "Status": "Partially Paid",
            "StatusCode": 2,
            "TrackingNumber": "boo",
        },
    ]

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_activity"
    ) as mock_request, patch("utils.braze_events.braze.send_event") as mock_send_event:
        mock_request.return_value = mock_response

        wallet_to_claims = get_wallets_with_pending_claims([wallet_with_pending_claims])

        case_1_claim_before_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id="123abc"
        ).one()
        case_1_claim_before_sync_status = case_1_claim_before_sync.status
        case_1_request_state = case_1_claim_before_sync.reimbursement_request.state

        case_2_claim_before_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id="456def"
        ).one()
        case_2_claim_before_sync_status = case_2_claim_before_sync.status
        case_2_request_state = case_2_claim_before_sync.reimbursement_request.state

        case_3_claim_before_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id="789ghi"
        ).one()
        case_3_claim_before_sync_status = case_3_claim_before_sync.status
        case_3_request_state = case_3_claim_before_sync.reimbursement_request.state

        case_4_claim_before_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id="bibidi"
        ).one()
        case_4_claim_before_sync_status = case_4_claim_before_sync.status
        case_4_request_state = case_4_claim_before_sync.reimbursement_request.state

        case_5_claim_before_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id="bobidi"
        ).one()
        case_5_claim_before_sync_status = case_5_claim_before_sync.status
        case_5_request_state = case_5_claim_before_sync.reimbursement_request.state

        case_6_claim_before_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id="boo"
        ).one()
        case_6_claim_before_sync_status = case_6_claim_before_sync.status
        case_6_request_state = case_6_claim_before_sync.reimbursement_request.state

        sync_pending_claims(wallet_to_claims)

        assert mock_send_event.call_count == 5  # claim 1 does not change state

        # Test successful sync for case 1 of a pending claim:
        case_1_claim_after_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id="123abc"
        ).one()

        assert (
            case_1_claim_before_sync_status.upper()
            == AlegeusClaimStatus.NEEDS_RECEIPT.value
        )
        assert case_1_request_state == ReimbursementRequestState.PENDING
        assert (
            case_1_claim_after_sync.status.upper()
            == AlegeusClaimStatus.SUBMITTED_UNDER_REVIEW.value
        )
        assert (
            case_1_claim_after_sync.reimbursement_request.state
            == ReimbursementRequestState.PENDING
        )

        # Test successful sync for case 2 of a pending claim:
        case_2_claim_after_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id="456def"
        ).one()

        assert (
            case_2_claim_before_sync_status.upper()
            == AlegeusClaimStatus.SUBMITTED_UNDER_REVIEW.value
        )
        assert case_2_request_state == ReimbursementRequestState.PENDING
        assert (
            case_2_claim_after_sync.status.upper() == AlegeusClaimStatus.APPROVED.value
        )
        assert (
            case_2_claim_after_sync.reimbursement_request.state
            == ReimbursementRequestState.APPROVED
        )
        assert (
            mock_send_event.call_args_list[0].kwargs["event_name"]
            == "wallet_reimbursement_state_approved"
        )

        # Test successful sync for case 3 of a pending claim:
        case_3_claim_after_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id="789ghi"
        ).one()

        assert (
            case_3_claim_before_sync_status.upper() == AlegeusClaimStatus.APPROVED.value
        )
        assert case_3_request_state == ReimbursementRequestState.APPROVED
        assert case_3_claim_after_sync.status.upper() == AlegeusClaimStatus.PAID.value
        assert (
            case_3_claim_after_sync.reimbursement_request.state
            == ReimbursementRequestState.REIMBURSED
        )
        assert (
            mock_send_event.call_args_list[1].kwargs["event_name"]
            == "wallet_reimbursement_state_reimbursed"
        )

        # Test successful sync for case 4 of a pending claim
        case_4_claim_after_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id="bibidi"
        ).one()

        assert (
            case_4_claim_before_sync_status.upper()
            == AlegeusClaimStatus.PARTIALLY_APPROVED.value
        )
        assert case_4_request_state == ReimbursementRequestState.APPROVED
        assert case_4_claim_after_sync.status.upper() == AlegeusClaimStatus.PAID.value
        assert (
            case_4_claim_after_sync.reimbursement_request.state
            == ReimbursementRequestState.REIMBURSED
        )
        assert (
            mock_send_event.call_args_list[2].kwargs["event_name"]
            == "wallet_reimbursement_state_reimbursed"
        )

        # Test successful sync for case 5 of a pending claim
        case_5_claim_after_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id="bobidi"
        ).one()

        assert (
            case_5_claim_before_sync_status.upper()
            == AlegeusClaimStatus.PARTIALLY_APPROVED.value
        )
        assert case_5_request_state == ReimbursementRequestState.APPROVED
        assert (
            case_5_claim_after_sync.status.upper()
            == AlegeusClaimStatus.CLAIM_ADJUSTED_OVERPAYMENT.value
        )
        assert (
            case_5_claim_after_sync.reimbursement_request.state
            == ReimbursementRequestState.REIMBURSED
        )
        assert (
            mock_send_event.call_args_list[3].kwargs["event_name"]
            == "wallet_reimbursement_state_reimbursed"
        )

        # Test successful sync for case 6 of a pending claim
        case_6_claim_after_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id="boo"
        ).one()

        assert (
            case_6_claim_before_sync_status.upper()
            == AlegeusClaimStatus.PARTIALLY_APPROVED.value
        )
        assert case_6_request_state == ReimbursementRequestState.APPROVED
        assert (
            case_6_claim_after_sync.status.upper()
            == AlegeusClaimStatus.PARTIALLY_PAID.value
        )
        assert (
            case_6_claim_after_sync.reimbursement_request.state
            == ReimbursementRequestState.REIMBURSED
        )
        assert (
            mock_send_event.call_args_list[4].kwargs["event_name"]
            == "wallet_reimbursement_state_reimbursed"
        )


def test_sync_pending_claims__failure_get_employee_activity(
    wallet_with_pending_claims,
):
    mock_response = Response()
    mock_response.status_code = 418
    mock_response.json = lambda: {}

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_activity"
    ) as mock_request, patch("utils.braze_events.braze.send_event") as mock_send_event:
        mock_request.return_value = mock_response

        wallets_to_claims = get_wallets_with_pending_claims(
            [wallet_with_pending_claims]
        )

        case_1_claim_before_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id="123abc"
        ).one()
        case_1_claim_before_sync_status = case_1_claim_before_sync.status
        case_1_before_request_state = (
            case_1_claim_before_sync.reimbursement_request.state
        )

        case_2_claim_before_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id="456def"
        ).one()
        case_2_claim_before_sync_status = case_2_claim_before_sync.status
        case_2_before_request_state = (
            case_2_claim_before_sync.reimbursement_request.state
        )

        case_3_claim_before_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id="789ghi"
        ).one()
        case_3_claim_before_sync_status = case_3_claim_before_sync.status
        case_3_before_request_state = (
            case_3_claim_before_sync.reimbursement_request.state
        )

        case_4_claim_before_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id="bibidi"
        ).one()
        case_4_claim_before_sync_status = case_4_claim_before_sync.status
        case_4_before_request_state = (
            case_4_claim_before_sync.reimbursement_request.state
        )

        sync_pending_claims(wallets_to_claims)

        assert mock_send_event.call_count == 0

        # Test failure sync for case 1 of a pending claim:
        case_1_claim_after_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id="123abc"
        ).one()

        assert case_1_claim_before_sync_status == AlegeusClaimStatus.NEEDS_RECEIPT.value
        assert case_1_before_request_state == ReimbursementRequestState.PENDING
        assert case_1_claim_after_sync.status == case_1_claim_before_sync_status
        assert (
            case_1_claim_after_sync.reimbursement_request.state
            == case_1_before_request_state
        )

        # Test successful sync for case 2 of a pending claim:
        case_2_claim_after_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id="456def"
        ).one()

        assert (
            case_2_claim_before_sync_status
            == AlegeusClaimStatus.SUBMITTED_UNDER_REVIEW.value
        )
        assert case_2_before_request_state == ReimbursementRequestState.PENDING
        assert case_2_claim_after_sync.status == case_2_claim_before_sync_status
        assert (
            case_2_claim_after_sync.reimbursement_request.state
            == case_2_before_request_state
        )

        # Test successful sync for case 3 of a pending claim:
        case_3_claim_after_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id="789ghi"
        ).one()

        assert case_3_claim_before_sync_status == AlegeusClaimStatus.APPROVED.value
        assert case_3_before_request_state == ReimbursementRequestState.APPROVED
        assert case_3_claim_after_sync.status == case_3_claim_before_sync_status
        assert (
            case_3_claim_after_sync.reimbursement_request.state
            == case_3_before_request_state
        )

        # Test successful sync for case 4 of a pending claim
        case_4_claim_after_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id="bibidi"
        ).one()

        assert (
            case_4_claim_before_sync_status
            == AlegeusClaimStatus.PARTIALLY_APPROVED.value
        )
        assert case_4_before_request_state == ReimbursementRequestState.APPROVED
        assert case_4_claim_after_sync.status == case_4_claim_before_sync_status
        assert (
            case_4_claim_after_sync.reimbursement_request.state
            == case_4_before_request_state
        )


def test_sync_pending_claim__invalid_status(
    wallet_with_pending_claims,
):
    """
    Tests that if we receive an invalid or unknown status from alegeus we will not update the
    ReimbursementRequest.state or ReimbursementClaim.status
    """
    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: [
        {
            "Status": "Unknown status from Alegeus",
            "StatusCode": 2,
            "TrackingNumber": "123abc",
        },
    ]

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_activity"
    ) as mock_request, patch("utils.braze_events.braze.send_event") as mock_send_event:
        mock_request.return_value = mock_response

        wallets_with_pending_claims = get_wallets_with_pending_claims(
            [wallet_with_pending_claims]
        )

        case_1_claim_before_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id="123abc"
        ).one()
        case_1_claim_before_sync_status = case_1_claim_before_sync.status
        case_1_before_request_state = (
            case_1_claim_before_sync.reimbursement_request.state
        )

        sync_pending_claims(wallets_with_pending_claims)

        assert mock_send_event.call_count == 0

        # Test no sync occurs for case 1 of a pending claim:
        case_1_claim_after_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id="123abc"
        ).one()

        assert case_1_claim_before_sync_status == AlegeusClaimStatus.NEEDS_RECEIPT.value
        assert case_1_before_request_state == ReimbursementRequestState.PENDING
        assert case_1_claim_after_sync.status == case_1_claim_before_sync_status
        assert (
            case_1_claim_after_sync.reimbursement_request.state
            == case_1_before_request_state
        )


def test_sync_no_pending_claims(wallet_with_no_pending_claims):
    """
    Tests that we will not sync ReimbursementRequests / ReimbursementClaims that do not fall under the pending criteria.
    All of these should not be valid for a sync and should not trigger any requests to Alegeus.
    """
    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_activity"
    ) as mock_request:
        wallets_with_pending_claims = get_wallets_with_pending_claims(
            [wallet_with_no_pending_claims]
        )

        sync_pending_claims(wallets_with_pending_claims)

        assert mock_request.call_count == 0


def test_sync_claim_not_in_alegeus(wallet_with_pending_claims):
    """
    Tests that Claims that were submitted to Alegeus
    but were deleted by Alegeus -- are also deleted in our system. This should be reflected by
    1. The response from Alegeus should not contain any matching claim for that alegeus_claim_id / "TrackingNumber"
    2. Syncing that claim should result in deleting the ReimbursementClaim that is linked to a
       Pending ReimbursementRequest and..
    3. Resetting that ReimbursementRequest back to state = 'NEW'
    """
    claim_1_alegeus_id = "123abc"
    claim_2_alegeus_id = "456def"
    claim_3_alegeus_id = "789ghi"
    claim_4_alegeus_id = "bibidi"

    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: [
        {
            "Status": "Submitted - Under Review",
            "StatusCode": 2,
            "TrackingNumber": claim_1_alegeus_id,
        },
        {
            "Status": "Approved",
            "StatusCode": 2,
            "TrackingNumber": claim_2_alegeus_id,
        },
    ]

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_activity"
    ) as mock_request:
        mock_request.return_value = mock_response

        wallet_to_claims = get_wallets_with_pending_claims([wallet_with_pending_claims])

        claim_1_before_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id=claim_1_alegeus_id
        ).one()

        request_1 = claim_1_before_sync.reimbursement_request

        claim_2_before_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id=claim_2_alegeus_id
        ).one()

        request_2 = claim_2_before_sync.reimbursement_request

        claim_3_before_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id=claim_3_alegeus_id
        ).one()

        request_3 = claim_3_before_sync.reimbursement_request

        claim_4_before_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id=claim_4_alegeus_id
        ).one()

        request_4 = claim_4_before_sync.reimbursement_request

        sync_pending_claims(wallet_to_claims)

        assert ReimbursementClaim.query.filter_by(
            alegeus_claim_id=claim_1_alegeus_id
        ).one()

        assert request_1.state != ReimbursementRequestState.NEW

        assert ReimbursementClaim.query.filter_by(
            alegeus_claim_id=claim_2_alegeus_id
        ).one()

        assert request_2.state != ReimbursementRequestState.NEW

        assert not ReimbursementClaim.query.filter_by(
            alegeus_claim_id=claim_3_alegeus_id
        ).one_or_none()

        assert request_3.state == ReimbursementRequestState.NEW

        assert not ReimbursementClaim.query.filter_by(
            alegeus_claim_id=claim_4_alegeus_id
        ).one_or_none()

        assert request_4.state == ReimbursementRequestState.NEW


def test_denied_claims_set_request_as_denied(wallet_with_pending_claims):
    """
    Tests that Claims that were submitted to Alegeus but were Denied by Alegeus,
    set the Request back to DENIED. This should be reflected by
    1. The response from Alegeus should contain the matching claim for that alegeus_claim_id / "TrackingNumber"
       and have status for it as Denied
    2. Syncing that claim should result in still saving the ReimbursementClaim and
    3. Resetting that ReimbursementRequest back to state = 'DENIED'
    """
    claim_1_alegeus_id = "123abc"
    claim_2_alegeus_id = "456def"

    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: [
        {
            "Status": "Denied",
            "StatusCode": 2,
            "TrackingNumber": claim_1_alegeus_id,
        },
        {
            "Status": "Approved",
            "StatusCode": 2,
            "TrackingNumber": claim_2_alegeus_id,
        },
    ]

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_activity"
    ) as mock_request, patch("utils.braze_events.braze.send_event") as mock_send_event:
        mock_request.return_value = mock_response

        wallet_to_claims = get_wallets_with_pending_claims([wallet_with_pending_claims])

        claim_1_before_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id=claim_1_alegeus_id
        ).one()

        request_1 = claim_1_before_sync.reimbursement_request

        assert request_1.state != ReimbursementRequestState.NEW

        claim_2_before_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id=claim_2_alegeus_id
        ).one()

        request_2 = claim_2_before_sync.reimbursement_request

        sync_pending_claims(wallet_to_claims)

        assert mock_send_event.call_count == 2

        assert ReimbursementClaim.query.filter_by(
            alegeus_claim_id=claim_1_alegeus_id
        ).one()

        assert request_1.state == ReimbursementRequestState.DENIED
        assert (
            mock_send_event.call_args_list[0].kwargs["event_name"]
            == "wallet_reimbursement_state_declined"
        )

        assert ReimbursementClaim.query.filter_by(
            alegeus_claim_id=claim_2_alegeus_id
        ).one()

        assert request_2.state != ReimbursementRequestState.NEW
        assert (
            mock_send_event.call_args_list[1].kwargs["event_name"]
            == "wallet_reimbursement_state_approved"
        )


def test_multiple_alegeus_claims_with_same_tracking_number(wallet_with_pending_claims):
    """
    Tests behavior for scenarios where Alegeus returns multiple Claims with the same Tracking Number.
    For this case, Alegeus can Deny a Claim, then create a new Claim with the same tracking number ID --
    Only now the new Claim is Partially Approved.
    We expect to treat the Claim as if its now Partially Approved and disregard the Denied Claim in the response.
    """
    claim_1_alegeus_id = "123abc"
    claim_2_alegeus_id = "456def"

    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: [
        {
            "Status": "Denied",
            "StatusCode": 2,
            "TrackingNumber": claim_1_alegeus_id,
        },
        {
            "Status": "Partially Approved",
            "StatusCode": 2,
            "TrackingNumber": claim_1_alegeus_id,
        },
        {
            "Status": "Denied",
            "StatusCode": 2,
            "TrackingNumber": claim_2_alegeus_id,
        },
        {
            "Status": "Partially Approved",
            "StatusCode": 2,
            "TrackingNumber": claim_2_alegeus_id,
        },
    ]

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_activity"
    ) as mock_request:
        mock_request.return_value = mock_response

        wallet_to_claims = get_wallets_with_pending_claims([wallet_with_pending_claims])

        claim_1_before_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id=claim_1_alegeus_id
        ).one()

        claim_1_before_sync.status = AlegeusClaimStatus.DENIED.value

        request_1 = claim_1_before_sync.reimbursement_request

        request_1.state = ReimbursementRequestState.NEW

        claim_2_before_sync = ReimbursementClaim.query.filter_by(
            alegeus_claim_id=claim_2_alegeus_id
        ).one()

        request_2 = claim_2_before_sync.reimbursement_request

        assert request_2.state != ReimbursementRequestState.NEW

        sync_pending_claims(wallet_to_claims)

        assert request_1.state == ReimbursementRequestState.APPROVED

        assert request_2.state == ReimbursementRequestState.APPROVED


@pytest.mark.parametrize(
    argnames="alegeus_claim_id, alegeus_claim_amount, alegeus_claim_key, expected_claim_amount, expected_claim_updated",
    argvalues=[
        # It's important to test this with and without cents, because the float-to-decimal
        # conversion is trivial for whole numbers, but can very in precision when there are cents.
        # Decimal(1) -> Decimal('1')
        # Decimal(1.01) -> Decimal('1.0100000000000000088817841970012523233890533447265625')
        # Decimal('1.01') -> Decimal('1.01')
        ## Original Amount without cents
        # approved full amount
        ("123abc", 100.00, 10, Decimal("100.00"), True),
        # approved lower amount w/ cents
        ("123abc", 99.50, 10, Decimal("99.50"), True),
        # approved lower amount w/ 6 decimal places (how Alegeus returns amounts)
        ("123abc", 99.000000, 10, Decimal("99.00"), True),
        ("123abc", 99.440000, 10, Decimal("99.44"), True),
        # approved lower amount w/ 6 decimal places, no rounding up
        ("123abc", 99.876000, 10, Decimal("99.87"), True),
        ## Original Amount with cents
        # approved full amount w/ cents
        ("456def", 250.20, 20, Decimal("250.20"), True),
        # approved lower amount w/ cents
        ("456def", 249.50, 20, Decimal("249.50"), True),
        ## Already approved claim
        # no changes triggered (is this suddenly failing? check logic in
        # _sync_claim_and_request against your fixture's defaults)
        ("789ghi", 500.000000, 3, Decimal("500.00"), False),
    ],
)
def test_sync_pending_claims__amount_and_claim_key(
    wallet_with_pending_claims,
    alegeus_claim_id,
    alegeus_claim_amount,
    alegeus_claim_key,
    expected_claim_amount,
    expected_claim_updated,
):
    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: [
        {
            "Status": "Approved",
            "Amount": alegeus_claim_amount,
            "TrackingNumber": alegeus_claim_id,
            "ClaimKey": alegeus_claim_key,
        },
    ]

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_activity"
    ) as mock_request:
        mock_request.return_value = mock_response

        wallet_to_claims = get_wallets_with_pending_claims([wallet_with_pending_claims])

        claim = ReimbursementClaim.query.filter_by(
            alegeus_claim_id=alegeus_claim_id
        ).one()

        request = claim.reimbursement_request

        # store copy of all columns
        claim_vars = vars(claim).copy()
        del claim_vars["modified_at"]

        sync_pending_claims(wallet_to_claims)

        assert claim.amount == expected_claim_amount
        assert claim.alegeus_claim_key == alegeus_claim_key
        assert request.amount == convert_dollars_to_cents(expected_claim_amount)

        # compare copy of all columns -- this will detect a change even if the underlying values are the same
        updated_claim_vars = vars(claim).copy()
        del updated_claim_vars["modified_at"]
        if expected_claim_updated:
            assert claim_vars != updated_claim_vars
        else:
            assert claim_vars == updated_claim_vars


def test_sync_amount_revised_by_alegeus(wallet_with_pending_claims):
    claim_1_alegeus_id = "123abc"
    claim_1_amount = 19500.00
    claim_1_amount_revised = 15000.0
    claim_1_key = 10

    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: [
        {
            "Status": "Approved",
            "AccountsPaidAmount": claim_1_amount_revised,
            "Amount": claim_1_amount,
            "TrackingNumber": claim_1_alegeus_id,
            "ClaimKey": claim_1_key,
        },
    ]

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_activity"
    ) as mock_request:
        mock_request.return_value = mock_response

        wallet_to_claims = get_wallets_with_pending_claims([wallet_with_pending_claims])

        claim_1 = ReimbursementClaim.query.filter_by(
            alegeus_claim_id=claim_1_alegeus_id
        ).one()

        request_1 = claim_1.reimbursement_request

        sync_pending_claims(wallet_to_claims)

        assert claim_1.amount == claim_1_amount_revised
        assert request_1.amount == convert_dollars_to_cents(claim_1_amount_revised)


# Values used to identify categories created in the following test org, and values used in the fixtures and test cases
_FERTILITY_CATEGORY_IDX = 0
_PRESERVATION_CATEGORY_IDX = 1
_ADOPTION_CATEGORY_IDX = 2
_SURROGACY_CATEGORY_IDX = 3
_FERTILITY_ACCOUNT_KEY = 99999
_PRESERVATION_ACCOUNT_KEY = 77777
_ADOPTION_ACCOUNT_KEY = 55555
_SURROGACY_ACCOUNT_KEY = 33333
_DTR_ACCOUNT_KEY = 11111


@pytest.fixture(scope="function")
def organization_for_sync_category_expense_type_subtype(wallet_test_helper):
    """
    This is a very specific organization designed to support the many test
    cases of test_sync__category_expense_type_and_subtype.
    The fixture defines:
       * An Organization
       * An ROS with categories (lifetime, currency) for:
         - 0: Fertility (FERTILITY & PRESERVATION)
         - 1: Preservation (PRESERVATION)
         - 2: Adoption (ADOPTION)
         - 3: Surrogacy (SURROGACY)
    """

    organization = wallet_test_helper.create_organization_with_wallet_enabled(
        reimbursement_organization_parameters={
            "allowed_reimbursement_categories__no_categories": True
        }
    )
    ros = organization.reimbursement_organization_settings[0]

    start_date = datetime.date(year=2020, month=1, day=1)
    end_date = datetime.date(year=2119, month=12, day=31)
    wallet_test_helper.add_currency_benefit(
        reimbursement_organization_settings=ros,
        alegeus_account_type=AlegeusAccountType.HRA,
        alegeus_plan_id="WTOLFERT",
        start_date=start_date,
        end_date=end_date,
        category_label="Fertility",
        category_short_label="Fertility",
        expense_types=[
            ReimbursementRequestExpenseTypes.FERTILITY,
            ReimbursementRequestExpenseTypes.PRESERVATION,
        ],
        reimbursement_request_category_maximum=25_000_00,
    )
    wallet_test_helper.add_currency_benefit(
        reimbursement_organization_settings=ros,
        alegeus_account_type=AlegeusAccountType.HR2,
        alegeus_plan_id="WTOLPRES",
        start_date=start_date,
        end_date=end_date,
        category_label="Preservation",
        category_short_label="Preservation",
        expense_types=[
            ReimbursementRequestExpenseTypes.PRESERVATION,
        ],
        reimbursement_request_category_maximum=25_000_00,
    )
    wallet_test_helper.add_currency_benefit(
        reimbursement_organization_settings=ros,
        alegeus_account_type=AlegeusAccountType.HR3,
        alegeus_plan_id="WTOLADOP",
        start_date=start_date,
        end_date=end_date,
        category_label="Adoption",
        category_short_label="Adoption",
        expense_types=[
            ReimbursementRequestExpenseTypes.ADOPTION,
        ],
        reimbursement_request_category_maximum=25_000_00,
    )
    wallet_test_helper.add_currency_benefit(
        reimbursement_organization_settings=ros,
        alegeus_account_type=AlegeusAccountType.HR4,
        alegeus_plan_id="WTOLSURR",
        start_date=start_date,
        end_date=end_date,
        category_label="Surrogacy",
        category_short_label="Surrogacy",
        expense_types=[
            ReimbursementRequestExpenseTypes.SURROGACY,
        ],
        reimbursement_request_category_maximum=25_000_00,
    )

    wallet_test_helper.add_hdhp_plan(reimbursement_organization_settings=ros)

    return organization


@pytest.fixture(scope="function")
def wallet_for_test_sync_category_expense_type_subtype(
    organization_for_sync_category_expense_type_subtype, wallet_test_helper
):
    """
    Wallet for test_sync__category_expense_type_and_subtype with access
    to Fertility & Surrogacy (not Preservation or Adoption)
    """
    user = wallet_test_helper.create_user_for_organization(
        organization_for_sync_category_expense_type_subtype
    )
    wallet = wallet_test_helper.create_pending_wallet(user)

    fertility_category_assoc = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            _FERTILITY_CATEGORY_IDX
        ]
    )
    ReimbursementWalletAllowedCategorySettingsFactory.create(
        reimbursement_organization_settings_allowed_category_id=fertility_category_assoc.id,
        reimbursement_wallet_id=wallet.id,
        access_level=CategoryRuleAccessLevel.FULL_ACCESS,
        access_level_source=CategoryRuleAccessSource.NO_RULES,
    )
    fertility_plan = (
        fertility_category_assoc.reimbursement_request_category.reimbursement_plan
    )
    ReimbursementAccountFactory.create(
        wallet=wallet,
        plan=fertility_plan,
        alegeus_account_type=fertility_plan.reimbursement_account_type,
        alegeus_flex_account_key=_FERTILITY_ACCOUNT_KEY,
    )

    surrogacy_category_assoc = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            _SURROGACY_CATEGORY_IDX
        ]
    )
    ReimbursementWalletAllowedCategorySettingsFactory.create(
        reimbursement_organization_settings_allowed_category_id=surrogacy_category_assoc.id,
        reimbursement_wallet_id=wallet.id,
        access_level=CategoryRuleAccessLevel.FULL_ACCESS,
        access_level_source=CategoryRuleAccessSource.NO_RULES,
    )
    surrogacy_plan = (
        surrogacy_category_assoc.reimbursement_request_category.reimbursement_plan
    )
    ReimbursementAccountFactory.create(
        wallet=wallet,
        plan=surrogacy_plan,
        alegeus_account_type=surrogacy_plan.reimbursement_account_type,
        alegeus_flex_account_key=_SURROGACY_ACCOUNT_KEY,
    )

    dtr_plan = ReimbursementPlan.query.filter_by(alegeus_plan_id="WTODTR").one()
    ReimbursementAccountFactory.create(
        wallet=wallet,
        plan=dtr_plan,
        alegeus_account_type=dtr_plan.reimbursement_account_type,
        alegeus_flex_account_key=_DTR_ACCOUNT_KEY,
    )

    # Qualify the wallet *after* creating plans and allowed category records otherwise the
    # qualification will trigger access to all categories on the ROS by default.
    wallet_test_helper.qualify_wallet(wallet)

    return wallet


@pytest.fixture(scope="function")
def wallet_for_test_sync_category_expense_type_subtype_alternate(
    organization_for_sync_category_expense_type_subtype, wallet_test_helper
):
    """
    Wallet for test_sync__category_expense_type_and_subtype_alternate with access
    to Preservation & Surrogacy
    """
    user = wallet_test_helper.create_user_for_organization(
        organization_for_sync_category_expense_type_subtype
    )
    wallet = wallet_test_helper.create_pending_wallet(user)

    preservation_category_assoc = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            _PRESERVATION_CATEGORY_IDX
        ]
    )
    ReimbursementWalletAllowedCategorySettingsFactory.create(
        reimbursement_organization_settings_allowed_category_id=preservation_category_assoc.id,
        reimbursement_wallet_id=wallet.id,
        access_level=CategoryRuleAccessLevel.FULL_ACCESS,
        access_level_source=CategoryRuleAccessSource.NO_RULES,
    )
    preservation_plan = (
        preservation_category_assoc.reimbursement_request_category.reimbursement_plan
    )
    ReimbursementAccountFactory.create(
        wallet=wallet,
        plan=preservation_plan,
        alegeus_account_type=preservation_plan.reimbursement_account_type,
        alegeus_flex_account_key=_PRESERVATION_ACCOUNT_KEY,
    )

    surrogacy_category_assoc = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            _SURROGACY_CATEGORY_IDX
        ]
    )
    ReimbursementWalletAllowedCategorySettingsFactory.create(
        reimbursement_organization_settings_allowed_category_id=surrogacy_category_assoc.id,
        reimbursement_wallet_id=wallet.id,
        access_level=CategoryRuleAccessLevel.FULL_ACCESS,
        access_level_source=CategoryRuleAccessSource.NO_RULES,
    )
    surrogacy_plan = (
        surrogacy_category_assoc.reimbursement_request_category.reimbursement_plan
    )
    ReimbursementAccountFactory.create(
        wallet=wallet,
        plan=surrogacy_plan,
        alegeus_account_type=surrogacy_plan.reimbursement_account_type,
        alegeus_flex_account_key=_SURROGACY_ACCOUNT_KEY,
    )

    # Qualify the wallet *after* creating plans and allowed category records otherwise the
    # qualification will trigger access to all categories on the ROS by default.
    wallet_test_helper.qualify_wallet(wallet)

    return wallet


@pytest.mark.parametrize(
    argnames="wallet_fixture, original_category_index, original_expense_type, original_scc, returned_flex_acct_key, returned_scc, expected_category_index, expected_expense_type, expected_scc, expect_notification",
    argvalues=[
        # Happy Path: Unadjudicated
        pytest.param(
            "wallet_for_test_sync_category_expense_type_subtype",
            # original
            _FERTILITY_CATEGORY_IDX,
            None,
            None,
            # returned
            0,
            None,
            # expected
            _FERTILITY_CATEGORY_IDX,
            None,
            None,
            False,
            id="HAPPY1",
        ),
        # Happy Path: DTR
        pytest.param(
            "wallet_for_test_sync_category_expense_type_subtype",
            # original
            _FERTILITY_CATEGORY_IDX,
            None,
            None,
            # returned
            _DTR_ACCOUNT_KEY,
            "FT",
            # expected
            _FERTILITY_CATEGORY_IDX,
            None,
            None,
            False,
            id="HAPPY2",
        ),
        # Happy Path: No ET or EST, EST returned
        pytest.param(
            "wallet_for_test_sync_category_expense_type_subtype",
            # original
            _FERTILITY_CATEGORY_IDX,
            None,
            None,
            # returned
            _FERTILITY_ACCOUNT_KEY,
            "FT",
            # expected
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.FERTILITY,
            "FT",
            False,
            id="HAPPY3",
        ),
        # Happy Path: No EST sent, EST returned
        pytest.param(
            "wallet_for_test_sync_category_expense_type_subtype",
            # original
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.FERTILITY,
            None,
            # returned
            _FERTILITY_ACCOUNT_KEY,
            "FT",
            # expected
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.FERTILITY,
            "FT",
            False,
            id="HAPPY4",
        ),
        # Happy Path: No changes returned
        pytest.param(
            "wallet_for_test_sync_category_expense_type_subtype",
            # original
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.FERTILITY,
            "FT",
            # returned
            _FERTILITY_ACCOUNT_KEY,
            "FT",
            # expected
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.FERTILITY,
            "FT",
            False,
            id="HAPPY5",
        ),
        # Happy Path: Changed EST returned
        pytest.param(
            "wallet_for_test_sync_category_expense_type_subtype",
            # original
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.FERTILITY,
            "FT",
            # returned
            _FERTILITY_ACCOUNT_KEY,
            "FIVF",
            # expected
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.FERTILITY,
            "FIVF",
            False,
            id="HAPPY6",
        ),
        # Happy Path: Hidden EST returned
        pytest.param(
            "wallet_for_test_sync_category_expense_type_subtype",
            # original
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.FERTILITY,
            None,
            # returned
            _FERTILITY_ACCOUNT_KEY,
            "FRTTRAVEL",
            # expected
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.FERTILITY,
            "FRTTRAVEL",
            False,
            id="HAPPY7",
        ),
        # Happy Path: No EST sent, EST returned w/ ET change
        pytest.param(
            "wallet_for_test_sync_category_expense_type_subtype",
            # original
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.FERTILITY,
            None,
            # returned
            _FERTILITY_ACCOUNT_KEY,
            "PRSEGG",
            # expected
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.PRESERVATION,
            "PRSEGG",
            False,
            id="HAPPY8",
        ),
        # Happy Path: No EST sent, EST returned w/ C+ET change
        pytest.param(
            "wallet_for_test_sync_category_expense_type_subtype",
            # original
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.FERTILITY,
            None,
            # returned
            _SURROGACY_ACCOUNT_KEY,
            "SGCC",
            # expected
            _SURROGACY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.SURROGACY,
            "SGCC",
            False,
            id="HAPPY9",
        ),
        # Happy Path: Changed EST returned w/ ET change
        pytest.param(
            "wallet_for_test_sync_category_expense_type_subtype",
            # original
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.FERTILITY,
            "FT",
            # returned
            _FERTILITY_ACCOUNT_KEY,
            "PRSEGG",
            # expected
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.PRESERVATION,
            "PRSEGG",
            False,
            id="HAPPY10",
        ),
        # Happy Path: Changed EST returned w/ C+ET change
        pytest.param(
            "wallet_for_test_sync_category_expense_type_subtype",
            # original
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.FERTILITY,
            "FT",
            # returned
            _SURROGACY_ACCOUNT_KEY,
            "SGCC",
            # expected
            _SURROGACY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.SURROGACY,
            "SGCC",
            False,
            id="HAPPY11",
        ),
        # Happy Path: No EST sent, dupe EST returned
        pytest.param(
            "wallet_for_test_sync_category_expense_type_subtype",
            # original
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.FERTILITY,
            None,
            # returned
            _FERTILITY_ACCOUNT_KEY,
            "FERTRX",
            # expected
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.FERTILITY,
            "FERTRX",
            False,
            id="HAPPY12",
        ),
        # Happy Path: No EST sent, dupe EST returned (secondary ET)
        pytest.param(
            "wallet_for_test_sync_category_expense_type_subtype",
            # original
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.PRESERVATION,
            None,
            # returned
            _FERTILITY_ACCOUNT_KEY,
            "FERTRX",
            # expected
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.PRESERVATION,
            "FERTRX",
            False,
            id="HAPPY13",
        ),
        # Happy Path: Denied claim w/o Account
        pytest.param(
            "wallet_for_test_sync_category_expense_type_subtype",
            # original
            _FERTILITY_CATEGORY_IDX,
            None,
            None,
            # returned
            -1,
            None,
            # expected
            _FERTILITY_CATEGORY_IDX,
            None,
            None,
            False,
            id="HAPPY14",
        ),
        # Okay Path: No EST sent, dupe EST returned w/ ET change
        pytest.param(
            "wallet_for_test_sync_category_expense_type_subtype",
            # original
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.DONOR,  # not configured on ROS, but ok for test
            None,
            # returned
            _FERTILITY_ACCOUNT_KEY,
            "FERTRX",
            # expected
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.FERTILITY,
            "FERTRX",
            False,
            id="OKAY1",
        ),
        # Okay Path: No EST sent, dupe EST returned w/ C change
        pytest.param(
            "wallet_for_test_sync_category_expense_type_subtype",
            # original
            _SURROGACY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.SURROGACY,
            None,
            # returned
            _FERTILITY_ACCOUNT_KEY,
            "FERTRX",
            # expected
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.FERTILITY,
            "FERTRX",
            False,
            id="OKAY2",
        ),
        # Okay Path: No EST sent, dupe EST returned w/ C change (secondary ET)
        pytest.param(
            "wallet_for_test_sync_category_expense_type_subtype_alternate",  # <<< note
            # original
            _SURROGACY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.SURROGACY,
            None,
            # returned
            _PRESERVATION_ACCOUNT_KEY,
            "FERTRX",
            # expected
            _PRESERVATION_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.PRESERVATION,
            "FERTRX",
            False,
            id="OKAY3",
        ),
        #
        # Sad Path: Unavailable C returned
        pytest.param(
            "wallet_for_test_sync_category_expense_type_subtype",
            # original
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.FERTILITY,
            None,
            # returned
            _ADOPTION_ACCOUNT_KEY,
            "ALF",
            # expected
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.FERTILITY,
            None,
            True,
            id="SAD1",
        ),
        # Sad Path: Changed C returned, mismatched ET
        pytest.param(
            "wallet_for_test_sync_category_expense_type_subtype",
            # original
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.FERTILITY,
            "FT",
            # returned
            _SURROGACY_ACCOUNT_KEY,
            "FT",
            # expected
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.FERTILITY,
            "FT",
            True,
            id="SAD2",
        ),
        # Sad Path: Changed C+EST returned, mismatched ET
        pytest.param(
            "wallet_for_test_sync_category_expense_type_subtype",
            # original
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.FERTILITY,
            None,
            # returned
            _SURROGACY_ACCOUNT_KEY,
            "FT",
            # expected
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.FERTILITY,
            None,
            True,
            id="SAD3",
        ),
        # Sad Path: Mismatched ET returned
        pytest.param(
            "wallet_for_test_sync_category_expense_type_subtype",
            # original
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.FERTILITY,
            "FT",
            # returned
            _FERTILITY_ACCOUNT_KEY,
            "SGCC",
            # expected
            _FERTILITY_CATEGORY_IDX,
            ReimbursementRequestExpenseTypes.FERTILITY,
            "FT",
            True,
            id="SAD4",
        ),
    ],
)
def test_sync__category_expense_type_and_subtype(
    wallet_fixture,
    original_category_index,
    original_expense_type,
    original_scc,
    returned_flex_acct_key,
    returned_scc,
    expected_category_index,
    expected_expense_type,
    expected_scc,
    expense_subtypes,
    expect_notification,
    request,
):
    wallet = request.getfixturevalue(wallet_fixture)

    original_category = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            original_category_index
        ].reimbursement_request_category
    )
    expected_category = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            expected_category_index
        ].reimbursement_request_category
    )

    reimbursement_request = ReimbursementRequestFactory.create(
        wallet=wallet,
        category=original_category,
        state=ReimbursementRequestState.PENDING,
        amount=9999,
        expense_type=original_expense_type,
        wallet_expense_subtype=expense_subtypes[original_scc] if original_scc else None,
    )
    reimbursement_claim = ReimbursementClaimFactory.create(
        alegeus_claim_id="xyz369",
        status=AlegeusClaimStatus.SUBMITTED_UNDER_REVIEW.value,
        reimbursement_request=reimbursement_request,
        alegeus_claim_key=123,
        amount=99.99,
    )

    account = ReimbursementAccount.query.filter_by(
        wallet=wallet,
        alegeus_flex_account_key=returned_flex_acct_key,
    ).one_or_none()

    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: [
        {
            "TrackingNumber": reimbursement_claim.alegeus_claim_id,
            "Status": "Approved",
            "ClaimKey": reimbursement_claim.alegeus_claim_key,
            "AccountsPaidAmount": reimbursement_claim.amount,
            "Amount": reimbursement_claim.amount,
            "AcctTypeCode": account.alegeus_account_type.alegeus_account_type
            if account
            else None,
            "FlexAcctKey": returned_flex_acct_key,
            "ServiceCategoryCode": returned_scc,
        },
    ]

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_activity"
    ) as mock_request, patch.object(
        SyncAccountSccPaymentOpsZendeskTicket, "update_zendesk"
    ) as mock_update_zendesk:
        mock_request.return_value = mock_response

        wallet_to_claims = get_wallets_with_pending_claims([wallet])
        sync_pending_claims(wallet_to_claims)

        assert reimbursement_request.category == expected_category
        assert reimbursement_request.expense_type == expected_expense_type
        if expected_scc:
            assert reimbursement_request.wallet_expense_subtype.code == expected_scc
        else:
            assert reimbursement_request.wallet_expense_subtype is None

        if expect_notification:
            mock_update_zendesk.assert_called_once()
        else:
            mock_update_zendesk.assert_not_called()


def test_sync_DTR_claim_set_request_as_denied(wallet_with_pending_claims):
    """
    Claims that are submitted for an HDHP / DTR Account and are 'Approved' should be denied in Admin as the
    Member has not exhausted their deductible yet.
    """
    claim_1_alegeus_id = "123abc"
    claim_1_amount = 255.50
    claim_1_key = 10

    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: [
        {
            "Status": "Approved",
            "Amount": claim_1_amount,
            "TrackingNumber": claim_1_alegeus_id,
            "ClaimKey": claim_1_key,
            "AcctTypeCode": "DTR",
        },
    ]

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_activity"
    ) as mock_request:
        mock_request.return_value = mock_response

        wallet_to_claims = get_wallets_with_pending_claims([wallet_with_pending_claims])

        claim_1 = ReimbursementClaim.query.filter_by(
            alegeus_claim_id=claim_1_alegeus_id
        ).one()

        request_1 = claim_1.reimbursement_request

        sync_pending_claims(wallet_to_claims)

        assert claim_1.status.upper() == AlegeusClaimStatus.APPROVED.value
        assert request_1.state == ReimbursementRequestState.DENIED


@pytest.mark.parametrize(
    argnames="alegeus_claim_response, expected_result",
    argvalues=[
        ({"AcctTypeCode": None}, ""),
        ({"AcctTypeCode": "hra"}, "HRA"),
        ({"AcctTypeCode": ""}, ""),
    ],
)
def test_get_account_type_code(alegeus_claim_response, expected_result):
    account_type_code = get_account_type_code(alegeus_claim_response)
    assert account_type_code == expected_result


@pytest.mark.parametrize(
    "rr_amount,member_responsibility,employer_responsibility,state,expected_mapping",
    [
        (100_00, 25_00, 100_00, "APPROVED", True),
        (50_00, 50_00, 100_00, "PAID", False),
    ],
)
def test_approved_mmb_claim_is_accumulated(
    direct_payment_wallet,
    feature_flag_on,
    rr_amount,
    member_responsibility,
    employer_responsibility,
    state,
    expected_mapping,
):
    org_settings = direct_payment_wallet.reimbursement_organization_settings
    org_settings.deductible_accumulation_enabled = True
    category = org_settings.allowed_reimbursement_categories[
        0
    ].reimbursement_request_category
    # include all the request fields required for accumulation
    request = ReimbursementRequestFactory.create(
        amount=rr_amount,
        person_receiving_service_id=direct_payment_wallet.user_id,
        person_receiving_service_member_status="MEMBER",
        procedure_type="MEDICAL",
        cost_sharing_category=CostSharingCategory.MEDICAL_CARE,
        wallet=direct_payment_wallet,
        category=category,
        state=ReimbursementRequestState.PENDING,
    )
    CostBreakdownFactory.create(
        wallet_id=direct_payment_wallet.id,
        reimbursement_request_id=request.id,
        total_member_responsibility=member_responsibility,
        total_employer_responsibility=employer_responsibility,
    )
    claim = ReimbursementClaimFactory.create(
        alegeus_claim_id="123abc",
        status=AlegeusClaimStatus.NEEDS_RECEIPT.value,
        reimbursement_request=request,
        alegeus_claim_key=1,
        amount=100.00,
    )
    wallet_claims = [WalletClaims(wallet=direct_payment_wallet, claims=[claim])]
    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: [
        {
            "Status": AlegeusClaimStatus(state).value,
            "AccountsPaidAmount": claim.amount,
            "Amount": claim.amount,
            "TrackingNumber": claim.alegeus_claim_id,
            "ClaimKey": claim.alegeus_claim_key,
        },
    ]

    # when
    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_activity",
        return_value=mock_response,
    ), patch(
        "payer_accumulator.accumulation_mapping_service.AccumulationMappingService.get_valid_payer",
        return_value=Mock(id=1),
    ):
        sync_pending_claims(wallet_claims)

    mapping = AccumulationTreatmentMapping.query.filter(
        AccumulationTreatmentMapping.reimbursement_request_id == request.id
    ).first()
    assert (mapping is not None) == expected_mapping


@pytest.mark.parametrize(
    "state,expect_deduction",
    [
        ("APPROVED", True),
        ("PAID", False),
    ],
)
def test_approved_cycle_claim_is_deducted(
    direct_payment_cycle_based_wallet,
    state,
    expect_deduction,
    feature_flag_on,
):
    allowed_category = direct_payment_cycle_based_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ]
    category = allowed_category.reimbursement_request_category

    request = ReimbursementRequestFactory.create(
        amount=10000,
        wallet=direct_payment_cycle_based_wallet,
        category=category,
        state=ReimbursementRequestState.PENDING,
        cost_credit=7,
    )
    CostBreakdownFactory.create(
        wallet_id=direct_payment_cycle_based_wallet.id,
        reimbursement_request_id=request.id,
        total_member_responsibility=5000,
        total_employer_responsibility=5000,
    )
    claim = ReimbursementClaimFactory.create(
        alegeus_claim_id="123abc",
        status=AlegeusClaimStatus.SUBMITTED_UNDER_REVIEW.value,
        reimbursement_request=request,
        alegeus_claim_key=1,
        amount=50.00,
    )
    wallet_claims = [
        WalletClaims(wallet=direct_payment_cycle_based_wallet, claims=[claim])
    ]
    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: [
        {
            "Status": AlegeusClaimStatus(state).value,
            "AccountsPaidAmount": claim.amount,
            "Amount": claim.amount,
            "TrackingNumber": claim.alegeus_claim_id,
            "ClaimKey": claim.alegeus_claim_key,
        },
    ]

    # when
    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_activity",
        return_value=mock_response,
    ):
        sync_pending_claims(wallet_claims)

    # wallet is created with 10 cycles (120 credits!)
    wallet_credits = ReimbursementCycleCredits.query.filter_by(
        reimbursement_wallet_id=direct_payment_cycle_based_wallet.id,
        reimbursement_organization_settings_allowed_category_id=allowed_category.id,
    ).first()

    if expect_deduction:
        assert wallet_credits.amount == 113

        new_transaction = wallet_credits.transactions[1]
        assert new_transaction.amount == -7
        assert new_transaction.reimbursement_request_id == request.id
    else:
        assert wallet_credits.amount == 120


@pytest.mark.parametrize(
    argnames="wallet_fixture, reimbursement_type, cost_credit, state, expected",
    argvalues=[
        # Happy paths
        (
            "direct_payment_cycle_based_wallet",
            ReimbursementRequestType.MANUAL,
            6,
            ReimbursementRequestState.APPROVED,
            True,
        ),
        # No credit cost (False)
        (
            "direct_payment_cycle_based_wallet",
            ReimbursementRequestType.MANUAL,
            None,
            ReimbursementRequestState.APPROVED,
            False,
        ),
        # Zero credit cost (False)
        (
            "direct_payment_cycle_based_wallet",
            ReimbursementRequestType.MANUAL,
            0,
            ReimbursementRequestState.APPROVED,
            False,
        ),
        # Not approved (False)
        (
            "direct_payment_cycle_based_wallet",
            ReimbursementRequestType.MANUAL,
            ReimbursementRequestState.PENDING,
            None,
            False,
        ),
        (
            "direct_payment_cycle_based_wallet",
            ReimbursementRequestType.MANUAL,
            ReimbursementRequestState.REIMBURSED,
            None,
            False,
        ),
        # Non-cycle wallet (False)
        (
            "direct_payment_wallet",
            ReimbursementRequestType.MANUAL,
            6,
            ReimbursementRequestState.APPROVED,
            False,
        ),
        # DP RRs (False)
        (
            "direct_payment_wallet",
            ReimbursementRequestType.DIRECT_BILLING,
            6,
            ReimbursementRequestState.APPROVED,
            False,
        ),
        (
            "direct_payment_cycle_based_wallet",
            ReimbursementRequestType.DIRECT_BILLING,
            6,
            ReimbursementRequestState.APPROVED,
            False,
        ),
        # non-DP org (False)
        (
            "qualified_alegeus_wallet_hra",
            ReimbursementRequestType.MANUAL,
            6,
            ReimbursementRequestState.APPROVED,
            False,
        ),
        # All the sad paths
        (
            "qualified_alegeus_wallet_hra",
            ReimbursementRequestType.DIRECT_BILLING,
            None,
            ReimbursementRequestState.DENIED,
            False,
        ),
    ],
)
def test_should_deduct_credits(
    wallet_fixture, reimbursement_type, cost_credit, state, expected, request
):
    wallet = request.getfixturevalue(wallet_fixture)
    category = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
    )

    reimbursement_request = ReimbursementRequestFactory.create(
        amount=100,
        wallet=wallet,
        category=category,
        reimbursement_type=reimbursement_type,
        cost_credit=cost_credit,
        state=state,
    )

    result = _should_deduct_credits(reimbursement_request)

    assert result == expected


def test_sync_pending_claims__revised_service_start_date(wallet_with_pending_claims):
    claim_alegeus_id = "123abc"
    new_service_date = "/Date(1710432000000-0600)/"
    expected_datetime = format_date_from_string_to_datetime(new_service_date)

    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: [
        {
            "Status": "Approved",
            "TrackingNumber": claim_alegeus_id,
            "ServiceStartDate": new_service_date,
        }
    ]

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_activity"
    ) as mock_request:
        mock_request.return_value = mock_response
        wallet_to_claims = get_wallets_with_pending_claims([wallet_with_pending_claims])

        claim = ReimbursementClaim.query.filter_by(
            alegeus_claim_id=claim_alegeus_id
        ).one()
        request = claim.reimbursement_request
        old_service_date = request.service_start_date

        sync_pending_claims(wallet_to_claims)

        # Service date should be updated
        assert request.service_start_date != old_service_date
        assert request.service_start_date == expected_datetime


def test_sync_pending_claims__invalid_service_date(wallet_with_pending_claims):
    claim_alegeus_id = "123abc"
    invalid_service_date = "invalid-date-format"

    mock_response = Response()
    mock_response.status_code = 200
    mock_response.json = lambda: [
        {
            "Status": "Approved",
            "TrackingNumber": claim_alegeus_id,
            "ServiceStartDate": invalid_service_date,
        }
    ]

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.AlegeusApi.get_employee_activity"
    ) as mock_request:
        mock_request.return_value = mock_response
        wallet_to_claims = get_wallets_with_pending_claims([wallet_with_pending_claims])

        claim = ReimbursementClaim.query.filter_by(
            alegeus_claim_id=claim_alegeus_id
        ).one()
        request = claim.reimbursement_request
        original_service_date = request.service_start_date

        sync_pending_claims(wallet_to_claims)

        # Service date should be unchanged when invalid
        assert request.service_start_date == original_service_date


class TestSyncPendingClaimsHelpers:
    def test_get_all_alegeus_user_wallets(
        self,
        pending_alegeus_wallet_hra,
        qualified_alegeus_wallet_hra,
        qualified_alegeus_wallet_hdhp_family,
    ):
        # 1 pending wallet 1 qualified wallet and 1 runout
        qualified_alegeus_wallet_hdhp_family.state = WalletState.RUNOUT
        wallets = get_all_alegeus_sync_claims_user_wallets()
        assert len(wallets) == 2

    def test_get_all_alegeus_user_wallets_missing_data(self):
        # missing alegeus ids
        ReimbursementWalletFactory.create(
            state=WalletState.QUALIFIED,
        )
        wallets = get_all_alegeus_sync_claims_user_wallets()
        assert len(wallets) == 0


class TestAddBackHraToAlegeusWalletBalance:
    def test_success(self, qualified_alegeus_wallet_hra):
        category = qualified_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories[
            1  # first is the default, second is the one created by pending_alegeus_wallet_hra
        ].reimbursement_request_category
        request = ReimbursementRequestFactory.create(
            wallet=qualified_alegeus_wallet_hra,
            category=category,
            state=ReimbursementRequestState.APPROVED,
            amount=100,
        )
        with patch(
            "wallet.utils.alegeus.claims.sync.create_direct_payment_claim_in_alegeus"
        ) as create_direct_payment_claim_in_alegeus:
            _add_back_hra_to_alegeus_wallet_balance(request, 100)
            create_direct_payment_claim_in_alegeus.assert_called_once()
