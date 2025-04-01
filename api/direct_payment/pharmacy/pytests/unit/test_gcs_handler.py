import csv
from io import StringIO
from unittest.mock import Mock

from google.cloud.exceptions import GoogleCloudError

from direct_payment.pharmacy.utils.gcs_handler import upload_to_gcp_bucket


def _get_contents():
    csv_data = [
        ["First_Name,Last_Name,Date_Of_Birth,Maven_Benefit_ID,Employer"],
    ]
    csv_stream = StringIO()
    csv.writer(csv_stream).writerows(csv_data)
    return csv_stream


def test_upload_to_gcp_bucket(mock_storage_client):
    mock_bucket, mock_blob = Mock(), Mock()
    mock_storage_client.return_value.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob
    mock_file_name = "test.csv"
    mock_file_contents = _get_contents()

    upload_to_gcp_bucket(mock_file_contents, mock_file_name, "mock_bucket")

    mock_bucket.blob.assert_called_once_with(mock_file_name)
    mock_blob.upload_from_string.assert_called_once_with(
        mock_file_contents.getvalue(), content_type="text/plain"
    )


def test_upload_retries(mock_storage_client):
    mock_bucket, mock_blob = Mock(), Mock()
    mock_storage_client.return_value.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob
    mock_file_name = "test.csv"
    mock_file_contents = _get_contents()

    mock_blob.upload_from_string.side_effect = [
        GoogleCloudError("foo"),
        GoogleCloudError("bar"),
        None,
    ]

    upload_to_gcp_bucket(mock_file_contents, mock_file_name, "mock_bucket")

    assert mock_blob.upload_from_string.call_count == 3
