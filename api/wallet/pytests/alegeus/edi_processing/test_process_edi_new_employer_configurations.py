from unittest import mock
from unittest.mock import patch

import paramiko
import pytest

from pytests.factories import OrganizationFactory
from wallet.pytests.factories import (
    ReimbursementOrganizationSettingsFactory,
    ReimbursementOrgSettingCategoryAssociationFactory,
    ReimbursementRequestCategoryFactory,
)
from wallet.utils.alegeus.edi_processing.common import (
    encrypt_data,
    set_encryption_password,
)
from wallet.utils.alegeus.edi_processing.process_edi_new_employer_configurations import (
    process_config_file,
    process_response_file,
    upload_new_employer_configurations,
)


def org_without_plans():
    org = OrganizationFactory.create(alegeus_employer_id="123")
    ReimbursementOrganizationSettingsFactory(organization_id=org.id)
    return org


def org_with_plans(plan):
    org = OrganizationFactory.create(alegeus_employer_id="123")
    org.alegeus_employer_id = "123"
    org_settings = ReimbursementOrganizationSettingsFactory(organization_id=org.id)

    # Configure Reimbursement Plan
    category = ReimbursementRequestCategoryFactory.create(
        label="fertility", reimbursement_plan=plan
    )
    ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_organization_settings=org_settings,
        reimbursement_request_category=category,
        reimbursement_request_category_maximum=5000,
    )
    return org


def banking_information(org, payroll_only=False):
    employer_id = org.alegeus_employer_id
    bank_info = {
        "org_id": org.id,
        "bank_account_usage_code": "3",
        "financial_institution": "" if payroll_only else "Testing Bank",
        "account_number": "" if payroll_only else 987654321,
        "routing_number": "" if payroll_only else 123456789,
        "payroll_only": payroll_only,
    }
    return bank_info, employer_id


class TestProcessingEmployerConfigurations:
    def test_process_response_file__success(
        self, employer_config_results_file_no_error
    ):
        with patch(
            "wallet.utils.alegeus.edi_processing.process_edi_new_employer_configurations.create_temp_file"
        ) as file_mock:
            file_mock.return_value = employer_config_results_file_no_error
            success = process_response_file("MAVEN_IU_1.res", None, 1)
            assert success

    def test_process_response_file__failure(self, employer_config_results_file_error):
        with patch(
            "wallet.utils.alegeus.edi_processing.process_edi_new_employer_configurations.create_temp_file"
        ) as file_mock:
            file_mock.return_value = employer_config_results_file_error
            success = process_response_file("MAVEN_IU_1.res", None, 1)
            assert success is False

    def test_process_config_file_no_matches(self):
        files = []
        filename = "MAVEN_IT_1.mbi"
        success, filename = process_config_file(filename, files, 1, sftp=None)
        assert success is False
        assert filename == "MAVEN_IT_1"

    def test_process_config_file_matches_no_error(self):
        files = ["MAVEN_IU_1.res", "MAVEN_IU_1_2.res"]
        filename = "MAVEN_IU_1.mbi"
        with patch(
            "wallet.utils.alegeus.edi_processing.process_edi_new_employer_configurations.process_response_file"
        ) as processed_response:
            processed_response.return_value = (
                True  # This means that the last res file contained no errors, move on.
            )
            success, filename = process_config_file(filename, files, 1, sftp=None)
            assert success
            assert filename == "MAVEN_IU_1_2"

    def test_process_config_file_matches_errors(self):
        files = ["MAVEN_IV_1.res", "MAVEN_IV_1_2.res"]
        filename = "MAVEN_IV_1.mbi"
        with patch(
            "wallet.utils.alegeus.edi_processing.process_edi_new_employer_configurations.process_response_file"
        ) as processed_response:
            processed_response.return_value = False  # This means that the last res file contained errors, try to re-upload.
            success, filename = process_config_file(filename, files, 1, sftp=None)
            assert success is False
            assert filename == "MAVEN_IV_1_3"


def create_client_sftp(files):
    mock_client = mock.Mock()
    mock_sftp = mock.Mock()

    mock_client.close.return_value = True
    mock_sftp.listdir.return_value = files

    return mock_client, mock_sftp


def encrypt_test_data(employer_id, bank_info):
    key = set_encryption_password(employer_id, "TEST_SECRET".encode())
    return encrypt_data(bank_info, key)


class TestUploadEmployerConfigurations:
    @patch(
        "wallet.utils.alegeus.edi_processing.common.ALEGEUS_PASSWORD_EDI",
        "TEST_SECRET",
    )
    def test_upload_new_employer_configurations_already_configured__success(
        self, valid_alegeus_plan_hra
    ):
        # All files are already present on the server.  Org is configured in Alegeus. Returns True
        org = org_with_plans(valid_alegeus_plan_hra)
        bank_info, alegeus_employer_id = banking_information(org)
        org_id = bank_info["org_id"]
        encrypted_data = encrypt_test_data(alegeus_employer_id, bank_info)
        files = [
            f"MAVEN_IS_{org_id}.res",
            f"MAVEN_IT_{org_id}.res",
            f"MAVEN_IV_{org_id}.res",
            f"MAVEN_IU_{org_id}.res",
        ]

        with patch(
            "wallet.utils.alegeus.edi_processing.process_edi_new_employer_configurations.get_client_sftp"
        ) as mock_client, patch(
            "wallet.utils.alegeus.edi_processing.process_edi_new_employer_configurations.process_config_file"
        ) as mock_process_config:
            mock_client.return_value = create_client_sftp(files=files)
            mock_process_config.side_effect = [
                (True, f"MAVEN_IS_{org_id}"),
                (True, f"MAVEN_IT_{org_id}"),
                (True, f"MAVEN_IV_{org_id}"),
                (True, f"MAVEN_IU_{org_id}"),
            ]
            success = upload_new_employer_configurations(encrypted_data, org_id)
            assert success

    @patch(
        "wallet.utils.alegeus.edi_processing.common.ALEGEUS_PASSWORD_EDI",
        "TEST_SECRET",
    )
    def test_upload_new_employer_configurations_bad_encryption__fails(
        self, valid_alegeus_plan_hra
    ):
        # Test decryption fails returns unsuccessful
        org = org_with_plans(valid_alegeus_plan_hra)
        bank_info, _ = banking_information(org)
        org_id = bank_info["org_id"]
        encrypted_data = encrypt_test_data("bad_data_here", bank_info)
        success = upload_new_employer_configurations(encrypted_data, org_id)
        assert success is False

    @patch(
        "wallet.utils.alegeus.edi_processing.common.ALEGEUS_PASSWORD_EDI",
        "TEST_SECRET",
    )
    def test_upload_new_employer_configurations_csv_creation__fails(self):
        # Test bad/missing data results in CSV creation failure returns unsuccessful
        org = org_without_plans()
        bank_info, alegeus_employer_id = banking_information(org)
        org_id = bank_info["org_id"]
        encrypted_data = encrypt_test_data(alegeus_employer_id, bank_info)
        success = upload_new_employer_configurations(encrypted_data, org_id)
        assert success is False

    @patch(
        "wallet.utils.alegeus.edi_processing.common.ALEGEUS_PASSWORD_EDI",
        "TEST_SECRET",
    )
    def test_upload_new_employer_configurations_bad_sftp__fails(
        self, valid_alegeus_plan_hra
    ):
        # SFTP does not connect returns unsuccessful
        org = org_with_plans(valid_alegeus_plan_hra)
        bank_info, alegeus_employer_id = banking_information(org)
        org_id = bank_info["org_id"]
        encrypted_data = encrypt_test_data(alegeus_employer_id, bank_info)
        with patch(
            "wallet.utils.alegeus.edi_processing.process_edi_new_employer_configurations.get_client_sftp"
        ) as mock_client:
            mock_client.side_effect = paramiko.SSHException
            success = upload_new_employer_configurations(encrypted_data, org_id)
            assert success is False

    @patch(
        "wallet.utils.alegeus.edi_processing.common.ALEGEUS_PASSWORD_EDI",
        "TEST_SECRET",
    )
    def test_upload_new_employer_configurations_upload_blob__fails(
        self, valid_alegeus_plan_hra
    ):
        # Attempting to upload file throws exception returning unsuccessful
        org = org_with_plans(valid_alegeus_plan_hra)
        bank_info, alegeus_employer_id = banking_information(org)
        org_id = bank_info["org_id"]
        encrypted_data = encrypt_test_data(alegeus_employer_id, bank_info)
        files = []
        with patch(
            "wallet.utils.alegeus.edi_processing.process_edi_new_employer_configurations.get_client_sftp"
        ) as mock_client, patch(
            "wallet.utils.alegeus.edi_processing.process_edi_new_employer_configurations.process_config_file"
        ) as mock_process_config, patch(
            "wallet.utils.alegeus.edi_processing.process_edi_new_employer_configurations.upload_blob"
        ) as mock_upload:
            mock_client.return_value = create_client_sftp(files=files)
            mock_process_config.return_value = (False, f"MAVEN_IS_{org_id}")
            mock_upload.side_effect = paramiko.SSHException
            success = upload_new_employer_configurations(encrypted_data, org_id)
            assert success is False

    testdata = [
        # Tests happy path all files successfully upload without errors returns successful.
        ([], True, True, [True], True),
        # Tests an existing file with errors retries uploading new file with success returns successful.
        (["MAVEN_IS_"], True, True, [False, True, True, True, True], True),
        # Tests new upload with file errors returns unsuccessful.
        ([], True, True, [True, True, False], False),
        # Test file not found in Alegeus SFTP returns unsuccessful
        ([], True, False, [False], False),
    ]

    @pytest.mark.parametrize(
        "files,upload,check_file,processed_response,expected",
        testdata,
        ids=["noop", "retry success", "upload fail", "file availability fail"],
    )
    @patch(
        "wallet.utils.alegeus.edi_processing.common.ALEGEUS_PASSWORD_EDI",
        "TEST_SECRET",
    )
    def test_upload_new_employer_configurations(
        self,
        files,
        upload,
        check_file,
        processed_response,
        expected,
        valid_alegeus_plan_hra,
    ):
        org = org_with_plans(valid_alegeus_plan_hra)
        bank_info, alegeus_employer_id = banking_information(org)
        encrypted_data = encrypt_test_data(alegeus_employer_id, bank_info)
        org_id = bank_info["org_id"]
        with patch(
            "wallet.utils.alegeus.edi_processing.process_edi_new_employer_configurations.get_client_sftp"
        ) as mock_client, patch(
            "wallet.utils.alegeus.edi_processing.process_edi_new_employer_configurations.upload_blob"
        ) as mock_upload, patch(
            "wallet.utils.alegeus.edi_processing.process_edi_new_employer_configurations.check_file_availability"
        ) as mock_check_file, patch(
            "wallet.utils.alegeus.edi_processing.process_edi_new_employer_configurations.process_response_file"
        ) as mock_processed_response:
            formatted_files = [f"{f}{org_id}" for f in files] if len(files) > 0 else []
            client, sftp = create_client_sftp(files=formatted_files)
            mock_client.return_value = client, sftp
            mock_upload.return_value = upload
            mock_check_file.return_value = check_file, client, sftp
            if len(processed_response) > 1:
                mock_processed_response.side_effect = processed_response
            else:
                mock_processed_response.return_value = processed_response[0]
            success = upload_new_employer_configurations(encrypted_data, org_id)

            assert success is expected
