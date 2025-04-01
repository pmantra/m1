import datetime
from decimal import Decimal
from unittest.mock import patch

from requests import Response

from pytests.factories import OrganizationEmployeeFactory
from wallet.models.constants import (
    CardStatus,
    CardStatusReason,
    ReimbursementRequestState,
    ReimbursementRequestType,
)
from wallet.models.reimbursement import ReimbursementRequest, ReimbursementTransaction
from wallet.models.reimbursement_wallet_debit_card import ReimbursementWalletDebitCard
from wallet.pytests.factories import (
    ReimbursementRequestCategoryFactory,
    ReimbursementRequestFactory,
    ReimbursementTransactionFactory,
    ReimbursementWalletDebitCardFactory,
    ReimbursementWalletFactory,
)
from wallet.utils.alegeus.edi_processing.edi_record_imports import (
    AlegeusExportRecordTypes,
)
from wallet.utils.alegeus.edi_processing.process_edi_transactions import (
    _process_em_record,
    _process_en_ek_record,
    _process_insufficient_transactions,
    download_and_process_alegeus_transactions_export,
    map_ek_records,
    map_em_records,
    map_en_records,
)


def test_map_en_records(en_record):
    en_dict = map_en_records(en_record())
    assert en_dict.get("record_type") == "EN"
    assert en_dict.get("transaction_status") == "AUP2"
    assert en_dict.get("employee_id") == "456"


def test_map_en_records_returns_none():
    en_dict = map_en_records([])
    assert en_dict is None


def test_map_ek_records(ek_record):
    ek_dict = map_ek_records(ek_record)
    assert ek_dict.get("record_type") == "EK"
    assert ek_dict.get("transaction_key") == "1250003156-20220908-14355875"
    assert ek_dict.get("employee_id") == "456"


def test_map_ek_records_returns_none():
    ek_dict = map_ek_records([])
    assert ek_dict is None


def test_map_em_records(em_record):
    record = em_record()
    em_dict = map_em_records(record)
    assert em_dict.get("record_type") == "EM"
    assert em_dict.get("shipment_tracking_number") == "tracking-number-123"
    assert em_dict.get("employee_id") == "456"


def test_map_em_records_returns_none():
    em_dict = map_em_records("")
    assert em_dict is None


@patch("wallet.utils.alegeus.edi_processing.process_edi_transactions")
@patch("flask_login.current_user")
def test_process_en_ek_record__success(
    mock_emit_audit_log_read,
    mock_current_user,
    en_record,
    qualified_alegeus_wallet_hra,
    get_employee_activity_response,
    wallet_debitcardinator,
):
    mock_emit_audit_log_read.return_value = None
    mock_current_user.return_value = {"id": "mock-id"}

    wallet = qualified_alegeus_wallet_hra
    wallet_debitcardinator(wallet)
    processed_records = set()

    mock_activity_response = Response()
    mock_activity_response.status_code = 200
    mock_activity_response.json = get_employee_activity_response

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_employee_activity"
    ) as mock_activity_request:
        mock_activity_request.return_value = mock_activity_response

        en_dict = map_en_records(en_record())
        _process_en_ek_record(en_dict, processed_records, AlegeusExportRecordTypes.EN)

        reimbursement_transaction = ReimbursementTransaction.query.first()

        assert reimbursement_transaction.reimbursement_request.wallet == wallet
        assert (
            reimbursement_transaction.alegeus_transaction_key
            == "1250000411-20220817-16154520"
        )
        assert reimbursement_transaction.reimbursement_request.label == "MEDICALTESTING"


def test_process_en_ek_record__empty(
    qualified_alegeus_wallet_hra,
    wallet_debitcardinator,
):
    wallet = qualified_alegeus_wallet_hra
    wallet_debitcardinator(wallet)
    processed_records = set()
    _process_en_ek_record({}, processed_records, AlegeusExportRecordTypes.EN)

    reimbursement_transaction = ReimbursementTransaction.query.all()
    assert len(reimbursement_transaction) == 0


def test_process_en_ek_record__skips_manual_claim(
    en_record,
    qualified_alegeus_wallet_hra,
    wallet_debitcardinator,
):
    wallet = qualified_alegeus_wallet_hra
    wallet_debitcardinator(wallet)
    processed_records = set()

    en_dict = map_en_records(en_record())
    # manual claims have empty values for card_proxy_number
    en_dict["card_proxy_number"] = None

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_employee_activity"
    ) as mock_activity_request:

        _process_en_ek_record(en_dict, processed_records, AlegeusExportRecordTypes.EN)

        assert ReimbursementTransaction.query.count() == 0
        assert mock_activity_request.call_count == 0


def test_process_en_ek_record_employee_id_exists(
    en_record,
    qualified_alegeus_wallet_hra,
    wallet_debitcardinator,
):
    wallet = qualified_alegeus_wallet_hra
    wallet_debitcardinator(wallet)
    processed_records = {"456"}

    en_dict = map_en_records(en_record())
    _process_en_ek_record(en_dict, processed_records, AlegeusExportRecordTypes.EN)

    reimbursement_transaction = ReimbursementTransaction.query.all()
    assert len(reimbursement_transaction) == 0


def test_process_en_ek_record_org_employee_does_not_exist(
    en_record,
    wallet_debitcardinator,
):
    wallet = ReimbursementWalletFactory()
    wallet_debitcardinator(wallet)
    processed_records = set()

    en_dict = map_en_records(en_record())
    _process_en_ek_record(en_dict, processed_records, AlegeusExportRecordTypes.EN)

    reimbursement_transaction = ReimbursementTransaction.query.all()
    assert len(reimbursement_transaction) == 0


def test_process_en_ek_record_wallet_does_not_exist(
    en_record,
):
    OrganizationEmployeeFactory(alegeus_id="456")
    processed_records = set()

    en_dict = map_en_records(en_record())
    _process_en_ek_record(en_dict, processed_records, AlegeusExportRecordTypes.EN)
    reimbursement_transaction = ReimbursementTransaction.query.all()

    assert len(reimbursement_transaction) == 0


@patch("wallet.utils.alegeus.edi_processing.process_edi_transactions")
@patch("flask_login.current_user")
def test_process_em_record_updates__success(
    mock_emit_audit_log_read, mock_current_user, em_record, qualified_alegeus_wallet_hra
):
    mock_emit_audit_log_read.return_value = None
    mock_current_user.return_value = {"id": "mock-id"}
    wallet = qualified_alegeus_wallet_hra
    ReimbursementWalletDebitCardFactory(
        reimbursement_wallet_id=wallet.id,
        card_proxy_number="1100054058115420",
        card_status=CardStatus.ACTIVE,
        card_status_reason=CardStatusReason.NONE,
    )
    success = _process_em_record(em_record())

    debit_card = ReimbursementWalletDebitCard.query.all()[0]

    assert success is True
    assert debit_card.shipping_tracking_number == "tracking-number-123"
    assert debit_card.card_status == CardStatus.CLOSED
    assert debit_card.card_status_reason == CardStatusReason.LOST_STOLEN
    assert debit_card.shipped_date == datetime.date(2022, 9, 19)


@patch("wallet.utils.alegeus.edi_processing.process_edi_transactions")
@patch("flask_login.current_user")
def test_process_em_record_creates__success(
    mock_emit_audit_log_read, mock_current_user, em_record, qualified_alegeus_wallet_hra
):
    mock_emit_audit_log_read.return_value = None
    mock_current_user.return_value = {"id": "mock-id"}
    assert len(ReimbursementWalletDebitCard.query.all()) == 0
    record = em_record(status=1)  # Sets the record to status 1 (NEW)
    success = _process_em_record(record)
    debit_card = ReimbursementWalletDebitCard.query.all()[0]

    assert len(ReimbursementWalletDebitCard.query.all()) == 1
    assert debit_card.card_proxy_number == "1100054058115420"
    assert debit_card.card_last_4_digits == "5420"
    assert success is True


@patch("wallet.utils.alegeus.edi_processing.process_edi_transactions")
@patch("flask_login.current_user")
def test_process_em_record_creates_when_a_card_exists(
    mock_emit_audit_log_read, mock_current_user, em_record, qualified_alegeus_wallet_hra
):
    mock_emit_audit_log_read.return_value = None
    mock_current_user.return_value = {"id": "mock-id"}
    wallet = qualified_alegeus_wallet_hra
    ReimbursementWalletDebitCardFactory(
        reimbursement_wallet_id=wallet.id,
        card_proxy_number="1100054058115422",
        card_status=CardStatus.CLOSED,
        card_status_reason=CardStatusReason.LOST_STOLEN,
    )
    record = em_record(status=1)  # Sets the record to status 1 (NEW)
    success = _process_em_record(record)
    debit_cards = ReimbursementWalletDebitCard.query.all()

    assert len(debit_cards) == 2
    assert success is True


def test_process_em_record_empty_dict(qualified_alegeus_wallet_hra):
    success = _process_em_record("")

    assert len(ReimbursementWalletDebitCard.query.all()) == 0
    assert success is False


@patch("wallet.utils.alegeus.edi_processing.process_edi_transactions")
@patch("flask_login.current_user")
def test_process_em_record_does_not_update_if_tracking_present(
    mock_emit_audit_log_read, mock_current_user, em_record, qualified_alegeus_wallet_hra
):
    mock_emit_audit_log_read.return_value = None
    mock_current_user.return_value = {"id": "mock-id"}
    wallet = qualified_alegeus_wallet_hra
    ReimbursementWalletDebitCardFactory(
        reimbursement_wallet_id=wallet.id,
        card_proxy_number="1100054058115420",
        card_status=CardStatus.ACTIVE,
        card_status_reason=CardStatusReason.NONE,
        shipping_tracking_number="abc",
    )
    record = em_record()
    success = _process_em_record(record)

    debit_card = ReimbursementWalletDebitCard.query.all()[0]

    assert debit_card is not None
    assert (
        debit_card.shipping_tracking_number == "abc"
    )  # em_record: tracking-number-123
    assert debit_card.card_status == CardStatus.CLOSED
    assert debit_card.card_status_reason == CardStatusReason.LOST_STOLEN
    assert debit_card.shipped_date == datetime.date(2022, 9, 19)
    assert success is True


def test_process_em_record_org_employee_does_not_exits(em_record):
    record = em_record()
    success = _process_em_record(record)

    assert len(ReimbursementWalletDebitCard.query.all()) == 0
    assert success is False


def test_process_em_record_wallet_does_not_exist(em_record):
    OrganizationEmployeeFactory(alegeus_id="456")
    success = _process_em_record(em_record())

    assert len(ReimbursementWalletDebitCard.query.all()) == 0
    assert success is False


def test_process_em_record_fail_setting_back_to_new(
    em_record, qualified_alegeus_wallet_hra
):
    wallet = qualified_alegeus_wallet_hra
    ReimbursementWalletDebitCardFactory(
        reimbursement_wallet_id=wallet.id,
        card_proxy_number="1100054058115420",
        card_status=CardStatus.ACTIVE,
        card_status_reason=CardStatusReason.NONE,
        shipping_tracking_number="abc",
    )

    record = em_record(status=1)  # Sets the record to status 1 (NEW)
    success = _process_em_record(record)
    debit_cards = ReimbursementWalletDebitCard.query.all()

    assert len(debit_cards) == 1
    assert debit_cards[0].card_status == CardStatus.ACTIVE
    assert success is False


def test_process_em_record_fail_setting_from_closed(
    em_record, qualified_alegeus_wallet_hra
):
    wallet = qualified_alegeus_wallet_hra
    ReimbursementWalletDebitCardFactory(
        reimbursement_wallet_id=wallet.id,
        card_proxy_number="1100054058115420",
        card_status=CardStatus.CLOSED,
        card_status_reason=CardStatusReason.NONE,
        shipping_tracking_number="abc",
    )

    record = em_record(status=2)  # Sets the record to status 2 (ACTIVE)
    success = _process_em_record(record)
    debit_cards = ReimbursementWalletDebitCard.query.all()

    assert len(debit_cards) == 1
    assert debit_cards[0].card_status == CardStatus.CLOSED
    assert success is False


@patch("wallet.utils.alegeus.edi_processing.process_edi_transactions")
@patch("flask_login.current_user")
def test_process_em_record_creates_card_if_does_not_exist_does_not_set_as_primary(
    mock_emit_audit_log_read, mock_current_user, em_record, qualified_alegeus_wallet_hra
):
    mock_emit_audit_log_read.return_value = None
    mock_current_user.return_value = {"id": "mock-id"}
    wallet = qualified_alegeus_wallet_hra
    debit_card = ReimbursementWalletDebitCardFactory(
        reimbursement_wallet_id=wallet.id,
        card_proxy_number="1100054058115499",
        card_status=CardStatus.CLOSED,
        card_status_reason=CardStatusReason.NONE,
        shipping_tracking_number="abc",
    )
    wallet.debit_card = debit_card

    record = em_record(status=4)  # Sets the record to status 4 (PERM INACTIVE)
    success = _process_em_record(record)
    debit_cards = ReimbursementWalletDebitCard.query.all()

    assert len(debit_cards) == 2
    assert debit_cards[1].card_status == CardStatus.CLOSED
    assert wallet.debit_card == debit_cards[0]
    assert success is True


def test_download_and_process_alegeus_transactions_export__success(export_file):
    file_date = datetime.datetime.now().date()
    file_name = file_date.strftime("%Y%m%d")
    with patch(
        "wallet.utils.alegeus.edi_processing.process_edi_transactions.get_files_from_alegeus"
    ) as client_mock, patch(
        "wallet.utils.alegeus.edi_processing.process_edi_transactions.create_temp_file"
    ) as file_mock, patch(
        "wallet.utils.alegeus.edi_processing.process_edi_transactions._process_en_ek_record",
        return_value=True,
    ):
        client_mock.return_value = None, None, [f"MAVENIL{file_name}.exp"]
        file_mock.return_value = export_file

        success = download_and_process_alegeus_transactions_export()
        assert success is True


def test_download_and_process_alegeus_transactions_export__fail(export_file):
    with patch(
        "wallet.utils.alegeus.edi_processing.process_edi_transactions.get_files_from_alegeus"
    ) as client_mock, patch(
        "wallet.utils.alegeus.edi_processing.process_edi_transactions.create_temp_file"
    ) as file_mock:
        client_mock.return_value = None, None, []
        file_mock.return_value = export_file

        success = download_and_process_alegeus_transactions_export()
        assert success is False


def test_download_and_process_alegeus_transactions_export_insufficient_receipt(
    export_file,
    qualified_alegeus_wallet_hra,
    get_employee_activity_response,
    wallet_debitcardinator,
):
    """
    This method tests that an EDI file with the insufficient status code updated the reimbursement request.  When the
    api returns the same transaction with a status code of 12 (NEEDS_RECEIPT) we do not allow the call to override
    the reimbursement state back to RECEIPT_SUBMITTED.
    """
    wallet_debitcardinator(qualified_alegeus_wallet_hra)

    mock_activity_response = Response()
    mock_activity_response.status_code = 200
    mock_activity_response.json = lambda: get_employee_activity_response(status_code=12)

    file_date = datetime.datetime.now().date()
    file_name = file_date.strftime("%Y%m%d")

    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    reimbursement_request = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hra,
        category=category,
        state=ReimbursementRequestState.NEEDS_RECEIPT,
        reimbursement_type=ReimbursementRequestType.DEBIT_CARD,
    )
    ReimbursementTransactionFactory(
        alegeus_transaction_key="1250000411-20220817-16154520",
        status=12,
        reimbursement_request=reimbursement_request,
        amount=Decimal("7093.00"),
        date=datetime.datetime.now(),
    )

    with patch(
        "wallet.utils.alegeus.edi_processing.process_edi_transactions.get_files_from_alegeus"
    ) as client_mock, patch("flask_login.current_user") as mock_current_user, patch(
        "wallet.utils.alegeus.edi_processing.process_edi_transactions.create_temp_file"
    ) as file_mock, patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_employee_activity"
    ) as mock_activity_request, patch(
        "utils.braze_events.braze.send_event"
    ) as event:
        client_mock.return_value = None, None, [f"MAVENIL{file_name}.exp"]
        mock_current_user.return_value = {"id": "mock-id"}
        file_mock.return_value = export_file
        mock_activity_request.return_value = mock_activity_response

        success = download_and_process_alegeus_transactions_export()
        reimbursement_request = ReimbursementRequest.query.all()

        assert success is True
        assert len(reimbursement_request) == 1
        assert (
            reimbursement_request[0].state
            == ReimbursementRequestState.INSUFFICIENT_RECEIPT
        )
        assert event.call_args[0][1] == "debit_card_transaction_insufficient_docs"
        assert event.call_args[0][2]["transaction_amount"] == "70.93"


@patch("wallet.utils.alegeus.edi_processing.process_edi_transactions")
@patch("flask_login.current_user")
def test_process_insufficient_transactions_updates_request(
    mock_emit_audit_log_read,
    mock_current_user,
    qualified_alegeus_wallet_hra,
):
    mock_emit_audit_log_read.return_value = None
    mock_current_user.return_value = {"id": "mock-id"}
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    reimbursement_request = ReimbursementRequestFactory.create(
        wallet=qualified_alegeus_wallet_hra,
        category=category,
        state=ReimbursementRequestState.NEEDS_RECEIPT,
        reimbursement_type=ReimbursementRequestType.DEBIT_CARD,
    )
    ReimbursementTransactionFactory(
        alegeus_transaction_key="1250000411-20220817-16154520",
        status=12,
        reimbursement_request=reimbursement_request,
        amount=Decimal("7093.00"),
        date=datetime.datetime.now(),
    )
    line = (
        b"EK,50015430,T01676,MVNIMPORT,HDHPANNUAL,456,HRA,20220101,20221231,369147258HRA,1100054073677275,,,"
        b"2835,2835,,40.00,40.00,40.00,0.00,12,AUPI,,20220913073448,20220913000000,20220913,20220913073936,"
        b"20220913,073936,0.00,1250000411-20220817-16154520\r\n "
    )
    with patch("utils.braze_events.braze.send_event") as event:
        _process_insufficient_transactions(line)

        assert (
            reimbursement_request.state
            == ReimbursementRequestState.INSUFFICIENT_RECEIPT
        )
        assert event.call_args[0][1] == "debit_card_transaction_insufficient_docs"
        assert event.call_args[0][2]["transaction_amount"] == "70.93"
