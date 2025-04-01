import pytest

from payer_accumulator.common import TreatmentAccumulationStatus
from payer_accumulator.edi.x12_file_parser_277ca import X12FileParser277CA
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.pytests.factories import AccumulationTreatmentMappingFactory
from payer_accumulator.pytests.test_files.test_277ca_data import (
    file_contents_277ca,
    parsed_277ca_data,
)


class TestX12FileParser277CA:
    def test_check_and_update_claim_statuses(self):
        # given accumulation treatment mapping for a claim that's data is rejected in the 277 file
        rejected_trace_number = parsed_277ca_data.claims[
            1
        ].claim_status_tracking.referenced_transaction_trace_number
        AccumulationTreatmentMappingFactory.create(
            accumulation_unique_id=rejected_trace_number
        )
        # when we call check_and_update_claim_statuses
        X12FileParser277CA(
            edi_content=file_contents_277ca
        ).check_and_update_claim_statuses(parsed_277ca_data)
        # then the corresponding accumulation treatment mapping is updated
        updated_mapping = AccumulationTreatmentMapping.query.filter(
            AccumulationTreatmentMapping.accumulation_unique_id == rejected_trace_number
        ).first()
        assert (
            updated_mapping.treatment_accumulation_status
            == TreatmentAccumulationStatus.REJECTED
        )

    @pytest.mark.parametrize(
        "claim_status_code, expected_result",
        [
            ("A0", TreatmentAccumulationStatus.SUBMITTED),
            ("A1", TreatmentAccumulationStatus.SUBMITTED),
            ("A2", TreatmentAccumulationStatus.SUBMITTED),
            ("A3", TreatmentAccumulationStatus.REJECTED),
            ("A4", TreatmentAccumulationStatus.REJECTED),
            ("A6", TreatmentAccumulationStatus.REJECTED),
        ],
    )
    def test_get_treatment_accumulation_status_from_claim_status(
        self, claim_status_code, expected_result
    ):
        assert (
            X12FileParser277CA(
                edi_content=file_contents_277ca
            ).get_treatment_accumulation_status_from_claim_status(claim_status_code)
            == expected_result
        )
