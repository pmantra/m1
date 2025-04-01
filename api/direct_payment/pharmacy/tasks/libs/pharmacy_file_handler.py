import datetime
import io
import os
from typing import Optional

import pytz
from google.cloud import storage

from direct_payment.pharmacy.constants import (
    GCP_QUATRIX_ACKNOWLEDGMENT_PATH,
    GCP_QUATRIX_ELIGIBILITY_PATH,
    GCP_QUATRIX_RECONCILIATION_PATH,
    GCP_SMP_ELIGIBILITY_PATH,
    GCP_SMP_INCOMING_PATH,
    GCP_SMP_RECONCILIATION_PATH,
    SMP_ELIGIBILITY_FILE_PREFIX,
    SMP_RECONCILIATION_FILE_PREFIX,
)
from utils.gcs_file_handler import GCSFileHandler
from utils.log import logger

log = logger(__name__)

ET_TIMEZONE = pytz.timezone("America/New_York")


class PharmacyFileHandler(GCSFileHandler):
    """
    ref: https://cloud.google.com/storage/docs/reference/libraries
    Handles file operations for pharmacy files in Google Cloud Storage
    """

    def __init__(self, internal_bucket_name: str, outgoing_bucket_name: str):
        super().__init__()
        self.client = storage.Client()
        self.internal_bucket = self.client.bucket(internal_bucket_name)
        self.outgoing_bucket = self.client.bucket(outgoing_bucket_name)

    def get_pharmacy_ingestion_file(
        self,
        file_prefix: str,
        file_type: str,
        input_date: Optional[datetime.date] = None,
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Retrieves the most recent pharmacy ingestion file from GCS.
        This method handles all SMP file types.
        """
        date_time_str = (
            input_date.strftime("%Y%m%d")
            if input_date
            else datetime.datetime.now(ET_TIMEZONE).strftime("%Y%m%d")
        )

        prefix = f"{GCP_SMP_INCOMING_PATH}/{file_prefix}_{date_time_str}"
        try:
            filenames = self.get_files_from_prefix(prefix, self.internal_bucket)
            if not filenames:
                log.error(
                    f"No {file_type} file found for date {date_time_str} in GCS.",
                    prefix=prefix,
                )
                return None, None

            most_recent_file = filenames[0]
            blob = self.get_one_from_gcp_bucket(
                file_name=most_recent_file, bucket=self.internal_bucket
            )

            content = blob.download_as_text(encoding="latin_1")
            if not content:
                log.error(f"Empty {file_type} file found: {most_recent_file}")
                return None, None

            filename = os.path.basename(most_recent_file)
            return content, filename
        except Exception as e:
            log.exception(f"Error retrieving {file_type} file from GCS: {e}", error=e)
            return None, None

    def send_file_receipt(
        self, received_file_content: str, original_filename: str
    ) -> None:
        """
        Send a receipt file acknowledging the received file.
        """
        log.info("Sending receipt file.")
        now = datetime.datetime.now(ET_TIMEZONE)
        date_time = now.strftime("%Y%m%d_%H%M%S")
        base_file_name, _ = os.path.splitext(original_filename)
        receipt_file_name = f"_Received_{date_time}.csv"
        new_file_path = (
            f"{GCP_QUATRIX_ACKNOWLEDGMENT_PATH}/{base_file_name}{receipt_file_name}"
        )
        log.info(f"File path for shipped: {new_file_path}")
        try:
            # Check if the file already exists
            blob = self.get_one_from_gcp_bucket(
                file_name=new_file_path, bucket=self.outgoing_bucket
            )
            if blob.exists():
                log.info(
                    f"Shipped receipt file '{new_file_path}' already exists. Skipping upload."
                )
                return

            self.upload_to_gcp_bucket(
                content=io.StringIO(received_file_content),
                filename=new_file_path,
                bucket=self.outgoing_bucket,
            )
            log.info("Shipped receipt file uploaded successfully.", file=base_file_name)

        except Exception as e:
            log.exception("Unable to upload receipt file to GCS:", error=e)

    def upload_eligibility_file(self, content: io.StringIO, date_time: str) -> bool:
        """
        Uploads eligibility file to GCS buckets.
        """
        file_name = f"{SMP_ELIGIBILITY_FILE_PREFIX}_{date_time}.csv"
        date_only = date_time[:8]  # YYYYMMDD

        try:
            # Check existing files in SMP bucket
            smp_prefix = (
                f"{GCP_SMP_ELIGIBILITY_PATH}/{SMP_ELIGIBILITY_FILE_PREFIX}_{date_only}"
            )
            today_files = self.get_files_from_prefix(
                file_prefix=smp_prefix, bucket=self.internal_bucket
            )

            if len(today_files) >= 3:
                log.error(
                    "Found three eligibility files already in SMP bucket for today! Cancelling upload..."
                )
                return False

            # Upload to Quatrix bucket first
            quatrix_path = f"{GCP_QUATRIX_ELIGIBILITY_PATH}/{file_name}"
            self.upload_to_gcp_bucket(
                content=content,
                filename=quatrix_path,
                bucket=self.outgoing_bucket,
            )
            log.info(
                "Eligibility file uploaded successfully to Quatrix bucket.",
                file_name=file_name,
            )

            # Then upload to SMP bucket
            smp_path = f"{GCP_SMP_ELIGIBILITY_PATH}/{SMP_ELIGIBILITY_FILE_PREFIX}_{date_time}.csv"
            content.seek(0)
            self.upload_to_gcp_bucket(
                content=content,
                filename=smp_path,
                bucket=self.internal_bucket,
            )
            log.info(
                "Eligibility file uploaded successfully to SMP bucket.",
                file_name=file_name,
            )

            return True

        except Exception as e:
            log.exception(
                "Failed to upload eligibility file.", error=e, file_name=file_name
            )
            return False

    def upload_reconciliation_file(
        self, content: io.StringIO, date_time_str: str
    ) -> bool:
        """
        Uploads reconciliation file to GCS buckets.
        """
        file_name = f"{SMP_RECONCILIATION_FILE_PREFIX}_{date_time_str}.csv"

        try:
            # Upload to Quatrix bucket first
            quatrix_path = f"{GCP_QUATRIX_RECONCILIATION_PATH}/{file_name}"
            self.upload_to_gcp_bucket(
                content=content,
                filename=quatrix_path,
                bucket=self.outgoing_bucket,
            )
            log.info(
                "Reconciliation file uploaded successfully to Quatrix GCS bucket.",
                file_name=file_name,
            )

            # Then upload to SMP bucket
            smp_path = f"{GCP_SMP_RECONCILIATION_PATH}/{SMP_RECONCILIATION_FILE_PREFIX}_{date_time_str}.csv"
            content.seek(0)
            self.upload_to_gcp_bucket(
                content=content,
                filename=smp_path,
                bucket=self.internal_bucket,
            )
            log.info(
                "Reconciliation file uploaded successfully to SMP GCS bucket.",
                file_name=file_name,
            )

            return True

        except Exception as e:
            log.exception(
                "Failed to upload reconciliation file to GCS bucket.",
                error=e,
                file_name=file_name,
            )
            return False
