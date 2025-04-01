import io
from typing import List

from google.cloud.exceptions import Conflict, GoogleCloudError
from google.cloud.storage import Blob, Bucket
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from utils.log import logger

log = logger(__name__)


class GCSFileHandler:
    """
    Base class for handling file operations in Google Cloud Storage.
    """

    def list_files(self, prefix: str, bucket: Bucket) -> List[str]:
        """
        List all files in the bucket with given prefix.
        """
        return [blob.name for blob in self.get_many_from_gcp_bucket(prefix, bucket)]

    def get_files_from_prefix(self, file_prefix: str, bucket: Bucket) -> List[str]:
        """
        Get list of files matching the exact prefix, sorted with latest first.
        """
        filenames = set(self.list_files(file_prefix, bucket))
        return sorted(
            [file for file in filenames if file.startswith(file_prefix)], reverse=True
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(multiplier=1, max=60),
        retry=(
            retry_if_exception_type(Conflict)
            | retry_if_exception_type(GoogleCloudError)
        ),
    )
    def upload_to_gcp_bucket(
        self, content: io.StringIO, filename: str, bucket: Bucket
    ) -> None:
        """
        Upload a file to a GCS bucket with retry logic.
        """
        try:
            blob = bucket.blob(filename)
            blob.upload_from_string(content.getvalue(), content_type="text/plain")
        except Exception as e:
            log.error(
                "Failed to upload a file to the GCS bucket.",
                filename=filename,
                bucket=bucket,
            )
            raise e

    def get_many_from_gcp_bucket(self, prefix: str, bucket: Bucket) -> List[Blob]:
        """
        List all blobs in bucket matching prefix.
        """
        try:
            return list(bucket.list_blobs(prefix=prefix))
        except Exception as e:
            log.error(
                "Failed to download files by prefix",
                prefix=prefix,
                bucket=bucket,
            )
            raise e

    def get_one_from_gcp_bucket(self, file_name: str, bucket: Bucket) -> Blob:
        """
        Get one blob in bucket matching a given filename.
        """
        try:
            return bucket.blob(blob_name=file_name)
        except Exception as e:
            log.error(
                "Failed to find file by file_name",
                file_name=file_name,
                bucket=bucket,
            )
            raise e
