import datetime
import json
from unittest import mock
from unittest.mock import patch

import paramiko
import pytest

from wallet.pytests.factories import ReimbursementPlanFactory
from wallet.utils.alegeus.edi_processing.common import (
    check_file_availability,
    decrypt_data,
    encrypt_data,
    get_employer_config_latest_response_filename,
    get_total_plan_count,
    get_versioned_file,
    set_encryption_password,
    ssh_connect_retry,
    validated_plan_items,
)


def test_get_versioned_file():
    file_date = datetime.datetime.now().date()
    file_name = file_date.strftime("%Y%m%d")
    created_file_prefix = f"MAVENIL{file_name}"

    with patch(
        "wallet.utils.alegeus.edi_processing.common.get_files_from_alegeus"
    ) as mock_client:
        mock_client.return_value = None, None, []
        file_prefix = get_versioned_file()

        assert file_prefix == created_file_prefix


def test_get_versioned_file_retry_upload():
    file_date = datetime.datetime.now().date()
    file_name = file_date.strftime("%Y%m%d")
    created_file_prefix = f"MAVENIL{file_name}"

    with patch(
        "wallet.utils.alegeus.edi_processing.common.get_files_from_alegeus"
    ) as mock_client:
        mock_client.return_value = None, None, [f"{created_file_prefix}.res"]
        file_prefix = get_versioned_file()

        assert file_prefix == f"MAVENIL{file_name}_1"


def test_get_versioned_file_retry_download():
    file_date = datetime.datetime.now().date()
    file_name = file_date.strftime("%Y%m%d")
    file_one = f"MAVENIL{file_name}.res"
    file_two = f"MAVENIL{file_name}.res"

    with patch(
        "wallet.utils.alegeus.edi_processing.common.get_files_from_alegeus"
    ) as mock_client:
        mock_client.return_value = None, None, [file_one, file_two]
        file_prefix = get_versioned_file(download=True)

        assert file_prefix == f"MAVENIL{file_name}_1"


def test_get_versioned_file_download__fails():
    with patch(
        "wallet.utils.alegeus.edi_processing.common.get_files_from_alegeus"
    ) as mock_client:
        mock_client.return_value = Exception
        with pytest.raises(  # noqa  B017  TODO:  `assertRaises(Exception)` and `pytest.raises(Exception)` should be considered evil. They can lead to your test passing even if the code being tested is never executed due to a typo. Assert for a more specific exception (builtin or custom), or use `assertRaisesRegex` (if using `assertRaises`), or add the `match` keyword argument (if using `pytest.raises`), or use the context manager form with a target.
            Exception
        ):
            get_versioned_file()


def test_get_total_plan_count(enterprise_user, pending_alegeus_wallet_hra):
    # wallet that is tied to an organization with a single plan.
    wallet_1 = pending_alegeus_wallet_hra
    wallet_2 = pending_alegeus_wallet_hra
    organization_1 = wallet_1.reimbursement_organization_settings.organization
    organization_2 = wallet_2.reimbursement_organization_settings.organization
    # Testing two organizations with a single plan each is counted
    total_count = get_total_plan_count([organization_1.id, organization_2.id])
    assert total_count == 2


def test_validate_plan_items__success(valid_alegeus_plan_hra):
    valid_plan = valid_alegeus_plan_hra
    plan_dict = validated_plan_items(valid_plan)
    assert valid_plan.alegeus_plan_id == plan_dict["plan_id"]


def test_validate_plan_items__fails():
    plan = ReimbursementPlanFactory.create(
        alegeus_plan_id="FAMILYFUND",
        start_date=datetime.date(year=2020, month=1, day=3),
        end_date=datetime.date(year=2199, month=12, day=31),
    )
    with pytest.raises(AssertionError):
        validated_plan_items(plan)


def test_get_employer_config_latest_response_file_multiple():
    files = ["MAVEN_IS.res", "MAVEN_IS_1.res"]
    file_prefix = "MAVEN_IS"
    filename, count = get_employer_config_latest_response_filename(files, file_prefix)
    assert filename == "MAVEN_IS_2"
    assert count == 2


def test_get_employer_config_latest_response_file_none():
    file_prefix = "MAVEN_IT"
    filename, count = get_employer_config_latest_response_filename([], file_prefix)
    assert filename == "MAVEN_IT"
    assert count == 0


def test_ssh_connect_retry_raises_timeout_raises_exception():
    with patch("paramiko.SSHClient") as mock_client:
        mock_client.connect.side_effect = paramiko.ssh_exception.SSHException
        with pytest.raises(TimeoutError):
            ssh_connect_retry(
                mock_client,
                "ALEGEUS_MOCK_HOST",
                port=22,
                username="ALEGEUS_MOCK_USERNAME",
                password="ALEGEUS_MOCK_PASSWORD",
                max_attempts=3,
            )


def test_ssh_connect_retry_on_timeout_succeeds():
    expected_conn = {
        "port": 22,
        "username": "ALEGEUS_MOCK_USERNAME",
        "password": "ALEGEUS_MOCK_PASSWORD",
    }
    with patch("paramiko.SSHClient") as mock_client:
        client = ssh_connect_retry(
            mock_client, "ALEGEUS_MOCK_HOST", **expected_conn, max_attempts=3
        )
        mock_client.connect.assert_called_once_with(
            "ALEGEUS_MOCK_HOST", **expected_conn
        )
        # Assert ssh_connect_retry returning client
        assert client == mock_client


def test_message_encryption():
    message = "Testing encryption"
    encrypt_key = set_encryption_password("a_little_salt", "SECRET_PASSWORD".encode())
    encrypted_data = encrypt_data(message, encrypt_key)
    decrypted_message = decrypt_data(encrypted_data, encrypt_key)
    assert message == json.loads(decrypted_message)


test_data = [
    # Test file found first check
    (["MAVEN_IT_1"], True),
    # Test file found after second check
    ([[], ["MAVEN_IT_1"]], True),
    # Test file never found
    ([[], [], []], False),
    # Test exception hit
    ([TimeoutError], False),
]


@pytest.mark.parametrize("sftp_return, expected", test_data)
@patch("time.sleep", return_value=None)
def test_check_file_availability_file_listed_after_exception__failure(
    sleep_mock, sftp_return, expected
):
    mock_client = mock.Mock()
    mock_sftp = mock.Mock()
    mock_client.close.return_value = True
    if len(sftp_return) == 1:
        mock_sftp.listdir.return_value = sftp_return
    else:
        mock_sftp.listdir.side_effect = sftp_return
    success = check_file_availability(
        "MAVEN_IT_1", mock_sftp, mock_client, max_attempts=3
    )
    assert success is expected
