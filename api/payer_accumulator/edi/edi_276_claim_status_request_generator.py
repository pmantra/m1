import io
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

import jsonschema
import sqlalchemy

from common.constants import Environment
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
)
from payer_accumulator.common import PayerName, TreatmentAccumulationStatus
from payer_accumulator.edi.constants import BLANK_SPACE, PAYERNAME_MAPPING, SchemaType
from payer_accumulator.edi.errors import (
    EDI276ClaimStatusRequestGeneratorException,
    X12FileWriterException,
)
from payer_accumulator.edi.helper import find_number_of_segments
from payer_accumulator.edi.x12_file_writer import X12FileWriter
from payer_accumulator.errors import NoCriticalAccumulationInfoError
from payer_accumulator.file_generators.accumulation_file_generator import (
    MappingWithDataT,
)
from payer_accumulator.file_generators.accumulation_file_generator_mixin import (
    AccumulationFileGeneratorMixin,
)
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from utils.log import logger
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_wallet import MemberHealthPlan

current_directory = Path(__file__).parent
log = logger(__name__)


class EDI276ClaimStatusRequestFileGenerator(AccumulationFileGeneratorMixin):
    def __init__(
        self,
        payer_name: PayerName,
        session: Optional[sqlalchemy.orm.Session] = None,
    ):
        super().__init__(session=session, payer_name=payer_name)

        file_path = current_directory / "models" / f"{SchemaType.EDI_276.value}.json"
        with open(file_path, "r") as schema_file:
            schema = json.load(schema_file)
        self.x12_file_writer = X12FileWriter(schema=schema)
        self.run_time = datetime.utcnow()
        self.hierarchical_id_number: int = 0

    @property
    def file_name(self) -> str:
        return f"Maven_{self.payer_name.value}_276_status_request_{self.run_time.strftime('%Y%m%d_%H%M%S')}.edi"

    def generate_file_contents(self) -> io.StringIO:
        try:
            log.info(
                "Start generating 276 status tracking file",
                payer_name=self.payer_name,
                run_time=self.run_time,
            )
            data: dict = self._get_file_data()
            if not data:
                log.info(
                    "No rows need to be included in claim status request file",
                    payer_name=self.payer_name,
                    run_time=self.run_time,
                )
                return io.StringIO()
            try:
                jsonschema.validate(instance=data, schema=self.x12_file_writer.schema)
                log.info(
                    "Successfully validated against file schema",
                    payer_name=self.payer_name,
                    file_name=self.file_name,
                    run_time=self.run_time,
                )
            except jsonschema.exceptions.ValidationError as e:
                log.error(
                    "Failed to validate against 276 schema",
                    payer_name=self.payer_name,
                    file_name=self.file_name,
                    run_time=self.run_time,
                    error=str(e),
                    traceback=traceback.format_exc(),
                )
                raise EDI276ClaimStatusRequestGeneratorException(
                    f"Validation error {str(e)}"
                )
            try:
                content: io.StringIO = self.x12_file_writer.generate_x12_file(data)
            except X12FileWriterException as e:
                log.error(
                    "Failed to generate x12 file",
                    payer_name=self.payer_name,
                    file_name=self.file_name,
                    run_time=self.run_time,
                    error=str(e),
                    traceback=traceback.format_exc(),
                )
                raise EDI276ClaimStatusRequestGeneratorException(
                    f"File generation error {str(e)}"
                )
            log.info(
                "Successfully generated 276 status tracking file",
                payer_name=self.payer_name,
                file_name=self.file_name,
                run_time=self.run_time,
            )
        except Exception as e:
            log.error(
                "276 status tracking file is not generated due to some failure",
                payer_name=self.payer_name,
                file_name=self.file_name,
                run_time=self.run_time,
                error=str(e),
                traceback=traceback.format_exc(),
            )
            raise EDI276ClaimStatusRequestGeneratorException(
                "Error running generate_file_contents"
            ) from e
        return content

    def _get_file_data(self) -> dict:
        rows_to_check = (
            self.session.query(
                AccumulationTreatmentMapping, TreatmentProcedure, ReimbursementRequest
            )
            .outerjoin(
                TreatmentProcedure,
                AccumulationTreatmentMapping.treatment_procedure_uuid
                == TreatmentProcedure.uuid,
            )
            .outerjoin(
                ReimbursementRequest,
                AccumulationTreatmentMapping.reimbursement_request_id
                == ReimbursementRequest.id,
            )
            .filter(
                AccumulationTreatmentMapping.treatment_accumulation_status
                == TreatmentAccumulationStatus.SUBMITTED,
                AccumulationTreatmentMapping.payer_id == self.payer_id,
            )
            .order_by(AccumulationTreatmentMapping.created_at)
            .all()
        )
        if len(rows_to_check) == 0:
            return {}

        self.hierarchical_id_number = 4  # claim loop starts from id 4
        unique_file_identifier = "0" + self.run_time.strftime("%y%m%d%H")
        header = dict(
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
                component_element_separator=">",
            ),
            functional_group_header=dict(
                functional_identifier_code="HR",
                application_sender_code="5010",
                application_receiver_code="030240928",
                date=self.run_time.strftime("%Y%m%d"),
                time=self.run_time.strftime("%H%M"),
                group_control_number=unique_file_identifier,
                responsible_agency_code="X",
                version_release_industry_identifier_code="005010X212",
            ),
        )
        transaction_set = dict(
            transaction_set_header=dict(
                transaction_set_identifier_code="276",
                transaction_set_control_number=str(unique_file_identifier),
                version_identifier="005010X212",
            ),
            beginning_of_hierarchical_transaction=dict(
                hierarchical_structure_code="0010",
                transaction_set_purpose_code="13",
                reference_identification=str(unique_file_identifier),
                transaction_set_creation_date=self.run_time.strftime("%Y%m%d"),
                transaction_set_creation_time=self.run_time.strftime("%H%M"),
            ),
            loop_2000A=[
                dict(
                    information_source_level=dict(
                        hierarchical_id_number=1,
                        hierarchical_level_code="20",
                        hierarchical_child_code="1",
                    ),
                    loop_2100A=[
                        dict(
                            payer_name=dict(
                                entity_identifier_code="PR",
                                entity_type_qualifier="2",
                                payer_name=PAYERNAME_MAPPING[self.payer_name].get(
                                    "payer_name"
                                ),
                                identification_code_qualifier="PI",
                                payer_identifier=PAYERNAME_MAPPING[self.payer_name].get(
                                    "payer_identifier"
                                ),
                            )
                        )
                    ],
                    loop_2000B=[
                        dict(
                            information_receiver_level=dict(
                                hierarchical_id_number=2,
                                hierarchical_parent_id_number=1,
                                hierarchical_level_code="21",
                                hierarchical_child_code="1",
                            ),
                            loop_2100B=[
                                dict(
                                    information_receiver_name=dict(
                                        entity_identifier_code="41",
                                        entity_type_qualifier="2",
                                        information_receiver_last_or_organization_name="MAVEN CLINIC CO.",
                                        identification_code_qualifier="46",
                                        information_receiver_identification_number="465747423",
                                    )
                                )
                            ],
                            loop_2000C=[
                                dict(
                                    service_provider_level=dict(
                                        hierarchical_id_number=3,
                                        hierarchical_parent_id_number=2,
                                        hierarchical_level_code="19",
                                        hierarchical_child_code="1",
                                    ),
                                    loop_2100C=[
                                        dict(
                                            provider_name=dict(
                                                entity_identifier_code="1P",
                                                entity_type_qualifier="2",
                                                identification_code_qualifier="XX",
                                                provider_identifier="1326898982",
                                            )
                                        )
                                    ],
                                    loop_2000D=[
                                        self._get_loop_2000d(row)
                                        for row in rows_to_check
                                    ],
                                )
                            ],
                        )
                    ],
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
        trailer = dict(
            functional_group_trailer=dict(
                number_of_transaction_sets_included=1,
                group_control_number=unique_file_identifier,
            ),
            interchange_control_trailer=dict(
                number_of_included_functional_groups=1,
                interchange_control_number=unique_file_identifier,
            ),
        )

        file = {}
        file.update(header)
        file.update(transaction_set)  # type: ignore[arg-type]  # Argument 1 to "update" of "MutableMapping" has incompatible type "dict[str, Collection[Collection[str]]]"; expected "SupportsKeysAndGetItem[str, dict[str, str]]"
        file.update(trailer)  # type: ignore[arg-type] # Argument 1 to "update" of "MutableMapping" has incompatible type "dict[str, dict[str, object]]"; expected "SupportsKeysAndGetItem[str, dict[str, str]]"
        return file

    def _get_loop_2000d(self, mapping: MappingWithDataT) -> dict:
        (
            accumulation_treatment_mapping,
            treatment_procedure,
            reimbursement_request,
        ) = mapping
        if reimbursement_request:
            member_id = reimbursement_request.person_receiving_service_id
            wallet_id = reimbursement_request.reimbursement_wallet_id
            effective_date = reimbursement_request.service_start_date
        elif treatment_procedure:
            member_id = treatment_procedure.member_id
            wallet_id = treatment_procedure.reimbursement_wallet_id
            effective_date = treatment_procedure.start_date  # type: ignore[assignment]
        else:
            raise NoCriticalAccumulationInfoError(
                "No mapping data provided for detail retrieval."
            )

        if member_id is None:
            raise NoCriticalAccumulationInfoError("No member id found")

        member_health_plan: Optional[MemberHealthPlan] = self.get_member_health_plan(
            member_id=member_id, wallet_id=wallet_id, effective_date=effective_date
        )
        if not member_health_plan:
            log.error(
                "Member health plan is missing for treatment_procedure or reimbursement request",
                mapping_id=accumulation_treatment_mapping.id,
            )
            raise NoCriticalAccumulationInfoError("No member health plan")
        data = dict(
            subscriber_level=dict(
                hierarchical_id_number=self.hierarchical_id_number,
                hierarchical_parent_id_number=3,
                hierarchical_level_code="22",
                hierarchical_child_code="0",
            ),
            loop_2100D=[
                dict(
                    subscriber_name=dict(
                        entity_identifier_code="IL",
                        entity_type_qualifier="1",
                        subscriber_last_name=member_health_plan.subscriber_last_name,
                        subscriber_first_name=member_health_plan.subscriber_first_name,
                        identification_code_qualifier="MI",
                        subscriber_identifier=member_health_plan.subscriber_insurance_id,
                    )
                )
            ],
        )
        self.hierarchical_id_number += 1
        if member_health_plan.is_subscriber:
            data.update(
                dict(
                    loop_2200D=[
                        dict(
                            claim_status_tracking_number=dict(
                                trace_type_code="1",
                                current_transaction_trace_number=accumulation_treatment_mapping.accumulation_unique_id,
                            )
                        )
                    ]
                )
            )
        else:
            data.update(
                dict(
                    loop_2000E=[
                        dict(
                            dependent_level=dict(
                                hierarchical_id_number=self.hierarchical_id_number,
                                hierarchical_parent_id_number=self.hierarchical_id_number
                                - 1,
                                hierarchical_level_code="23",
                            ),
                            dependent_demographic_information=dict(
                                date_time_period_format_qualifier="D8",
                                patient_birth_date=member_health_plan.patient_date_of_birth.strftime("%Y%m%d"),  # type: ignore[union-attr] # Item "None" of "date | None" has no attribute "strftime"
                            ),
                            loop_2100E=[
                                dict(
                                    dependent_name=dict(
                                        entity_identifier_code="QC",
                                        entity_type_qualifier="1",
                                        patient_last_name=member_health_plan.subscriber_last_name,
                                        patient_first_name=member_health_plan.subscriber_first_name,
                                    ),
                                )
                            ],
                            loop_2200E=[
                                dict(
                                    claim_status_tracking_number=dict(
                                        trace_type_code="1",
                                        current_transaction_trace_number=accumulation_treatment_mapping.accumulation_unique_id,
                                    ),
                                )
                            ],
                        )
                    ],
                )
            )
            self.hierarchical_id_number += 1
        return data
