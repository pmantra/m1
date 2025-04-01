import io
from abc import ABC, abstractmethod
from datetime import datetime, time
from typing import Optional, Tuple

import sqlalchemy

from common import stats
from common.stats import PodNames
from cost_breakdown.models.cost_breakdown import CostBreakdown
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureType,
)
from payer_accumulator.common import (
    DetailWrapper,
    OrganizationName,
    PayerName,
    TreatmentAccumulationStatus,
)
from payer_accumulator.errors import (
    AccumulationOpsActionableError,
    NoCriticalAccumulationInfoError,
    NoMappingDataProvidedError,
    NoMemberHealthPlanError,
    SkipAccumulationDueToMissingInfo,
)
from payer_accumulator.file_generators.accumulation_file_generator_mixin import (
    AccumulationFileGeneratorMixin,
)
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.models.payer_accumulation_reporting import (
    PayerAccumulationReports,
)
from utils.log import logger
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_wallet import MemberHealthPlan

log = logger(__name__)

MappingWithDataT = Tuple[
    AccumulationTreatmentMapping,
    Optional[TreatmentProcedure],
    Optional[ReimbursementRequest],
]

METRIC_PREFIX = "api.payer_accumulator.accumulation_file_generator"
ELIGIBLE_TREATMENT_PROCEDURE_COUNT = "eligible_treatment_procedure.count"
FILE_ROW_COUNT = "file_row.count"
MISSING_CRITICAL_ACCUMULATION_INFO = "missing_critical_accumulation_info"
ROW_GENERATION_METRIC = "row_generation"


class AccumulationFileGenerator(ABC, AccumulationFileGeneratorMixin):
    def __init__(
        self,
        payer_name: PayerName,
        session: Optional[sqlalchemy.orm.Session] = None,
        organization_name: Optional[OrganizationName] = None,
        health_plan_name: Optional[str] = None,
        newline: Optional[bool] = False,
    ):
        super().__init__(
            session=session,
            payer_name=payer_name,
            organization_name=organization_name,
            health_plan_name=health_plan_name,
        )
        self.newline = newline

    @property
    @abstractmethod
    def file_name(self) -> str:
        pass

    # instance level cache for _get_treatment_procedures_and_accumulation_mappings
    _cached_accumulation_mappings_with_data: Optional[list[MappingWithDataT]] = None

    @property
    def _accumulation_mappings_with_data(self) -> list[MappingWithDataT]:
        if self.organization_name:
            organization_id = self._get_organization_id(self.organization_name.value)
        else:
            organization_id = None

        if self.health_plan_name:
            health_plan_ids = self._get_health_plan_ids(self.health_plan_name)
        else:
            health_plan_ids = None

        if self._cached_accumulation_mappings_with_data is not None:
            return self._cached_accumulation_mappings_with_data
        self._cached_accumulation_mappings_with_data = (
            self.get_accumulation_mappings_with_data(
                self.payer_id, organization_id, health_plan_ids
            )
        )
        rows = len(self._cached_accumulation_mappings_with_data)
        log.info(
            f"Retrieved {rows} accumulation mappings with data for accumulation.",
            payer=self.payer_name,
            filename=self.file_name,
        )
        stats.gauge(
            metric_name=f"{METRIC_PREFIX}.{ELIGIBLE_TREATMENT_PROCEDURE_COUNT}",
            metric_value=rows,
            pod_name=PodNames.PAYMENTS_PLATFORM,
            tags=[f"payer_name:{self.payer_name.value}"],
        )

        return self._cached_accumulation_mappings_with_data

    def generate_file_contents(self) -> io.StringIO:
        log.info(
            "Starting generating accumulation file",
            payer=self.payer_name,
            filename=self.file_name,
        )
        report = self.create_new_accumulation_report(
            payer_id=self.payer_id,
            file_name=self.file_name,
            run_time=self.run_time,
        )

        buffer = io.StringIO()
        buffer.write(self._generate_header() + ("\n" if self.newline else ""))

        self.record_count = 0
        oop_total = 0
        for (
            mapping,
            treatment_procedure,
            reimbursement_request,
        ) in self._accumulation_mappings_with_data:
            buffer, oop_total = self._add_row_from_mapping(
                buffer=buffer,
                oop_total=oop_total,
                mapping=mapping,
                report=report,
                treatment_procedure=treatment_procedure,
                reimbursement_request=reimbursement_request,
            )
        stats.gauge(
            metric_name=f"{METRIC_PREFIX}.{FILE_ROW_COUNT}",
            metric_value=self.record_count,
            pod_name=PodNames.PAYMENTS_PLATFORM,
            tags=[f"payer_name:{self.payer_name.value}"],
        )

        buffer.write(self._generate_trailer(self.record_count, oop_total))
        self.session.commit()
        log.info(
            "Successfully created new accumulation report",
            payer=self.payer_name,
            filename=self.file_name,
        )
        return buffer

    def regenerate_file_contents_from_report(
        self,
        report: PayerAccumulationReports,
    ) -> io.StringIO:
        log.info(
            "Rewriting existing accumulation report",
            payer=self.payer_name,
            filename=self.file_name,
        )

        buffer = io.StringIO()
        buffer.write(self._generate_header() + ("\n" if self.newline else ""))

        self.record_count = 0
        oop_total = 0
        for mapping in report.treatment_mappings:
            treatment_procedure = (
                self.session.query(TreatmentProcedure)
                .filter(TreatmentProcedure.uuid == mapping.treatment_procedure_uuid)
                .one_or_none()
            )
            reimbursement_request = ReimbursementRequest.query.get(
                mapping.reimbursement_request_id
            )
            mapping.treatment_accumulation_status = (
                TreatmentAccumulationStatus.REFUNDED
                if mapping.is_refund
                else TreatmentAccumulationStatus.PAID
            )
            buffer, oop_total = self._add_row_from_mapping(
                buffer=buffer,
                oop_total=oop_total,
                mapping=mapping,
                report=report,
                treatment_procedure=treatment_procedure,
                reimbursement_request=reimbursement_request,
                is_regeneration=True,
            )

        stats.gauge(
            metric_name=f"{METRIC_PREFIX}.{FILE_ROW_COUNT}",
            metric_value=self.record_count,
            pod_name=PodNames.PAYMENTS_PLATFORM,
            tags=[f"payer_name:{self.payer_name.value}"],
        )

        buffer.write(self._generate_trailer(self.record_count, oop_total))
        self.session.commit()
        log.info(
            "Successfully created new accumulation report",
            payer=self.payer_name,
            filename=self.file_name,
        )
        return buffer

    def _add_row_from_mapping(
        self,
        buffer: io.StringIO,
        oop_total: int,
        mapping: AccumulationTreatmentMapping,
        report: PayerAccumulationReports,
        treatment_procedure: Optional[TreatmentProcedure] = None,
        reimbursement_request: Optional[ReimbursementRequest] = None,
        is_regeneration: bool = False,
    ) -> Tuple[io.StringIO, int]:
        # track initial status
        accumulation_status = TreatmentAccumulationStatus(
            mapping.treatment_accumulation_status
        )
        # add row from mapping
        try:
            # TODO: Move setting deductible and oop into data sourcer job
            cost_breakdown = self.get_cost_breakdown(
                treatment_procedure=treatment_procedure,
                reimbursement_request=reimbursement_request,
            )
            is_reversal = accumulation_status == TreatmentAccumulationStatus.REFUNDED
            if is_reversal or is_regeneration:
                # in the case we are regenerating the file, these values are either already set based on cost breakdown
                # or overriden and should not be recalculated
                deductible = mapping.deductible
                oop = mapping.oop_applied
                hra_applied = mapping.hra_applied or 0
            else:
                deductible = cost_breakdown.deductible
                oop = self.get_oop_to_submit(
                    deductible=deductible, oop_applied=cost_breakdown.oop_applied
                )
                hra_applied = cost_breakdown.hra_applied or 0

            detail_wrapper = self.get_detail(
                treatment_procedure=treatment_procedure,
                reimbursement_request=reimbursement_request,
                sequence_number=mapping.id,
                deductible=deductible,  # type: ignore[arg-type] # Argument "deductible" to "get_detail" of "AccumulationFileGenerator" has incompatible type "Optional[int]"; expected "int"
                oop_applied=oop,  # type: ignore[arg-type] # Argument "oop_applied" to "get_detail" of "AccumulationFileGenerator" has incompatible type "Optional[int]"; expected "int"
                hra_applied=hra_applied,
                is_reversal=is_reversal,
                cost_breakdown=cost_breakdown,
                is_regeneration=is_regeneration,
            )
            # Set the legacy accumulation_transaction_id from the detail wrapper.
            # Note that it defaults to the procedure/claim identifier if there's no transaction_id configured.
            # TODO: if/when we separate file gen and content gen, pull this from the filegen directly
            transaction_id = str(
                detail_wrapper.transaction_id
                or (
                    treatment_procedure.uuid
                    if treatment_procedure
                    else (reimbursement_request.id if reimbursement_request else None)
                )
            )
            if transaction_id is None:
                raise NoCriticalAccumulationInfoError(
                    "No mapping data provided for transaction id."
                )

            # update mapping
            mapping.accumulation_unique_id = detail_wrapper.unique_id
            mapping.accumulation_transaction_id = transaction_id
            mapping.deductible = deductible
            mapping.oop_applied = oop
            mapping.hra_applied = hra_applied
            mapping.report_id = report.id
            # record row
            buffer.write(detail_wrapper.line + ("\n" if self.newline else ""))
            self.record_count += 1
            oop_total += oop

            # success status
            accumulation_status = TreatmentAccumulationStatus.PROCESSED
            mapping.row_error_reason = None
        except SkipAccumulationDueToMissingInfo:
            # skip status
            log.info(
                "Skipping Payer Accumulation Row due to missing info.",
                mapping=mapping.id,
            )
            accumulation_status = TreatmentAccumulationStatus.SKIP
            # Skipped rows will be added in PAY-5408
        except Exception as e:
            log.error(
                "Failed to generate accumulation",
                error_message=str(e),
                mapping=mapping.id,
                treatment_procedure=mapping.treatment_procedure_uuid,
                reimbursement_request_id=str(mapping.reimbursement_request_id),
            )
            # failure status
            accumulation_status = TreatmentAccumulationStatus.ROW_ERROR
            # row error reason must be less than 1024 characters
            if isinstance(e, AccumulationOpsActionableError):
                mapping.row_error_reason = f"Need Ops Action: {str(e)}"
            else:
                mapping.row_error_reason = f"Need Eng Action: {str(e)}"
            # TODO: factor this shared status/session code out in PAY-5408
            mapping.treatment_accumulation_status = accumulation_status  # type: ignore[assignment] # Incompatible types in assignment (expression has type "TreatmentAccumulationStatus", variable has type "Optional[str]")
            self.session.add(mapping)
        finally:
            stats.increment(
                metric_name=f"{METRIC_PREFIX}.{ROW_GENERATION_METRIC}",
                pod_name=PodNames.PAYMENTS_PLATFORM,
                tags=[
                    f"payer_name:{self.payer_name.value}",
                    f"row_status:{accumulation_status.name}",
                ],
            )
            # TODO: factor this shared status/session code out in PAY-5408
            mapping.treatment_accumulation_status = accumulation_status  # type: ignore[assignment] # Incompatible types in assignment (expression has type "TreatmentAccumulationStatus", variable has type "Optional[str]")
            self.session.add(mapping)
        return buffer, oop_total

    def get_detail(
        self,
        deductible: int,
        oop_applied: int,
        cost_breakdown: CostBreakdown,
        sequence_number: int,
        hra_applied: Optional[int] = 0,
        treatment_procedure: Optional[TreatmentProcedure] = None,
        reimbursement_request: Optional[ReimbursementRequest] = None,
        is_reversal: bool = False,
        is_regeneration: bool = False,
    ) -> DetailWrapper:
        if deductible == 0 and oop_applied == 0:
            raise SkipAccumulationDueToMissingInfo(
                "No row can be generated for 0 deductible / 0 OOP cost breakdowns."
            )
        if treatment_procedure is not None:
            detail = self._generate_detail_by_treatment_procedure(
                treatment_procedure,
                sequence_number=sequence_number,
                deductible=deductible,
                oop_applied=oop_applied,
                cost_breakdown=cost_breakdown,
                hra_applied=hra_applied,
                is_reversal=is_reversal,
                is_regeneration=is_regeneration,
            )
        elif reimbursement_request is not None:
            detail = self._generate_detail_by_reimbursement_request(
                reimbursement_request=reimbursement_request,
                record_type=reimbursement_request.procedure_type,  # type: ignore[arg-type] # Argument "record_type" to "_generate_detail_by_reimbursement_request" of "AccumulationFileGenerator" has incompatible type "Optional[str]"; expected "str"
                sequence_number=sequence_number,
                deductible_apply_amount=deductible,
                oop_apply_amount=oop_applied,
                cost_breakdown=cost_breakdown,
                hra_apply_amount=hra_applied,
                is_regeneration=is_regeneration,
            )
        else:
            raise NoMappingDataProvidedError(
                "No mapping data provided for detail retrieval."
            )
        return detail

    def _generate_detail_by_treatment_procedure(
        self,
        treatment_procedure: TreatmentProcedure,
        sequence_number: int,
        deductible: int,
        oop_applied: int,
        cost_breakdown: CostBreakdown,
        hra_applied: Optional[int] = 0,
        is_reversal: bool = False,
        is_regeneration: bool = False,
    ) -> DetailWrapper:
        member_health_plan = self.get_member_health_plan(
            member_id=treatment_procedure.member_id,
            wallet_id=treatment_procedure.reimbursement_wallet_id,
            effective_date=treatment_procedure.start_date,
        )
        if not member_health_plan:
            log.error(
                "Member health plan is missing for treatment_procedure",
                treatment_procedure=treatment_procedure.uuid,
            )
            stats.increment(
                metric_name=f"{METRIC_PREFIX}.{MISSING_CRITICAL_ACCUMULATION_INFO}",
                pod_name=PodNames.PAYMENTS_PLATFORM,
                tags=[
                    f"payer_name:{self.payer_name.value}",
                    "info_type:member_health_plan",
                ],
            )
            raise NoMemberHealthPlanError("No member health plan")
        return self._generate_detail(
            record_id=treatment_procedure.id,
            record_type=TreatmentProcedureType(treatment_procedure.procedure_type),
            sequence_number=sequence_number,
            cost_breakdown=cost_breakdown,  # Used as ESI transmission_id for TreatmentProcedures
            service_start_date=datetime.combine(
                treatment_procedure.start_date, time.min  # type: ignore[arg-type] # Argument 1 to "combine" of "datetime" has incompatible type "date | None"; expected "date"
            ),
            member_health_plan=member_health_plan,
            deductible=deductible,
            oop_applied=oop_applied,
            hra_applied=hra_applied,  # type: ignore[arg-type] # Argument "hra_applied" to "_generate_detail" of "AccumulationFileGenerator" has incompatible type "int | None"; expected "int"
            is_reversal=is_reversal,
            is_regeneration=is_regeneration,
        )

    def _generate_detail_by_reimbursement_request(
        self,
        reimbursement_request: ReimbursementRequest,
        record_type: str,
        sequence_number: int,
        deductible_apply_amount: int,
        oop_apply_amount: int,
        cost_breakdown: CostBreakdown,
        hra_apply_amount: Optional[int] = 0,
        is_regeneration: bool = False,
    ) -> DetailWrapper:
        member_health_plan = self.get_member_health_plan(
            member_id=reimbursement_request.person_receiving_service_id,  # type: ignore[arg-type]
            wallet_id=reimbursement_request.reimbursement_wallet_id,
            effective_date=reimbursement_request.service_start_date,
        )
        if not member_health_plan:
            log.error(
                "Member health plan is missing for reimbursement request.",
                reimbursement_request_id=str(reimbursement_request.id),
            )
            stats.increment(
                metric_name=f"{METRIC_PREFIX}.{MISSING_CRITICAL_ACCUMULATION_INFO}",
                pod_name=PodNames.PAYMENTS_PLATFORM,
                tags=[
                    f"payer_name:{self.payer_name.value}",
                    "info_type:member_health_plan",
                ],
            )
            raise NoMemberHealthPlanError("No member health plan")

        procedure_record_type = TreatmentProcedureType(record_type)
        return self._generate_detail(
            record_id=reimbursement_request.id,
            record_type=procedure_record_type,
            sequence_number=sequence_number,
            cost_breakdown=cost_breakdown,
            service_start_date=reimbursement_request.service_start_date,
            member_health_plan=member_health_plan,
            deductible=deductible_apply_amount,
            oop_applied=oop_apply_amount,
            hra_applied=hra_apply_amount,  # type: ignore[arg-type] # Argument "hra_applied" to "_generate_detail" of "AccumulationFileGenerator" has incompatible type "int | None"; expected "int"
            is_reversal=False,
            is_regeneration=is_regeneration,
        )

    @abstractmethod
    def _generate_header(self) -> str:
        pass

    @abstractmethod
    def _generate_detail(
        self,
        record_id: int,
        record_type: TreatmentProcedureType,
        cost_breakdown: CostBreakdown,
        service_start_date: datetime,
        deductible: int,
        oop_applied: int,
        hra_applied: int,
        member_health_plan: MemberHealthPlan,
        is_reversal: bool,
        is_regeneration: bool,
        sequence_number: int,
    ) -> DetailWrapper:
        pass

    @abstractmethod
    def _generate_trailer(self, record_count: int, oop_total: int = 0) -> str:
        pass

    @staticmethod
    @abstractmethod
    def get_oop_to_submit(deductible: int, oop_applied: int) -> int:
        pass

    def get_run_datetime(self, length: int = 14) -> str:
        if not (4 <= length <= 20):
            raise ValueError("The length parameter must be between 4 and 20")
        return self.run_time.strftime("%Y%m%d%H%M%S%f")[:length]
