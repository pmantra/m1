import os
from unittest import mock

import pytest

from payer_accumulator.common import PayerName, TreatmentAccumulationStatus
from payer_accumulator.file_generators.csv.bcbs_ma import (
    AccumulationCSVFileGeneratorBCBSMA,
)
from payer_accumulator.pytests.factories import AccumulationTreatmentMappingFactory
from payer_accumulator.tasks.rq_payer_accumulation_csv_response_processing import (
    AccumulationCSVResponseProcessingJob,
)


def read_test_file_contents(test_file_name: str) -> str:
    """Read contents of a test file.

    Args:
        test_file_name: Name of the test file to read

    Returns:
        Contents of the test file as a string
    """
    file_path = os.path.join(
        os.path.dirname(__file__),
        f"../test_files/{test_file_name}",
    )
    with open(file_path, "r") as file:
        content = file.read()
    return content


class TestAccumulationCSVResponseProcessingJob:
    def test_init_with_csv_generator(self, bcbs_ma_payer) -> None:
        """Test initialization with a CSV file generator."""
        job = AccumulationCSVResponseProcessingJob(payer_name=PayerName.BCBS_MA)
        assert isinstance(job.file_generator, AccumulationCSVFileGeneratorBCBSMA)

    def test_init_with_incompatible_generator(self, anthem_payer) -> None:
        """Test initialization fails with a non-CSV file generator."""
        # Use ANTHEM which is not a CSV-based payer
        with pytest.raises(RuntimeError) as exc_info:
            AccumulationCSVResponseProcessingJob(payer_name=PayerName.ANTHEM)
        assert "must be a CSV file generator" in str(exc_info.value)

    def test_process_accumulation_response_file(
        self, mock_accumulation_file_handler: mock.MagicMock, bcbs_ma_payer
    ) -> None:
        test_file_name = "TEST_RESPONSE_20240101.csv"
        test_file_contents = (
            "MemberID,DateOfService,TypeOfClaim,Notes\n12345,01/01/2024,MEDICAL,"
        )

        # Configure the mock to return our test file contents
        mock_accumulation_file_handler.download_file.return_value = test_file_contents

        with mock.patch(
            "payer_accumulator.tasks.rq_payer_accumulation_csv_response_processing.AccumulationFileHandler",
            return_value=mock_accumulation_file_handler,
        ):
            response_processing_job = AccumulationCSVResponseProcessingJob(
                payer_name=PayerName.BCBS_MA
            )
            total_records = response_processing_job.process_accumulation_response_file(
                test_file_name
            )

            assert total_records == 1  # Only one record in the test file
            assert mock_accumulation_file_handler.download_file.call_count == 1

    def test_process_empty_response_file(
        self,
        mock_accumulation_file_handler: mock.MagicMock,
        bcbs_ma_payer,
    ) -> None:
        """Test processing an empty CSV response file."""
        test_file_name = "empty_response.csv"
        test_file_contents = "MemberID,DateOfService,TypeOfClaim,Notes\n"
        mock_accumulation_file_handler.download_file.return_value = test_file_contents

        with mock.patch(
            "payer_accumulator.tasks.rq_payer_accumulation_csv_response_processing.AccumulationFileHandler",
            return_value=mock_accumulation_file_handler,
        ):
            job = AccumulationCSVResponseProcessingJob(payer_name=PayerName.BCBS_MA)
            result = job.process_accumulation_response_file(test_file_name)
            assert result == 0

    def test_process_accumulation_response_records(
        self,
        bcbs_ma_payer,
    ) -> None:
        """Test processing CSV response records with both accepted and rejected records."""
        records = [
            # Accepted record
            {
                "Status": "Completed",
                "MemberID": "12345",
                "DateOfService": "01/01/2024",
                "TypeOfClaim": "MEDICAL",
                'InNetworkIndividualDeductibleAppliedby"Vendor"': "12.34",
                'InNetworkIndividualOOPAppliedby"Vendor"': "56.78",
                "Type of Claim": "New",
                "Cost Share posted": "Y",
                "Adjustment Needed": "N",
                "Adjustment Reason": "",
                "Reprocess": "N",
                "Cost Share Type": "Ded & OOP",
                "Notes": "Family Ded & OOP fully met // No accumulations remaining",
            },
            # Rejected record
            {
                "Status": "Not Completed",
                "MemberID": "67890",
                "DateOfService": "01/01/2024",
                "TypeOfClaim": "MEDICAL",
                'InNetworkIndividualDeductibleAppliedby"Vendor"': "12.34",
                'InNetworkIndividualOOPAppliedby"Vendor"': "56.78",
                "Type of Claim": "New",
                "Cost Share posted": "Y",
                "Adjustment Needed": "Y",
                "Adjustment Reason": "",
                "Reprocess": "Y",
                "Cost Share Type": "Ded & OOP",
                "Notes": "REJECT: Invalid member ID",
            },
            # Non-response record (should be logged as warning)
            {
                "Status": "Completed",
                "MemberID": "99999",
                "DateOfService": "01/01/2024",
                "TypeOfClaim": "",
                'InNetworkIndividualDeductibleAppliedby"Vendor"': "12.34",
                'InNetworkIndividualOOPAppliedby"Vendor"': "56.78",
                "Type of Claim": "Adjustment",
                "Cost Share posted": "Y",
                "Adjustment Needed": "N",
                "Adjustment Reason": "",
                "Reprocess": "N",
                "Cost Share Type": "Ded & OOP",
                "Notes": "",
            },
        ]

        # Create test mappings in the database
        AccumulationTreatmentMappingFactory.create(
            payer_id=bcbs_ma_payer.id,  # Use the actual payer ID from the fixture
            treatment_procedure_uuid="00000000-0000-0000-0000-000000000001",
            accumulation_unique_id="12345-20240101-1234-5678",
            accumulation_transaction_id="1",
            treatment_accumulation_status=TreatmentAccumulationStatus.SUBMITTED,
        )
        AccumulationTreatmentMappingFactory.create(
            payer_id=bcbs_ma_payer.id,  # Use the actual payer ID from the fixture
            treatment_procedure_uuid="00000000-0000-0000-0000-000000000002",
            accumulation_unique_id="67890-20240101-1234-5678",
            accumulation_transaction_id="2",
            treatment_accumulation_status=TreatmentAccumulationStatus.SUBMITTED,
        )

        response_processing_job = AccumulationCSVResponseProcessingJob(
            payer_name=PayerName.BCBS_MA
        )
        process_stats = response_processing_job.process_accumulation_response_records(
            records
        )

        assert process_stats["total_records"] == 3
        assert process_stats["accepted_update_count"] == 1
        assert process_stats["rejected_update_count"] == 1
        assert process_stats["rejected_record_count"] == 1

    def test_get_detail_metadata(
        self,
        bcbs_ma_payer,
    ) -> None:
        """Test extracting metadata from CSV records."""
        test_cases = [
            # Accepted record
            (
                {
                    "Status": "Completed",
                    "MemberID": "12345",
                    "DateOfService": "01/01/2024",
                    "TypeOfClaim": "MEDICAL",
                    'InNetworkIndividualDeductibleAppliedby"Vendor"': "12.34",
                    'InNetworkIndividualOOPAppliedby"Vendor"': "56.78",
                    "Type of Claim": "New",
                    "Cost Share posted": "Y",
                    "Adjustment Needed": "N",
                    "Adjustment Reason": "",
                    "Reprocess": "N",
                    "Cost Share Type": "Ded & OOP",
                    "Notes": "Family Ded & OOP fully met // No accumulations remaining",
                },
                {
                    "is_response": True,
                    "is_rejection": False,
                    "should_update": False,
                    "member_id": "12345",
                    "unique_id": "12345-20240101-1234-5678",
                    "response_status": "Completed",
                    "response_code": "cost_share_posted: Y<br>adjustment_needed: N<br>adjustment_reason: )<br>reprocess: N<br>cost_share_type: Ded & OOP<br>notes: Family Ded & OOP fully met // No accumulations remaining",
                    "response_reason": "Family Ded & OOP fully met // No accumulations remaining",
                },
            ),
            # Rejected record
            (
                {
                    "Status": "Not Completed",
                    "MemberID": "67890",
                    "DateOfService": "01/01/2024",
                    "TypeOfClaim": "MEDICAL",
                    'InNetworkIndividualDeductibleAppliedby"Vendor"': "12.34",
                    'InNetworkIndividualOOPAppliedby"Vendor"': "56.78",
                    "Type of Claim": "New",
                    "Cost Share posted": "Y",
                    "Adjustment Needed": "Y",
                    "Adjustment Reason": "",
                    "Reprocess": "Y",
                    "Cost Share Type": "Ded & OOP",
                    "Notes": "REJECT: Invalid member ID",
                },
                {
                    "is_response": True,
                    "is_rejection": True,
                    "should_update": True,
                    "member_id": "67890",
                    "unique_id": "67890-20240101-1234-5678",
                    "response_status": "Not Completed",
                    "response_code": "cost_share_posted: Y<br>adjustment_needed: Y<br>adjustment_reason: )<br>reprocess: Y<br>cost_share_type: Ded & OOP<br>notes: REJECT: Invalid member ID",
                    "response_reason": "REJECT: Invalid member ID",
                },
            ),
            # Non-response record
            (
                {
                    "Status": "Completed",
                    "MemberID": "99999",
                    "DateOfService": "01/01/2024",
                    "TypeOfClaim": "",
                    'InNetworkIndividualDeductibleAppliedby"Vendor"': "12.34",
                    'InNetworkIndividualOOPAppliedby"Vendor"': "56.78",
                    "Type of Claim": "Adjustment",
                    "Cost Share posted": "Y",
                    "Adjustment Needed": "N",
                    "Adjustment Reason": "",
                    "Reprocess": "N",
                    "Cost Share Type": "Ded & OOP",
                    "Notes": "",
                },
                {
                    "is_response": False,
                    "is_rejection": False,
                    "should_update": False,
                    "member_id": "99999",
                    "unique_id": "99999-20240101-1234-5678",
                    "response_status": "Completed",
                    "response_code": "cost_share_posted: Y<br>adjustment_needed: N<br>adjustment_reason: )<br>reprocess: N<br>cost_share_type: Ded & OOP<br>notes: ",
                    "response_reason": "",
                },
            ),
        ]

        response_processing_job = AccumulationCSVResponseProcessingJob(
            payer_name=PayerName.BCBS_MA
        )

        for record, expected in test_cases:
            metadata = response_processing_job.file_generator.get_detail_metadata(
                record
            )
            assert metadata.is_response == expected["is_response"]
            assert metadata.is_rejection == expected["is_rejection"]
            assert metadata.should_update == expected["should_update"]
            assert metadata.member_id == expected["member_id"]
            assert metadata.unique_id == expected["unique_id"]
            assert metadata.response_status == expected["response_status"]
            assert metadata.response_code == expected["response_code"]
            assert metadata.response_reason == expected["response_reason"]

    def test_fuzzy_get_exact_match(self, bcbs_ma_payer):
        dict_obj = {"MemberID": "12345", "DateOfService": "01/01/2024"}
        search_key = "MemberID"
        result = AccumulationCSVFileGeneratorBCBSMA().fuzzy_get(dict_obj, search_key)
        assert result == "12345"

    def test_fuzzy_get_close_match(self, bcbs_ma_payer):
        dict_obj = {"MemberID": "12345", "DateOfService": "01/01/2024"}
        search_key = "Member Id"  # Close match to "MemberID"
        result = AccumulationCSVFileGeneratorBCBSMA().fuzzy_get(dict_obj, search_key)
        assert result == "12345"

    def test_fuzzy_get_substring_match(self, bcbs_ma_payer):
        dict_obj = {
            "Type of Claim (New/Reversal/Adjustment)": "Adjustment",
            "DateOfService": "01/01/2024",
        }
        search_key = "Type of Claim"
        result = AccumulationCSVFileGeneratorBCBSMA().fuzzy_get(dict_obj, search_key)
        assert result == "Adjustment"

    def test_fuzzy_get_no_match(self, bcbs_ma_payer):
        dict_obj = {"MemberID": "12345", "DateOfService": "01/01/2024"}
        search_key = "InvalidKey"
        result = AccumulationCSVFileGeneratorBCBSMA().fuzzy_get(dict_obj, search_key)
        assert result == ""
