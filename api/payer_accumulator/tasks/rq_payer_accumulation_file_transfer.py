from datetime import datetime, timedelta
from io import StringIO
from traceback import format_exc
from typing import List, Optional

from common import stats
from payer_accumulator.accumulation_report_service import AccumulationReportService
from payer_accumulator.common import (
    OrganizationName,
    PayerName,
    TreatmentAccumulationStatus,
)
from payer_accumulator.constants import (
    ACCUMULATION_FILE_BUCKET,
    AETNA_QUATRIX_FOLDER,
    ANTHEM_QUATRIX_FOLDER,
    CIGNA_AMAZON_QUATRIX_FOLDER,
    CIGNA_FOLDER,
    CIGNA_GOLDMAN_QUATRIX_FOLDER,
    CREDENCE_QUATRIX_FOLDER,
    DATA_SENDER_BUCKET,
    ESI_FOLDER,
    LUMINARE_QUATRIX_FOLDER,
    PGP_ENCRYPTION_OUTBOUND_BUCKET,
    PGP_ENCRYPTION_PAYERS,
    PREMERA_QUATRIX_FOLDER,
    QUATRIX_OUTBOUND_BUCKET,
    QUATRIX_PAYERS,
    SUREST_QUATRIX_FOLDER,
    UHC_FOLDER,
)
from payer_accumulator.errors import InvalidPayerError
from payer_accumulator.file_handler import AccumulationFileHandler
from payer_accumulator.helper_functions import (
    get_filename_without_prefix,
    update_status_for_accumulation_report_and_treatment_procedure_mappings,
)
from payer_accumulator.models.payer_accumulation_reporting import (
    PayerAccumulationReports,
    PayerReportStatus,
)
from storage.connection import db
from tasks.queues import job
from utils.log import logger

log = logger(__name__)

METRIC_PREFIX = "payer_accumulator.tasks.rq_payer_accumulation_file_transfer"
FILE_TRANSFER_METRIC = "file_transfer"
JOB_RUN_METRIC = "job_run"
MISSING_ACCUMULATION_REPORT = "missing_accumulation_report"


class AccumulationFileTransferHandler:
    def __init__(
        self,
        payer_name: PayerName,
        target_date: datetime,
        organization_name: Optional[OrganizationName] = None,
    ):
        self.payer_name = payer_name
        self.organization_name = organization_name
        self.date_prefix = target_date.strftime("%Y/%m/%d")

        self.file_handler = AccumulationFileHandler()
        self.session = db.session
        self.report_service = AccumulationReportService(session=self.session)

    def transfer_files(self) -> None:
        eligible_filenames = self.get_eligible_filenames_from_source_bucket()
        if len(eligible_filenames) > 0:
            log.info(
                "Found payer accumulation report files eligible for transfer.",
                file_count=len(eligible_filenames),
                payer_name=self.payer_name,
            )
        else:
            log.info(
                "No payer accumulation report files eligible for transfer.",
                payer_name=self.payer_name,
            )

        for filename in eligible_filenames:
            try:
                self.transfer_file_to_destination_bucket(filename)
                self.update_status_after_file_submission(filename, is_success=True)
                log.info(
                    "Successfully transferred payer accumulation file",
                    payer_name=self.payer_name.value,
                    filename=filename,
                )
                stats.increment(
                    metric_name=f"{METRIC_PREFIX}.{FILE_TRANSFER_METRIC}",
                    pod_name=stats.PodNames.PAYMENTS_PLATFORM,
                    tags=["success:true", f"payer_name:{self.payer_name.value}"],
                )
            except Exception as e:
                self.update_status_after_file_submission(filename, is_success=False)
                log.error(
                    "Failed to transfer file",
                    payer_name=self.payer_name.value,
                    filename=filename,
                    reason=format_exc(),
                    error_message=str(e),
                )
                stats.increment(
                    metric_name=f"{METRIC_PREFIX}.{FILE_TRANSFER_METRIC}",
                    pod_name=stats.PodNames.PAYMENTS_PLATFORM,
                    tags=["error:true", f"payer_name:{self.payer_name.value}"],
                )

    def get_eligible_filenames_from_source_bucket(self) -> List:
        """
        Eligible files for transfer satisfy the following conditions:
          - from the target date
          - the file has NEW status in the PayerAccumulationReports table
        """
        files = self.file_handler.get_many_from_gcp_bucket(
            prefix=f"{self.payer_name.value}/{self.date_prefix}/",
            bucket=ACCUMULATION_FILE_BUCKET,
        )
        eligible_filenames = []
        for file in files:
            full_filename = file.name
            filename_without_prefix = get_filename_without_prefix(full_filename)
            if (
                self.organization_name
                and self.organization_name.value not in filename_without_prefix
            ):
                continue
            report = (
                self.session.query(PayerAccumulationReports)
                .filter(PayerAccumulationReports.filename == filename_without_prefix)
                .one_or_none()
            )
            if not report:
                log.error(
                    "Failed to find payer accumulation report in DB",
                    payer_name=self.payer_name.value,
                    filename=filename_without_prefix,
                )
                stats.increment(
                    metric_name=f"{METRIC_PREFIX}.{MISSING_ACCUMULATION_REPORT}",
                    pod_name=stats.PodNames.PAYMENTS_PLATFORM,
                    tags=[f"payer_name:{self.payer_name.value}"],
                )
                continue
            if report.status == PayerReportStatus.NEW:
                eligible_filenames.append(full_filename)
        # ESI will error if we send then more than one file at a time, so only send one per transfer job.
        if self.payer_name == PayerName.ESI:
            eligible_filenames = eligible_filenames[:1]
        return eligible_filenames

    def transfer_file_to_destination_bucket(self, filename: str) -> None:
        accumulation_file = self.file_handler.get_from_gcp_bucket(
            filename=filename, bucket=ACCUMULATION_FILE_BUCKET
        )
        filename_for_destination_bucket = self.generate_filename_for_destination_bucket(
            full_filename=filename,
            payer_name=self.payer_name,
            organization_name=self.organization_name,
        )
        buffer = StringIO()
        buffer.write(accumulation_file)

        file_generator_class_by_payer = AccumulationReportService().get_generator_class_for_payer_name(
            payer_name=self.payer_name.value  # type: ignore[arg-type] # Argument "payer_name" to "get_generator_class_for_payer_name" of "AccumulationReportService" has incompatible type "Union[str, str, str, str, str, str]"; expected "Literal['cigna', 'esi', 'uhc']"
        )
        record_count = file_generator_class_by_payer.get_record_count_from_buffer(
            buffer=buffer
        )

        log.info(
            "Accumulation file record count.",
            record_count=record_count,
            payer_name=self.payer_name.value,
            filename=filename,
        )
        try:
            report_file_name = get_filename_without_prefix(full_filename=filename)
            self.report_service.validate_reports(filename=report_file_name)
        except Exception as e:
            log.error(
                "Exception attempting to validate contents for report file",
                exception=e,
                report_name=report_file_name,
                reason=format_exc(),
            )
        if self.payer_name in PGP_ENCRYPTION_PAYERS:
            bucket = PGP_ENCRYPTION_OUTBOUND_BUCKET
        elif self.payer_name in QUATRIX_PAYERS:
            bucket = QUATRIX_OUTBOUND_BUCKET
        else:
            bucket = DATA_SENDER_BUCKET
        self.file_handler.send_to_gcp_bucket(
            content=buffer,
            filename=filename_for_destination_bucket,
            bucket=bucket,
        )

    def update_status_after_file_submission(
        self, full_filename: str, is_success: bool
    ) -> None:
        filename_without_prefix = get_filename_without_prefix(full_filename)
        report = (
            self.session.query(PayerAccumulationReports)
            .filter(PayerAccumulationReports.filename == filename_without_prefix)
            .one()
        )
        if is_success:
            (report_status, treatment_procedure_status) = (
                PayerReportStatus.SUBMITTED,
                TreatmentAccumulationStatus.SUBMITTED,
            )
        else:
            (report_status, treatment_procedure_status) = (
                PayerReportStatus.FAILURE,
                TreatmentAccumulationStatus.ROW_ERROR,
            )
        update_status_for_accumulation_report_and_treatment_procedure_mappings(
            self.session,
            accumulation_report=report,
            report_status=report_status,
            treatment_procedure_status=treatment_procedure_status,
        )
        self.session.commit()

    @staticmethod
    def generate_filename_for_destination_bucket(
        full_filename: str,
        payer_name: PayerName,
        organization_name: Optional[OrganizationName] = None,
    ) -> str:
        filename_without_prefix = get_filename_without_prefix(full_filename)
        payer_prefix = None
        if payer_name == PayerName.AETNA:
            payer_prefix = AETNA_QUATRIX_FOLDER
        elif payer_name == PayerName.ANTHEM:
            payer_prefix = ANTHEM_QUATRIX_FOLDER
        elif payer_name == PayerName.Cigna:
            payer_prefix = CIGNA_FOLDER
        elif payer_name == PayerName.CIGNA_TRACK_1:
            if organization_name == OrganizationName.AMAZON:
                payer_prefix = CIGNA_AMAZON_QUATRIX_FOLDER
            elif organization_name == OrganizationName.GOLDMAN:
                payer_prefix = CIGNA_GOLDMAN_QUATRIX_FOLDER
        elif payer_name == PayerName.CREDENCE:
            payer_prefix = CREDENCE_QUATRIX_FOLDER
        elif payer_name == PayerName.ESI:
            payer_prefix = ESI_FOLDER
        elif payer_name == PayerName.LUMINARE:
            payer_prefix = LUMINARE_QUATRIX_FOLDER
        elif payer_name == PayerName.PREMERA:
            payer_prefix = PREMERA_QUATRIX_FOLDER
        elif payer_name == PayerName.SUREST:
            payer_prefix = SUREST_QUATRIX_FOLDER
        elif payer_name == PayerName.UHC:
            payer_prefix = UHC_FOLDER
        if not payer_prefix:
            raise InvalidPayerError("Invalid payer for accumulation file transfer")
        return f"{payer_prefix}/{filename_without_prefix}"


def transfer_payer_accumulation_files_to_aetna() -> None:
    transfer_payer_accumulation_files_to_outbound_bucket(
        target_payer_name=PayerName.AETNA
    )


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def transfer_payer_accumulation_files_to_anthem() -> None:
    transfer_payer_accumulation_files_to_outbound_bucket(
        target_payer_name=PayerName.ANTHEM
    )


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def transfer_payer_accumulation_files_to_bcbs_ma() -> None:
    transfer_payer_accumulation_files_to_outbound_bucket(
        target_payer_name=PayerName.BCBS_MA
    )


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def transfer_payer_accumulation_files_to_cigna_data_sender() -> None:
    transfer_payer_accumulation_files_to_outbound_bucket(
        target_payer_name=PayerName.Cigna
    )


def transfer_payer_accumulation_files_to_amazon_cigna_track_1() -> None:
    transfer_payer_accumulation_files_to_outbound_bucket(
        target_payer_name=PayerName.CIGNA_TRACK_1,
        organization_name=OrganizationName.AMAZON,
    )


def transfer_payer_accumulation_files_to_goldman_sachs_cigna_track_1() -> None:
    transfer_payer_accumulation_files_to_outbound_bucket(
        target_payer_name=PayerName.CIGNA_TRACK_1,
        organization_name=OrganizationName.GOLDMAN,
    )


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def transfer_payer_accumulation_files_to_credence() -> None:
    transfer_payer_accumulation_files_to_outbound_bucket(
        target_payer_name=PayerName.CREDENCE
    )


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def transfer_payer_accumulation_files_to_esi_data_sender() -> None:
    transfer_payer_accumulation_files_to_outbound_bucket(
        target_payer_name=PayerName.ESI
    )


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def transfer_payer_accumulation_files_to_luminare() -> None:
    transfer_payer_accumulation_files_to_outbound_bucket(
        target_payer_name=PayerName.LUMINARE
    )


def transfer_payer_accumulation_files_to_surest() -> None:
    transfer_payer_accumulation_files_to_outbound_bucket(
        target_payer_name=PayerName.SUREST
    )


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def transfer_payer_accumulation_files_to_premera() -> None:
    # Most other payers are on a schedule to generate the file in the evening
    # and then send it the next morning. For Premera we generate and send
    # twice per day. Look for files from yesterday *and* today. (Most likely
    # only "today" will have files because of the schedule in place, but this
    # covers more bases.)
    today = datetime.utcnow()
    one_day = timedelta(days=1)

    transfer_payer_accumulation_files_to_outbound_bucket(
        target_payer_name=PayerName.PREMERA, target_date=today - one_day
    )
    transfer_payer_accumulation_files_to_outbound_bucket(
        target_payer_name=PayerName.PREMERA, target_date=today
    )


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def transfer_payer_accumulation_files_to_uhc_data_sender() -> None:
    transfer_payer_accumulation_files_to_outbound_bucket(
        target_payer_name=PayerName.UHC
    )


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def transfer_payer_accumulation_files_to_outbound_bucket(
    target_payer_name: PayerName,
    organization_name: Optional[OrganizationName] = None,
    target_date: Optional[datetime] = None,
) -> None:
    if not target_date:
        today = datetime.utcnow()
        one_day = timedelta(days=1)
        target_date = today - one_day

    log.info(
        "Starting file transfer for payer accumulation files to destination",
        target_date=target_date,
        target_payer_name=target_payer_name.value,
    )
    try:
        file_transfer_handler = AccumulationFileTransferHandler(
            payer_name=target_payer_name,
            target_date=target_date,
            organization_name=organization_name,
        )
        file_transfer_handler.transfer_files()
    except Exception as e:
        # used in logging alert
        log.error(
            "Failed to transfer payer accumulation files to destination",
            payer_name=target_payer_name.value,
            reason=format_exc(),
            error_message=str(e),
        )
    log.info("Finished file transfer job for payer accumulation files to destination.")
    stats.increment(
        metric_name=f"{METRIC_PREFIX}.{JOB_RUN_METRIC}",
        pod_name=stats.PodNames.PAYMENTS_PLATFORM,
    )


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def transfer_payer_accumulation_report_file_to_data_sender(report_id: str) -> None:
    log.info(
        f"Starting file transfer for payer accumulation files to data-sender for report {report_id}"
    )
    report = PayerAccumulationReports.query.get(report_id)
    filename = report.file_path()
    payer_name = report.payer_name
    report_date = report.report_date
    target_date = datetime(report_date.year, report_date.month, report_date.day)

    file_transfer_handler = AccumulationFileTransferHandler(
        payer_name=payer_name, target_date=target_date
    )
    try:
        file_transfer_handler.transfer_file_to_destination_bucket(filename)
        file_transfer_handler.update_status_after_file_submission(
            filename, is_success=True
        )
        stats.increment(
            metric_name=f"{METRIC_PREFIX}.{FILE_TRANSFER_METRIC}",
            pod_name=stats.PodNames.PAYMENTS_PLATFORM,
            tags=["success:true", f"payer_name:{payer_name.value}"],
        )
    except Exception as e:
        file_transfer_handler.update_status_after_file_submission(
            filename, is_success=False
        )
        log.error(
            f"Failed to transfer payer accumulation file to data-sender for payer {e}",
            payer_name=payer_name.value,
            filename=filename,
            reason=format_exc(),
        )
    log.info(
        f"Finished file transfer job for payer accumulation report {report_id} to data-sender.",
        payer_name=payer_name.value,
        filename=filename,
    )
