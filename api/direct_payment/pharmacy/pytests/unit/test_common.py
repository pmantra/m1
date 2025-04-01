import io
import os
import tempfile
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
import pytz

from braze.client import constants
from common.global_procedures.procedure import GlobalProcedure, ProcedureService
from direct_payment.pharmacy.constants import RX_GP_HCPCS_CODE
from direct_payment.pharmacy.tasks.libs.common import (
    _send_file_receipt,
    convert_to_string_io,
    create_rx_global_procedure,
    get_global_procedure,
    get_most_recent_file,
    get_or_create_rx_global_procedure,
    get_wallet_user,
    raw_rows_count,
    validate_file,
    wallet_reimbursement_state_rx_auto_approved_event,
)
from pytests.common.global_procedures.factories import GlobalProcedureFactory
from pytests.factories import DefaultUserFactory, ReimbursementWalletUsersFactory
from pytests.freezegun import freeze_time
from wallet.models.constants import WalletUserStatus, WalletUserType

FAKE_EVENT_DATETIME = datetime(2050, 1, 1, 1, 1).isoformat()


def test_get_most_recent_file_success():
    # Given
    file_list = [
        "Maven_Rx_Scheduled_20231002_103627.csv",
        "Maven_Rx_Scheduled_20231002_103838.csv",
        "Maven_Rx_Scheduled_20231002_103758.csv",
    ]
    # When
    most_recent_file = get_most_recent_file(file_list)

    # Then
    assert most_recent_file == "Maven_Rx_Scheduled_20231002_103838.csv"


def test_get_most_recent_file_fails():
    # Given
    file_list = [
        "Maven_Rx_Scheduled_20231002_103627.csv",
        "Maven_Rx_Scheduled_20231002_103838.csv",
        "Maven_Rx_Scheduled_20231002_103758_wrong_format.csv",
    ]
    # When/Then
    with pytest.raises(ValueError):
        get_most_recent_file(file_list)


@pytest.mark.parametrize(
    argnames="wallet_user_status, patient_name_match, user_id_match",
    argvalues=(
        # Inactive Wallet
        (WalletUserStatus.PENDING, True, True),
        # Patient name does not match
        (WalletUserStatus.ACTIVE, False, True),
        # User id does not match
        (WalletUserStatus.ACTIVE, True, False),
    ),
)
def test_get_wallet_users_fails(
    wallet, wallet_user_status, patient_name_match, user_id_match
):
    # Given
    given_user_id = wallet.member.id if user_id_match else wallet.member.id + 1
    given_first_name = wallet.member.first_name if patient_name_match else "Unknown"
    given_last_name = wallet.member.last_name

    ReimbursementWalletUsersFactory.create(
        user_id=given_user_id,
        reimbursement_wallet_id=wallet.id,
        status=wallet_user_status,
        type=WalletUserType.EMPLOYEE,
    )
    # When
    found_wallet = get_wallet_user(
        wallet=wallet, first_name=given_first_name, last_name=given_last_name
    )
    # Then
    assert found_wallet is None


def test_get_wallet_users(wallet):
    # Given
    ReimbursementWalletUsersFactory.create(
        user_id=wallet.member.id,
        reimbursement_wallet_id=wallet.id,
    )
    given_first_name = wallet.member.first_name
    given_last_name = wallet.member.last_name
    # When
    found_wallet = get_wallet_user(
        wallet=wallet, first_name=given_first_name, last_name=given_last_name
    )
    # Then
    assert found_wallet


def test_create_global_procedure(wallet):
    # Given
    procedure_service = ProcedureService()
    ReimbursementWalletUsersFactory.create(
        user_id=wallet.member.id,
        reimbursement_wallet_id=wallet.id,
    )

    given_procedure_created = GlobalProcedureFactory.create(
        id=1, name="Test", type="pharmacy"
    )

    expected_post_data = GlobalProcedure(
        name="Updated_Test",
        type=given_procedure_created["type"],
        credits=given_procedure_created["credits"],
        ndc_number="1234-1223-22",
        is_partial=False,
        hcpcs_code=RX_GP_HCPCS_CODE,
        annual_limit=given_procedure_created["annual_limit"],
        is_diagnostic=given_procedure_created["is_diagnostic"],
        cost_sharing_category=given_procedure_created["cost_sharing_category"],
    )

    with patch.object(
        ProcedureService,
        "create_global_procedure",
        return_value=given_procedure_created,
    ) as mock_create_global_procedure:
        # When
        gp = create_rx_global_procedure(
            "Updated_Test", "1234-1223-22", given_procedure_created, procedure_service
        )

    # Then
    assert gp
    mock_create_global_procedure.assert_called_with(global_procedure=expected_post_data)


def test_get_global_procedure():
    # Given
    procedure_service = ProcedureService()
    given_procedure_medical = GlobalProcedureFactory.create(
        id=1, name="Test", type="medical"
    )
    given_procedure_pharmacy = GlobalProcedureFactory.create(
        id=2, name="Test", type="pharmacy", ndc_number="1234-1234-10"
    )
    with patch.object(
        ProcedureService,
        "get_procedures_by_ndc_numbers",
        return_value=[given_procedure_medical, given_procedure_pharmacy],
    ):
        # When
        gp = get_global_procedure(procedure_service, rx_ndc_number="1234-1234-10")

    # Then
    assert gp


def test_get_global_procedure_none():
    # Given
    procedure_service = ProcedureService()
    with patch.object(
        ProcedureService,
        "get_procedures_by_names",
        return_value=[],
    ):
        # When
        gp = get_global_procedure(procedure_service, rx_ndc_number="1234-1234-10")

    # Then
    assert gp is None


def test_update_global_procedure_created(treatment_procedure):
    # Given
    given_existing_global_procedure = GlobalProcedureFactory.create(
        id=2, name="Existing Procedure", type="pharmacy"
    )
    given_created_procedure = GlobalProcedureFactory.create(
        id=2, name="New Procedure", type="pharmacy"
    )

    with patch.object(
        ProcedureService,
        "get_procedures_by_ndc_numbers",
        return_value=[],
    ), patch.object(
        ProcedureService,
        "get_procedure_by_id",
        return_value=given_existing_global_procedure,
    ), patch.object(
        ProcedureService,
        "create_global_procedure",
        return_value=given_created_procedure,
    ):
        # When
        gp = get_or_create_rx_global_procedure(
            given_created_procedure["ndc_number"], "New Procedure", treatment_procedure
        )

    # Then
    assert gp


def test_update_global_procedure_found(treatment_procedure):
    # Given
    given_global_procedure = GlobalProcedureFactory.create(
        id=2, name="Found Procedure", type="pharmacy"
    )

    with patch.object(
        ProcedureService,
        "get_procedures_by_ndc_numbers",
        return_value=[given_global_procedure],
    ):
        # When
        gp = get_or_create_rx_global_procedure(
            given_global_procedure["ndc_number"], "Found Procedure", treatment_procedure
        )

    # Then
    assert gp


def test_update_global_procedure_existing_procedure_not_found(treatment_procedure):
    # Given
    with patch.object(
        ProcedureService,
        "get_procedures_by_ndc_numbers",
        return_value=[],
    ), patch.object(
        ProcedureService,
        "get_procedure_by_id",
        return_value=None,
    ), patch.object(
        ProcedureService, "create_global_procedure", return_value=None
    ) as created:
        # When
        gp = get_or_create_rx_global_procedure(
            "000-000-000", "New Procedure", treatment_procedure
        )

    # Then
    assert gp is None
    created.assert_not_called()


def test__send_file_receipt(smp_shipped_file):
    # Given
    mock_temp_file = smp_shipped_file()
    date_now = datetime.now(pytz.timezone("America/New_York"))
    date_time = date_now.strftime("%Y%m%d_%H%M%S")
    base_file_name, _ = os.path.splitext(mock_temp_file.name)
    receipt_file_name = f"_Received_{date_time}.csv"
    expected_formatted_file_name = (
        f"Maven/ToSMPTest/MavenAcknowledgement/{base_file_name}{receipt_file_name}"
    )
    with patch("paramiko.SSHClient") as mock_ssh, patch(
        "direct_payment.pharmacy.tasks.libs.common.datetime.datetime"
    ) as date_mock:
        date_mock.now.return_value = date_now
        mock_ftp = mock_ssh.return_value.open_sftp.return_value = Mock()
        mock_ftp.listdir.return_value = []
        mock_ftp.putfo.return_value = None
        # When
        _send_file_receipt(mock_temp_file)
        # Then
        mock_ftp.putfo.assert_called_once_with(
            mock_temp_file, expected_formatted_file_name, confirm=False
        )


def test__send_file_receipt_file_exists(smp_shipped_file):
    # Given
    mock_temp_file = smp_shipped_file()
    now = datetime.now(pytz.timezone("America/New_York"))
    date_time = now.strftime("%Y%m%d_%H%M%S")
    base_file_name, _ = os.path.splitext(mock_temp_file.name)
    receipt_file_name = f"_Received_{date_time}.csv"
    formatted_file_name = f"{base_file_name}{receipt_file_name}"
    with patch("paramiko.SSHClient") as mock_ssh:
        mock_ftp = mock_ssh.return_value.open_sftp.return_value = Mock()
        mock_ftp.listdir.return_value = [formatted_file_name]
        mock_ftp.putfo.return_value = None
        # When
        _send_file_receipt(mock_temp_file)
        # Then
        mock_ftp.listdir.assert_called_once_with("Maven/ToSMPTest/MavenAcknowledgement")
        mock_ftp.putfo.assert_not_called()


def test_validate_file_none():
    # Given
    mock_temp_file = None
    # When
    valid_file = validate_file(mock_temp_file)
    assert valid_file is False


def test_validate_file_success(smp_shipped_file):
    # Given
    mock_temp_file = smp_shipped_file()
    # When
    valid_file = validate_file(mock_temp_file)
    assert valid_file


def test_validate_file_empty(smp_shipped_file):
    # Given
    mock_temp_file = tempfile.NamedTemporaryFile()
    mock_temp_file.name = "Maven_Rx_Shipped_2024201_063051.csv"
    # When
    valid_file = validate_file(mock_temp_file)
    assert valid_file is False


@patch("braze.client.BrazeClient._make_request")
@freeze_time(FAKE_EVENT_DATETIME)
def test_send_wallet_reimbursement_state_rx_auto_approved_event(mock_request):
    user = DefaultUserFactory.create()
    wallet_reimbursement_state_rx_auto_approved_event(user_id=user.id)

    mock_request.assert_called_with(
        endpoint=constants.USER_TRACK_ENDPOINT,
        data={
            "events": [
                {
                    "external_id": user.esp_id,
                    "name": "wallet_reimbursement_state_rx_auto_approved",
                    "time": FAKE_EVENT_DATETIME,
                    "properties": None,
                }
            ]
        },
    )


def test_convert_to_string_io_with_binary_file():
    # Given
    binary_content = b"header1,header2\nvalue1,value2\n"
    binary_file = tempfile.NamedTemporaryFile()
    binary_file.write(binary_content)
    binary_file.seek(0)
    # When
    string_io = convert_to_string_io(binary_file)
    # Then
    assert isinstance(string_io, io.StringIO)
    assert string_io.getvalue() == "header1,header2\nvalue1,value2\n"


def test_convert_to_string_io_with_text_file():
    # Given
    text_content = "header1,header2\nvalue1,value2\n"
    text_file = io.StringIO(text_content)
    # When
    string_io = convert_to_string_io(text_file)
    # Then
    assert isinstance(string_io, io.StringIO)
    assert string_io.getvalue() == text_content


def test_convert_to_string_io_raises_on_none():
    # Given
    invalid_file = None
    # When/Then
    with pytest.raises(ValueError, match="File cannot be empty!"):
        convert_to_string_io(invalid_file)


def test_convert_to_string_io_raises_on_error():
    # Given
    invalid_file = Mock()
    invalid_file.seek.side_effect = Exception("File error")
    # When/Then
    with pytest.raises(ValueError, match="Error converting file to StringIO."):
        convert_to_string_io(invalid_file)


def test_raw_rows_count_with_data():
    # Given
    content = "header1,header2\nrow1-1,row1-2\nrow2-1,row2-2\n"
    string_io = io.StringIO(content)
    # When
    count = raw_rows_count(string_io)
    # Then
    assert count == 2
    assert string_io.getvalue() == content


def test_raw_rows_count_empty_file():
    # Given
    string_io = io.StringIO("")
    # When
    count = raw_rows_count(string_io)
    # Then
    assert count == 0


def test_raw_rows_count_only_header():
    # Given
    content = "header1,header2\n"
    string_io = io.StringIO(content)
    # When
    count = raw_rows_count(string_io)
    # Then
    assert count == 0


def test_raw_rows_count_handles_error():
    # Given
    invalid_file = Mock()
    invalid_file.seek.side_effect = Exception("File error")
    # When
    count = raw_rows_count(invalid_file)
    # Then
    assert count == 0
