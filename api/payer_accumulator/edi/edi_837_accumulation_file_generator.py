import io
import json
import traceback
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

import jsonschema
import sqlalchemy

from common.constants import Environment
from common.global_procedures.procedure import ProcedureService
from cost_breakdown.models.cost_breakdown import CostBreakdown
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureType,
)
from models.profiles import Address
from payer_accumulator.common import (
    DetailWrapper,
    PayerName,
    TreatmentAccumulationStatus,
)
from payer_accumulator.edi.constants import BLANK_SPACE, PAYERNAME_MAPPING
from payer_accumulator.edi.errors import (
    EDI837AccumulationFileGeneratorException,
    NoValidRowIncludedException,
    X12FileWriterException,
)
from payer_accumulator.edi.helper import find_number_of_segments
from payer_accumulator.edi.x12_file_writer import X12FileWriter
from payer_accumulator.errors import (
    AccumulationOpsActionableError,
    InvalidSubscriberIdError,
    NoCriticalAccumulationInfoError,
    NoGlobalProcedureFoundError,
    NoHcpcsCodeForGlobalProcedureError,
    NoMemberHealthPlanError,
    NoMemberIdError,
    SkipAccumulationDueToMissingInfo,
)
from payer_accumulator.file_generators.accumulation_file_generator import (
    AccumulationFileGenerator,
    MappingWithDataT,
)
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.models.payer_accumulation_reporting import (
    PayerAccumulationReports,
)
from storage.connection import db
from utils.log import logger
from wallet.constants import MAVEN_ADDRESS
from wallet.models.constants import (
    MemberHealthPlanPatientRelationship,
    MemberHealthPlanPatientSex,
)
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_wallet import MemberHealthPlan

current_directory = Path(__file__).parent
log = logger(__name__)


class EDI837AccumulationFileGenerator(AccumulationFileGenerator):
    def __init__(
        self,
        payer_name: PayerName,
        session: Optional[sqlalchemy.orm.Session] = None,
    ):
        super().__init__(session=session, payer_name=payer_name)

        file_path = current_directory / "models" / "837.json"
        with open(file_path, "r") as schema_file:
            schema = json.load(schema_file)
        self.x12_file_writer = X12FileWriter(schema=schema)
        self.run_time = datetime.utcnow()
        self.procedure_code_cache = {}

    def generate_file_contents(self) -> io.StringIO:
        """
        Entry point of Accumulation file generator, it will
        1. generate a 837 data dictionary by querying accumulation_treatment_mapping table
        2. validate the dictionary against 837 file schema defined in json
        3. use X12FileWriter to recursively generate x12 file
        """
        try:
            mappings: list[MappingWithDataT] = self.get_accumulation_mappings_with_data(
                payer_id=self.payer_id
            )
            if len(mappings) == 0:
                log.info(
                    "No ready rows need to be sent to payer",
                    payer_name=self.payer_name,
                    run_time=self.run_time,
                )
                return io.StringIO("")

            report: PayerAccumulationReports = self.create_new_accumulation_report(
                payer_id=self.payer_id,
                file_name=self.file_name,
                run_time=self.run_time,
            )
            log.info(
                "Start generating accumulation report",
                payer_name=self.payer_name,
                report_id=report.id,
                file_name=self.file_name,
                run_time=self.run_time,
            )
            for mapping, treatment_procedure, reimbursement_request in mappings:
                if mapping.oop_applied is None or mapping.deductible is None:
                    # duplicating oop/ded logic from default file generator jobs to handle pharmacy mappings
                    cost_breakdown = self.get_cost_breakdown(
                        treatment_procedure=treatment_procedure,
                        reimbursement_request=reimbursement_request,
                    )
                    if cost_breakdown is not None:
                        mapping.deductible = cost_breakdown.deductible
                        mapping.oop_applied = cost_breakdown.oop_applied

            data: dict = self._get_file_data(report=report, mappings=mappings)
            content = self._validate_and_generate_file_from_data(data, report)
        except NoValidRowIncludedException:
            self.session.commit()
            log.info(
                "No ready rows need to be sent to payer",
                payer_name=self.payer_name,
                run_time=self.run_time,
            )
            return io.StringIO("")
        except Exception as e:
            self.session.rollback()
            log.error(
                "837 accumulation file is not generated due to some failure",
                payer_name=self.payer_name,
                file_name=self.file_name,
                run_time=self.run_time,
                error=str(e),
                traceback=traceback.format_exc(),
            )
            raise EDI837AccumulationFileGeneratorException(
                "Error running generate_file_contents"
            ) from e
        return content

    def regenerate_file_contents_from_report(
        self, report: PayerAccumulationReports
    ) -> io.StringIO:
        """
        Used to regenerate file contents when an unsent report is edited
        """
        try:
            log.info(
                "Rewriting existing accumulation report",
                payer_name=self.payer_name,
                report_id=report.id,
                file_name=self.file_name,
                run_time=self.run_time,
            )
            if len(report.treatment_mappings) == 0:
                log.info(
                    "No ready rows need to be sent to payer",
                    payer_name=self.payer_name,
                    run_time=self.run_time,
                )
                return io.StringIO("")
            mappings: list[MappingWithDataT] = []
            for mapping in report.treatment_mappings:
                treatment_procedure = (
                    db.session.query(TreatmentProcedure)
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
                mappings.append((mapping, treatment_procedure, reimbursement_request))
            data: dict = self._get_file_data(
                report=report, mappings=mappings, is_regeneration=True
            )
            content = self._validate_and_generate_file_from_data(data, report)

        except Exception as e:
            self.session.rollback()
            log.error(
                "837 accumulation file is not regenerated due to some failure",
                payer_name=self.payer_name,
                file_name=self.file_name,
                run_time=self.run_time,
                error=str(e),
                traceback=traceback.format_exc(),
            )
            raise EDI837AccumulationFileGeneratorException(
                "Error running regenerate_file_contents_from_report"
            ) from e
        return content

    def _validate_and_generate_file_from_data(
        self, data: dict, report: PayerAccumulationReports
    ) -> io.StringIO:
        try:
            jsonschema.validate(instance=data, schema=self.x12_file_writer.schema)
            log.info(
                "Successfully validated against file schema",
                payer_name=self.payer_name,
                report_id=report.id,
                file_name=self.file_name,
                run_time=self.run_time,
            )
        except jsonschema.exceptions.ValidationError as e:
            log.error(
                "Failed to validate against 837 schema",
                payer_name=self.payer_name,
                report_id=report.id,
                file_name=self.file_name,
                run_time=self.run_time,
                error=str(e),
                traceback=traceback.format_exc(),
            )
            raise EDI837AccumulationFileGeneratorException(f"Validation error {str(e)}")
        try:
            content: io.StringIO = self.x12_file_writer.generate_x12_file(data)
        except X12FileWriterException as e:
            log.error(
                "Failed to generate x12 file",
                payer_name=self.payer_name,
                report_id=report.id,
                file_name=self.file_name,
                run_time=self.run_time,
                error=str(e),
                traceback=traceback.format_exc(),
            )
            raise EDI837AccumulationFileGeneratorException(
                f"File generation error {str(e)}"
            )
        self.session.commit()
        log.info(
            "Successfully generated accumulation report",
            payer_name=self.payer_name,
            report_id=report.id,
            file_name=self.file_name,
            run_time=self.run_time,
        )
        return content

    @property
    def file_name(self) -> str:
        return f"Maven_{self.payer_name.value.capitalize()}_Accumulation_file_{self.run_time.strftime('%Y%m%d_%H%M%S')}.edi"

    def _get_member_claim_loop(
        self, mapping: MappingWithDataT, is_regeneration: bool = False
    ) -> dict:
        (
            accumulation_treatment_mapping,
            treatment_procedure,
            reimbursement_request,
        ) = mapping
        if reimbursement_request:
            member_id = reimbursement_request.person_receiving_service_id
            wallet_id = reimbursement_request.reimbursement_wallet_id
            effective_date = reimbursement_request.service_start_date
            service_date = reimbursement_request.service_start_date.strftime("%Y%m%d")
            if not reimbursement_request.wallet_expense_subtype:
                log.error(
                    "No wallet expense subtype for reimbursement request",
                    reimbursement_request=reimbursement_request.id,
                )
                raise NoCriticalAccumulationInfoError(
                    "No wallet expense subtype for reimbursement request"
                )
            procedure_id = (
                reimbursement_request.wallet_expense_subtype.global_procedure_id
            )
        elif treatment_procedure:
            member_id = treatment_procedure.member_id
            wallet_id = treatment_procedure.reimbursement_wallet_id
            effective_date = treatment_procedure.start_date  # type: ignore[assignment]
            service_date = treatment_procedure.start_date.strftime("%Y%m%d")  # type: ignore[union-attr] # Item "None" of "date | None" has no attribute "strftime"
            procedure_id = treatment_procedure.global_procedure_id
        else:
            raise NoCriticalAccumulationInfoError(
                "No mapping data provided for detail retrieval."
            )
        if member_id is None:
            raise NoMemberIdError(
                "No member id found for treatment_procedure member id"
                " or reimbursement request person receiving service id"
            )

        procedure_code = self.procedure_code_cache.get(procedure_id)
        if not procedure_code:
            procedure = ProcedureService(internal=True).get_procedure_by_id(
                procedure_id=procedure_id
            )
            if not procedure:
                log.error(
                    "Could not find existing Global Procedure record.",
                    global_procedure_id=procedure_id,
                )
                raise NoGlobalProcedureFoundError(
                    f"No global procedure found for procedure id {procedure_id}"
                )
            procedure_code = procedure["hcpcs_code"]
            if not procedure_code:
                log.error(
                    "Could not find hcpcs_code from Global Procedure record.",
                    global_procedure_id=procedure_id,
                )
                raise NoHcpcsCodeForGlobalProcedureError(
                    f"Global procedure {procedure_id} does not contain hcpcs_code"
                )
            self.procedure_code_cache[procedure_id] = procedure_code

        member_health_plan: Optional[MemberHealthPlan] = self.get_member_health_plan(
            member_id=member_id, wallet_id=wallet_id, effective_date=effective_date
        )
        if not member_health_plan:
            log.error(
                "Member health plan is missing for treatment_procedure or reimbursement request",
                mapping_id=accumulation_treatment_mapping.id,
            )
            raise NoMemberHealthPlanError(
                f"No member health plan found for this member {member_id}"
            )

        insurance_id = member_health_plan.subscriber_insurance_id
        if (
            len(insurance_id) > 12
            or len(insurance_id) == 0
            or (not insurance_id.isalnum())
        ):
            raise InvalidSubscriberIdError("Invalid subscriber insurance id")

        cost_breakdown = self.get_cost_breakdown(
            treatment_procedure=treatment_procedure,
            reimbursement_request=reimbursement_request,
        )
        accumulation_status = TreatmentAccumulationStatus(
            accumulation_treatment_mapping.treatment_accumulation_status
        )
        is_reversal = accumulation_status == TreatmentAccumulationStatus.REFUNDED
        if is_reversal or is_regeneration:
            deductible = accumulation_treatment_mapping.deductible
            oop = accumulation_treatment_mapping.oop_applied
            hra = accumulation_treatment_mapping.hra_applied or 0
        else:
            deductible = cost_breakdown.deductible
            oop = cost_breakdown.oop_applied
            hra = cost_breakdown.hra_applied

        if oop == 0:
            log.error(
                "Got 0 oop_applied amount for treatment_procedure or reimbursement request",
                mapping_id=accumulation_treatment_mapping.id,
            )
            raise SkipAccumulationDueToMissingInfo("got 0 oop_applied amount")

        if oop is None:
            log.error(
                "Got empty oop_applied amount",
                mapping_id=accumulation_treatment_mapping.id,
            )
            raise NoCriticalAccumulationInfoError("got empty oop_applied amount")

        amount = abs(float(Decimal(oop) / Decimal(100)))
        timestamp = self.get_run_datetime(length=16)
        unique_id = f"{timestamp}{self.loop_id:04}"
        original_claim_unique_id = (
            self._get_original_claim_unique_id(accumulation_treatment_mapping)
            if is_reversal
            else unique_id
        )
        if is_reversal:
            log.info(
                "Calculated original_claim_unique_id for reversal",
                member_id=member_id,
                original_claim_unique_id=original_claim_unique_id,
                accumulation_treatment_mapping=accumulation_treatment_mapping.id,
            )

        address: Optional[Address] = self.get_member_address(member_id=member_id)
        if not address:
            log.info(
                "No member address found, use default address", member_id=member_id
            )
            address_line = (
                f"{MAVEN_ADDRESS['address_1']} {MAVEN_ADDRESS['address_2']}".strip()
            )
            city = MAVEN_ADDRESS["city"].strip()
            state = MAVEN_ADDRESS["state"].strip()
            zip_code = MAVEN_ADDRESS["zip"].strip()
        else:
            log.info("Member address found", member_id=member_id)
            address_line = address.street_address.strip()
            city = address.city.strip()
            state = address.state.strip()
            zip_code = address.zip_code.strip()

        data = dict(
            subscriber_hierarchical_level=dict(
                hierarchical_id_number=str(
                    self.loop_id + 1
                ),  # plus one due to starting from two
                hierarchical_parent_id_number="1",
                hierarchical_level_code="22",
                hierarchical_child_code="0"
                if member_health_plan.is_subscriber
                else "1",
            ),
            subscriber_information=dict(
                payer_responsibility_sequence_number_code="P",
                individual_relationship_code="18"
                if member_health_plan.is_subscriber
                else "",
                claim_filing_indicator_code="ZZ",
            ),
            loop_2010BA=[
                dict(
                    subscriber_name=dict(
                        entity_identifier_code="IL",
                        entity_type_qualifier="1",
                        subscriber_last_name=member_health_plan.subscriber_last_name,
                        subscriber_first_name=member_health_plan.subscriber_first_name,
                        identification_code_qualifier="MI",
                        subscriber_primary_identifier=member_health_plan.subscriber_insurance_id,
                    ),
                    subscriber_address=dict(
                        subscriber_address_line_1=address_line,
                    ),
                    subscriber_city_state_zipcode=dict(
                        subscriber_city_name=city,
                        subscriber_state_code=state,
                        subscriber_postal_zone_or_zip_code=zip_code,
                    ),
                    subscriber_demographic_info=dict(
                        date_time_period_format_qualifier="D8",
                        subscriber_birth_date=member_health_plan.subscriber_date_of_birth.strftime("%Y%m%d"),  # type: ignore[union-attr] # Item "None" of "date | None" has no attribute "strftime"
                        subscriber_gender_code=self._get_subscriber_gender_code(
                            member_health_plan
                        ),
                    ),
                )
            ],
            loop_2010BB=[
                dict(
                    payer_name=dict(
                        entity_identifier_code="PR",
                        entity_type_qualifier="2",
                        payer_name=PAYERNAME_MAPPING[self.payer_name].get("payer_name"),
                        identification_code_qualifier="PI",
                        payer_identifier=PAYERNAME_MAPPING[self.payer_name].get(
                            "payer_identifier"
                        ),
                    )
                )
            ],
        )
        loop_2300 = dict(
            claim_information=dict(
                patient_control_number=unique_id,
                total_claim_charge_amount=amount,
                health_care_service_location_information=dict(
                    place_of_service_code="11",
                    facility_code_qualifier="B",
                    claim_frequency_code="8" if is_reversal else "1",
                ),
                provider_or_supplier_signature_indicator="Y",
                assignment_or_plan_participation_code="A",
                benefits_assignment_certification_indicator="W",
                release_of_information_code="Y",
            ),
            payer_claim_control_number=dict(
                reference_identification_qualifier="F8",
                payer_claim_control_number=original_claim_unique_id,
            ),
            health_care_diagnosis_code=dict(
                c022_health_care_code_information_1=dict(
                    diagnosis_type_code="ABK",
                    diagnosis_code="Z3183",
                )
            ),
            loop_2400=[
                dict(
                    service_line_number=dict(assigned_number=1),
                    professional_service=dict(
                        composite_medical_procedure_identifier=dict(
                            product_or_service_id_qualifier="HC",
                            procedure_code=procedure_code,
                            procedure_modifiers=["", "", "", ""],
                            description="RELATED TO BUNDLED FERTILITY SERVICES",
                        ),
                        line_item_charge_amount=amount,
                        unit_or_basis_for_measurement_code="UN",
                        service_unit_count=1,
                        composite_diagnosis_code_pointer=dict(
                            diagnosis_code_pointer_1=1
                        ),
                    ),
                    service_line_date_service_date=dict(
                        date_time_qualifier="472",
                        date_time_period_format_qualifier="D8",
                        service_date=service_date,
                    ),
                )
            ],
        )
        if not is_reversal:
            loop_2300.pop("payer_claim_control_number")
        if member_health_plan.is_subscriber:
            data.update(
                dict(
                    loop_2300=[loop_2300],
                )
            )
            self.loop_id += 1
        else:
            data.update(
                dict(
                    loop_2000C=[
                        dict(
                            patient_hierarchical_level=dict(
                                hierarchical_id_number=str(self.loop_id + 2),
                                hierarchical_parent_id_number=str(self.loop_id + 1),
                                hierarchical_level_code="23",
                                hierarchical_child_code="0",
                            ),
                            patient_information=dict(
                                individual_relationship_code="01",
                            ),
                            loop_2010CA=[
                                dict(
                                    patient_name=dict(
                                        entity_identifier_code="QC",
                                        entity_type_qualifier="1",
                                        patient_last_name=member_health_plan.patient_last_name,
                                        patient_first_name=member_health_plan.patient_first_name,
                                    ),
                                    patient_address=dict(
                                        patient_address_line_1=address_line
                                    ),
                                    patient_city_state_zipcode=dict(
                                        patient_city_name=city,
                                        patient_state_code=state,
                                        patient_postal_zone=zip_code,
                                    ),
                                    patient_demographic_information=dict(
                                        date_time_period_format_qualifier="D8",
                                        patient_birth_date=member_health_plan.patient_date_of_birth.strftime("%Y%m%d"),  # type: ignore[union-attr] # Item "None" of "date | None" has no attribute "strftime"
                                        patient_gender_code=self._get_patient_gender_code(
                                            member_health_plan
                                        ),
                                    ),
                                )
                            ],
                            loop_2300=[loop_2300],
                        )
                    ]
                )
            )
            self.loop_id += 2
        accumulation_treatment_mapping.accumulation_unique_id = unique_id
        accumulation_treatment_mapping.deductible = deductible
        accumulation_treatment_mapping.oop_applied = oop
        accumulation_treatment_mapping.hra_applied = hra
        return data

    def _get_file_header(self, unique_file_identifier: int) -> dict:
        return dict(
            interchange_control_header=dict(
                authorization_information_qualifier="00",
                authorization_information=BLANK_SPACE * 10,
                security_information_qualifier="00",
                security_information=BLANK_SPACE * 10,
                interchange_id_qualifier_sender="ZZ",
                interchange_sender_id="AV09311993" + BLANK_SPACE * 5,
                interchange_id_qualifier_receiver="01",
                interchange_receiver_id="030240928" + BLANK_SPACE * 6,
                interchange_date=self.run_time.strftime("%y%m%d"),
                interchange_time=self.run_time.strftime("%H%M"),
                repetition_separator="^",
                interchange_control_version_number="00501",
                interchange_control_number=unique_file_identifier,
                acknowledgment_requested="1",
                interchange_usage_indicator="P"
                if Environment.current() == Environment.PRODUCTION
                else "T",
                component_element_separator="<",
            ),
            functional_group_header=dict(
                functional_identifier_code="HC",
                application_sender_code="5010",
                application_receiver_code="030240928",
                date=self.run_time.strftime("%Y%m%d"),
                time=self.run_time.strftime("%H%M"),
                group_control_number=unique_file_identifier,
                responsible_agency_code="X",
                version_release_industry_identifier_code="005010X222A1",
            ),
        )

    def _get_file_trailer(self, unique_file_identifier: int) -> dict:
        return dict(
            functional_group_trailer=dict(
                number_of_transaction_sets_included=1,
                group_control_number=unique_file_identifier,
            ),
            interchange_control_trailer=dict(
                number_of_included_functional_groups=1,
                interchange_control_number=unique_file_identifier,
            ),
        )

    @staticmethod
    def _get_patient_gender_code(member_health_plan: MemberHealthPlan) -> str:
        if member_health_plan.patient_sex == MemberHealthPlanPatientSex.MALE:
            return "M"
        elif member_health_plan.patient_sex == MemberHealthPlanPatientSex.FEMALE:
            return "F"
        return "U"

    @staticmethod
    def _get_subscriber_gender_code(member_health_plan: MemberHealthPlan) -> str:
        if (
            member_health_plan.patient_relationship
            == MemberHealthPlanPatientRelationship.CARDHOLDER
        ):
            return EDI837AccumulationFileGenerator._get_patient_gender_code(
                member_health_plan
            )
        return "U"

    def _get_file_transaction_set(
        self,
        mappings: list[MappingWithDataT],
        unique_file_identifier: int,
        report: PayerAccumulationReports,
        is_regeneration: bool = False,
    ) -> dict:
        loop_2000Bs = []
        self.loop_id = 1
        for mapping_data in mappings:
            mapping: AccumulationTreatmentMapping = mapping_data[0]
            try:
                loop_2000b = self._get_member_claim_loop(
                    mapping=mapping_data, is_regeneration=is_regeneration
                )
                mapping.treatment_accumulation_status = TreatmentAccumulationStatus.PROCESSED  # type: ignore[assignment] # Incompatible types in assignment (expression has type "TreatmentAccumulationStatus", variable has type "Optional[str]")
                mapping.row_error_reason = None
                mapping.report_id = report.id
                loop_2000Bs.append(loop_2000b)
                log.info(
                    "Successfully generated claim for accumulation row",
                    row=mapping.id,
                    treatment_uuid=mapping.treatment_procedure_uuid,
                    reimbursement_request_id=mapping.reimbursement_request_id,
                    unique_id=mapping.accumulation_unique_id,
                )
            except SkipAccumulationDueToMissingInfo:
                mapping.treatment_accumulation_status = TreatmentAccumulationStatus.SKIP  # type: ignore[assignment] # Incompatible types in assignment (expression has type "TreatmentAccumulationStatus", variable has type "Optional[str]")
                log.error(
                    "Skipped payer accumulation row",
                    row=mapping.id,
                    treatment_uuid=mapping.treatment_procedure_uuid,
                    reimbursement_request_id=mapping.reimbursement_request_id,
                )
            except Exception as e:
                mapping.treatment_accumulation_status = TreatmentAccumulationStatus.ROW_ERROR  # type: ignore[assignment] # Incompatible types in assignment (expression has type "TreatmentAccumulationStatus", variable has type "Optional[str]")
                # row error reason must be less than 1024 characters
                if isinstance(e, AccumulationOpsActionableError):
                    mapping.row_error_reason = f"Need Ops Action: {str(e)}"
                else:
                    mapping.row_error_reason = f"Need Eng Action: {str(e)}"
                log.error(
                    "Error generating claim for accumulation row",
                    row=mapping.id,
                    treatment_procedure=mapping.treatment_procedure_uuid,
                    reimbursement_request_id=str(mapping.reimbursement_request_id),
                    error_message=str(e),
                )
            self.session.add(mapping)

        if len(loop_2000Bs) == 0:
            log.error(
                "Error generating transaction set, no valid transaction included",
                unique_file_id=unique_file_identifier,
            )
            raise NoValidRowIncludedException(
                "Error generating transaction set, no valid transaction included"
            )

        transaction_set = dict(
            transaction_set_header=dict(
                transaction_set_identifier_code="837",
                transaction_set_control_number=str(unique_file_identifier),
                version_identifier="005010X222A1",
            ),
            beginning_of_hierachical_transaction=dict(
                hierarchical_structure_code="0019",
                transaction_set_purpose_code="00",
                originator_application_transaction_identifier=str(
                    unique_file_identifier
                ),
                transaction_set_creation_date=self.run_time.strftime("%Y%m%d"),
                transaction_set_creation_time=self.run_time.strftime("%H%M"),
                claim_or_encounter_identifier="CH",
            ),
            loop_1000A=[
                dict(
                    submitter_name=dict(
                        entity_identifier_code="41",
                        entity_type_qualifier="2",
                        submitter_last_or_organization_name="MAVEN CLINIC CO.",
                        identification_code_qualifier="46",
                        submitter_identifier="465747423",
                    ),
                    submitter_edi_contact_information=dict(
                        contact_function_code="IC",
                        communication_number_qualifier="EM",
                        communication_number="aetna-accumulator@mavenclinic.com",
                    ),
                )
            ],
            loop_1000B=[
                dict(
                    receiver_name=dict(
                        entity_identifier_code="40",
                        entity_type_qualifier="2",
                        receiver_name=PAYERNAME_MAPPING[self.payer_name].get(
                            "payer_name"
                        ),
                        identification_code_qualifier="46",
                        receiver_primary_identifier=PAYERNAME_MAPPING[
                            self.payer_name
                        ].get("payer_identifier"),
                    )
                )
            ],
            loop_2000A=[
                dict(
                    billing_provider_hierarchical_level=dict(
                        hierarchical_id_number="1",
                        hierarchical_level_code="20",
                        hierarchical_child_code="1",
                    ),
                    billing_provider_specialty_information=dict(
                        provider_code="BI",
                        reference_identification_qualifier="PXC",
                        provider_taxonomy_code="207VE0102X",
                    ),
                    loop_2010AA=[
                        dict(
                            billing_provider_name=dict(
                                entity_identifier_code="85",
                                entity_type_qualifier="2",
                                billing_provider_last_or_organizational_name="MAVEN CLINIC CO.",
                                identification_code_qualifier="XX",
                                billing_provider_identifier="1326898982",
                            ),
                            billing_provider_address=dict(
                                billing_provider_address_line="160 VARICK ST FL 6"
                            ),
                            billing_provider_city_state_zipcode=dict(
                                billing_provider_city_name="NEW YORK",
                                billing_provider_state_or_province_code="NY",
                                billing_provider_postal_zone_or_zipcode="100131272",
                            ),
                            billing_provider_tax_identification=dict(
                                reference_identification_qualifier="EI",
                                billing_provider_tax_identification_number="465747423",
                            ),
                        )
                    ],
                    loop_2000B=loop_2000Bs,
                )
            ],
        )
        count = find_number_of_segments(transaction_set)
        transaction_set.update(
            dict(
                transaction_set_trailer=dict(
                    transaction_segment_count=count
                    + 1,  # need to count trailer itself as well
                    transaction_set_control_number=str(unique_file_identifier),
                )
            )
        )
        return transaction_set

    def _get_file_data(
        self,
        report: PayerAccumulationReports,
        mappings: list[MappingWithDataT],
        is_regeneration: bool = False,
    ) -> dict:
        unique_file_identifier = 10**8 + report.id
        data = {}
        header: dict = self._get_file_header(
            unique_file_identifier=unique_file_identifier
        )
        transaction_set: dict = self._get_file_transaction_set(
            mappings=mappings,
            unique_file_identifier=unique_file_identifier,
            report=report,
            is_regeneration=is_regeneration,
        )
        trailer: dict = self._get_file_trailer(unique_file_identifier)
        data.update(header)
        data.update(transaction_set)
        data.update(trailer)
        return data

    def _get_original_claim_unique_id(
        self, new_treatment_mapping: AccumulationTreatmentMapping
    ) -> str:
        potential_claim_statuses = [
            TreatmentAccumulationStatus.PROCESSED,
            TreatmentAccumulationStatus.SUBMITTED,
            TreatmentAccumulationStatus.ACCEPTED,
        ]

        query = db.session.query(AccumulationTreatmentMapping).filter(
            AccumulationTreatmentMapping.treatment_accumulation_status.in_(
                potential_claim_statuses
            ),
            AccumulationTreatmentMapping.accumulation_unique_id.isnot(None),
        )

        if new_treatment_mapping.treatment_procedure_uuid:
            query = query.filter(
                AccumulationTreatmentMapping.treatment_procedure_uuid
                == new_treatment_mapping.treatment_procedure_uuid
            )
        elif new_treatment_mapping.reimbursement_request_id:
            query = query.filter(
                AccumulationTreatmentMapping.reimbursement_request_id
                == new_treatment_mapping.reimbursement_request_id
            )

        mapping = query.order_by(AccumulationTreatmentMapping.created_at.desc()).first()

        if not mapping or not mapping.accumulation_unique_id:
            log.error(
                "Mapping is marked as reversal, but no original AccumulationTreatmentMapping unique_id is found",
                new_treatment_mapping=new_treatment_mapping.id,
            )
            raise ValueError(
                "Mapping is marked as reversal, but no original AccumulationTreatmentMapping unique_id is found"
            )
        return mapping.accumulation_unique_id

    def get_run_datetime(self, length: int = 14) -> str:
        if not (4 <= length <= 20):
            raise ValueError("The length parameter must be between 4 and 20")
        return self.run_time.strftime("%Y%m%d%H%M%S%f")[:length]

    def file_contents_to_dicts(self, file_contents: str) -> List[dict]:
        return []

    def generate_file_contents_from_json(self, report_data: List[dict]) -> io.StringIO:
        return io.StringIO("")

    def get_record_count_from_buffer(self, buffer: io.StringIO) -> int:
        return 0

    @staticmethod
    def get_oop_to_submit(deductible: int, oop_applied: int) -> int:
        return oop_applied

    def _generate_header(self) -> str:
        return ""

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
        return DetailWrapper(unique_id="", line="")

    def _generate_trailer(self, record_count: int, oop_total: int = 0) -> str:
        return ""

    def detail_to_dict(self, detail_line: str) -> dict:
        return {}

    def get_oop_from_row(self, detail_row: dict) -> int:
        return 0
