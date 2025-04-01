from payer_accumulator.common import TreatmentAccumulationStatus
from payer_accumulator.edi.constants import RejectedClaimStatusCategoryCodes
from payer_accumulator.edi.models.segments import X12Data277
from payer_accumulator.edi.x12_file_parser_277 import X12FileParser277
from utils.log import logger

log = logger(__name__)


class X12FileParser277CA(X12FileParser277):
    def check_and_update_claim_statuses(self, data: X12Data277) -> None:
        for claim in data.claims:
            if not claim.claim_level_status or not claim.claim_status_tracking:
                log.error(
                    "Claim record in 277CA file has incomplete claim data.",
                    claim=claim,
                )
                continue
            claim_status_code = (
                claim.claim_level_status.health_care_claim_status_category_code
            )
            claim_status_detail_code = claim.claim_level_status.claim_status_code
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
                == TreatmentAccumulationStatus.REJECTED
            ):
                log.error(
                    "Claim record in 277CA file has rejected status. Updating treatment accumulation status.",
                    claim_status_code=claim_status_code,
                    claim_status_detail_code=claim_status_detail_code,
                    accumulation_unique_id=accumulation_unique_id,
                )
                self.set_accumulation_treatment_mapping(
                    accumulation_unique_id,
                    TreatmentAccumulationStatus.REJECTED,
                    claim_status_code,
                    claim_status_detail_code,
                )
            else:
                log.info(
                    "Claim record in 277CA file is not REJECTED. Not updating treatment accumulation status.",
                    claim_status_code=claim_status_code,
                    accumulation_unique_id=accumulation_unique_id,
                )
        return

    def get_treatment_accumulation_status_from_claim_status(
        self, claim_status_code: str
    ) -> TreatmentAccumulationStatus:
        if claim_status_code in {
            code.value for code in RejectedClaimStatusCategoryCodes
        }:
            return TreatmentAccumulationStatus.REJECTED
        return TreatmentAccumulationStatus.SUBMITTED
