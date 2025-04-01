import io
from traceback import format_exc
from typing import List, Optional

from audit_log.utils import emit_audit_log_create, get_flask_admin_user
from common import stats
from common.stats import PodNames
from payer_accumulator.accumulation_report_service import AccumulationReportService
from payer_accumulator.common import (
    OrganizationName,
    PayerName,
    PayerNameT,
    TreatmentAccumulationStatus,
)
from payer_accumulator.constants import ACCUMULATION_FILE_BUCKET
from payer_accumulator.edi.edi_837_accumulation_file_generator import (
    EDI837AccumulationFileGenerator,
)
from payer_accumulator.file_handler import AccumulationFileHandler
from payer_accumulator.helper_functions import (
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

METRIC_PREFIX = "api.payer_accumulator.rq_payer_accumulation_file_generation"
FILE_GENERATION_METRIC = "file_generation"
JOB_RUN = "job_run"
UPLOAD_FILE_METRIC = "upload_file"
SUCCESS = "success"
FAILURE = "failure"


class AccumulationFileGenerationJob:
    def __init__(self, payer_name: PayerNameT, organization_name: Optional[OrganizationName] = None, health_plan_name: Optional[str] = None):  # type: ignore[valid-type] # Optional[...] must have exactly one type argument
        self.payer_name = payer_name
        self.file_generator = (
            AccumulationReportService.get_generator_class_for_payer_name(
                payer_name,
                organization_name=organization_name,
                health_plan_name=health_plan_name,
            )
        )
        self.filename = self.file_generator.file_name
        self.session = db.session

    def run(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            self.create_and_upload_accumulation_report()
            self.increment_metric(JOB_RUN, SUCCESS)
        except Exception as e:
            log.error(
                "Failed to run accumulation file generation job due to exception.",
                reason=format_exc(),
                payer_name=self.payer_name,
                exc_info=True,
                error_message=str(e),
            )
            self.increment_metric(JOB_RUN, FAILURE)

    def create_and_upload_accumulation_report(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        log.info("Creating accumulation file", payer_name=self.payer_name)
        accumulation_report_content = self.generate_accumulation_file()
        if (
            isinstance(self.file_generator, EDI837AccumulationFileGenerator)
            and accumulation_report_content.getvalue() == ""
        ):
            log.info(
                "Empty edi file generated, skip sending to payer",
                payer_name=self.payer_name,
                run_time=self.file_generator.run_time,
            )
            return
        accumulation_report = (
            self.session.query(PayerAccumulationReports)
            .filter(PayerAccumulationReports.filename == self.filename)
            .one()
        )
        self.upload_accumulation_report(
            accumulation_report_content, accumulation_report
        )

        if get_flask_admin_user():
            emit_audit_log_create(accumulation_report)
        log.info(
            "Successfully created accumulation file and submitted to GCS bucket",
            payer_name=self.payer_name,
            file_name=self.filename,
            date=self.file_generator.run_time.date().strftime("%Y%m%d"),
        )

    def generate_accumulation_file(self) -> io.StringIO:
        try:
            buffer = self.file_generator.generate_file_contents()
            self.increment_metric(FILE_GENERATION_METRIC, SUCCESS)
            return buffer
        except Exception as e:
            log.error(
                "Failed to generate accumulation report.",
                payer_name=self.payer_name,
                reason=format_exc(),
                exc_info=True,
                error_message=str(e),
            )
            self.increment_metric(FILE_GENERATION_METRIC, FAILURE)
            raise

    def upload_accumulation_report(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        accumulation_report_content: io.StringIO,
        accumulation_report: PayerAccumulationReports,
    ):
        log.info(
            "Uploading accumulation file to GCS bucket",
            payer_name=self.payer_name,
            file_name=self.filename,
        )
        try:
            file_handler = AccumulationFileHandler()
            file_handler.upload_file(
                content=accumulation_report_content,
                filename=accumulation_report.file_path(),
                bucket=ACCUMULATION_FILE_BUCKET,
            )
            self.increment_metric(UPLOAD_FILE_METRIC, SUCCESS)
        except Exception as e:
            log.error(
                "Failed to upload accumulation file to GCS bucket",
                payer_name=self.payer_name,
                file_name=self.filename,
                reason=format_exc(),
                exc_info=True,
                error_message=str(e),
            )
            self.increment_metric(UPLOAD_FILE_METRIC, FAILURE)
            update_status_for_accumulation_report_and_treatment_procedure_mappings(
                self.session,
                accumulation_report=accumulation_report,
                report_status=PayerReportStatus.FAILURE,
                treatment_procedure_status=TreatmentAccumulationStatus.ROW_ERROR,
            )
            self.session.commit()
            raise e

    def increment_metric(self, metric_name: str, result: str = None):  # type: ignore[no-untyped-def,assignment] # Function is missing a return type annotation #type: ignore[assignment] # Incompatible default for argument "result" (default has type "None", argument has type "str") #type: ignore[assignment] # Incompatible default for argument "result" (default has type "None", argument has type "str")
        tags = [f"payer_name:{self.payer_name}"]
        if result:
            tags.append(f"{result}:true")
        stats.increment(
            metric_name=f"{METRIC_PREFIX}.{metric_name}",
            pod_name=PodNames.PAYMENTS_PLATFORM,
            tags=tags,
        )


def run_accumulation_file_generation_by_plan_name(
    payer_name: PayerName, health_plan_names: List[str]
) -> None:
    if not health_plan_names:
        log.error(
            "No health plans found for payer. Accumulation file will not be generated",
            payer_name=payer_name.value,
        )
        return
    log.info(
        "Health plans found for payer. Starting accumulation file generation jobs.",
        payer_name=payer_name.value,
        num_health_plans=len(health_plan_names),
    )
    for health_plan_name in health_plan_names:
        log.info(
            "Starting accumulation file generation job for health plan",
            payer_name=payer_name.value,
            health_plan_name=health_plan_name,
        )
        job = AccumulationFileGenerationJob(
            payer_name.value,
            health_plan_name=health_plan_name,
        )
        job.run()


def aetna_accumulation_file_generation() -> None:
    aetna_job = AccumulationFileGenerationJob(PayerName.AETNA.value)
    aetna_job.run()


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def anthem_accumulation_file_generation() -> None:
    anthem_job = AccumulationFileGenerationJob(PayerName.ANTHEM.value)
    anthem_job.run()


def bcbs_ma_accumulation_file_generation() -> None:
    plan_names = [
        "HUGHP",
        "HarvardF&S",
    ]  # this list will need to be updated if new plans are added to bcbs_ma
    run_accumulation_file_generation_by_plan_name(PayerName.BCBS_MA, plan_names)


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def cigna_accumulation_file_generation() -> None:
    cigna_job = AccumulationFileGenerationJob(PayerName.Cigna.value)
    cigna_job.run()


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def credence_accumulation_file_generation() -> None:
    credence_job = AccumulationFileGenerationJob(PayerName.CREDENCE.value)
    credence_job.run()


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def esi_accumulation_file_generation() -> None:
    esi_job = AccumulationFileGenerationJob(PayerName.ESI.value)
    esi_job.run()


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def luminare_accumulation_file_generation() -> None:
    luminare_job = AccumulationFileGenerationJob(PayerName.LUMINARE.value)
    luminare_job.run()


def surest_accumulation_file_generation() -> None:
    surest_job = AccumulationFileGenerationJob(PayerName.SUREST.value)
    surest_job.run()


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def cigna_track_1_amazon_accumulation_file_generation() -> None:
    cigna_track_1_job = AccumulationFileGenerationJob(
        PayerName.CIGNA_TRACK_1.value, organization_name=OrganizationName.AMAZON
    )
    cigna_track_1_job.run()


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def cigna_track_1_goldman_sachs_accumulation_file_generation() -> None:
    cigna_track_1_job = AccumulationFileGenerationJob(
        PayerName.CIGNA_TRACK_1.value, organization_name=OrganizationName.GOLDMAN
    )
    cigna_track_1_job.run()


def premera_accumulation_file_generation() -> None:
    premera_job = AccumulationFileGenerationJob(PayerName.PREMERA.value)
    premera_job.run()


@job(service_ns="payer_accumulation", team_ns="payments_platform")
def uhc_accumulation_file_generation() -> None:
    uhc_job = AccumulationFileGenerationJob(PayerName.UHC.value)
    uhc_job.run()
