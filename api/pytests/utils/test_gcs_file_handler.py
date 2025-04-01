import io
from unittest import mock

import pytest
from google.cloud.exceptions import Conflict, GoogleCloudError
from google.cloud.storage import Blob, Bucket
from tenacity import RetryError

from utils.gcs_file_handler import GCSFileHandler

MOCK_BUCKET_NAME = "test-bucket"


@pytest.fixture
def mock_bucket() -> mock.Mock:
    mock_bucket = mock.Mock(spec=Bucket)
    mock_bucket.name = MOCK_BUCKET_NAME
    return mock_bucket


@pytest.fixture
def gcs_file_handler() -> GCSFileHandler:
    return GCSFileHandler()


class TestGCSFileHandler:
    def test_list_files(
        self, gcs_file_handler: GCSFileHandler, mock_bucket: mock.Mock
    ) -> None:
        # simulate GCS prefix filtering
        def mock_list_blobs(prefix: str = None) -> list[mock.Mock]:
            all_blobs = [
                "folder1/file1.txt",
                "folder1/file2.txt",
                "folder2/file3.txt",
            ]
            filtered_blobs = []
            for name in all_blobs:
                if prefix and name.startswith(prefix):
                    mock_blob = mock.Mock(spec=Blob)
                    mock_blob.name = name
                    filtered_blobs.append(mock_blob)
            return filtered_blobs

        mock_bucket.list_blobs.side_effect = mock_list_blobs

        # Test folder1 prefix
        result = gcs_file_handler.list_files("folder1", mock_bucket)
        assert result == ["folder1/file1.txt", "folder1/file2.txt"]

        # Test folder2 prefix
        result = gcs_file_handler.list_files("folder2", mock_bucket)
        assert result == ["folder2/file3.txt"]

        # Test non-matching prefix
        result = gcs_file_handler.list_files("folder3", mock_bucket)
        assert result == []

    def test_list_files_error(
        self, gcs_file_handler: GCSFileHandler, mock_bucket: mock.Mock
    ) -> None:
        mock_bucket.list_blobs.side_effect = GoogleCloudError("List failed")

        with pytest.raises(GoogleCloudError):
            gcs_file_handler.list_files("test_prefix", mock_bucket)

    def test_get_files_from_prefix(
        self, gcs_file_handler: GCSFileHandler, mock_bucket: mock.Mock
    ) -> None:
        with mock.patch.object(gcs_file_handler, "list_files") as mock_list:
            mock_list.return_value = [
                "folder1/file_20240101_1.txt",
                "folder1/file_20240101_2.txt",
                "folder1/file_20240102_1.txt",
                "folder2/file_20240101_3.txt",
            ]

            result = gcs_file_handler.get_files_from_prefix(
                "folder1/file_20240101", mock_bucket
            )
            assert result == [
                "folder1/file_20240101_2.txt",
                "folder1/file_20240101_1.txt",
            ]

            mock_list.assert_called_with("folder1/file_20240101", mock_bucket)

    def test_get_files_from_prefix_empty(
        self, gcs_file_handler: GCSFileHandler, mock_bucket: mock.Mock
    ) -> None:
        with mock.patch.object(gcs_file_handler, "list_files") as mock_list:
            mock_list.return_value = []

            result = gcs_file_handler.get_files_from_prefix("folder1/none", mock_bucket)
            assert result == []

    def test_get_files_from_prefix_error(
        self, gcs_file_handler: GCSFileHandler, mock_bucket: mock.Mock
    ) -> None:
        with mock.patch.object(gcs_file_handler, "list_files") as mock_list:
            mock_list.side_effect = GoogleCloudError("List failed")

            with pytest.raises(GoogleCloudError):
                gcs_file_handler.get_files_from_prefix("test_prefix", mock_bucket)

    def test_upload_to_gcp_bucket_success(
        self, gcs_file_handler: GCSFileHandler, mock_bucket: mock.Mock
    ) -> None:
        mock_blob = mock.Mock()
        mock_bucket.blob.return_value = mock_blob

        content = io.StringIO("test content")
        gcs_file_handler.upload_to_gcp_bucket(
            content=content,
            filename="test.txt",
            bucket=mock_bucket,
        )

        mock_bucket.blob.assert_called_once_with("test.txt")
        mock_blob.upload_from_string.assert_called_once_with(
            "test content", content_type="text/plain"
        )

    def test_upload_to_gcp_bucket_retries(
        self,
        gcs_file_handler: GCSFileHandler,
        mock_bucket: mock.Mock,
    ) -> None:
        # Override wait time to 0 for faster tests
        with mock.patch("tenacity.wait_random_exponential", return_value=lambda x: 0):
            mock_blob = mock.Mock()
            mock_blob.upload_from_string.side_effect = [
                Conflict("conflict"),
                GoogleCloudError("error"),
                None,
            ]

            mock_bucket.blob.return_value = mock_blob

            gcs_file_handler.upload_to_gcp_bucket(
                content=io.StringIO("test"),
                filename="test.txt",
                bucket=mock_bucket,
            )

            assert mock_blob.upload_from_string.call_count == 3

    def test_upload_to_gcp_bucket_max_retries(
        self, gcs_file_handler: GCSFileHandler, mock_bucket: mock.Mock
    ) -> None:
        with mock.patch("tenacity.wait_random_exponential", return_value=lambda x: 0):
            mock_blob = mock.Mock()
            mock_blob.upload_from_string.side_effect = Conflict("conflict")
            mock_bucket.blob.return_value = mock_blob

            with pytest.raises(RetryError):
                gcs_file_handler.upload_to_gcp_bucket(
                    content=io.StringIO("test"),
                    filename="test.txt",
                    bucket=mock_bucket,
                )

            assert mock_blob.upload_from_string.call_count == 3

    def test_get_many_from_gcp_bucket_success(
        self, gcs_file_handler: GCSFileHandler, mock_bucket: mock.Mock
    ) -> None:
        mock_blobs = [
            mock.Mock(spec=Blob, name="file1.txt"),
            mock.Mock(spec=Blob, name="file2.txt"),
        ]
        mock_bucket.list_blobs.return_value = mock_blobs

        result = gcs_file_handler.get_many_from_gcp_bucket(
            prefix="test_prefix", bucket=mock_bucket
        )

        assert result == mock_blobs
        mock_bucket.list_blobs.assert_called_once_with(prefix="test_prefix")

    def test_get_many_from_gcp_bucket_error(
        self, gcs_file_handler: GCSFileHandler, mock_bucket: mock.Mock
    ) -> None:
        mock_bucket.list_blobs.side_effect = GoogleCloudError("List failed")

        with pytest.raises(GoogleCloudError):
            gcs_file_handler.get_many_from_gcp_bucket(
                prefix="test_prefix", bucket=mock_bucket
            )

    def test_get_one_from_gcp_bucket_success(
        self, gcs_file_handler: GCSFileHandler, mock_bucket: mock.Mock
    ) -> None:
        mock_blob = mock.Mock(spec=Blob)
        mock_bucket.blob.return_value = mock_blob

        result = gcs_file_handler.get_one_from_gcp_bucket(
            file_name="test_file", bucket=mock_bucket
        )

        assert result == mock_blob
        mock_bucket.blob.assert_called_once_with(blob_name="test_file")

    def test_get_one_from_gcp_bucket_error(
        self, gcs_file_handler: GCSFileHandler, mock_bucket: mock.Mock
    ) -> None:
        mock_bucket.blob.side_effect = GoogleCloudError("Get blob failed")

        with pytest.raises(GoogleCloudError):
            gcs_file_handler.get_one_from_gcp_bucket(
                file_name="test_file", bucket=mock_bucket
            )
