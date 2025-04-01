from decimal import Decimal
from typing import Optional
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from requests import Response

from cost_breakdown.constants import ClaimType
from cost_breakdown.errors import (
    CreateDirectPaymentClaimErrorResponseException,
    InvalidDirectPaymentClaimCreationRequestException,
)
from cost_breakdown.pytests.factories import CostBreakdownFactory
from cost_breakdown.wallet_balance_reimbursements import _create_direct_payment_claim
from direct_payment.pharmacy.errors import AutoProcessedDirectPaymentException
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from wallet.models.constants import (
    AlegeusClaimStatus,
    ReimbursementMethod,
    ReimbursementRequestAutoProcessing,
)
from wallet.models.reimbursement import ReimbursementClaim, ReimbursementRequest
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.pytests.factories import ReimbursementClaimFactory
from wallet.utils.alegeus.claims.create import (
    create_auto_processed_claim_in_alegeus,
    create_claim_in_alegeus,
    create_direct_payment_claim_in_alegeus,
    download_user_asset_to_b64_str,
    get_reimbursement_account_from_request_and_wallet,
    upload_claim_attachments_to_alegeus,
)


@pytest.fixture
def make_mocked_direct_payment_claim_response():
    def _make_mocked_response(
        status_code,
        error_code: Optional[int],
        txn_amt_orig: Optional[float],
        txn_approved_amt: Optional[float],
    ):
        mock_response = Response()
        mock_response.status_code = status_code
        payload = {
            "ReimbursementMode": "None",
            "PayProviderFlag": "No",
            "TrackingNumber": "DPNOPAYTEST8",
            "TxnResponseList": [
                {"AcctTypeCde": "HRA", "DisbBal": 0.00, "TxnAmt": 13.80}
            ],
        }
        if error_code is not None:
            payload["ErrorCode"] = error_code
        if txn_amt_orig is not None:
            payload["TxnAmtOrig"] = txn_amt_orig
        if txn_approved_amt is not None:
            payload["TxnApprovedAmt"] = txn_approved_amt
        mock_response.json = lambda: payload

        return mock_response

    return _make_mocked_response


def test_get_reimbursement_account_from_request_and_wallet(
    wallet_with_pending_requests_with_claims_and_attachments,
):
    reimbursement_request = (
        wallet_with_pending_requests_with_claims_and_attachments.reimbursement_requests[
            0
        ]
    )

    reimbursement_plan = reimbursement_request.category.reimbursement_plan

    reimbursement_account = get_reimbursement_account_from_request_and_wallet(
        reimbursement_request,
        wallet_with_pending_requests_with_claims_and_attachments,
    )

    assert reimbursement_account
    assert reimbursement_account.plan == reimbursement_plan
    assert (
        reimbursement_account.wallet
        == wallet_with_pending_requests_with_claims_and_attachments
    )


def test_create_direct_payment_claim_in_alegeus__successful_mock_alegeus_api(
    wallet_with_approved_direct_billing_request_no_claim,
    make_mocked_direct_payment_claim_response,
):
    reimbursement_request = (
        wallet_with_approved_direct_billing_request_no_claim.reimbursement_requests[0]
    )

    mock_response = make_mocked_direct_payment_claim_response(200, 0, 13.80, 13.80)
    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_request.return_value = mock_response

        create_direct_payment_claim_in_alegeus(
            wallet_with_approved_direct_billing_request_no_claim,
            reimbursement_request,
            ClaimType.EMPLOYER,
        )
        reimbursement_claim = ReimbursementClaim.query.filter_by(
            reimbursement_request_id=reimbursement_request.id
        ).all()
        mock_request.assert_called_once()
        assert len(reimbursement_claim) == 1


@pytest.mark.parametrize(
    "http_status,alegeus_error_code,tax_orig,tax_approved,expects",
    [
        (200, 133, 13.80, 13.80, ["Error in the response for claim", "code: 133"]),
        (200, 0, None, 13.80, ["TxnAmtOrig in the response is unavailable for claim"]),
        (
            200,
            0,
            13.80,
            None,
            ["TxnApprovedAmt in the response is unavailable for claim"],
        ),
        (
            200,
            0,
            28.20,
            13.80,
            [
                "Insufficient balance: TxnApprovedAmt and TxnAmtOrig are not equal for claim"
            ],
        ),
    ],
    ids=[
        "Error code in the response",
        "TxnAmtOrig not available",
        "TxnApprovedAmt not available",
        "Insufficient balance so TxnAmtOrig is larger than TxnApprovedAmt",
    ],
)
def test_create_direct_payment_claim_in_alegeus_invalid_response(
    wallet_with_approved_direct_billing_request_no_claim,
    make_mocked_direct_payment_claim_response,
    http_status,
    alegeus_error_code,
    tax_orig,
    tax_approved,
    expects,
):
    reimbursement_request = (
        wallet_with_approved_direct_billing_request_no_claim.reimbursement_requests[0]
    )

    # Case 2: error code in the response
    mock_response = make_mocked_direct_payment_claim_response(
        http_status, alegeus_error_code, tax_orig, tax_approved
    )
    with patch(
        "wallet.utils.alegeus.claims.create.AlegeusApi.post_direct_payment_claim"
    ) as mock_request:
        mock_request.return_value = mock_response

        with pytest.raises(CreateDirectPaymentClaimErrorResponseException) as exc_info:
            create_direct_payment_claim_in_alegeus(
                wallet_with_approved_direct_billing_request_no_claim,
                reimbursement_request,
                ClaimType.EMPLOYER,
            )

        mock_request.assert_called_once()
        for expected in expects:
            assert expected in str(exc_info.value)


def test_create_direct_payment_claim_in_alegeus__response_throws_exception(
    wallet_with_approved_direct_billing_request_no_claim,
):
    reimbursement_request = (
        wallet_with_approved_direct_billing_request_no_claim.reimbursement_requests[0]
    )

    mock_response = Response()
    mock_response._content = b"I am not a json response"
    mock_response.status_code = 500
    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_request.return_value = mock_response

        with pytest.raises(CreateDirectPaymentClaimErrorResponseException) as exc_info:
            create_direct_payment_claim_in_alegeus(
                wallet_with_approved_direct_billing_request_no_claim,
                reimbursement_request,
                ClaimType.EMPLOYER,
            )

        assert "Unsuccessful response status code 500 in the response for claim" in str(
            exc_info.value
        )


def test_create_direct_payment_claim_in_alegeus__failed_mock_alegeus_api(
    wallet_with_approved_direct_billing_request_no_claim,
    make_mocked_direct_payment_claim_response,
):
    reimbursement_request = (
        wallet_with_approved_direct_billing_request_no_claim.reimbursement_requests[0]
    )

    # Case 1: error status code
    mock_response = make_mocked_direct_payment_claim_response(404, 0, 13.80, 13.80)
    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_request.return_value = mock_response

        with pytest.raises(CreateDirectPaymentClaimErrorResponseException) as exc_info:
            create_direct_payment_claim_in_alegeus(
                wallet_with_approved_direct_billing_request_no_claim,
                reimbursement_request,
                ClaimType.EMPLOYER,
            )
        reimbursement_claim = ReimbursementClaim.query.filter_by(
            reimbursement_request_id=reimbursement_request.id
        ).all()
        mock_request.assert_called_once()
        assert "Unsuccessful response status code 404 in the response for claim" in str(
            exc_info.value
        )
        assert len(reimbursement_claim) == 0


def test_create_direct_payment_claim_in_alegeus__account_not_found(
    qualified_alegeus_wallet_hdhp_family,
    wallet_with_approved_direct_billing_request_no_claim,
):
    reimbursement_request = (
        wallet_with_approved_direct_billing_request_no_claim.reimbursement_requests[0]
    )

    with patch(
        "wallet.utils.alegeus.claims.create.AlegeusApi.post_direct_payment_claim"
    ) as mock_api:
        with pytest.raises(
            InvalidDirectPaymentClaimCreationRequestException
        ) as excinfo:
            create_direct_payment_claim_in_alegeus(
                qualified_alegeus_wallet_hdhp_family,
                reimbursement_request,
                ClaimType.EMPLOYER,
            )

        mock_api.assert_not_called()
        assert "Can not find reimbursement account from Reimbursement" in str(
            excinfo.value
        )


def test_create_direct_payment_claim_in_alegeus__invalid_reimbursement_request_type(
    wallet_with_pending_requests_no_claims,
):
    reimbursement_request = (
        wallet_with_pending_requests_no_claims.reimbursement_requests[0]
    )

    with patch(
        "wallet.utils.alegeus.claims.create.AlegeusApi.post_direct_payment_claim"
    ) as mock_api:
        _create_direct_payment_claim(
            123,
            123,
            wallet_with_pending_requests_no_claims,
            reimbursement_request,
            ClaimType.EMPLOYER,
        )

        mock_api.assert_not_called()


def test_create_direct_payment_claim_in_alegeus__claim_type_not_match_reimbursement_request_status(
    wallet_with_approved_direct_billing_request_no_claim,
):
    reimbursement_request = (
        wallet_with_approved_direct_billing_request_no_claim.reimbursement_requests[0]
    )

    with patch(
        "wallet.utils.alegeus.claims.create.AlegeusApi.post_direct_payment_claim"
    ) as mock_api:
        _create_direct_payment_claim(
            123,
            123,
            wallet_with_approved_direct_billing_request_no_claim,
            reimbursement_request,
            ClaimType.EMPLOYEE_DEDUCTIBLE,
        )

        mock_api.assert_not_called()


@pytest.mark.parametrize(
    argnames=(
        "wallet_with_pending_currency_specific_request_no_claims",
        "expected_amount",
    ),
    argvalues=[
        ((10000, None, None), Decimal("100.00")),
        ((10000, None, "USD"), Decimal("100.00")),
        ((None, 20000, "AUD"), Decimal("200.00")),
        ((None, 30000, "NZD"), Decimal("300.00")),
    ],
    ids=[
        "USD-request-where-benefit-currency-is-None",
        "USD-request-where-benefit-currency-is-USD",
        "AUD-request-where-benefit-currency-is-AUD",
        "NZD-request-where-benefit-currency-is-NZD",
    ],
    indirect=["wallet_with_pending_currency_specific_request_no_claims"],
)
def test_create_claim_in_alegeus_uses_correct_amount(
    wallet_with_pending_currency_specific_request_no_claims: ReimbursementWallet,
    expected_amount: int,
):
    # Given
    reimbursement_request: ReimbursementRequest = (
        wallet_with_pending_currency_specific_request_no_claims.reimbursement_requests[
            0
        ]
    )

    with patch("wallet.utils.alegeus.claims.create._create_claim") as mock_create_claim:
        expected_claim_key = "123456789"
        mock_create_claim.return_value = (True, expected_claim_key)

        # When
        (_, _, created_claim) = create_claim_in_alegeus(
            wallet_with_pending_currency_specific_request_no_claims,
            reimbursement_request,
            [],
        )

    # Then
    assert created_claim.amount == expected_amount


def test_create_claim_in_alegeus__successful(
    wallet_with_pending_requests_no_claims,
):
    assert ReimbursementClaim.query.count() == 0

    reimbursement_request = (
        wallet_with_pending_requests_no_claims.reimbursement_requests[0]
    )

    with patch("wallet.utils.alegeus.claims.create._create_claim") as mock_create_claim:
        expected_claim_key = "123456789"
        mock_create_claim.return_value = (True, expected_claim_key)

        messages = []

        (was_successful, messages, created_claim,) = create_claim_in_alegeus(
            wallet_with_pending_requests_no_claims,
            reimbursement_request,
            messages,
        )

        assert was_successful is True
        assert created_claim
        assert ReimbursementClaim.query.count() == 1


def test_create_claim_in_alegeus__failure_create_claim(
    wallet_with_pending_requests_no_claims,
):
    assert ReimbursementClaim.query.count() == 0

    reimbursement_request = (
        wallet_with_pending_requests_no_claims.reimbursement_requests[0]
    )

    with patch("wallet.utils.alegeus.claims.create._create_claim") as mock_create_claim:
        mock_create_claim.return_value = (False, None)

        messages = []

        (was_successful, messages, created_claim,) = create_claim_in_alegeus(
            wallet_with_pending_requests_no_claims,
            reimbursement_request,
            messages,
        )

        assert was_successful is False
        assert created_claim is None
        assert ReimbursementClaim.query.count() == 0


def test_upload_claim_attachments_to_alegeus__successful(
    wallet_with_pending_requests_no_claims,
):
    reimbursement_request = (
        wallet_with_pending_requests_no_claims.reimbursement_requests[0]
    )

    reimbursement_claim = ReimbursementClaimFactory.create(
        alegeus_claim_id="123abc",
        status=AlegeusClaimStatus.NEEDS_RECEIPT.value,
        reimbursement_request=reimbursement_request,
        alegeus_claim_key=1,
    )

    mock_response_1 = Response()
    mock_response_1.status_code = 200
    mock_response_1.json = lambda: {}

    mock_response_2 = Response()
    mock_response_2.status_code = 200
    mock_response_2.json = lambda: {}

    mock_blob_instance = MagicMock()
    mock_blob_instance.download_as_bytes = lambda: b"pizza"

    with patch(
        "wallet.utils.alegeus.claims.create.AlegeusApi.upload_attachment_for_claim"
    ) as mock_request, patch(
        "models.enterprise.UserAsset.blob", new_callable=PropertyMock
    ) as mock_blob:
        mock_request.side_effect = [mock_response_1, mock_response_2]
        mock_blob.return_value = mock_blob_instance

        messages = []

        was_successful, messages = upload_claim_attachments_to_alegeus(
            wallet_with_pending_requests_no_claims,
            reimbursement_request,
            reimbursement_claim,
            messages,
        )

        assert was_successful is True


def test_upload_claim_attachments_to_alegeus__failure_upload_attachments(
    wallet_with_pending_requests_with_claims_and_attachments,
):
    reimbursement_request = (
        wallet_with_pending_requests_with_claims_and_attachments.reimbursement_requests[
            0
        ]
    )

    reimbursement_claim = reimbursement_request.claims[0]

    mock_response_1 = Response()
    mock_response_1.status_code = 418
    mock_response_1.headers["content-type"] = "image/jpeg"
    mock_response_1.json = lambda: {}

    mock_response_2 = Response()
    mock_response_2.status_code = 418
    mock_response_2.headers["content-type"] = "image/jpeg"
    mock_response_2.json = lambda: {}

    mock_blob_instance = MagicMock()
    mock_blob_instance.download_as_bytes = lambda: b"empanada"

    with patch(
        "wallet.utils.alegeus.claims.create.AlegeusApi.upload_attachment_for_claim"
    ) as mock_request, patch(
        "models.enterprise.UserAsset.blob", new_callable=PropertyMock
    ) as mock_blob:
        mock_request.side_effect = [mock_response_1, mock_response_2]
        mock_blob.return_value = mock_blob_instance

        messages = []

        was_successful, messages = upload_claim_attachments_to_alegeus(
            wallet_with_pending_requests_with_claims_and_attachments,
            reimbursement_request,
            reimbursement_claim,
            messages,
        )

        assert was_successful is False


def test_upload_claim_attachments_to_alegeus__failure_could_not_upload_all_attachments(
    wallet_with_pending_requests_with_claims_and_attachments,
):
    reimbursement_request = (
        wallet_with_pending_requests_with_claims_and_attachments.reimbursement_requests[
            0
        ]
    )

    reimbursement_claim = reimbursement_request.claims[0]

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
        "wallet.utils.alegeus.claims.create.AlegeusApi.upload_attachment_for_claim"
    ) as mock_request, patch(
        "models.enterprise.UserAsset.blob", new_callable=PropertyMock
    ) as mock_blob:
        mock_request.side_effect = [mock_response_1, mock_response_2]
        mock_blob.return_value = mock_blob_instance

        messages = []

        was_successful, messages = upload_claim_attachments_to_alegeus(
            wallet_with_pending_requests_with_claims_and_attachments,
            reimbursement_request,
            reimbursement_claim,
            messages,
        )

        assert was_successful is False


def test_download_user_asset_to_b64_str__successful(
    wallet_with_pending_requests_no_claims,
):
    reimbursement_request = (
        wallet_with_pending_requests_no_claims.reimbursement_requests[0]
    )

    mock_blob_instance = MagicMock()
    mock_blob_instance.download_as_bytes = lambda: b"pizza"

    with patch(
        "models.enterprise.UserAsset.blob", new_callable=PropertyMock
    ) as mock_blob:
        mock_blob.return_value = mock_blob_instance
        source = reimbursement_request.sources[0]
        user_asset = source.user_asset
        blob_bytes_b64_str = download_user_asset_to_b64_str(user_asset)
        assert "cGl6emE=" == blob_bytes_b64_str


def test_download_user_asset_to_b64_str__failure(
    wallet_with_pending_requests_no_claims,
):
    reimbursement_request = (
        wallet_with_pending_requests_no_claims.reimbursement_requests[0]
    )

    with patch(
        "models.enterprise.UserAsset.blob", new_callable=PropertyMock
    ) as mock_blob:
        mock_blob.return_value = ""

    with pytest.raises(  # noqa  B017  TODO:  `assertRaises(Exception)` and `pytest.raises(Exception)` should be considered evil. They can lead to your test passing even if the code being tested is never executed due to a typo. Assert for a more specific exception (builtin or custom), or use `assertRaisesRegex` (if using `assertRaises`), or add the `match` keyword argument (if using `pytest.raises`), or use the context manager form with a target.
        Exception
    ):
        source = reimbursement_request.sources[0]
        user_asset = source.user_asset

        download_user_asset_to_b64_str(user_asset)


@pytest.mark.parametrize(
    argnames=(
        "claim_type",
        "deductible",
        "total_member_responsibility",
        "total_employer_responsibility",
        "txn_approved_amt",
        "expected_amount",
    ),
    argvalues=[
        # Case 1: DTR Deductible different than member responsibility - deductible sent to Alegeus with sufficient funds
        (ClaimType.EMPLOYEE_DEDUCTIBLE, 1000, 2000, 1500, 10.00, 10.0),
        # Case 2: HRA employer responsibility - insufficient funds but it doesn't throw an exception
        (ClaimType.EMPLOYER, 1000, 2000, 1500, 10.00, 15.0),
    ],
    ids=["DTR", "HRA"],
)
def test_create_auto_processed_claim_in_alegeus__successful_mock_alegeus_api(
    claim_type,
    deductible,
    total_member_responsibility,
    total_employer_responsibility,
    txn_approved_amt,
    expected_amount,
    wallet_with_approved_direct_billing_request_no_claim,
    make_mocked_direct_payment_claim_response,
):
    reimbursement_request = (
        wallet_with_approved_direct_billing_request_no_claim.reimbursement_requests[0]
    )
    reimbursement_request.amount = total_employer_responsibility
    reimbursement_request.procedure_type = TreatmentProcedureType.PHARMACY.value
    reimbursement_request.auto_processed = ReimbursementRequestAutoProcessing.RX
    cost_breakdown = CostBreakdownFactory.create(
        wallet_id=wallet_with_approved_direct_billing_request_no_claim.id,
        deductible=deductible,
        total_member_responsibility=total_member_responsibility,
        total_employer_responsibility=total_employer_responsibility,
    )

    mock_response = make_mocked_direct_payment_claim_response(
        200, 0, 13.80, txn_approved_amt
    )

    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_request.return_value = mock_response
        reimbursement_amount = (
            cost_breakdown.deductible
            if claim_type == ClaimType.EMPLOYEE_DEDUCTIBLE
            else reimbursement_request.usd_reimbursement_amount
        )
        create_auto_processed_claim_in_alegeus(
            wallet=wallet_with_approved_direct_billing_request_no_claim,
            reimbursement_request=reimbursement_request,
            reimbursement_amount=reimbursement_amount,
            claim_type=claim_type,
            reimbursement_mode=ReimbursementMethod.DIRECT_DEPOSIT,
        )
        reimbursement_claim = ReimbursementClaim.query.filter_by(
            reimbursement_request_id=reimbursement_request.id
        ).all()
        mock_request.assert_called_once()
        assert len(reimbursement_claim) == 1
        assert (
            mock_request.call_args.kwargs["data"]["ApprovedClaimAmount"]
            == expected_amount
        )


@pytest.mark.parametrize(
    argnames=(
        "status_code",
        "error_code",
        "txn_amt_org",
        "txn_approved_amt",
        "error_string",
    ),
    argvalues=[
        # Case 1: error status code
        (404, 0, 13.80, 13.80, "Unsuccessful response status code"),
        # Case 2: error code in the response
        (200, 133, 13.80, 13.80, "Error in the response for claim"),
        # Case 3: TxnAmtOrig not available
        (200, 0, None, 13.80, "TxnAmtOrig in the response is unavailable"),
        # Case 4: TxnApprovedAmt not available
        (200, 0, 13.80, None, "TxnApprovedAmt in the response is unavailable"),
    ],
    ids=[
        "error-status-code",
        "error-code-in-response",
        "TxnAmtOrig-not-available",
        "TxnApprovedAmt-not-available",
    ],
)
def test_create_auto_processed_claim_in_alegeus__failed_mock_alegeus_api(
    wallet_with_approved_direct_billing_request_no_claim,
    status_code,
    error_code,
    txn_amt_org,
    txn_approved_amt,
    error_string,
    make_mocked_direct_payment_claim_response,
):
    wallet = wallet_with_approved_direct_billing_request_no_claim
    reimbursement_request = (
        wallet_with_approved_direct_billing_request_no_claim.reimbursement_requests[0]
    )
    reimbursement_request.procedure_type = TreatmentProcedureType.PHARMACY.value
    reimbursement_request.auto_processed = ReimbursementRequestAutoProcessing.RX
    given_mock_response = make_mocked_direct_payment_claim_response(
        status_code, error_code, txn_amt_org, txn_approved_amt
    )

    with patch("wallet.alegeus_api.AlegeusApi.make_api_request") as mock_request:
        mock_request.return_value = given_mock_response

        with pytest.raises(CreateDirectPaymentClaimErrorResponseException) as e:
            create_auto_processed_claim_in_alegeus(
                wallet=wallet,
                reimbursement_request=reimbursement_request,
                reimbursement_amount=1234,
                claim_type=ClaimType.EMPLOYER,
                reimbursement_mode=ReimbursementMethod.DIRECT_DEPOSIT,
            )
        reimbursement_claim = ReimbursementClaim.query.filter_by(
            reimbursement_request_id=reimbursement_request.id
        ).all()
        mock_request.assert_called_once()
        assert error_string in str(e.value)
        assert len(reimbursement_claim) == 0


def test_create_auto_processed_claim_in_alegeus__account_not_found(
    qualified_alegeus_wallet_hdhp_family,
    wallet_with_approved_direct_billing_request_no_claim,
):
    # Using a different wallet than the RR wallet
    reimbursement_request = (
        wallet_with_approved_direct_billing_request_no_claim.reimbursement_requests[0]
    )
    reimbursement_request.procedure_type = TreatmentProcedureType.PHARMACY.value
    reimbursement_request.auto_processed = ReimbursementRequestAutoProcessing.RX

    with patch(
        "wallet.utils.alegeus.claims.create.AlegeusApi.post_direct_payment_claim"
    ) as mock_api:
        with pytest.raises(AutoProcessedDirectPaymentException) as e:
            create_auto_processed_claim_in_alegeus(
                wallet=qualified_alegeus_wallet_hdhp_family,
                reimbursement_request=reimbursement_request,
                reimbursement_amount=1234,
                claim_type=ClaimType.EMPLOYER,
                reimbursement_mode=ReimbursementMethod.DIRECT_DEPOSIT,
            )

        mock_api.assert_not_called()
        assert (
            e.value.args[0] == "Can not find reimbursement account from Reimbursement"
        )


@pytest.mark.parametrize(
    argnames=(
        "procedure_type",
        "auto_processing",
    ),
    argvalues=[
        ("MEDICAL", ReimbursementRequestAutoProcessing.RX),
        ("PHARMACY", None),
    ],
)
def test_create_auto_processed_claim_in_alegeus__invalid_reimbursement_request_type(
    procedure_type,
    auto_processing,
    wallet_with_pending_requests_no_claims,
):
    reimbursement_request = (
        wallet_with_pending_requests_no_claims.reimbursement_requests[0]
    )
    reimbursement_request.procedure_type = procedure_type
    reimbursement_request.auto_processed = auto_processing
    with patch(
        "wallet.utils.alegeus.claims.create.AlegeusApi.post_direct_payment_claim"
    ) as mock_api:
        with pytest.raises(AutoProcessedDirectPaymentException) as e:
            create_auto_processed_claim_in_alegeus(
                wallet=wallet_with_pending_requests_no_claims,
                reimbursement_request=reimbursement_request,
                reimbursement_amount=1234,
                claim_type=ClaimType.EMPLOYER,
                reimbursement_mode=ReimbursementMethod.DIRECT_DEPOSIT,
            )

        mock_api.assert_not_called()
        assert (
            e.value.args[0]
            == "The reimbursement request is invalid for an auto approved claim."
        )
