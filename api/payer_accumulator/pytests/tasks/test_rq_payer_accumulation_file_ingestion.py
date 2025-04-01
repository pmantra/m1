import datetime
from unittest.mock import MagicMock, patch

import pytest

from payer_accumulator.common import PayerName
from payer_accumulator.edi.constants import SchemaType
from payer_accumulator.pytests.test_files.test_277_data import (
    file_contents_277,
    parsed_277_data,
)
from payer_accumulator.pytests.test_files.test_277ca_data import (
    file_contents_277ca,
    parsed_277ca_data,
)
from payer_accumulator.tasks.rq_payer_accumulation_file_ingestion import (
    X12FileIngestionJob,
)
from utils.sftp import SSHError


class TestX12FileIngestionJob:
    @patch(
        "payer_accumulator.tasks.rq_payer_accumulation_file_ingestion.get_sftp_from_secret"
    )
    @patch(
        "payer_accumulator.tasks.rq_payer_accumulation_file_ingestion.X12FileIngestionJob.get_files_from_availity"
    )
    @patch(
        "payer_accumulator.tasks.rq_payer_accumulation_file_ingestion.X12FileIngestionJob.download_file"
    )
    @patch(
        "payer_accumulator.tasks.rq_payer_accumulation_file_ingestion.X12FileIngestionJob.parse_277_file_and_update_claim_statuses"
    )
    def test_download_and_parse_files__success(
        self,
        parse_277_file_and_update_claim_statuses_mock,
        download_file_mock,
        get_files_from_availity_mock,
        get_sftp_from_secret_mock,
    ):
        # given
        get_sftp_from_secret_mock.return_value = MagicMock()
        target_date = datetime.datetime(2024, 10, 21)
        get_files_from_availity_mock.return_value = [
            "277-12345-2024102112200000-001.277",
        ]
        download_file_mock.return_value = file_contents_277
        # when
        X12FileIngestionJob(
            payer_name=PayerName.AETNA, file_type=SchemaType.EDI_277
        ).download_and_parse_files(target_date=target_date)
        # then
        parse_277_file_and_update_claim_statuses_mock.assert_called_once_with(
            file_content=file_contents_277
        )

    @patch("payer_accumulator.tasks.rq_payer_accumulation_file_ingestion.log.warning")
    @patch(
        "payer_accumulator.tasks.rq_payer_accumulation_file_ingestion.get_sftp_from_secret"
    )
    def test_download_and_parse_files__sftp_error(
        self, get_sftp_from_secret_mock, mock_log
    ):
        # given
        get_sftp_from_secret_mock.return_value = {}
        target_date = datetime.datetime(2024, 10, 21)
        # when
        with pytest.raises(SSHError):
            X12FileIngestionJob(
                payer_name=PayerName.AETNA, file_type=SchemaType.EDI_277
            ).download_and_parse_files(target_date=target_date)
            # then
            mock_log.assert_called_once_with(
                "Failed to connect to SFTP. No 277 files downloaded from Availity",
                payer_name=PayerName.AETNA.value,
                target_date=target_date,
            )

    @patch("payer_accumulator.tasks.rq_payer_accumulation_file_ingestion.log.warning")
    @patch(
        "payer_accumulator.tasks.rq_payer_accumulation_file_ingestion.get_sftp_from_secret"
    )
    @patch(
        "payer_accumulator.tasks.rq_payer_accumulation_file_ingestion.X12FileIngestionJob.get_files_from_availity"
    )
    def test_download_and_parse_files__no_files_found(
        self, get_files_from_availity_mock, get_sftp_from_secret_mock, mock_log
    ):
        # given
        get_sftp_from_secret_mock.return_value = MagicMock()
        target_date = datetime.datetime(2024, 10, 21)
        get_files_from_availity_mock.return_value = []
        # when
        X12FileIngestionJob(
            payer_name=PayerName.AETNA, file_type=SchemaType.EDI_277
        ).download_and_parse_files(target_date=target_date)
        # then
        mock_log.assert_called_once_with(
            "No files of specified type and payer found from Availity",
            payer_name=PayerName.AETNA.value,
            file_type=SchemaType.EDI_277.value,
            target_date=target_date,
        )

    def test_get_files_from_availity(self):
        # given
        mock_sftp = MagicMock()
        mock_sftp.listdir.return_value = [
            "277-AETNA60054-2024102116455010-001.277",
            "277-AETNA60054-2024102134563476-002.277",
            "277-AETNA60054-2024102016455010-001.277",
            "277-AETNA60054-2024102116455010-001.277ebr",
        ]
        expected_result = [
            "277-AETNA60054-2024102116455010-001.277",
            "277-AETNA60054-2024102134563476-002.277",
        ]
        # when
        files = X12FileIngestionJob(
            payer_name=PayerName.AETNA, file_type=SchemaType.EDI_277
        ).get_files_from_availity(
            target_date=20241021, sftp_client=mock_sftp, file_type=SchemaType.EDI_277
        )
        # then
        assert files == expected_result

    @patch(
        "payer_accumulator.edi.x12_file_parser_277.X12FileParser277.check_and_update_claim_statuses"
    )
    def test_parse_277_file_and_update_claim_statuses(
        self, check_and_update_claim_statuses_mock
    ):
        X12FileIngestionJob(
            payer_name=PayerName.AETNA, file_type=SchemaType.EDI_277
        ).parse_277_file_and_update_claim_statuses(file_contents_277)
        check_and_update_claim_statuses_mock.assert_called_once_with(
            data=parsed_277_data
        )

    @patch(
        "payer_accumulator.edi.x12_file_parser_277.X12FileParser277.check_and_update_claim_statuses"
    )
    def test_parse_277ca_file_and_update_claim_statuses(
        self, check_and_update_claim_statuses_mock
    ):
        X12FileIngestionJob(
            payer_name=PayerName.AETNA, file_type=SchemaType.EDI_277CA
        ).parse_277_file_and_update_claim_statuses(file_contents_277ca)
        check_and_update_claim_statuses_mock.assert_called_once_with(
            data=parsed_277ca_data
        )
