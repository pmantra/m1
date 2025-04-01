from unittest.mock import patch

import pytest

from payer_accumulator.common import TreatmentAccumulationStatus
from payer_accumulator.edi.models.segments import ClaimLevelStatusInformation
from payer_accumulator.edi.x12_file_parser_277 import X12FileParser277
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.pytests.factories import AccumulationTreatmentMappingFactory
from payer_accumulator.pytests.test_files.test_277_data import (
    file_contents_277,
    file_contents_277_missing_claim_status,
    parsed_277_data,
    parsed_277_data_missing_claim_status,
)


class TestX12FileParser277:
    def test_get_data(self):
        # given a valid 277 file with claims
        parser = X12FileParser277(edi_content=file_contents_277)
        # when we call get_data
        data = parser.get_data()
        # then the data is formatted as expected
        assert data == parsed_277_data

    def test_get_data__header_not_277(self):
        # given a file with the wrong transaction set identifier code (276)
        file_contents = """ISA*00*          *00*          *01*030240928      *ZZ*AV09311993     *240927*1300*^*00501*007205100*0*T*:~
        GS*HN*030240928*AV01101957*20240927*1300*156441*X*005010X212~
        ST*276*1001*005010X212~"""
        parser = X12FileParser277(edi_content=file_contents)
        # when we call get_data
        data = parser.get_data()
        # then there are no results
        assert not data

    def test_get_data__incomplete_claim_data(self):
        # given a valid 277 file with claims that do not have claim status info
        parser = X12FileParser277(edi_content=file_contents_277_missing_claim_status)
        # when we call get_data
        data = parser.get_data()
        # then the data is formatted as expected
        assert data == parsed_277_data_missing_claim_status

    def test_get_claim_level_status_information(self):
        # given claim level elements
        claim_level_elements = [
            "A1:21",
            "20240927",
            "",
            "8513.88",
            "0",
            "",
            "",
            "",
            "",
            "E0:0",
        ]
        expected_claim_obj = ClaimLevelStatusInformation(
            health_care_claim_status_category_code="A1",
            claim_status_code="21",
        )
        # when we extract claim level information
        parser = X12FileParser277(edi_content=file_contents_277)
        parser.component_element_separator = ":"
        results = parser._get_claim_level_status_information(claim_level_elements)
        # then it is formatted as we would expect
        assert expected_claim_obj == results

    def test_check_and_update_claim_statuses(self):
        # given accumulation treatment mapping for a claim that's data is rejected in the 277 file
        rejected_trace_number = parsed_277_data.claims[
            1
        ].claim_status_tracking.referenced_transaction_trace_number
        AccumulationTreatmentMappingFactory.create(
            accumulation_unique_id=rejected_trace_number
        )
        # when we call check_and_update_claim_statuses
        X12FileParser277(edi_content=file_contents_277).check_and_update_claim_statuses(
            parsed_277_data
        )
        # then the corresponding accumulation treatment mapping is updated
        updated_mapping = AccumulationTreatmentMapping.query.filter(
            AccumulationTreatmentMapping.accumulation_unique_id == rejected_trace_number
        ).first()
        assert (
            updated_mapping.treatment_accumulation_status
            == TreatmentAccumulationStatus.REJECTED
        )

    def test_set_accumulation_treatment_mapping__success(self):
        # given referenced_transaction_trace_number
        mapping = AccumulationTreatmentMappingFactory.create()
        referenced_transaction_trace_number = mapping.accumulation_unique_id
        # when we try to set the accumulation treatment mapping as rejected
        X12FileParser277(
            edi_content=file_contents_277
        ).set_accumulation_treatment_mapping(
            referenced_transaction_trace_number, TreatmentAccumulationStatus.REJECTED
        )
        # then the record's treatment_accumulation_status is updated to REJECTED
        updated_mapping = AccumulationTreatmentMapping.query.filter(
            AccumulationTreatmentMapping.accumulation_unique_id
            == referenced_transaction_trace_number
        ).first()
        assert (
            updated_mapping.treatment_accumulation_status
            == TreatmentAccumulationStatus.REJECTED
        )

    @patch("payer_accumulator.edi.x12_file_parser_277.log.error")
    @patch("payer_accumulator.edi.x12_file_parser_277.db.session.commit")
    def test_set_accumulation_treatment_mapping__mapping_not_found(
        self, mock_commit, mock_log
    ):
        # given referenced_transaction_trace_number that does not exist
        referenced_transaction_trace_number = "000-000-XXX"
        # when we try to set the accumulation treatment mapping as rejected
        X12FileParser277(
            edi_content=file_contents_277
        ).set_accumulation_treatment_mapping(
            referenced_transaction_trace_number, TreatmentAccumulationStatus.REJECTED
        )
        # then commit is not called and error is logged
        mock_commit.assert_not_called()
        mock_log.assert_called_once_with(
            "AccumulationTreatmentMapping not found for claim",
            accumulation_unique_id=referenced_transaction_trace_number,
        )

    @pytest.mark.parametrize(
        "claim_status_code, expected_result",
        [
            ("A2", TreatmentAccumulationStatus.SUBMITTED),
            ("F0", TreatmentAccumulationStatus.ACCEPTED),
            ("F2", TreatmentAccumulationStatus.REJECTED),
            ("F4", TreatmentAccumulationStatus.ACCEPTED),
            ("R14", TreatmentAccumulationStatus.SUBMITTED),
            ("A4", TreatmentAccumulationStatus.REJECTED),
            ("DR03", TreatmentAccumulationStatus.REJECTED),
            ("E0", TreatmentAccumulationStatus.REJECTED),
            ("Invalid Code", TreatmentAccumulationStatus.SUBMITTED),
        ],
    )
    def test_get_treatment_accumulation_status_from_claim_status(
        self, claim_status_code, expected_result
    ):
        assert (
            X12FileParser277(
                edi_content=file_contents_277
            ).get_treatment_accumulation_status_from_claim_status(claim_status_code)
            == expected_result
        )
