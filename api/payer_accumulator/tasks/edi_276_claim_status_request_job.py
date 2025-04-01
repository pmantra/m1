import io
from traceback import format_exc
from typing import Optional

from common import stats
from common.stats import PodNames
from payer_accumulator.common import PayerName
from payer_accumulator.edi.constants import (
    AVAILITY_OUTBOUND_DIR,
    AVAILITY_PORT_NUMBER,
    AVAILITY_SFTP_SECRET,
)
from payer_accumulator.edi.edi_276_claim_status_request_generator import (
    EDI276ClaimStatusRequestFileGenerator,
)
from payer_accumulator.file_handler import AccumulationFileHandler
from utils.log import logger
from utils.sftp import SSHError, get_sftp_from_secret

log = logger(__name__)

METRIC_PREFIX = "api.payer_accumulator.edi_276_claim_status_request_job"
JOB_RUN_METRIC = "job_run"
UPLOAD_FILE_METRIC = "upload_file"


class EDI276ClaimStatusRequestJob:
    def __init__(self, payer_name: PayerName):
        self.payer_name = payer_name
        self.file_generator = EDI276ClaimStatusRequestFileGenerator(self.payer_name)
        self.filename = self.file_generator.file_name
        self.file_handler = AccumulationFileHandler()

    def upload_file(self, content: io.StringIO) -> None:
        try:
            log.info("Trying to connect to Availity.", payer_name=self.payer_name.value)
            sftp_client = get_sftp_from_secret(AVAILITY_SFTP_SECRET, port=AVAILITY_PORT_NUMBER)  # type: ignore[arg-type] # Argument 1 to "get_sftp_from_secret" has incompatible type "Optional[str]"; expected "str"
            if not sftp_client:
                log.warning(
                    "Failed to connect to SFTP",
                    payer_name=self.payer_name.value,
                )
                raise SSHError(message="Failed to connect to SFTP")
            sftp_client.putfo(
                io.BytesIO(content.getvalue().encode("utf-8")),
                f"{AVAILITY_OUTBOUND_DIR}/{self.filename}",
                confirm=False,
            )
            log.info(
                "Uploaded 276 file to Availity folder",
                payer_name=self.payer_name,
                file_name=self.filename,
            )
            self.increment_metric(UPLOAD_FILE_METRIC, success=True)
        except Exception as e:
            log.error(
                "Failed to upload 276 file to Availity folder",
                payer_name=self.payer_name,
                file_name=self.filename,
                reason=format_exc(),
                exc_info=True,
                error_message=str(e),
            )
            self.increment_metric(UPLOAD_FILE_METRIC, success=False)
            raise e

    def run(self) -> None:
        try:
            content: io.StringIO = self.file_generator.generate_file_contents()
            if content.getvalue() == "":
                log.info("Empty file generated, no need to upload to availity")
                return
            self.upload_file(content)
            self.increment_metric(JOB_RUN_METRIC, success=True)
        except Exception as e:
            log.error(
                "Failed to run 276 claim status request job due to exception.",
                reason=format_exc(),
                payer_name=self.payer_name.value,
                exc_info=True,
                error_message=str(e),
            )
            self.increment_metric(JOB_RUN_METRIC, success=False)
            raise e

    def increment_metric(
        self,
        metric_name: str,
        success: Optional[bool] = None,
        extra_tags: Optional[list] = None,
    ) -> None:
        tags = extra_tags or []
        tags.append(f"payer_name:{self.payer_name.value}")
        if success is not None:
            success_value = "true" if success else "false"
            tags.append(f"success:{success_value}")
        stats.increment(
            metric_name=f"{METRIC_PREFIX}.{metric_name}",
            pod_name=PodNames.PAYMENTS_PLATFORM,
            tags=tags,
        )


def aetna_claim_status_request_generation() -> None:
    aetna_job = EDI276ClaimStatusRequestJob(PayerName.AETNA)
    aetna_job.run()
