from io import StringIO

import pytest

from wallet.models.models import AlegeusAccountBalanceUpdate
from wallet.utils.alegeus.edi_processing.process_edi_balance_update import (
    IHEdiFileGenerator,
)

MOCK_SUCCESS_RESPONSE_FILE = """RA,MAVEN_IH_2025_UPDATE_202411082244.mbi,20241108,2,0,1,Maven_Conversion_Results
RH,MVN6e2f186e,98f1ef2575dc7b0982cc45b5c83298,,HRA,,,2,11834.32,0,0,Success.
"""

MOCK_FAILED_RESPONSE_FILE = """RA,MAVEN_IH_2025_UPDATE_202411081927.mbi,20241108,2,1,1,Maven_Conversion_Results
RH,,,,,,,,,,100517,Record fields do not match with template
"""


class TestIHFileGenerator:
    @staticmethod
    def test_file_generation():
        # Given
        row_dicts: list[AlegeusAccountBalanceUpdate] = [
            {
                "employer_id": "id1",
                "employee_id": "MVN123",
                "account_type": "HRA",
                "usd_amount": 123456,
            },
            {
                "employer_id": "id2",
                "employee_id": "MVN123",
                "account_type": "HRA",
                "usd_amount": 654321,
            },
        ]
        ih_file_generator = IHEdiFileGenerator(data=row_dicts)

        # When
        file_content = ih_file_generator.generate_file()

        # Then
        expected_file_content = "IA,2,,Maven_Conversion_Import,Maven_Conversion_Results,Maven_Conversion_Export\r\nIH,,id1,MVN123,2,HRA,123456,0,1\r\nIH,,id2,MVN123,2,HRA,654321,0,1\r\n"

        assert expected_file_content == file_content.getvalue()

    @staticmethod
    def test_file_generation_no_data():
        # Given
        ih_file_generator = IHEdiFileGenerator(data=[])

        # When Then
        with pytest.raises(ValueError, match="No data found to generate file with"):
            ih_file_generator.generate_file()

    @staticmethod
    def test_file_generation_bad_key():
        # Given
        row_dicts: list[AlegeusAccountBalanceUpdate] = [
            {
                "employer_id": "id1",
                "employee_id": "MVN123",
                "account_type": "HRA",
                "usd_amount": 123456,
            },
            {
                "employer_id": "id2",
                "employee_id": "MVN123",
                "account_type": "HRA",
                "amount": 654321,
            },
        ]
        ih_file_generator = IHEdiFileGenerator(data=row_dicts)

        # When Then
        with pytest.raises(KeyError, match="'usd_amount'"):
            ih_file_generator.generate_file()

    @staticmethod
    def test_response_file_parse_success():
        # Given
        buffer = StringIO(MOCK_SUCCESS_RESPONSE_FILE)
        ih_file_generator = IHEdiFileGenerator(data=[])

        # When
        summary = ih_file_generator.parse_response_file(buffer=buffer)

        # Then
        assert summary.success is True
        assert summary.num_failure_rows == 0
        assert summary.file_name == "MAVEN_IH_2025_UPDATE_202411082244.mbi"
        assert len(summary.row_summaries) == 1
        assert summary.row_summaries[0].identifier == (
            "MVN6e2f186e",
            "98f1ef2575dc7b0982cc45b5c83298",
        )
        assert summary.row_summaries[0].response_code == 0
        assert summary.row_summaries[0].message == "Success."

    @staticmethod
    def test_response_file_parse_failure():
        # Given
        buffer = StringIO(MOCK_FAILED_RESPONSE_FILE)
        ih_file_generator = IHEdiFileGenerator(data=[])

        # When
        summary = ih_file_generator.parse_response_file(buffer=buffer)

        # Then
        assert summary.success is False
        assert summary.num_failure_rows == 1
        assert summary.file_name == "MAVEN_IH_2025_UPDATE_202411081927.mbi"
        assert len(summary.row_summaries) == 1
        assert summary.row_summaries[0].identifier == ("", "")
        assert summary.row_summaries[0].response_code == 100517
        assert (
            summary.row_summaries[0].message
            == "Record fields do not match with template"
        )
