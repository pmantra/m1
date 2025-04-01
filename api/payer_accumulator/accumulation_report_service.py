from __future__ import annotations

import json
from typing import Optional

from payer_accumulator.accumulation_report_validator import AccumulationReportValidator
from payer_accumulator.common import OrganizationName, PayerName, PayerNameT
from payer_accumulator.constants import ACCUMULATION_FILE_BUCKET
from payer_accumulator.csv.csv_accumulation_file_generator import (
    CSVAccumulationFileGenerator,
)
from payer_accumulator.edi.edi_837_accumulation_file_generator import (
    EDI837AccumulationFileGenerator,
)
from payer_accumulator.file_generators import (
    AccumulationCSVFileGeneratorBCBSMA,
    AccumulationCSVFileGeneratorCigna,
    AccumulationFileGeneratorAnthem,
    AccumulationFileGeneratorCigna,
    AccumulationFileGeneratorCredence,
    AccumulationFileGeneratorLuminare,
    AccumulationFileGeneratorPremera,
    AccumulationFileGeneratorSurest,
    AccumulationFileGeneratorUHC,
    ESIAccumulationFileGenerator,
)
from payer_accumulator.file_generators.fixed_width_accumulation_file_generator import (
    FixedWidthAccumulationFileGenerator,
)
from payer_accumulator.file_handler import AccumulationFileHandler
from payer_accumulator.models.payer_accumulation_reporting import (
    PayerAccumulationReports,
)
from payer_accumulator.models.payer_list import Payer
from storage.connection import db
from storage.connector import RoutingSQLAlchemy
from utils.log import logger

log = logger(__name__)


class AccumulationReportService:
    def __init__(
        self, force_local: bool = False, session: Optional[RoutingSQLAlchemy] = None
    ):
        self.file_handler = AccumulationFileHandler(force_local=force_local)
        self.session = session or db.session

    def get_report_by_id(self, report_id) -> PayerAccumulationReports:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        return PayerAccumulationReports.query.get(report_id)

    def get_payer_name_for_report(self, report: PayerAccumulationReports) -> PayerNameT:
        payer = Payer.query.get(report.payer_id)
        return payer.payer_name.value

    # TODO: move data sourcer if/else switch statement in here

    @staticmethod
    def get_generator_class_for_payer_name(
        payer_name: PayerNameT,
        organization_name: Optional[OrganizationName] = None,
        health_plan_name: Optional[str] = None,
    ) -> (
        FixedWidthAccumulationFileGenerator
        | EDI837AccumulationFileGenerator
        | CSVAccumulationFileGenerator
    ):
        if payer_name == PayerName.AETNA.value:
            return EDI837AccumulationFileGenerator(payer_name=PayerName.AETNA)
        elif payer_name == PayerName.ANTHEM.value:
            return AccumulationFileGeneratorAnthem()
        elif payer_name == PayerName.BCBS_MA.value:
            return AccumulationCSVFileGeneratorBCBSMA(health_plan_name=health_plan_name)
        elif payer_name == PayerName.Cigna.value:
            return AccumulationFileGeneratorCigna()
        elif payer_name == PayerName.CREDENCE.value:
            return AccumulationFileGeneratorCredence()
        elif payer_name == PayerName.ESI.value:
            return ESIAccumulationFileGenerator()
        elif payer_name == PayerName.LUMINARE.value:
            return AccumulationFileGeneratorLuminare()
        elif payer_name == PayerName.PREMERA.value:
            return AccumulationFileGeneratorPremera()
        elif payer_name == PayerName.SUREST.value:
            return AccumulationFileGeneratorSurest()
        elif payer_name == PayerName.UHC.value:
            return AccumulationFileGeneratorUHC()
        elif payer_name == PayerName.CIGNA_TRACK_1.value:
            return AccumulationCSVFileGeneratorCigna(
                organization_name=organization_name
            )
        else:
            raise ValueError("Accumulation File Generator not found.")

    def get_raw_data_for_report(self, report: PayerAccumulationReports) -> str:
        report_data = self.file_handler.download_file(
            report.file_path(), ACCUMULATION_FILE_BUCKET
        )
        return report_data

    def get_structured_data_for_report(
        self, report: PayerAccumulationReports
    ) -> list[dict]:
        payer_name = self.get_payer_name_for_report(report)
        raw_data = self.get_raw_data_for_report(report)
        file_generator = self.get_generator_class_for_payer_name(payer_name)
        return file_generator.file_contents_to_dicts(raw_data)

    def get_json_for_report(self, report: PayerAccumulationReports) -> str:
        structured_data = self.get_structured_data_for_report(report)
        return json.dumps(structured_data, indent=4)

    def overwrite_report_with_json(self, report, report_json: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        try:
            report_data = json.loads(report_json)
        except ValueError:
            raise ValueError("Invalid JSON for report generation.")

        payer_name = self.get_payer_name_for_report(report)
        file_generator = self.get_generator_class_for_payer_name(payer_name)
        file_content = file_generator.generate_file_contents_from_json(report_data)
        self.file_handler.upload_file(
            file_content, report.file_path(), ACCUMULATION_FILE_BUCKET
        )

    def get_file_generator_for_report(self, report: PayerAccumulationReports):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        payer_name = self.get_payer_name_for_report(report)
        return self.get_generator_class_for_payer_name(payer_name)

    def _validate_report(self, report: PayerAccumulationReports):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        file_generator = self.get_file_generator_for_report(report=report)
        raw_data_for_report = self.get_raw_data_for_report(report=report)
        try:
            AccumulationReportValidator(
                session=self.session
            ).validate_report_member_sums(
                report=report,
                raw_report=raw_data_for_report,
                file_generator=file_generator,
            )
            log.info(
                "Checked validation on payer accumulation report",
                report_id=report.id,
                payer_id=report.payer_id,
            )
        except Exception as e:
            log.error(
                "Exception validating payer accumulation report",
                exception=e,
                report_id=report.id,
                payer_id=report.payer_id,
            )

    def _get_report_by_filename(self, filename: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        reports = (
            self.session.query(PayerAccumulationReports)
            .filter(PayerAccumulationReports.filename == filename)
            .all()
        )
        if not reports:
            log.error("No reports found to validate", report_name=filename)
        return reports

    def validate_reports(self, filename: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        reports = self._get_report_by_filename(filename=filename)
        for report in reports:
            self._validate_report(report=report)

    def regenerate_and_overwrite_report(
        self,
        file_generator: FixedWidthAccumulationFileGenerator
        | EDI837AccumulationFileGenerator
        | CSVAccumulationFileGenerator,
        report: PayerAccumulationReports,
    ) -> dict:
        log.info(
            "Starting to regenerate and overwrite accumulation report.",
            report_id=report.id,
        )
        file_contents = file_generator.regenerate_file_contents_from_report(
            report=report
        )
        log.info(
            "Got file contents for regenerated accumulation file",
            report_id=report.id,
            payer_name=report.payer_name.value,
            filename=report.filename,
        )
        # overwrites existing file with the same name
        self.file_handler.upload_file(
            content=file_contents,
            filename=report.file_path(),
            bucket=ACCUMULATION_FILE_BUCKET,
        )
        log.info(
            "Successfully regenerated, overwrote, and uploaded accumulation report.",
            report_id=report.id,
            payer_name=report.payer_name.value,
            filename=report.filename,
        )
        return {
            "id": report.id,
            "filename": report.filename,
            "payer_id": report.payer_id,
            "status": report.status,
            "report_date": report.report_date,
        }
