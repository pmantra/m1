import overpunch

from payer_accumulator.common import PayerName, TreatmentAccumulationStatus
from payer_accumulator.errors import InvalidPayerError
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.models.payer_accumulation_reporting import (
    PayerAccumulationReports,
    PayerReportStatus,
)
from payer_accumulator.models.payer_list import Payer
from utils.log import logger
from wallet.models.constants import MemberHealthPlanPatientRelationship
from wallet.models.reimbursement_wallet import MemberHealthPlan


def get_payer_id(payer_name: PayerName, log: logger = None) -> int:  # type: ignore[valid-type] # Function "utils.log.logger" is not valid as a type
    payer_id = Payer.query.filter_by(payer_name=payer_name).first()
    if not payer_id:
        error_msg = "Failed to get payer_id by payer_name"
        if log:
            log.error(error_msg, payer_name=payer_name)  # type: ignore[attr-defined] # logger? has no attribute "error"
        raise InvalidPayerError(f"{error_msg}: {payer_name}")
    return payer_id.id


def update_status_for_accumulation_report_and_treatment_procedure_mappings(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    session,
    accumulation_report: PayerAccumulationReports,
    report_status: PayerReportStatus,
    treatment_procedure_status: TreatmentAccumulationStatus,
):
    """
    Updates PayerAccumulationReport to report_status
    and treatment procedure mappings in the report to treatment_procedure_status
    """
    accumulation_report.status = report_status  # type: ignore[assignment] # Incompatible types in assignment (expression has type "PayerReportStatus", variable has type "Optional[str]")
    session.add(accumulation_report)

    treatment_procedure_mappings_in_report = (
        session.query(AccumulationTreatmentMapping)
        .filter(AccumulationTreatmentMapping.report_id == accumulation_report.id)
        .all()
    )
    for treatment_procedure_mapping in treatment_procedure_mappings_in_report:
        if _verify_status_to_update(
            treatment_procedure_status,
            treatment_procedure_mapping.treatment_accumulation_status,
        ):
            treatment_procedure_mapping.treatment_accumulation_status = (
                treatment_procedure_status
            )
            session.add(treatment_procedure_mapping)


def _verify_status_to_update(
    treatment_procedure_status: TreatmentAccumulationStatus,
    current_treatment_accumulation_status: TreatmentAccumulationStatus,
) -> bool:
    if treatment_procedure_status == TreatmentAccumulationStatus.ROW_ERROR or (
        treatment_procedure_status == TreatmentAccumulationStatus.SUBMITTED
        and current_treatment_accumulation_status
        == TreatmentAccumulationStatus.PROCESSED
    ):
        return True
    else:
        return False


def get_patient_first_name(member_health_plan: MemberHealthPlan) -> str:
    if (
        member_health_plan.patient_relationship
        == MemberHealthPlanPatientRelationship.CARDHOLDER
    ):
        return member_health_plan.subscriber_first_name  # type: ignore[return-value] # Incompatible return value type (got "Optional[str]", expected "str")
    else:
        return member_health_plan.patient_first_name  # type: ignore[return-value] # Incompatible return value type (got "Optional[str]", expected "str")


def get_patient_last_name(
    member_health_plan: MemberHealthPlan,
) -> str:
    if (
        member_health_plan.patient_relationship
        == MemberHealthPlanPatientRelationship.CARDHOLDER
    ):
        return member_health_plan.subscriber_last_name  # type: ignore[return-value] # Incompatible return value type (got "Optional[str]", expected "str")
    else:
        return member_health_plan.patient_last_name  # type: ignore[return-value] # Incompatible return value type (got "Optional[str]", expected "str")


def get_cents_from_overpunch(overpunch_repr: str) -> int:
    return int(overpunch.extract(overpunch_repr) * 100)


def get_filename_without_prefix(full_filename: str) -> str:
    """
    full_filename is assumed to have the following format:
        <foo>/<bar>/<filename>
    e.g. cigna/2023/12/11/test_file
    """
    filename_split = full_filename.split("/")
    return filename_split[len(filename_split) - 1]
