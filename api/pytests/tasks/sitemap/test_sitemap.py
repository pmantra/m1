from hashlib import sha1
from os import environ, path
from unittest import mock
from unittest.mock import MagicMock, call

from google.cloud.storage import Blob, Bucket, Client

from pytests.freezegun import freeze_time
from tasks.sitemap import sitemap

__FILE_DIR = path.dirname(path.realpath(__file__))


@freeze_time("2023-04-20T00:00:00")
def test_sitemap():
    with mock.patch("tasks.sitemap.sitemap.storage.Client") as mock_client_constructor:
        bucket_name = "sitemapbucket"
        environ["SITEMAP_BUCKET"] = bucket_name

        mock_client: Client = MagicMock()
        mock_client_constructor.return_value = mock_client
        mock_bucket: Bucket = MagicMock()
        mock_client.get_bucket.return_value = mock_bucket
        mock_sitemap_blob: Blob = MagicMock()
        mock_index_blob: Blob = MagicMock()
        mock_bucket.blob.side_effect = [mock_sitemap_blob, mock_index_blob]

        sitemap.update()

        mock_client_constructor.assert_called()
        mock_client.get_bucket.assert_called_with(bucket_name)
        assert mock_bucket.blob.call_count == 2
        with open(
            path.join(__FILE_DIR, "expected_sitemap.xml"), "rb"
        ) as expected_sitemap_file:
            expected_sitemap_contents = expected_sitemap_file.read()
            mock_bucket.blob.assert_has_calls(
                [
                    call(f"sitemap/{sha1(expected_sitemap_contents).hexdigest()}.xml"),
                    call("sitemap.xml"),
                ]
            )
            mock_sitemap_blob.upload_from_string.assert_called_once_with(
                expected_sitemap_contents, content_type="text/xml"
            )
        with open(
            path.join(__FILE_DIR, "expected_index.xml"), "rb"
        ) as expected_index_file:
            mock_index_blob.upload_from_string.assert_called_once_with(
                expected_index_file.read(), content_type="text/xml"
            )
