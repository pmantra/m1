import json
from unittest import mock

import factory
import pytest

from cost_breakdown.pytests.factories import CostBreakdownFactory
from payer_accumulator.accumulation_report_service import AccumulationReportService
from payer_accumulator.common import PayerName, PayerNameT
from payer_accumulator.file_generators import AccumulationFileGeneratorUHC
from payer_accumulator.file_generators.fixed_width_accumulation_file_generator import (
    FixedWidthAccumulationFileGenerator,
)
from payer_accumulator.pytests.factories import PayerFactory


@pytest.fixture(autouse=True)
def init_payers():
    return PayerFactory.create_batch(
        7,
        payer_name=factory.Iterator(
            [
                PayerName.ANTHEM,
                PayerName.Cigna,
                PayerName.CREDENCE,
                PayerName.ESI,
                PayerName.LUMINARE,
                PayerName.PREMERA,
                PayerName.UHC,
            ]
        ),
        payer_code=factory.Iterator(
            [
                "anthem_code",
                "cigna_code",
                "credence_code",
                "esi_code",
                "luminare_code",
                "premera_code",
                "uhc_code",
            ]
        ),
    )


@pytest.fixture(scope="function")
def uhc_file_generator(uhc_payer):
    return AccumulationFileGeneratorUHC()


@pytest.fixture
def cost_breakdown():
    return CostBreakdownFactory.create(deductible=10000, oop_applied=10000)


@pytest.fixture
def raw_report_data():
    return """0MAVEN     MAVEN CLINIC        123 Broadway Ave    New York          NY10012    6461231234UHG       2023101113:31:40T001                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                
423284123456789123456789  21234567 1                              00202310112023101120231011123456789           99                    Christopher                                       Green                              0198902151                                                                                                                                                                                I0000000{0000000{0000000{0000000{000000000{000000000{0000000{000000000{000000000{20231011                                                                                                          
8MAVEN     1         3                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  
"""


@pytest.fixture
def structured_report_data():
    return [
        {
            "record_code": "0",
            "sender_id": "MAVEN",
            "processor_name": "MAVEN CLINIC",
            "processor_address": "123 Broadway Ave",
            "processor_city": "New York",
            "processor_state": "NY",
            "processor_zip": "10012",
            "processor_phone": "6461231234",
            "receiver_id": "UHG",
            "run_date": "20231011",
            "run_time": "13:31:40",
            "file_content_type": "T",
            "version_number": "001",
            "filler": " ",
        },
        {
            "record_code": "4",
            "batch_number": "23284",
            "transaction_id": "123456789123456789",
            "record_type_code": "2",
            "carrier_number": "1234567",
            "adjustment_type": "1",
            "adjustment_code": " ",
            "adjustment_reason_code": " ",
            "group_id": " ",
            "service_reference_number": " ",
            "fill_number": "00",
            "adjudication_date": "20231011",
            "first_date_of_service": "20231011",
            "last_date_of_service": "20231011",
            "cardholder_id": "123456789",
            "cardholder_id_qualifier": "99",
            "patient_id": " ",
            "patient_first_name": "Christopher",
            "patient_middle_name": " ",
            "patient_last_name": "Green",
            "patient_gender": "0",
            "patient_dob": "19890215",
            "patient_relationship_code": "1",
            "service_provider_id_qualifier": " ",
            "service_provider_id": " ",
            "pharmacy_chain": " ",
            "provider_name": " ",
            "provider_address": " ",
            "provider_city": " ",
            "provider_state": " ",
            "provider_zip": " ",
            "provider_phone_number": " ",
            "provider_tax_id_number": " ",
            "pharmacy_county_code": " ",
            "pharmacy_class_code": " ",
            "in_or_out_network_indicator": "I",
            "client_amount_due": "0000000{",
            "other_payer_amount_paid": "0000000{",
            "copay_coinsurance": "0000000{",
            "deductible_apply_amount": "0000000{",
            "deductible_total_accumulated_amount": "000000000{",
            "deductible_remaining_amount": "000000000{",
            "oop_apply_amount": "0000000{",
            "oop_total_accumulated_amount": "000000000{",
            "oop_remaining_amount": "000000000{",
            "plan_year": "20231011",
            "subscriber_last_name": " ",
            "type_of_benefit_ind": " ",
            "filler": " ",
        },
        {
            "record_code": "8",
            "sender_id": "MAVEN",
            "transaction_count": "1",
            "total_record_count": "3",
            "filler": " ",
        },
    ]


@pytest.fixture
def report_service():
    svc = AccumulationReportService()
    return svc


class TestAccumulationReportService:
    @pytest.mark.parametrize(
        "payer_name",
        ["anthem", "cigna", "credence", "esi", "luminare", "premera", "uhc"],
    )
    def test_get_generator_class_for_payer_name(self, payer_name: PayerNameT):
        res = AccumulationReportService.get_generator_class_for_payer_name(payer_name)
        assert isinstance(res, FixedWidthAccumulationFileGenerator)

    def test_get_generator_class_for_payer_name_fails(self):
        with pytest.raises(ValueError) as e:
            AccumulationReportService.get_generator_class_for_payer_name("not_a_payer")
        assert str(e.value) == "Accumulation File Generator not found."

    def test_get_raw_data(self, report_service):
        with mock.patch.object(
            report_service.file_handler, "download_file"
        ) as expected_call:
            report_service.get_raw_data_for_report(
                report=mock.MagicMock(filename="test_file")
            )
        assert expected_call.called

    def test_get_structured_data_for_report(
        self, report_service, uhc_payer, structured_report_data, raw_report_data
    ):
        report_service.file_handler.download_file = mock.MagicMock(
            return_value=raw_report_data
        )
        res = report_service.get_structured_data_for_report(
            report=mock.MagicMock(payer_id=uhc_payer.id, filename="test_file.txt")
        )
        assert res == structured_report_data

    def test_get_json_for_report(
        self, report_service, uhc_payer, structured_report_data, raw_report_data
    ):
        report_service.file_handler.download_file = mock.MagicMock(
            return_value=raw_report_data
        )
        res = report_service.get_json_for_report(
            report=mock.MagicMock(payer_id=uhc_payer.id, filename="test_file.txt")
        )
        assert res == json.dumps(structured_report_data, indent=4)

    def test_overwrite_report_with_invalid_json(self, report_service, uhc_payer):
        with pytest.raises(ValueError) as e:
            report_service.overwrite_report_with_json(
                report=mock.MagicMock(payer_id=uhc_payer.id, filename="test_file.txt"),
                report_json="invalid_json",
            )
        assert str(e.value) == "Invalid JSON for report generation."

    def test_overwrite_report_with_json(
        self, structured_report_data, uhc_payer, report_service
    ):
        with mock.patch.object(
            report_service.file_handler, "upload_file"
        ) as expected_call:
            structured_report_data[0]["record_code"] = "1"
            new_json = json.dumps(structured_report_data)
            report_service.overwrite_report_with_json(
                report=mock.MagicMock(payer_id=uhc_payer.id, filename="test_file.txt"),
                report_json=new_json,
            )
        assert expected_call.called
