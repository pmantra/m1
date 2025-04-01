import io
from typing import List, Optional

import sqlalchemy

from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
)
from payer_accumulator.common import OrganizationName, PayerName
from payer_accumulator.errors import NoMappingDataProvidedError
from payer_accumulator.file_generators.accumulation_file_generator import (
    AccumulationFileGenerator,
)
from utils.log import logger
from wallet.models.reimbursement import ReimbursementRequest

CSV_DELIMITER = ","
log = logger(__name__)


class CSVAccumulationFileGenerator(AccumulationFileGenerator):
    def __init__(
        self,
        payer_name: PayerName,
        session: Optional[sqlalchemy.orm.Session] = None,
        organization_name: Optional[OrganizationName] = None,
        health_plan_name: Optional[str] = None,
    ):
        super().__init__(
            session=session,
            payer_name=payer_name,
            organization_name=organization_name,
            health_plan_name=health_plan_name,
            newline=True,
        )

    @staticmethod
    def _get_date_of_service(
        treatment_procedure: Optional[TreatmentProcedure],
        reimbursement_request: Optional[ReimbursementRequest],
    ) -> str:
        if treatment_procedure is not None:
            service_date = treatment_procedure.start_date.strftime("%Y%m%d")  # type: ignore[union-attr] # Item "None" of "date | None" has no attribute "strftime"
        elif reimbursement_request is not None:
            service_date = reimbursement_request.service_start_date.strftime("%Y%m%d")
        else:
            log.error("Both treatment procedure and reimbursement request are None")
            raise NoMappingDataProvidedError(
                "Either treatment procedure or reimbursement request must be non-empty"
            )
        return service_date

    def _generate_trailer(self, record_count: int, oop_total: int = 0) -> str:
        return ""

    def file_contents_to_dicts(self, file_contents: str) -> List[dict]:
        # TODO: implement this function for admin page
        return []

    def generate_file_contents_from_json(self, report_data: List[dict]) -> io.StringIO:
        # TODO: implement this function for admin page
        return io.StringIO("")

    def get_record_count_from_buffer(self, buffer: io.StringIO) -> int:
        # TODO: implement this function for admin page
        return 0

    @staticmethod
    def get_oop_to_submit(deductible: int, oop_applied: int) -> int:
        return oop_applied

    def detail_to_dict(self, detail_line: str) -> dict:
        # TODO: implement this function for admin page
        return {}
