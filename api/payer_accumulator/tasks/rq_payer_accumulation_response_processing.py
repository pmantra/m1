import collections
import datetime
import os
from traceback import format_exc
from typing import List, Optional, Tuple

import gnupg

from common import stats
from common.stats import PodNames
from payer_accumulator.accumulation_mapping_service import AccumulationMappingService
from payer_accumulator.accumulation_report_service import AccumulationReportService
from payer_accumulator.common import PayerName
from payer_accumulator.constants import ACCUMULATION_RESPONSE_BUCKET
from payer_accumulator.file_generators.fixed_width_accumulation_file_generator import (
    FixedWidthAccumulationFileGenerator,
)
from payer_accumulator.file_handler import AccumulationFileHandler
from payer_accumulator.helper_functions import get_filename_without_prefix
from storage.connection import db
from tasks.queues import job
from utils.log import logger

log = logger(__name__)

METRIC_PREFIX = "api.payer_accumulator.rq_payer_accumulation_file_processing"
TASK_RUN_METRIC = "task_run"
JOB_RUN_METRIC = "job_run"
PROCESS_RESPONSE_METRIC = "response_processed"
RESPONSE_REJECTED_METRIC = "response_rejected"

RECEIVED_DIR = "received"
ARCHIVED_DIR = "archived"

PAYER_ACCUMULATION_PRIVATE_KEY = "PAYER_ACCUMULATION_PRIVATE_KEY"
PAYER_ACCUMULATION_PASSPHRASE = "PAYER_ACCUMULATION_PASSPHRASE"

PAYERS_WHO_SEND_EMPTY_FILES = {
    PayerName.ANTHEM,
}


class AccumulationResponseProcessingJob:
    def __init__(self, payer_name: PayerName):
        self.payer_name = payer_name
        self.file_handler = AccumulationFileHandler()
        file_generator = AccumulationReportService.get_generator_class_for_payer_name(
            payer_name.value
        )
        if not isinstance(file_generator, FixedWidthAccumulationFileGenerator):
            raise RuntimeError("Incompatible File Generator")
        self.file_generator: FixedWidthAccumulationFileGenerator = file_generator
        self.session = db.session
        self.mapping_service = AccumulationMappingService(session=db.session)

    def run(self) -> None:
        try:
            self.process_responses()
            self.increment_metric(JOB_RUN_METRIC, success=True)
        except Exception as e:
            log.error(
                "Failed to run accumulation response processing job due to exception.",
                reason=format_exc(),
                payer_name=self.payer_name.value,
                exc_info=True,
                error_message=str(e),
            )
            self.increment_metric(JOB_RUN_METRIC, success=False)

    def process_responses(self) -> int:
        processed = 0
        new_files = self.find_files_to_process()
        if len(new_files) > 0:
            log.info(
                "Found payer response files eligible for handling.",
                file_count=len(new_files),
                payer_name=self.payer_name.value,
            )
        else:
            log.info(
                "No payer response files eligible for handling.",
                payer_name=self.payer_name.value,
            )

        for file_name in new_files:
            try:
                self.process_accumulation_response_file(file_name)
                self.archive_response_file(file_name)
                self.increment_metric(PROCESS_RESPONSE_METRIC, success=True)
                processed += 1
            except Exception as e:
                log.error(
                    "Failed to handle file",
                    payer_name=self.payer_name.value,
                    filename=file_name,
                    reason=format_exc(),
                    error_message=str(e),
                )
                self.increment_metric(PROCESS_RESPONSE_METRIC, success=False)

        return processed

    def process_accumulation_response_file(self, file_name: str) -> int:
        log.info(
            "Processing accumulation response",
            payer_name=self.payer_name.value,
            file_name=file_name,
        )

        accumulation_response_content = self.download_accumulation_response_file(
            file_name=file_name
        )

        if file_name[-4:].upper() == ".PGP":
            # decrypt will raise on error
            private_key, passphrase = self.get_decrypt_params()
            accumulation_response_content = self.decrypt(
                accumulation_response_content, private_key, passphrase
            )

        # Check for empty file. Only some payers are allowed to send them.
        # Log different messages for alerting purposes and return zero.
        stripped_content = accumulation_response_content.strip(" \r\n\t")
        if len(stripped_content) == 0:
            if self.payer_name in PAYERS_WHO_SEND_EMPTY_FILES:
                log.info(
                    "Successfully processed empty accumulation response file",
                    payer_name=self.payer_name.value,
                    file_name=file_name,
                )
            else:
                log.error(
                    "Failed processing of empty response file",
                    payer_name=self.payer_name.value,
                    file_name=file_name,
                )
            return 0

        report_rows = self.file_generator.file_contents_to_dicts(
            accumulation_response_content
        )
        records = self.file_generator.get_detail_rows(report_rows)

        process_stats = self.process_accumulation_response_records(records)

        log.info(
            "Successfully processed accumulation response file",
            payer_name=self.payer_name.value,
            file_name=file_name,
            **process_stats,
        )

        return process_stats["total_records"]

    def find_files_to_process(self) -> List[str]:
        prefix = f"{self.payer_name.value}/{RECEIVED_DIR}/"
        file_names = self.file_handler.list_files(
            prefix=prefix,
            bucket_name=ACCUMULATION_RESPONSE_BUCKET,
        )
        eligible_file_names = []
        for file_name in file_names:
            filename_without_prefix = get_filename_without_prefix(file_name)
            if self.file_generator.match_response_filename(filename_without_prefix):
                eligible_file_names.append(file_name)
            elif file_name == prefix:
                pass
            else:
                log.warning(
                    "Unknown file found",
                    payer_name=self.payer_name.value,
                    file_name=file_name,
                )
        return eligible_file_names

    def download_accumulation_response_file(
        self,
        file_name: str,
    ) -> str:
        log.info(
            "Download accumulation response file",
            payer_name=self.payer_name.value,
            file_name=file_name,
        )
        try:
            return self.file_handler.download_file(
                filename=file_name,
                bucket=ACCUMULATION_RESPONSE_BUCKET,
            )
        except Exception as e:
            log.error(
                "Failed to download accumulation response file",
                payer_name=self.payer_name.value,
                file_name=file_name,
                reason=format_exc(),
                exc_info=True,
                error_message=str(e),
            )
            raise e

    def get_decrypt_params(self) -> Tuple[str, str]:
        private_key = os.environ.get(PAYER_ACCUMULATION_PRIVATE_KEY)
        passphrase = os.environ.get(PAYER_ACCUMULATION_PASSPHRASE)
        if not private_key or not passphrase:
            raise RuntimeWarning("Cannot load decryption params.")
        private_key = private_key.replace("\\n", "\n")
        return private_key, passphrase

    def decrypt(
        self,
        file_contents: str,
        private_key: str,
        passphrase: str,
    ) -> str:
        log.info(
            "Decrypt accumulation response file",
            payer_name=self.payer_name.value,
        )
        gpg = gnupg.GPG(gnupghome="/tmp")
        imported_result = gpg.import_keys(private_key)
        if not imported_result.count:
            log.error(
                "Failed to decrypt accumulation response file",
                payer_name=self.payer_name.value,
                error_message=str(imported_result.stderr),
            )
            raise RuntimeError("Failed to import private key.")
        result = gpg.decrypt(
            file_contents,
            passphrase=passphrase,
            always_trust=True,
            extra_args=["--ignore-mdc-error"],
        )
        if not result.ok:
            log.error(
                "Failed to decrypt accumulation response file",
                payer_name=self.payer_name.value,
                error_message=str(result.stderr),
            )
            raise RuntimeError("Decryption failed.")
        return str(result)

    def process_accumulation_response_records(
        self, records: list[dict[str, str]]
    ) -> dict[str, int]:
        try:
            process_stats = collections.defaultdict(int)
            process_stats["total_records"] = len(records)

            for record in records:
                detail_metadata = self.file_generator.get_detail_metadata(record)
                if detail_metadata.is_response:
                    process_stats["response_count"] += 1
                    if detail_metadata.is_rejection:
                        process_stats["rejected_record_count"] += 1
                        self.increment_metric(
                            RESPONSE_REJECTED_METRIC,
                            extra_tags=[f"reject_code:{detail_metadata.response_code}"],
                        )
                        # alerting is done off this log line
                        log.warning(
                            "Accumulation Record Rejected",
                            payer_name=self.payer_name.value,
                            member_id=detail_metadata.member_id or "Unknown",
                            accumulation_unique_id=detail_metadata.unique_id,
                            reject_reason=detail_metadata.response_reason,
                        )
                        if detail_metadata.should_update:
                            updated = self.mapping_service.update_status_to_rejected(
                                accumulation_unique_id=detail_metadata.unique_id,
                                response_status=detail_metadata.response_status,
                                response_code=detail_metadata.response_code,
                            )
                            if updated:
                                process_stats["rejected_update_count"] += 1
                            else:
                                process_stats["rejected_update_error_count"] += 1
                        else:
                            log.info(
                                "Not a valid rejection",
                                accumulation_unique_id=detail_metadata.unique_id,
                                response_status=detail_metadata.response_status,
                                response_code=detail_metadata.response_code,
                            )
                    else:
                        updated = self.mapping_service.update_status_to_accepted(
                            accumulation_unique_id=detail_metadata.unique_id,
                            response_status=detail_metadata.response_status,
                            response_code=detail_metadata.response_code,
                        )
                        if updated:
                            process_stats["accepted_update_count"] += 1
                        else:
                            process_stats["accepted_update_error_count"] += 1
                else:
                    # We shouldn't be getting any records that aren't responses
                    log.warning(
                        "Not a response record",
                        payer_name=self.payer_name.value,
                        unique_id=detail_metadata.unique_id,
                    )
            return process_stats

        except Exception as e:
            log.error(
                "Failed to process accumulation response records.",
                payer_name=self.payer_name.value,
                reason=format_exc(),
                exc_info=True,
                error_message=str(e),
            )
            raise

    def archive_response_file(self, file_name: str) -> None:
        log.info(
            "Archive accumulation response file",
            payer_name=self.payer_name.value,
            file_name=file_name,
        )

        filename_without_prefix = get_filename_without_prefix(file_name)
        file_date = self.file_generator.get_response_file_date(filename_without_prefix)
        if file_date:
            date_prefix = f"{file_date[0:4]}/{file_date[4:6]}/{file_date[6:8]}"
        else:
            date_prefix = datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y/%m/%d"
            )
        new_file_name = f"{self.payer_name.value}/{ARCHIVED_DIR}/{date_prefix}/{filename_without_prefix}"

        try:
            return self.file_handler.move_file(
                old_filename=file_name,
                new_filename=new_file_name,
                bucket=ACCUMULATION_RESPONSE_BUCKET,
            )
        except Exception as e:
            log.error(
                "Failed to archive accumulation response file",
                payer_name=self.payer_name.value,
                file_name=file_name,
                reason=format_exc(),
                exc_info=True,
                error_message=str(e),
            )
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


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def process_accumulation_responses(
    target_payer_names: Optional[List[PayerName]] = None,
) -> None:
    if not target_payer_names:
        target_payer_names = [
            PayerName.ANTHEM,
            PayerName.CREDENCE,
            PayerName.LUMINARE,
            PayerName.PREMERA,
        ]

    log.info("Starting accumulation response processing")

    for payer_name in target_payer_names:
        try:
            response_processing_job = AccumulationResponseProcessingJob(
                payer_name=payer_name
            )
            response_processing_job.run()
        except Exception as e:
            log.error(
                "Failed to process accumulation response",
                payer_name=payer_name.value,
                reason=format_exc(),
                error_message=str(e),
            )

    log.info("Finished accumulation response processing")
    stats.increment(
        metric_name=f"{METRIC_PREFIX}.{TASK_RUN_METRIC}",
        pod_name=stats.PodNames.PAYMENTS_PLATFORM,
    )


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def anthem_process_accumulation_responses() -> None:
    process_accumulation_responses(target_payer_names=[PayerName.ANTHEM])


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def credence_process_accumulation_responses() -> None:
    process_accumulation_responses(target_payer_names=[PayerName.CREDENCE])


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def luminare_process_accumulation_responses() -> None:
    process_accumulation_responses(target_payer_names=[PayerName.LUMINARE])


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def premera_process_accumulation_responses() -> None:
    process_accumulation_responses(target_payer_names=[PayerName.PREMERA])
