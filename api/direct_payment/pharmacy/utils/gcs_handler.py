import io

from google.cloud import storage
from google.cloud.exceptions import Conflict, GoogleCloudError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from utils.log import logger

log = logger(__name__)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, max=60),
    retry=(
        retry_if_exception_type(Conflict) | retry_if_exception_type(GoogleCloudError)
    ),
)
def upload_to_gcp_bucket(content: io.StringIO, filename: str, bucket: str) -> None:
    try:
        client = storage.Client()
        bucket = client.bucket(bucket)
        blob = bucket.blob(filename)  # type: ignore[attr-defined] # "str" has no attribute "blob"
        blob.upload_from_string(content.getvalue(), content_type="text/plain")
    except Exception as e:
        log.error(
            "Failed to upload a file to the GCS bucket.",
            filename=filename,
            bucket=bucket,
        )
        raise e
