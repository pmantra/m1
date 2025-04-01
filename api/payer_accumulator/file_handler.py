import io
import os
from typing import List

from google.cloud import storage
from google.cloud.storage import Blob

from payer_accumulator.constants import LOCAL_FILE_BUCKET
from utils.log import logger

log = logger(__name__)


class AccumulationFileHandler:
    """
    ref: https://cloud.google.com/storage/docs/reference/libraries
    It would be good to put a warning here for files over 2GB if that ever becomes a risk.
    Large files should use different upload/download methods. (Using in memory/str here.)
    """

    def __init__(self, force_local=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.force_local = force_local or os.environ.get(
            "FORCE_LOCAL_ACCUMULATION_REPORTING", False
        )

    def upload_file(self, content: io.StringIO, filename: str, bucket: str) -> None:
        # TODO: remove temp test file condition
        if self.force_local or filename == "test_output.txt":
            self.send_to_local_dir(content, filename)
        else:
            self.send_to_gcp_bucket(content, filename, bucket)

    def download_file(self, filename: str, bucket: str) -> str:
        # TODO: remove temp test file condition
        if self.force_local or filename == "test_output.txt":
            return self.get_from_local_dir(filename)
        else:
            return self.get_from_gcp_bucket(filename, bucket)

    def list_files(self, prefix: str, bucket_name: str) -> List[str]:
        if self.force_local:
            return self.list_from_local_dir(prefix)
        else:
            return [
                blob.name for blob in self.get_many_from_gcp_bucket(prefix, bucket_name)
            ]

    def move_file(self, old_filename: str, new_filename: str, bucket: str) -> None:
        if self.force_local:
            return self.move_file_in_local_dir(old_filename, new_filename)
        else:
            return self.move_file_in_gcp_bucket(old_filename, new_filename, bucket)

    def send_to_gcp_bucket(
        self, content: io.StringIO, filename: str, bucket: str
    ) -> None:
        # ref: https://cloud.google.com/storage/docs/uploading-objects-from-memory#storage-upload-object-from-memory-python
        try:
            client = storage.Client()
            bucket = client.bucket(bucket)
            blob = bucket.blob(filename)  # type: ignore[attr-defined] # "str" has no attribute "blob"
            blob.upload_from_string(content.getvalue(), content_type="text/plain")
        except Exception as e:
            log.error(
                "Fail to upload a file to the GCS bucket",
                filename=filename,
                bucket=bucket,
            )
            raise e

    def get_from_gcp_bucket(self, filename: str, bucket: str) -> str:
        # ref: https://cloud.google.com/storage/docs/downloading-objects-intgo-memory#storage-download-object-python
        try:
            client = storage.Client()
            bucket = client.bucket(bucket)
            blob = bucket.blob(filename)  # type: ignore[attr-defined] # "str" has no attribute "blob"
            content = blob.download_as_bytes()
        except Exception as e:
            log.error(
                "Fail to download a file from the GCS bucket",
                filename=filename,
                bucket=bucket,
            )
            raise e
        return str(content, encoding="latin_1")

    def get_many_from_gcp_bucket(self, prefix: str, bucket: str) -> List[Blob]:
        try:
            client = storage.Client()
            bucket = client.bucket(bucket)
            return bucket.list_blobs(prefix=prefix)  # type: ignore[attr-defined] # "str" has no attribute "list_blobs"
        except Exception as e:
            log.error("Fail to download files by prefix", prefix=prefix, bucket=bucket)
            raise e

    def move_file_in_gcp_bucket(
        self, old_filename: str, new_filename: str, bucket_name: str
    ) -> None:
        try:
            client = storage.Client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(old_filename)  # type: ignore[attr-defined] # "str" has no attribute "blob"
            bucket.rename_blob(blob, new_filename)
        except Exception as e:
            log.error(
                "Fail to rename a file in the GCS bucket",
                old_filename=old_filename,
                new_filename=new_filename,
                bucket=bucket,
            )
            raise e

    def check_for_local_dir(self, file_location: str) -> bool:
        directory = os.path.dirname(file_location)
        return os.path.isdir(directory)

    def create_local_dir(self, file_location: str) -> None:
        directory = os.path.dirname(file_location)
        os.makedirs(directory)

    def send_to_local_dir(self, content: io.StringIO, filename: str) -> None:
        file_location = LOCAL_FILE_BUCKET + filename

        if not self.check_for_local_dir(file_location):
            self.create_local_dir(file_location)

        with open(file_location, "w+") as output:
            output.write(content.getvalue())

    def get_from_local_dir(self, filename: str) -> str:
        file_location = LOCAL_FILE_BUCKET + filename
        # Reading as binary and forcing as latin1 allows this method to return a str for all
        # files types. Allows local testing of encrypted files.
        with open(file_location, "rb") as file:
            file_contents = file.read()
        return file_contents.decode("latin_1")

    def list_from_local_dir(self, prefix: str) -> list[str]:
        # prefix assumed to be a subdirectory
        if not prefix.endswith("/"):
            prefix = prefix + "/"
        full_prefix = LOCAL_FILE_BUCKET + prefix
        directory = os.path.dirname(full_prefix)
        return [
            prefix + x for x in os.listdir(directory) if os.path.isfile(full_prefix + x)
        ]

    def move_file_in_local_dir(self, old_filename: str, new_filename: str) -> None:
        old_file_location = LOCAL_FILE_BUCKET + old_filename
        new_file_location = LOCAL_FILE_BUCKET + new_filename
        if not self.check_for_local_dir(new_file_location):
            self.create_local_dir(new_file_location)
        os.rename(old_file_location, new_file_location)
