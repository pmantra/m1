from flask import flash

from common.constants import Environment
from data_admin.maker_base import _MakerBase
from payer_accumulator.accumulation_report_service import AccumulationReportService
from payer_accumulator.common import TreatmentAccumulationStatus
from payer_accumulator.constants import ACCUMULATION_FILE_BUCKET
from payer_accumulator.file_handler import AccumulationFileHandler
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.models.payer_accumulation_reporting import (
    PayerAccumulationReports,
)
from storage.connection import db


class AccumulationMappingMaker(_MakerBase):
    def create_object(self, spec: dict, parent=None) -> AccumulationTreatmentMapping:  # type: ignore[no-untyped-def] # Function is missing a type annotation
        mapping = AccumulationTreatmentMapping(
            treatment_procedure_uuid=spec.get("treatment_procedure_uuid"),
            reimbursement_request_id=spec.get("reimbursement_request_id"),
            treatment_accumulation_status=TreatmentAccumulationStatus(
                # must be paid or refunded to be auto-appended to a report
                spec.get("treatment_accumulation_status")
            ),
            deductible=spec.get("deductible"),
            oop_applied=spec.get("oop_applied"),
            hra_applied=spec.get("hra_applied", None),
            completed_at=spec.get("completed_at"),
            payer_id=spec.get("payer_id"),
            is_refund=spec.get("is_refund", False),
        )
        db.session.add(mapping)
        return mapping


class AccumulationReportMaker(_MakerBase):
    # https://www.notion.so/mavenclinic/4edd0ddd7eca4abb97049c00ed589ddb?v=03cb1363604142a4a2e549eb5e7c125b&p=fff15ef5a64780109b27ee1bb23690e0&pm=s
    def create_object(self, spec: dict, parent=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # create report model
        payer_name = spec.get("payer")
        file_generator = AccumulationReportService.get_generator_class_for_payer_name(
            payer_name  # type: ignore[arg-type]
        )

        # generate file
        try:
            file_handler = AccumulationFileHandler(
                force_local=Environment.current() == Environment.LOCAL
            )
            report_contents = file_generator.generate_file_contents()
            report = PayerAccumulationReports.query.filter(
                PayerAccumulationReports.filename == file_generator.file_name
            ).one()
            file_handler.upload_file(
                content=report_contents,
                filename=report.file_path(),
                bucket=ACCUMULATION_FILE_BUCKET,
            )
        except Exception as e:
            flash(
                f"Accumulation Report for {payer_name} was created, but we failed to generate a file.",
                "error",
            )
            raise e
        return report
