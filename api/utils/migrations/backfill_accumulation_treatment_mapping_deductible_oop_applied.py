from pygtrie import Trie

from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
)
from payer_accumulator.accumulation_report_service import AccumulationReportService
from payer_accumulator.file_generators.fixed_width_accumulation_file_generator import (
    FixedWidthAccumulationFileGenerator,
)
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.models.payer_accumulation_reporting import (
    PayerAccumulationReports,
)
from storage.connection import db
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_wallet import MemberHealthPlan

session = db.session().using_bind("default")
report_service = AccumulationReportService(session=session)


def output(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    mapping: AccumulationTreatmentMapping,
    deductible: int,
    oop_applied: int,
    report_id: int,
    read_only: bool,
):
    if read_only:
        print(  # noqa
            f"Update mapping {mapping.id} for report {report_id} with deductible {deductible} and oop_applied {oop_applied}"  # noqa
        )  # noqa
    else:
        mapping.deductible = deductible
        mapping.oop_applied = oop_applied
        session.add(mapping)
        session.commit()


def process_report(report: PayerAccumulationReports, read_only: bool):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    try:
        file_generator = report_service.get_file_generator_for_report(report=report)
        payer_name = report_service.get_payer_name_for_report(report=report)
        print(f"Processing report {report.id}")  # noqa
        raw_data_for_report = report_service.get_raw_data_for_report(report=report)
        structured_data = file_generator.file_contents_to_dicts(
            raw_report=raw_data_for_report
        )
        detail_rows = file_generator.get_detail_rows(report_rows=structured_data)
        if payer_name == "cigna":
            process_cigna_report(
                file_generator=file_generator,
                detail_rows=detail_rows,
                report_id=report.id,
                read_only=read_only,
            )
        elif payer_name == "esi" or payer_name == "uhc":
            process_esi_or_uhc_report(
                file_generator=file_generator,
                detail_rows=detail_rows,
                report_id=report.id,
                read_only=read_only,
            )
        else:
            print(  # noqa
                f"Skipping report {report.id} - Report has invalid payer name {payer_name}"  # noqa
            )  # noqa
    except Exception as e:
        print(f"Exception processing report {report.id} error {str(e)}")  # noqa


def process_esi_or_uhc_report(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    file_generator: FixedWidthAccumulationFileGenerator,
    detail_rows,
    report_id,
    read_only: bool,
):
    """
    for each detail row, get the
        transaction ID, deductible, oop_applied
        query db for transaction ID and report ID - if theres anything != 1 entry print an error message
            if there is one entry update the deductible and oop_applied values
    """
    transaction_id_key = "transaction_id"
    for row in detail_rows:
        try:
            transaction_id = row[transaction_id_key]
            deductible = file_generator.get_deductible_from_row(detail_row=row)
            oop_applied = file_generator.get_oop_from_row(detail_row=row)
            mapping = (
                session.query(AccumulationTreatmentMapping)
                .filter(
                    AccumulationTreatmentMapping.report_id == report_id,
                    AccumulationTreatmentMapping.treatment_accumulation_status
                    == "SUBMITTED",
                    AccumulationTreatmentMapping.accumulation_transaction_id
                    == transaction_id,
                )
                .one()
            )
            output(
                mapping=mapping,
                deductible=deductible,
                oop_applied=oop_applied,
                report_id=report_id,
                read_only=read_only,
            )
        except Exception as e:
            print(  # noqa
                f"Exception processing transaction {transaction_id}, error {str(e)}"  # noqa
            )  # noqa


def get_cigna_mappings_by_subscriber_id(report_id: int) -> Trie:
    subscriber_id_to_mapping = Trie()
    mappings = (
        session.query(AccumulationTreatmentMapping)
        .filter(
            AccumulationTreatmentMapping.treatment_accumulation_status == "SUBMITTED",
            AccumulationTreatmentMapping.report_id == report_id,
        )
        .all()
    )
    for mapping in mappings:
        try:
            if mapping.reimbursement_request_id:
                subscriber_ids = (
                    session.query(MemberHealthPlan)
                    .with_entities(MemberHealthPlan.subscriber_insurance_id)
                    .join(
                        ReimbursementRequest,
                        ReimbursementRequest.reimbursement_wallet_id
                        == MemberHealthPlan.reimbursement_wallet_id,
                    )
                    .filter(ReimbursementRequest.id == mapping.reimbursement_request_id)
                    .distinct()
                    .all()
                )
                # only one of these subscriber IDs will be in the report file so its fine to add both
                # this case is only hit if a member health plan has numerous subscriber IDs associated with it
                for subscriber_id in subscriber_ids:
                    subscriber_id_to_mapping[subscriber_id[0]] = mapping
            elif mapping.treatment_procedure_uuid:
                subscriber_id = (
                    session.query(MemberHealthPlan)
                    .with_entities(MemberHealthPlan.subscriber_insurance_id)
                    .join(
                        TreatmentProcedure,
                        TreatmentProcedure.member_id == MemberHealthPlan.member_id,
                    )
                    .filter(TreatmentProcedure.uuid == mapping.treatment_procedure_uuid)
                    .one()[0]
                )
                subscriber_id_to_mapping[subscriber_id] = mapping
            else:
                raise Exception
        except Exception as e:
            print(f"Exception processing {mapping.id}, error {str(e)}")  # noqa
    return subscriber_id_to_mapping


def process_cigna_report(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    file_generator: FixedWidthAccumulationFileGenerator,
    detail_rows,
    report_id,
    read_only: bool,
):
    """
    for each row for this report ID in the accumulation treatment mapping table,
        get and add to a Trie the subscriber ID, dob, accumulation_treatment_mapping.id

    for each detail row, get the
    subscriber ID, patient DOB, deductible, oop_applied
    subscriber ID is a substring! if theres more than one row for a subscriber ID prefix in a file then print out the rows details

    get the associated subscriber ID by prefix - if theres more than one print the results
    if theres ONE match on subscriber ID prefix then update deductible and oop_applied if so
        else print details
    """
    subscriber_id_to_db_mapping = get_cigna_mappings_by_subscriber_id(
        report_id=report_id
    )
    subscriber_id_prefix_to_apply_values = {}
    # create map of subscriber ID prefix to apply values from the report contents
    for row in detail_rows:
        subscriber_id_prefix = file_generator.get_cardholder_id_from_detail_dict(
            detail_row_dict=row
        )
        deductible = file_generator.get_deductible_from_row(detail_row=row)
        oop_applied = file_generator.get_oop_from_row(detail_row=row)
        if subscriber_id_prefix_to_apply_values.get(subscriber_id_prefix):
            # we want to handle this manually because we cant tell for sure which db mapping should
            # be updated if there are more than one transaction w the same subcsriber ID prefix
            subscriber_id_prefix_to_apply_values.pop(subscriber_id_prefix)
            print(  # noqa
                f"Skipping subscriber ID prefix {subscriber_id_prefix} in report {report_id} because there are overlapping mappings"
            )  # noqa
        else:
            subscriber_id_prefix_to_apply_values[subscriber_id_prefix] = {
                "deductible": deductible,
                "oop_applied": oop_applied,
            }

    # for each item in the report contents map we want to try to get the mapping for it, and
    # if present (and unique) update its values
    for (
        subscriber_id_prefix,
        apply_values,
    ) in subscriber_id_prefix_to_apply_values.items():
        try:
            mappings = list(subscriber_id_to_db_mapping[subscriber_id_prefix:])
            if len(mappings) > 1:
                print(  # noqa
                    f"Skipping update - Multiple db mappings for subscriber id prefix {subscriber_id_prefix}",  # noqa
                )  # noqa
            else:
                mapping = mappings[0]
                output(
                    mapping=mapping,
                    deductible=apply_values["deductible"],
                    oop_applied=apply_values["oop_applied"],
                    report_id=report_id,
                    read_only=read_only,
                )
        except Exception as e:
            print(  # noqa
                f"Skipping processing subscriber id prefix {subscriber_id_prefix} with error {str(e)}",  # noqa
            )  # noqa


def run_backfill(read_only=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    all_submitted_reports = (
        session.query(PayerAccumulationReports)
        .filter(PayerAccumulationReports.status == "SUBMITTED")
        .distinct()
        .all()
    )
    for report in all_submitted_reports:
        process_report(report=report, read_only=read_only)
