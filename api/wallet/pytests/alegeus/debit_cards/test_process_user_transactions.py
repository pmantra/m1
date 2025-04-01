import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from requests import Response

from pytests.factories import DefaultUserFactory
from storage.connection import db
from wallet.alegeus_api import format_date_from_string_to_datetime
from wallet.models.constants import (
    AlegeusTransactionStatus,
    CardStatus,
    ReimbursementRequestState,
    ReimbursementRequestType,
    TaxationState,
)
from wallet.models.reimbursement import ReimbursementRequest, ReimbursementTransaction
from wallet.pytests.factories import (
    ReimbursementRequestCategoryFactory,
    ReimbursementRequestFactory,
    ReimbursementTransactionFactory,
    ReimbursementWalletDebitCardFactory,
    ReimbursementWalletFactory,
)
from wallet.utils.alegeus.debit_cards.transactions.process_user_transactions import (
    AlegeusAuthType,
    AlegeusTransactionType,
    compute_prepayment_and_taxation,
    create_reimbursement_request,
    create_reimbursement_transaction,
    create_response_dict_from_api,
    get_all_debit_card_transactions,
    get_notes_from_alegeus_transaction_details,
    get_transaction_details_from_alegeus,
    map_reimbursement_request_state_from_transaction_status,
    process_transactions,
    update_reimbursement_request,
    update_reimbursement_transaction,
)


@pytest.fixture(scope="function")
def get_employee_activity_response_multi():
    def _get_employee_activity_response_multi(
        second_transaction_key="1250000411-20220817-89101112",
        second_sequence_num=1,
        second_description=AlegeusAuthType.CARD_POST.value,
        second_transaction_type=AlegeusTransactionType.CARD_TRANSACTION.value,
        second_amount=5.00,
        second_status_code=12,
    ):
        response = [
            {
                "AccountsPaidAmount": 6.8800,
                "Amount": 6.8800,
                "CardTransactionDetails": {
                    "MerchantName": "MEDICALTESTING",
                    "CustomDescription": "FAMILYFUND",
                },
                "Claimant": "Jane Doe",
                "Date": "/Date(1664371751010-0500)/",
                "Description": AlegeusAuthType.CARD_POST.value,
                "DisplayStatus": "Action Required",
                "HasReceipts": False,
                "PendedComment": None,
                "PendedReason": None,
                "SeqNumber": 1,
                "ServiceEndDate": "/Date(1663736400000-0500)/",
                "ServiceStartDate": "/Date(1663736400000-0500)/",
                "SettlementDate": "20220928",
                "Status": "Paid",
                "StatusCode": 12,
                "TransactionKey": "1250000411-20220817-1234567",
                "Type": AlegeusTransactionType.CARD_TRANSACTION.value,
                "CustomDescription": "FAMILYFUND",
                "AcctTypeCode": "HRA",
            },
            {
                "AccountsPaidAmount": 10.8800,
                "Amount": second_amount,
                "CardTransactionDetails": {
                    "MerchantName": "",
                    "CustomDescription": "FAMILYFUND",
                },
                "Claimant": "Joe Doe",
                "Date": "/Date(1664371751010-0500)/",
                "Description": second_description,
                "DisplayStatus": "Action Required",
                "HasReceipts": True,
                "PendedComment": None,
                "PendedReason": None,
                "SeqNumber": second_sequence_num,
                "ServiceEndDate": "/Date(1663736400000-0500)/",
                "ServiceStartDate": "/Date(1663736400000-0500)/",
                "SettlementDate": "20220928",
                "Status": "Paid",
                "StatusCode": second_status_code,
                "TransactionKey": second_transaction_key,
                "Type": second_transaction_type,
                "CustomDescription": "FAMILYFUND",
                "AcctTypeCode": "HRA",
            },
        ]
        return response

    return _get_employee_activity_response_multi


@pytest.fixture(scope="function")
def wallet_debit_card(qualified_alegeus_wallet_hra):
    """
    Use the method provided by this fixture to add a debit card to your wallet.
    """
    wallet = qualified_alegeus_wallet_hra
    wallet.debit_card = ReimbursementWalletDebitCardFactory(
        reimbursement_wallet_id=wallet.id,
        card_status=CardStatus.ACTIVE,
    )


@pytest.fixture(scope="function")
def get_transaction_details_response():
    def _get_transaction_details_response():
        response = {
            "PlanID": "123",
            "AccTypeCode": "string",
            "PlanStartDate": "20210101",
            "PlanEndDate": "20221201",
            "Amount": 10,
            "TransactionCode": 1,
            "TransactionStatus": 12,
            "TransactionDate": "2023-01-09T16:26:03.864Z",
            "SeqNum": "1",
            "SettlementDate": "20220928",
            "SettlementSeqNum": 0,
            "TransactionKey": "1250000411-20220817-1234567",
            "ReimbDate": "20220925",
            "Notes": "prepaid",
            "DeductibleAmount": 0,
            "ServiceStartDate": "2023-01-09T16:26:03.864Z",
            "ServiceEndDate": "2023-01-09T16:26:03.864Z",
            "CardNumber": "123456789",
            "ReimbAmt": 0,
        }
        return response

    return _get_transaction_details_response


def test_get_all_debit_card_transactions__successful(
    wallet_debit_card,
    qualified_alegeus_wallet_hra,
    get_employee_activity_response_multi,
):
    mock_activity_response = Response()
    mock_activity_response.status_code = 200
    mock_activity_response.json = get_employee_activity_response_multi

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_employee_activity"
    ) as mock_activity_request, patch("utils.braze_events.braze.send_event") as event:
        mock_activity_request.return_value = mock_activity_response
        success = get_all_debit_card_transactions(qualified_alegeus_wallet_hra)

        reimbursement_transactions = ReimbursementTransaction.query.all()
        assert success is True
        assert (
            reimbursement_transactions[0].reimbursement_request.label
            == "MEDICALTESTING"
        )
        assert (
            reimbursement_transactions[1].reimbursement_request.label
            == "Maven Card Transaction"
        )
        assert (
            reimbursement_transactions[0].reimbursement_request.state.value
            == ReimbursementRequestState.NEEDS_RECEIPT.value
        )
        assert (
            reimbursement_transactions[1].reimbursement_request.state.value
            == ReimbursementRequestState.RECEIPT_SUBMITTED.value
        )
        assert len(reimbursement_transactions) == 2
        assert event.call_count == 1


def test_get_all_debit_card_refunded_transactions_not_created(
    wallet_debit_card,
    qualified_alegeus_wallet_hra,
    get_employee_activity_response_multi,
):
    # Tests a refunded transaction by setting amount positive and type to manual.
    mock_activity_response = Response()
    mock_activity_response.status_code = 200
    mock_activity_response.json = lambda: get_employee_activity_response_multi(
        second_transaction_type=AlegeusTransactionType.MANUAL_CLAIM.value,
        second_amount=8.00,
    )

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_employee_activity"
    ) as mock_activity_request:
        mock_activity_request.return_value = mock_activity_response

        success = get_all_debit_card_transactions(qualified_alegeus_wallet_hra)

        reimbursement_transactions = ReimbursementTransaction.query.all()

        assert success is True
        assert len(reimbursement_transactions) == 1


def test_get_all_debit_card_refunded_transactions(
    wallet_debit_card,
    qualified_alegeus_wallet_hra,
    get_employee_activity_response_multi,
):
    # Tests a refunded transaction by setting amount to negative and type to manual.
    mock_activity_response = Response()
    mock_activity_response.status_code = 200
    mock_activity_response.json = lambda: get_employee_activity_response_multi(
        second_transaction_type=AlegeusTransactionType.MANUAL_CLAIM.value,
        second_amount=-8.00,
        second_status_code=1,
    )

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_employee_activity"
    ) as mock_activity_request:
        mock_activity_request.return_value = mock_activity_response

        success = get_all_debit_card_transactions(qualified_alegeus_wallet_hra)

        reimbursement_transactions = ReimbursementTransaction.query.all()

        assert success is True
        assert (
            reimbursement_transactions[1].reimbursement_request.state.value
            == ReimbursementRequestState.REFUNDED.value
        )

        assert len(reimbursement_transactions) == 2


def test_get_all_debit_card_split_transactions_created(
    wallet_debit_card,
    qualified_alegeus_wallet_hra,
    get_employee_activity_response_multi,
):
    mock_activity_response = Response()
    mock_activity_response.status_code = 200
    mock_activity_response.json = lambda: get_employee_activity_response_multi(
        second_transaction_key="1250000411-20220817-1234567",  # same as first
        second_sequence_num=2,
    )

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_employee_activity"
    ) as mock_activity_request:
        mock_activity_request.return_value = mock_activity_response

        success = get_all_debit_card_transactions(qualified_alegeus_wallet_hra)

        reimbursement_transactions = ReimbursementTransaction.query.all()

        assert success is True
        assert len(reimbursement_transactions) == 2


def test_get_all_debit_card_split_transactions_updated(
    wallet_debit_card,
    qualified_alegeus_wallet_hra,
    get_employee_activity_response_multi,
):
    transaction_key = "1250000411-20220817-1234567"  # key in first activity response
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    reimbursement_request1 = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hra,
        category=category,
        state=ReimbursementRequestState.NEEDS_RECEIPT,
    )
    ReimbursementTransactionFactory(
        alegeus_transaction_key=transaction_key,
        sequence_number=1,
        status=AlegeusTransactionStatus.RECEIPT.value,
        reimbursement_request=reimbursement_request1,
    )
    reimbursement_request2 = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hra,
        category=category,
        state=ReimbursementRequestState.NEEDS_RECEIPT,
    )
    ReimbursementTransactionFactory(
        alegeus_transaction_key=transaction_key,
        sequence_number=2,
        status=AlegeusTransactionStatus.RECEIPT.value,
        reimbursement_request=reimbursement_request2,
    )

    mock_activity_response = Response()
    mock_activity_response.status_code = 200
    mock_activity_response.json = lambda: get_employee_activity_response_multi(
        second_transaction_key=transaction_key,
        second_sequence_num=2,
        second_status_code=AlegeusTransactionStatus.APPROVED.value,
    )

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_employee_activity"
    ) as mock_activity_request, patch(
        "wallet.utils.alegeus.debit_cards.transactions.process_user_transactions.get_notes_from_alegeus_transaction_details"
    ) as mock_get_notes, patch(
        "wallet.utils.alegeus.debit_cards.transactions.process_user_transactions.emit_bulk_audit_log_update"
    ) as mock_emit_log, patch(
        "flask_login.current_user"
    ) as mock_current_user:
        mock_current_user.return_value = DefaultUserFactory.create()
        mock_activity_request.return_value = mock_activity_response
        mock_get_notes.return_value = None
        mock_emit_log.return_value = None
        success = get_all_debit_card_transactions(qualified_alegeus_wallet_hra)

        reimbursement_transactions = ReimbursementTransaction.query.all()
        mock_emit_log.assert_called_once()
        assert success is True
        assert len(reimbursement_transactions) == 2  # unchanged
        assert (
            reimbursement_request1.state == ReimbursementRequestState.NEEDS_RECEIPT
        )  # unchanged
        assert (
            reimbursement_request2.state == ReimbursementRequestState.APPROVED
        )  # updated


def test_get_all_debit_card_transactions__failed_get_activity(
    wallet_debit_card, qualified_alegeus_wallet_hra, get_employee_activity_response
):
    # Testing a failed get_employee_activity endpoint. No data to process.
    mock_activity_response = Response()
    mock_activity_response.status_code = 500
    mock_activity_response.json = lambda: {}

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_employee_activity"
    ) as mock_activity_request:
        mock_activity_request.return_value = mock_activity_response

        success = get_all_debit_card_transactions(qualified_alegeus_wallet_hra)
        reimbursement_transactions = ReimbursementTransaction.query.all()

        assert success is False
        assert len(reimbursement_transactions) == 0


def test_get_all_debit_card_transactions__failed_no_debit_card(
    qualified_alegeus_wallet_hra, get_employee_activity_response
):
    # Tests passing in a wallet without a debit card. No data to process
    success = get_all_debit_card_transactions(qualified_alegeus_wallet_hra)
    reimbursement_transactions = ReimbursementTransaction.query.all()

    assert success is False
    assert len(reimbursement_transactions) == 0


def test_process_transactions_auth_approved_does_not_create_request(
    wallet_debit_card,
    qualified_alegeus_wallet_hra,
    get_employee_activity_response_multi,
):
    # Tests a transaction with an AUTH type and Needs Receipt status does not create transaction/reimbursement
    mock_activity_response = Response()
    mock_activity_response.status_code = 200
    mock_activity_response.json = lambda: get_employee_activity_response_multi(
        second_transaction_key="1150000411-20220817-1234567",
    )

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_employee_activity"
    ) as mock_activity_request:

        mock_activity_request.return_value = mock_activity_response
        get_all_debit_card_transactions(qualified_alegeus_wallet_hra)

        reimbursement_transactions = ReimbursementTransaction.query.all()
        reimbursement_requests = ReimbursementRequest.query.all()

        assert (
            reimbursement_transactions[0].reimbursement_request.label
            == "MEDICALTESTING"
        )
        assert (
            reimbursement_transactions[0].reimbursement_request.state.value
            == ReimbursementRequestState.NEEDS_RECEIPT.value
        )
        assert len(reimbursement_transactions) == 1
        assert len(reimbursement_requests) == 1


def test_process_transactions_auth_denied_creates_request(
    wallet_debit_card,
    qualified_alegeus_wallet_hra,
    get_employee_activity_response_multi,
):
    # Tests a transaction with an AUTH type and DENIED status does create transaction/reimbursement
    mock_activity_response = Response()
    mock_activity_response.status_code = 200
    mock_activity_response.json = lambda: get_employee_activity_response_multi(
        second_transaction_key="1150000411-20220817-1234567",
        second_status_code=13,
    )
    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_employee_activity"
    ) as mock_activity_request, patch("utils.braze_events.braze.send_event") as event:
        mock_activity_request.return_value = mock_activity_response
        get_all_debit_card_transactions(qualified_alegeus_wallet_hra)

        reimbursement_transactions = ReimbursementTransaction.query.all()
        reimbursement_requests = ReimbursementRequest.query.all()

        assert (
            reimbursement_transactions[0].reimbursement_request.label
            == "MEDICALTESTING"
        )
        assert (
            reimbursement_transactions[1].reimbursement_request.state.value
            == ReimbursementRequestState.FAILED.value
        )
        assert len(reimbursement_transactions) == 2
        assert len(reimbursement_requests) == 2
        assert event.call_count == 2


def test_get_all_debit_card_transactions__failed_no_wallet_or_plan(
    wallet_debit_card, get_employee_activity_response
):
    # This tests a wallet with no plan
    transaction_detail = get_employee_activity_response()
    wallet = ReimbursementWalletFactory()

    process_transactions(transaction_detail, wallet)

    reimbursement_transactions = ReimbursementTransaction.query.all()
    assert len(reimbursement_transactions) == 0


def test_get_all_debit_card_transactions__failed_missing_transaction_start_date(
    wallet_debit_card,
    qualified_alegeus_wallet_hra,
    get_employee_activity_response,
):
    # This tests a transaction with no start date
    transaction_detail = get_employee_activity_response(start_date=None)
    process_transactions(transaction_detail, qualified_alegeus_wallet_hra)

    reimbursement_transactions = ReimbursementTransaction.query.all()
    assert len(reimbursement_transactions) == 0


def test_get_all_debit_card_transactions__type_not_card_transaction(
    wallet_debit_card,
    qualified_alegeus_wallet_hra,
    get_employee_activity_response_multi,
):
    # This tests a transaction with no one CARD_TRANSACTION one MANUAL_CLAIM
    transaction_detail = get_employee_activity_response_multi(
        second_transaction_type=AlegeusTransactionType.MANUAL_CLAIM.value
    )
    process_transactions(transaction_detail, qualified_alegeus_wallet_hra)

    reimbursement_transactions = ReimbursementTransaction.query.all()
    assert len(reimbursement_transactions) == 1


def test_format_date_from_string_to_datetime():
    date_string = "/Date(1660712400000-0500)/"
    set_date = datetime.datetime(2022, 8, 17, 5, 0)
    calculated_date = format_date_from_string_to_datetime(date_string)
    assert isinstance(calculated_date, datetime.datetime)
    assert set_date == calculated_date


def test_format_date_from_string_to_datetime__fails():
    date_string = ""
    with pytest.raises(AttributeError):
        format_date_from_string_to_datetime(date_string)


def test_create_response_dict_from_api(get_employee_activity_response):
    transaction = get_employee_activity_response()[0]
    activity_response_dict = create_response_dict_from_api(transaction)
    assert len(activity_response_dict) == 18
    assert isinstance(activity_response_dict.get("settlement_date"), datetime.date)
    assert isinstance(activity_response_dict.get("service_end_date"), datetime.datetime)
    assert activity_response_dict.get("amount") == 15000


def test_create_response_dict_from_api__fails(get_employee_activity_response):
    transaction = get_employee_activity_response(start_date=None)[0]
    with pytest.raises(AttributeError):
        create_response_dict_from_api(transaction)


def test_update_reimbursement_transaction_success(
    qualified_alegeus_wallet_hra,
    get_employee_activity_response,
):
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    reimbursement_request = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hra,
        category=category,
        state=ReimbursementRequestState.NEW,
    )
    reimbursement_transaction = ReimbursementTransactionFactory(
        alegeus_transaction_key="1250000411-20220817-16154520",
        status=19,  # Not mapped
        reimbursement_request=reimbursement_request,
    )
    transaction = get_employee_activity_response()[0]
    activity_response_dict = create_response_dict_from_api(transaction)
    update_reimbursement_transaction(activity_response_dict, None)
    db.session.commit()

    # is_prepaid is False by default
    assert reimbursement_request.is_prepaid is False
    assert (
        reimbursement_transaction.status
        == AlegeusTransactionStatus.INELIGIBLE_EXPENSE.value
    )


def test_update_reimbursement_request_success(
    qualified_alegeus_wallet_hra,
    get_employee_activity_response,
):
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    reimbursement_request = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hra,
        category=category,
        state=ReimbursementRequestState.PENDING,
        reimbursement_type=ReimbursementRequestType.DEBIT_CARD,
        is_prepaid=True,
    )
    reimbursement_transaction = ReimbursementTransactionFactory(
        alegeus_transaction_key="1250000411-20220817-1234567",
        status=AlegeusTransactionStatus.FAILED.value,
        reimbursement_request=reimbursement_request,
        notes="prepayment",
    )
    transaction = get_employee_activity_response()[0]
    activity_response_dict = create_response_dict_from_api(transaction)
    with patch("utils.braze_events.braze.send_event") as event:
        update_reimbursement_request(reimbursement_transaction, activity_response_dict)
        db.session.commit()
        assert reimbursement_request.is_prepaid is True
        assert reimbursement_transaction.notes == "prepayment"
        assert reimbursement_request.state == ReimbursementRequestState.FAILED
        assert event.assert_called
        assert event.call_args[0][1] == "debit_card_transaction_denied"


def test_update_reimbursement_request_sends_email__success(
    qualified_alegeus_wallet_hra,
    get_employee_activity_response,
):
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    reimbursement_request = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hra,
        category=category,
        state=ReimbursementRequestState.PENDING,
        reimbursement_type=ReimbursementRequestType.DEBIT_CARD,
    )
    reimbursement_transaction = ReimbursementTransactionFactory(
        alegeus_transaction_key="1250000411-20220817-1234567",
        status=AlegeusTransactionStatus.APPROVED.value,
        reimbursement_request=reimbursement_request,
    )
    transaction = get_employee_activity_response()[0]
    activity_response_dict = create_response_dict_from_api(transaction)
    with patch("utils.braze_events.braze.send_event") as event:
        update_reimbursement_request(reimbursement_transaction, activity_response_dict)
        db.session.commit()
        assert reimbursement_request.state == ReimbursementRequestState.APPROVED
        assert event.call_args[0][1] == "debit_card_transaction_approved"
        assert event.call_args[0][2]["transaction_amount"] == "150.00"


def test_create_reimbursement_transaction_and_reimbursement_request_success(
    qualified_alegeus_wallet_hra,
    get_employee_activity_response,
    get_transaction_details_response,
):
    # Transaction without a receipt and code 12 should send an email prompting member to upload receipt.
    transaction = get_employee_activity_response(has_receipts=False, status_code=12)[0]
    activity_response_dict = create_response_dict_from_api(transaction)
    transaction_details = get_transaction_details_response()
    notes = transaction_details.get("Notes")

    with patch("utils.braze_events.braze.send_event") as event:
        reimbursement_request = create_reimbursement_request(
            activity_response_dict,
            qualified_alegeus_wallet_hra,
            notes,
        )
        reimbursement_transaction = create_reimbursement_transaction(
            activity_response_dict,
            reimbursement_request,
            notes,
        )
        assert (
            reimbursement_request.id
            == reimbursement_transaction.reimbursement_request.id
        )
        assert reimbursement_request.state == ReimbursementRequestState.NEEDS_RECEIPT
        assert reimbursement_request.is_prepaid is True
        assert reimbursement_transaction.notes == notes
        assert event.call_args[0][1] == "debit_card_transaction_needs_receipt"
        assert event.call_args[0][2]["transaction_amount"] == "150.00"


def test_create_reimbursement_request_populates_currency_columns(
    qualified_alegeus_wallet_hra,
    get_employee_activity_response,
    get_transaction_details_response,
):
    # Given
    transaction = get_employee_activity_response(has_receipts=False, status_code=12)[0]
    activity_response_dict = create_response_dict_from_api(transaction)
    transaction_details = get_transaction_details_response()
    notes = transaction_details.get("Notes")
    expected_amount: int = activity_response_dict.get("amount")
    expected_rate = Decimal("1.00")

    # When
    reimbursement_request = create_reimbursement_request(
        activity_response_dict,
        qualified_alegeus_wallet_hra,
        notes,
    )

    # Then
    assert (
        reimbursement_request.usd_amount,
        reimbursement_request.transaction_amount,
        reimbursement_request.transaction_currency_code,
        reimbursement_request.amount,
        reimbursement_request.benefit_currency_code,
        reimbursement_request.transaction_to_benefit_rate,
        reimbursement_request.transaction_to_usd_rate,
    ) == (
        expected_amount,
        expected_amount,
        "USD",
        expected_amount,
        "USD",
        expected_rate,
        expected_rate,
    )


def test_create_reimbursement_request_fails__no_plan(
    get_employee_activity_response, get_transaction_details_response
):
    # Passes in a wallet with no plan created
    transaction = get_employee_activity_response()[0]
    transaction_details = get_transaction_details_response()
    activity_response_dict = create_response_dict_from_api(transaction)
    wallet = ReimbursementWalletFactory()
    reimbursement_request = create_reimbursement_request(
        activity_response_dict, wallet, transaction_details.get("Notes")
    )

    assert reimbursement_request is None


@pytest.mark.parametrize(
    argnames="transaction_status, has_receipt, amount, display_status, old_state, expected_status",
    argvalues=[
        (1, None, 100, None, None, ReimbursementRequestState.APPROVED),
        (1, None, -100, None, None, ReimbursementRequestState.REFUNDED),
        (13, None, 100, None, None, ReimbursementRequestState.FAILED),
        (12, None, 100, None, None, ReimbursementRequestState.NEEDS_RECEIPT),
        (12, True, 100, None, None, ReimbursementRequestState.RECEIPT_SUBMITTED),
        (
            12,
            True,
            100,
            None,
            ReimbursementRequestState.APPROVED,
            ReimbursementRequestState.RECEIPT_SUBMITTED,
        ),
        (12, False, 100, None, None, ReimbursementRequestState.NEEDS_RECEIPT),
        (
            12,
            False,
            100,
            None,
            ReimbursementRequestState.INSUFFICIENT_RECEIPT,
            ReimbursementRequestState.NEEDS_RECEIPT,
        ),
        (
            12,
            True,
            100,
            None,
            ReimbursementRequestState.INSUFFICIENT_RECEIPT,
            ReimbursementRequestState.INSUFFICIENT_RECEIPT,
        ),
        (16, None, 100, None, None, ReimbursementRequestState.INELIGIBLE_EXPENSE),
        (15, None, 100, None, None, ReimbursementRequestState.RESOLVED),
        (4, None, 100, None, None, ReimbursementRequestState.RESOLVED),
        (2, None, 100, None, None, ReimbursementRequestState.REFUNDED),
        (99, False, 100, None, None, ReimbursementRequestState.NEW),
        (None, None, None, None, None, ReimbursementRequestState.NEW),
    ],
)
def test_map_reimbursement_request_state_from_transaction_status(
    transaction_status, has_receipt, amount, display_status, old_state, expected_status
):
    assert (
        map_reimbursement_request_state_from_transaction_status(
            transaction_status, has_receipt, amount, display_status, old_state
        )
        == expected_status
    )


def test_get_transaction_details_from_alegeus__successful(
    qualified_alegeus_wallet_hra,
    get_transaction_details_response,
):
    transaction_details_response = get_transaction_details_response()
    transactionid = transaction_details_response.get("TransactionKey")
    seqnum = transaction_details_response.get("SeqNum")
    setldate = transaction_details_response.get("SettlementDate")

    mock_transaction_details_response = Response()
    mock_transaction_details_response.status_code = 200
    mock_transaction_details_response.json = lambda: transaction_details_response

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_transaction_details"
    ) as mock_get_transaction_details:
        mock_get_transaction_details.return_value = mock_transaction_details_response
        is_success, transaction_details = get_transaction_details_from_alegeus(
            qualified_alegeus_wallet_hra, transactionid, seqnum, setldate
        )
        assert is_success is True
        assert transaction_details == transaction_details_response


def test_get_transaction_details_from_alegeus__failed_api_call(
    qualified_alegeus_wallet_hra, get_transaction_details_response
):
    transaction_details_response = get_transaction_details_response()
    transactionid = transaction_details_response.get("TransactionKey")
    seqnum = transaction_details_response.get("SeqNum")
    setldate = transaction_details_response.get("SettlementDate")

    # Testing a failed get_transaction_details endpoint. No data to process.
    mock_transaction_details_response = Response()
    mock_transaction_details_response.status_code = 500
    mock_transaction_details_response.json = None

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_transaction_details"
    ) as mock_get_transaction_details:
        mock_get_transaction_details.return_value = mock_transaction_details_response
        success, transaction_details = get_transaction_details_from_alegeus(
            qualified_alegeus_wallet_hra, transactionid, seqnum, setldate
        )
        assert success is False
        assert transaction_details is None


def test_get_transaction_details_from_alegeus__failed_no_query_params(
    qualified_alegeus_wallet_hra,
):
    mock_get_transaction_details = Response()
    mock_get_transaction_details.status_code = 400

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_transaction_details"
    ) as mock_get_transaction_details_request:
        mock_get_transaction_details_request.return_value = mock_get_transaction_details
        success, transaction_details = get_transaction_details_from_alegeus(
            qualified_alegeus_wallet_hra, None, None, None
        )

        assert success is False
        assert transaction_details is None


def test_update_reimbursement_transaction_and_update_reimbursement_request_card_transaction(
    qualified_alegeus_wallet_hra,
    get_employee_activity_response,
    get_transaction_details_response,
):
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    reimbursement_request = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hra,
        category=category,
        state=ReimbursementRequestState.NEW,
    )
    ReimbursementTransactionFactory(
        alegeus_transaction_key="1250000411-20220817-16154520",
        status=12,
        reimbursement_request=reimbursement_request,
    )

    mock_transaction_details_response = Response()
    mock_transaction_details_response.status_code = 200
    mock_transaction_details_response.json = get_transaction_details_response

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_transaction_details"
    ) as mock_get_transaction_details:
        mock_get_transaction_details.return_value = mock_transaction_details_response
        transaction = get_employee_activity_response()[0]
        activity_response_dict = create_response_dict_from_api(transaction)
        notes = get_notes_from_alegeus_transaction_details(
            qualified_alegeus_wallet_hra, transaction
        )
        reimbursement_transaction = update_reimbursement_transaction(
            activity_response_dict, notes
        )
        reimbursement_request = update_reimbursement_request(
            reimbursement_transaction, activity_response_dict
        )
        db.session.commit()

        assert reimbursement_transaction.notes == "prepaid"
        assert reimbursement_request.is_prepaid is True
        assert reimbursement_request.taxation_status == TaxationState.TAXABLE
        assert (
            reimbursement_transaction.status
            == AlegeusTransactionStatus.INELIGIBLE_EXPENSE.value
        )


def test_update_reimbursement_transaction_and_update_reimbursement_request_manual_claim(
    qualified_alegeus_wallet_hra,
    get_employee_activity_response,
    get_transaction_details_response,
):
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    reimbursement_request = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hra,
        category=category,
        state=ReimbursementRequestState.NEW,
    )
    ReimbursementTransactionFactory(
        alegeus_transaction_key="1250000411-20220817-16154520",
        status=12,
        reimbursement_request=reimbursement_request,
    )

    mock_transaction_details_response = Response()
    mock_transaction_details_response.status_code = 200
    mock_transaction_details_response.json = get_transaction_details_response

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_transaction_details"
    ) as mock_get_transaction_details:
        mock_get_transaction_details.return_value = mock_transaction_details_response
        employee_activity_response = get_employee_activity_response()[0]
        employee_activity_response["Type"] = AlegeusTransactionType.MANUAL_CLAIM

        activity_response_dict = create_response_dict_from_api(
            employee_activity_response
        )
        notes = get_notes_from_alegeus_transaction_details(
            qualified_alegeus_wallet_hra, employee_activity_response
        )

        reimbursement_transaction = update_reimbursement_transaction(
            activity_response_dict, notes
        )
        reimbursement_request = update_reimbursement_request(
            reimbursement_transaction, activity_response_dict
        )
        db.session.commit()

        assert reimbursement_transaction.notes == "prepaid"
        # assert is_prepaid is False for Manual Claims
        assert reimbursement_request.is_prepaid is False
        assert (
            reimbursement_transaction.status
            == AlegeusTransactionStatus.INELIGIBLE_EXPENSE.value
        )


def test_get_notes_from_alegeus_transaction_details_returns_notes(
    qualified_alegeus_wallet_hra,
    get_employee_activity_response,
    get_transaction_details_response,
):
    employee_activity = get_employee_activity_response()[0]
    mock_transaction_details_response = Response()
    mock_transaction_details_response.status_code = 200
    mock_transaction_details_response.json = get_transaction_details_response

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_transaction_details"
    ) as mock_get_transaction_details:
        mock_get_transaction_details.return_value = mock_transaction_details_response
        notes = get_notes_from_alegeus_transaction_details(
            qualified_alegeus_wallet_hra, employee_activity
        )
        assert notes == "prepaid"


def test_get_notes_from_alegeus_transaction_details_returns_none(
    qualified_alegeus_wallet_hra,
    get_employee_activity_response,
    get_transaction_details_response,
):
    employee_activity = get_employee_activity_response()[0]
    mock_transaction_details_response = Response()
    mock_transaction_details_response.status_code = 400
    mock_transaction_details_response.json = None

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_transaction_details"
    ) as mock_get_transaction_details:
        mock_get_transaction_details.return_value = mock_transaction_details_response
        notes = get_notes_from_alegeus_transaction_details(
            qualified_alegeus_wallet_hra, employee_activity
        )
        assert notes is None


@pytest.mark.parametrize(
    "transaction_type,notes,expected_is_prepaid,expected_taxation_status",
    [
        (
            AlegeusTransactionType.MANUAL_CLAIM.value,
            "",
            None,
            None,
        ),  # no notes, no changes
        (
            AlegeusTransactionType.CARD_TRANSACTION.value,
            "",
            None,
            None,
        ),  # same for debit
        (
            AlegeusTransactionType.MANUAL_CLAIM.value,
            "prepaid",
            None,
            None,
        ),  # prepaid doesn't affect manual
        (
            AlegeusTransactionType.CARD_TRANSACTION.value,
            "prepaid",
            True,
            TaxationState.TAXABLE,
        ),  # prepaid for debit
        (
            AlegeusTransactionType.CARD_TRANSACTION.value,
            "PREPAID",
            True,
            TaxationState.TAXABLE,
        ),  # all caps
        (
            AlegeusTransactionType.CARD_TRANSACTION.value,
            "PrePaid",
            True,
            TaxationState.TAXABLE,
        ),  # mixed case
        (
            AlegeusTransactionType.CARD_TRANSACTION.value,
            "pre-paid",
            True,
            TaxationState.TAXABLE,
        ),  # hyphenated
        (
            AlegeusTransactionType.CARD_TRANSACTION.value,
            "pre paid",
            True,
            TaxationState.TAXABLE,
        ),  # space
        (
            AlegeusTransactionType.CARD_TRANSACTION.value,
            "pre",
            True,
            TaxationState.TAXABLE,
        ),  # shorty
        (
            AlegeusTransactionType.CARD_TRANSACTION.value,
            "repaid",
            None,
            None,
        ),  # close but no cigar
    ],
)
def test_compute_prepayment_and_taxation(
    transaction_type: str, notes: str, expected_is_prepaid, expected_taxation_status
):
    is_prepaid, taxation_status = compute_prepayment_and_taxation(
        transaction_type, notes
    )
    assert is_prepaid == expected_is_prepaid
    assert taxation_status == expected_taxation_status
