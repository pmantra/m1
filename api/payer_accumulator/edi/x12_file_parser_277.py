from typing import List, Optional

from payer_accumulator.common import TreatmentAccumulationStatus
from payer_accumulator.edi.constants import (
    INSURED_OR_SUBSCRIBER_ENTITY_ID,
    AcceptedClaimStatusCategoryCodes,
    RejectedClaimStatusCategoryCodes,
    SchemaType,
    Segments,
)
from payer_accumulator.edi.models.segments import (
    ClaimData,
    ClaimLevelStatusInformation,
    ClaimStatusTrackingInformation,
    InterchangeControlHeader,
    TransactionSetHeader,
    X12Data277,
)
from payer_accumulator.edi.x12_file_parser import X12FileParser
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class X12FileParser277(X12FileParser):
    def get_data(self) -> Optional[X12Data277]:
        data = X12Data277(interchange_control_header=None, transaction_set_header=None)
        claim_data = ClaimData(claim_status_tracking=None, claim_level_status=None)
        segments = self.extract_segments()

        for segment in segments:
            segment_id = segment["segment_id"]
            elements = segment["elements"]

            # Header values
            if segment_id == Segments.INTERCHANGE_CONTROL_HEADER.value:
                data.interchange_control_header = self._get_interchange_control_header(
                    elements
                )
                # we will need to use element separators to parse later sections of the file
                self.component_element_separator = (
                    data.interchange_control_header.component_element_separator
                )
                self.repetition_separator = (
                    data.interchange_control_header.repetition_separator
                )

            elif segment_id == Segments.TRANSACTION_SET_HEADER.value:
                data.transaction_set_header = self._get_transaction_set_header(elements)
                if (
                    data.transaction_set_header.transaction_set_identifier_code
                    != SchemaType.EDI_277.value
                ):
                    log.error(
                        "EDI file is not 277",
                        transaction_set_identifier_code=data.transaction_set_header.transaction_set_identifier_code,
                    )
                    return None
            # Start individual claim information
            elif segment_id == Segments.INDIVIDUAL_OR_ORGANIZATIONAL_NAME.value:
                # if NM1 element 0 is IL, we have a subscriber, which means we are starting a new claim section
                # we don't need any other NM1 data
                if elements[0] == INSURED_OR_SUBSCRIBER_ENTITY_ID and (
                    claim_data.claim_status_tracking or claim_data.claim_level_status
                ):
                    # if claim_data has claim_status_tracking or claim_level_status_information, then the last claim was
                    # never appended to "data"
                    data.claims.append(claim_data)
                    claim_data = ClaimData(
                        claim_status_tracking=None, claim_level_status=None
                    )
            elif segment_id == Segments.TRACE.value:
                claim_status_tracking_information = (
                    self._get_claim_status_tracking_information(elements)
                )
                claim_data.claim_status_tracking = claim_status_tracking_information
            elif segment_id == Segments.STATUS_INFORMATION.value:
                claim_level_status_information = (
                    self._get_claim_level_status_information(elements)
                )
                # this is the last part of claims information we need, so we can add it to the overall data structure
                claim_data.claim_level_status = claim_level_status_information
                data.claims.append(claim_data)
                claim_data = ClaimData(
                    claim_status_tracking=None, claim_level_status=None
                )
            elif segment_id == Segments.TRANSACTION_SET_TRAILER.value:
                if claim_data.claim_status_tracking or claim_data.claim_level_status:
                    # if we make it to the footer and claim_data has claim_status_tracking or
                    # claim_level_status_information then the last claim was never appended to "data"
                    data.claims.append(claim_data)
                    claim_data = ClaimData(
                        claim_status_tracking=None, claim_level_status=None
                    )
        return data

    def _get_interchange_control_header(
        self, elements: List[str]
    ) -> InterchangeControlHeader:
        elements = [e.strip() for e in elements]
        return InterchangeControlHeader(*elements)

    def _get_transaction_set_header(self, elements: List[str]) -> TransactionSetHeader:
        elements = [e.strip() for e in elements]
        return TransactionSetHeader(*elements)

    def _get_claim_status_tracking_information(
        self, elements: List[str]
    ) -> ClaimStatusTrackingInformation:
        elements = [e.strip() for e in elements]
        return ClaimStatusTrackingInformation(*elements)

    def _get_claim_level_status_information(
        self, elements: List[str]
    ) -> ClaimLevelStatusInformation:
        elements = [e.strip() for e in elements]
        # claim status is split by the component_element_separator like "XX>XXXX>MSC>RX"
        claim_status_elements = elements.pop(0).split(self.component_element_separator)
        claim_status_fields = ClaimLevelStatusInformation(
            health_care_claim_status_category_code=claim_status_elements[0],
            claim_status_code=claim_status_elements[1],
        )
        return claim_status_fields

    def check_and_update_claim_statuses(self, data: X12Data277) -> None:
        for claim in data.claims:
            if not claim.claim_level_status or not claim.claim_status_tracking:
                log.error(
                    "Claim record in 277 file has incomplete claim data.",
                    claim=claim,
                )
                continue
            claim_status_code = (
                claim.claim_level_status.health_care_claim_status_category_code
            )
            accumulation_unique_id = (
                claim.claim_status_tracking.referenced_transaction_trace_number
            )
            treatment_accumulation_status_from_claim_status = (
                self.get_treatment_accumulation_status_from_claim_status(
                    claim_status_code
                )
            )
            if (
                treatment_accumulation_status_from_claim_status
                == TreatmentAccumulationStatus.ACCEPTED
            ):
                log.info(
                    "Claim record in 277 file has accepted status. Updating treatment accumulation status.",
                    claim_status_code=claim_status_code,
                    accumulation_unique_id=accumulation_unique_id,
                )
                self.set_accumulation_treatment_mapping(
                    accumulation_unique_id, TreatmentAccumulationStatus.ACCEPTED
                )
            elif (
                treatment_accumulation_status_from_claim_status
                == TreatmentAccumulationStatus.REJECTED
            ):
                log.error(
                    "Claim record in 277 file has rejected status. Updating treatment accumulation status.",
                    claim_status_code=claim_status_code,
                    accumulation_unique_id=accumulation_unique_id,
                )
                self.set_accumulation_treatment_mapping(
                    accumulation_unique_id, TreatmentAccumulationStatus.REJECTED
                )
            else:
                log.info(
                    "Claim record in 277 file is neither ACCEPTED nor REJECTED. Not updating treatment accumulation status.",
                    claim_status_code=claim_status_code,
                    accumulation_unique_id=accumulation_unique_id,
                )
        return

    def get_treatment_accumulation_status_from_claim_status(
        self, claim_status_code: str
    ) -> TreatmentAccumulationStatus:
        if claim_status_code in [
            code.value for code in AcceptedClaimStatusCategoryCodes
        ]:
            return TreatmentAccumulationStatus.ACCEPTED
        if claim_status_code in [
            code.value for code in RejectedClaimStatusCategoryCodes
        ]:
            return TreatmentAccumulationStatus.REJECTED
        return TreatmentAccumulationStatus.SUBMITTED

    def set_accumulation_treatment_mapping(
        self,
        referenced_transaction_trace_number: str,
        treatment_accumulation_status: TreatmentAccumulationStatus,
        claim_status_code: Optional[str] = None,
        claim_status_detail_code: Optional[str] = None,
    ) -> None:
        mapping = AccumulationTreatmentMapping.query.filter(
            AccumulationTreatmentMapping.accumulation_unique_id
            == referenced_transaction_trace_number
        ).first()
        if not mapping:
            log.error(
                "AccumulationTreatmentMapping not found for claim",
                accumulation_unique_id=referenced_transaction_trace_number,
            )
            return
        try:
            if claim_status_code or claim_status_detail_code:
                mapping.response_code = (
                    f"{claim_status_code}:{claim_status_detail_code}"
                )
            mapping.treatment_accumulation_status = treatment_accumulation_status
            db.session.commit()
        except Exception as e:
            log.error(
                "Error updating treatment accumulation status",
                accumulation_unique_id=referenced_transaction_trace_number,
                treatment_accumulation_status=treatment_accumulation_status,
                exception=e,
            )
        log.info(
            "Treatment accumulation status updated",
            accumulation_unique_id=referenced_transaction_trace_number,
            treatment_accumulation_status=treatment_accumulation_status,
        )
        return
