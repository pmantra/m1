import io
from datetime import datetime
from unittest import mock

import pytest
from google.cloud.exceptions import GoogleCloudError
from google.cloud.storage import Blob, Bucket

from direct_payment.pharmacy.tasks.libs.pharmacy_file_handler import PharmacyFileHandler

BUCKET_NAME = "test-smp-bucket"
QUATRIX_BUCKET = "test-quatrix-bucket"


@pytest.fixture
def mock_storage_client() -> mock.Mock:
    with mock.patch("google.cloud.storage.Client") as mock_client:
        yield mock_client


@pytest.fixture
def mock_bucket() -> mock.Mock:
    mock_bucket = mock.Mock(spec=Bucket)
    mock_bucket.name = BUCKET_NAME
    return mock_bucket


@pytest.fixture
def pharmacy_file_handler(
    mock_storage_client: mock.Mock, mock_bucket: mock.Mock
) -> PharmacyFileHandler:
    mock_storage_client.return_value.bucket.return_value = mock_bucket
    return PharmacyFileHandler(
        internal_bucket_name=BUCKET_NAME, outgoing_bucket_name=QUATRIX_BUCKET
    )


class TestPharmacyFileHandler:
    def test_init_success(self, mock_storage_client: mock.Mock) -> None:
        mock_bucket = mock.Mock(spec=Bucket)
        mock_storage_client.return_value.bucket.return_value = mock_bucket

        handler = PharmacyFileHandler(
            internal_bucket_name=BUCKET_NAME,
            outgoing_bucket_name=QUATRIX_BUCKET,
        )

        assert handler.internal_bucket == mock_bucket
        assert handler.outgoing_bucket == mock_bucket
        mock_storage_client.return_value.bucket.assert_has_calls(
            [
                mock.call(BUCKET_NAME),
                mock.call(QUATRIX_BUCKET),
            ]
        )

    def test_init_bucket_error(self, mock_storage_client: mock.Mock) -> None:
        mock_storage_client.return_value.bucket.side_effect = GoogleCloudError(
            "Invalid bucket"
        )

        with pytest.raises(GoogleCloudError):
            PharmacyFileHandler(
                internal_bucket_name="invalid-bucket",
                outgoing_bucket_name="invalid-bucket",
            )

    def test_get_pharmacy_ingestion_file(
        self, pharmacy_file_handler: PharmacyFileHandler, mock_bucket: mock.Mock
    ) -> None:
        mock_blob = mock.Mock(spec=Blob)
        mock_blob.name = "IncomingSMPFiles/Maven_Rx_Reimbursement_20250209_082148.csv"
        mock_blob.download_as_text.return_value = "file content"

        with mock.patch.object(
            pharmacy_file_handler, "get_files_from_prefix"
        ) as mock_get_files, mock.patch.object(
            pharmacy_file_handler, "get_one_from_gcp_bucket"
        ) as mock_get_one:
            mock_get_files.return_value = [
                "IncomingSMPFiles/Maven_Rx_Reimbursement_20250209_082148.csv"
            ]
            mock_get_one.return_value = mock_blob

            test_date = datetime(2025, 2, 9).date()
            content, filename = pharmacy_file_handler.get_pharmacy_ingestion_file(
                file_prefix="Maven_Rx_Reimbursement",
                file_type="test",
                input_date=test_date,
            )

            assert content == "file content"
            assert filename == "Maven_Rx_Reimbursement_20250209_082148.csv"
            mock_get_files.assert_called_with(
                "IncomingSMPFiles/Maven_Rx_Reimbursement_20250209",
                pharmacy_file_handler.internal_bucket,
            )

    def test_get_pharmacy_ingestion_file_no_files(
        self, pharmacy_file_handler: PharmacyFileHandler, mock_bucket: mock.Mock
    ) -> None:
        with mock.patch.object(
            pharmacy_file_handler, "get_files_from_prefix"
        ) as mock_get_files:
            mock_get_files.return_value = []

            content, filename = pharmacy_file_handler.get_pharmacy_ingestion_file(
                file_prefix="Maven_Rx_Reimbursement",
                file_type="test",
                input_date=datetime(2025, 2, 9).date(),
            )

            assert content is None
            assert filename is None
            mock_get_files.assert_called_with(
                "IncomingSMPFiles/Maven_Rx_Reimbursement_20250209",
                pharmacy_file_handler.internal_bucket,
            )

    def test_get_pharmacy_ingestion_file_empty_content(
        self, pharmacy_file_handler: PharmacyFileHandler, mock_bucket: mock.Mock
    ) -> None:
        mock_blob = mock.Mock(spec=Blob)
        mock_blob.name = "Maven_Rx_Reimbursement_20250209_082148.csv"
        mock_blob.download_as_text.return_value = ""

        with mock.patch.object(
            pharmacy_file_handler, "get_files_from_prefix"
        ) as mock_get_files, mock.patch.object(
            pharmacy_file_handler, "get_one_from_gcp_bucket"
        ) as mock_get_one:
            mock_get_files.return_value = ["Maven_Rx_Reimbursement_20250209_082148.csv"]
            mock_get_one.return_value = mock_blob

            content, filename = pharmacy_file_handler.get_pharmacy_ingestion_file(
                file_prefix="Maven_Rx_Reimbursement",
                file_type="test",
                input_date=datetime(2025, 2, 9).date(),
            )

            assert content is None
            assert filename is None

    def test_get_pharmacy_ingestion_file_exception(
        self, pharmacy_file_handler: PharmacyFileHandler, mock_bucket: mock.Mock
    ) -> None:
        mock_blob = mock.Mock(spec=Blob)
        mock_blob.download_as_text.side_effect = GoogleCloudError("Download failed")

        with mock.patch.object(
            pharmacy_file_handler, "get_files_from_prefix"
        ) as mock_get_files, mock.patch.object(
            pharmacy_file_handler, "get_one_from_gcp_bucket"
        ) as mock_get_one:
            mock_get_files.return_value = ["Maven_Rx_Reimbursement_20250209_082148.csv"]
            mock_get_one.return_value = mock_blob

            content, filename = pharmacy_file_handler.get_pharmacy_ingestion_file(
                file_prefix="Maven_Rx_Reimbursement",
                file_type="test",
            )

            assert content is None
            assert filename is None

    def test_send_file_receipt_success(
        self, pharmacy_file_handler: PharmacyFileHandler, mock_bucket: mock.Mock
    ) -> None:
        mock_blob = mock.Mock()
        mock_blob.exists.return_value = False
        pharmacy_file_handler.outgoing_bucket.blob.return_value = mock_blob

        with mock.patch.object(
            pharmacy_file_handler, "upload_to_gcp_bucket"
        ) as mock_upload:
            pharmacy_file_handler.send_file_receipt(
                "content", "Maven_Rx_Shipped_20250210_082148.csv"
            )

            mock_upload.assert_called_once()
            call_args = mock_upload.call_args.kwargs
            assert isinstance(call_args["content"], io.StringIO)
            assert call_args["content"].getvalue() == "content"
            assert call_args["bucket"] == pharmacy_file_handler.outgoing_bucket

    def test_send_file_receipt_existing_file(
        self, pharmacy_file_handler: PharmacyFileHandler, mock_bucket: mock.Mock
    ) -> None:
        mock_blob = mock.Mock()
        mock_blob.exists.return_value = True
        pharmacy_file_handler.outgoing_bucket.blob.return_value = mock_blob

        pharmacy_file_handler.send_file_receipt(
            "content", "Maven_Rx_Shipped_20250210_082148.csv"
        )

        mock_blob.upload_from_string.assert_not_called()

    def test_upload_eligibility_file_success(
        self, pharmacy_file_handler: PharmacyFileHandler
    ) -> None:
        date_time = "20240101_120000"
        content = io.StringIO("test content")

        with mock.patch.object(
            pharmacy_file_handler, "list_files"
        ) as mock_list, mock.patch.object(
            pharmacy_file_handler, "upload_to_gcp_bucket"
        ) as mock_upload:
            mock_list.return_value = mock_list.return_value = [
                "Eligibility/Maven_Custom_Rx_Eligibility_20231231_1.csv",  # day before file
                "Eligibility/Maven_Custom_Rx_Eligibility_20240102_1.csv",  # day after file
                "Eligibility/Maven_Custom_Rx_Eligibility_20240101_1.csv",  # one day of file
            ]

            result = pharmacy_file_handler.upload_eligibility_file(content, date_time)

            assert result is True
            assert mock_upload.call_count == 2
            mock_upload.assert_has_calls(
                [
                    mock.call(
                        content=content,
                        filename="SMP_MavenGoldEligibility/Maven_Custom_Rx_Eligibility_20240101_120000.csv",
                        bucket=pharmacy_file_handler.outgoing_bucket,
                    ),
                    mock.call(
                        content=content,
                        filename="Eligibility/Maven_Custom_Rx_Eligibility_20240101_120000.csv",
                        bucket=pharmacy_file_handler.internal_bucket,
                    ),
                ]
            )

    def test_upload_eligibility_file_too_many_files(
        self, pharmacy_file_handler: PharmacyFileHandler
    ) -> None:
        """Test when too many eligibility files exist for the day."""
        date_time = "20240101_120000"
        content = io.StringIO("test content")

        with mock.patch.object(
            pharmacy_file_handler, "get_files_from_prefix"
        ) as mock_list:
            mock_list.return_value = [
                "Eligibility/Maven_Custom_Rx_Eligibility_20240101_1.csv",
                "Eligibility/Maven_Custom_Rx_Eligibility_20240101_2.csv",
                "Eligibility/Maven_Custom_Rx_Eligibility_20240101_3.csv",
            ]

            result = pharmacy_file_handler.upload_eligibility_file(content, date_time)
            assert result is False

    def test_upload_eligibility_file_invalid_content(
        self, pharmacy_file_handler: PharmacyFileHandler
    ) -> None:
        """Test uploading eligibility file with invalid content."""
        date_time = "20240101_120000"
        content = io.StringIO("invalid content")

        with mock.patch.object(
            pharmacy_file_handler, "get_files_from_prefix"
        ) as mock_list, mock.patch.object(
            pharmacy_file_handler, "upload_to_gcp_bucket"
        ) as mock_upload:
            mock_list.return_value = []
            mock_upload.side_effect = GoogleCloudError("Invalid content")

            result = pharmacy_file_handler.upload_eligibility_file(content, date_time)
            assert result is False

    def test_upload_eligibility_file_first_upload_fails(
        self, pharmacy_file_handler: PharmacyFileHandler
    ) -> None:
        date_time = "20240101_120000"
        content = io.StringIO("test content")

        with mock.patch.object(
            pharmacy_file_handler, "get_files_from_prefix"
        ) as mock_list, mock.patch.object(
            pharmacy_file_handler, "upload_to_gcp_bucket"
        ) as mock_upload:
            mock_list.return_value = []
            mock_upload.side_effect = [GoogleCloudError("Upload failed"), None]

            result = pharmacy_file_handler.upload_eligibility_file(content, date_time)
            assert result is False
            assert mock_upload.call_count == 1  # Should fail after first upload

    def test_upload_eligibility_file_second_upload_fails(
        self, pharmacy_file_handler: PharmacyFileHandler
    ) -> None:
        date_time = "20240101_120000"
        content = io.StringIO("test content")

        with mock.patch.object(
            pharmacy_file_handler, "get_files_from_prefix"
        ) as mock_list, mock.patch.object(
            pharmacy_file_handler, "upload_to_gcp_bucket"
        ) as mock_upload:
            mock_list.return_value = []
            mock_upload.side_effect = [None, GoogleCloudError("Upload failed")]

            result = pharmacy_file_handler.upload_eligibility_file(content, date_time)
            assert result is False
            assert mock_upload.call_count == 2

    def test_upload_reconciliation_file_success(
        self, pharmacy_file_handler: PharmacyFileHandler
    ) -> None:
        date_time = "20240101_120000"
        content = io.StringIO("test content")

        with mock.patch.object(
            pharmacy_file_handler, "upload_to_gcp_bucket"
        ) as mock_upload:
            result = pharmacy_file_handler.upload_reconciliation_file(
                content, date_time
            )

            assert result is True
            assert mock_upload.call_count == 2
            mock_upload.assert_has_calls(
                [
                    mock.call(
                        content=content,
                        filename="SMP_MavenGoldStripePayments/MavenGold_StripePayments_20240101_120000.csv",
                        bucket=pharmacy_file_handler.outgoing_bucket,
                    ),
                    mock.call(
                        content=content,
                        filename="MavenGoldStripePayments/MavenGold_StripePayments_20240101_120000.csv",
                        bucket=pharmacy_file_handler.internal_bucket,
                    ),
                ]
            )

    def test_upload_reconciliation_file_fails(
        self, pharmacy_file_handler: PharmacyFileHandler
    ) -> None:
        date_time = "20240101_120000"
        content = io.StringIO("test content")

        with mock.patch.object(
            pharmacy_file_handler, "upload_to_gcp_bucket"
        ) as mock_upload:
            mock_upload.side_effect = [GoogleCloudError("Upload failed"), None]
            result = pharmacy_file_handler.upload_reconciliation_file(
                content, date_time
            )

            assert result is False
            assert mock_upload.call_count == 1
