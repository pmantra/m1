from unittest.mock import Mock, patch

from payer_accumulator.edi.constants import (
    AETNA_277_FILENAME_DATE_INDEX,
    AETNA_277_FILENAME_PATTERN,
)
from payer_accumulator.edi.file_ingestion import FileIngestionJob


class MockTempFile:
    def __init__(self, name):
        self.name = name

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def read(self):
        return "fake content"


class TestFileIngestionJob:
    def test_download(self):
        mock_sftp = Mock()
        mock_file_name = "test_file.txt"
        mock_temp_file_name = "/tmp/test_file.txt"

        mock_temp_file = Mock()
        mock_temp_file.name = mock_temp_file_name
        mock_sftp.get.return_value = None

        with patch("paramiko.SFTPClient", return_value=mock_sftp):
            FileIngestionJob()._download(mock_file_name, mock_temp_file_name, mock_sftp)
            mock_sftp.get.assert_called_once_with(mock_file_name, mock_temp_file_name)

    def test_find_files_to_execute(
        self,
    ):
        files = [
            "277-AETNA60054-2024102116455010-001.277",
            "277-AETNA60054-2024102134563476-002.277",
            "277-AETNA60054-2024102016455010-001.277",
            "277-AETNA60054-2024102116455010-001.277ebr",
        ]
        expected_result = [
            "277-AETNA60054-2024102116455010-001.277",
            "277-AETNA60054-2024102134563476-002.277",
        ]
        ret = FileIngestionJob().find_files_to_process(
            files,
            AETNA_277_FILENAME_PATTERN,
            20241021,
            date_index=AETNA_277_FILENAME_DATE_INDEX,
        )
        assert expected_result == ret

    @patch(
        "payer_accumulator.edi.file_ingestion.open",
        return_value=MockTempFile("opened_file"),
    )
    @patch("payer_accumulator.edi.file_ingestion.FileIngestionJob._download")
    @patch("tempfile.NamedTemporaryFile", return_value=MockTempFile(name="temp"))
    def test_download_file__success(self, mock_tempfile, mock_download, mock_file):
        mock_sftp = Mock()
        assert (
            FileIngestionJob().download_file(
                "dummy", "Fake_route", mock_sftp, "FAKE_METRIC"
            )
            == "fake content"
        )
        mock_download.assert_called_once_with("Fake_route/dummy", "temp", mock_sftp)

    @patch(
        "payer_accumulator.edi.file_ingestion.FileIngestionJob._download",
        side_effect=IOError(),
    )
    @patch("tempfile.NamedTemporaryFile", return_value=MockTempFile(name="temp"))
    def test_download_file__download_error(self, mock_tempfile, mock_download):
        mock_sftp = Mock()
        assert (
            FileIngestionJob().download_file(
                "dummy", "Fake_route", mock_sftp, "FAKE_METRIC"
            )
            == ""
        )
