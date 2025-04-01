import datetime
import os
from io import StringIO
from unittest.mock import ANY

import factory
import pytest

from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from payer_accumulator.common import PayerName, TreatmentAccumulationStatus
from payer_accumulator.errors import NoMemberHealthPlanError
from payer_accumulator.file_generators import AccumulationFileGeneratorUHC
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.models.payer_accumulation_reporting import (
    PayerAccumulationReports,
    PayerReportStatus,
)
from payer_accumulator.pytests.factories import (
    AccumulationTreatmentMappingFactory,
    PayerFactory,
)
from wallet.models.constants import WalletState
from wallet.pytests.factories import (
    EmployerHealthPlanFactory,
    MemberHealthPlanFactory,
    ReimbursementOrganizationSettingsFactory,
    ReimbursementWalletFactory,
)


@pytest.fixture(scope="function")
def cost_breakdown_mr_100():
    return CostBreakdownFactory.create(deductible=10000, oop_applied=10000)


@pytest.fixture(scope="function")
def cost_breakdown_mr_100_for_reversal():
    return CostBreakdownFactory.create(deductible=10000, oop_applied=10000)


@pytest.fixture(scope="function")
def cost_breakdown_mr_0():
    return CostBreakdownFactory.create(deductible=0, oop_applied=0)


@pytest.fixture(scope="function")
def treatment_procedures(
    member_health_plans,
    cost_breakdown_mr_100,
    cost_breakdown_mr_0,
    cost_breakdown_mr_100_for_reversal,
):
    return [
        TreatmentProcedureFactory.create(
            id=1001,
            start_date=datetime.datetime(2023, 2, 15),
            end_date=datetime.datetime(2023, 3, 15),
            member_id=1,
            reimbursement_wallet_id=5,
            cost_breakdown_id=cost_breakdown_mr_100.id,
            procedure_type=TreatmentProcedureType.MEDICAL,
        ),
        TreatmentProcedureFactory.create(
            id=1002,
            start_date=datetime.datetime(2023, 7, 1),
            end_date=datetime.datetime(2023, 7, 15),
            member_id=1,
            reimbursement_wallet_id=5,
            cost_breakdown_id=cost_breakdown_mr_0.id,
            procedure_type=TreatmentProcedureType.MEDICAL,
        ),
        TreatmentProcedureFactory.create(
            id=1003,
            start_date=datetime.datetime(2023, 9, 1),
            end_date=datetime.datetime(2023, 10, 1),
            member_id=1,
            reimbursement_wallet_id=5,
            procedure_type=TreatmentProcedureType.PHARMACY,
        ),
        TreatmentProcedureFactory.create(
            id=1004,
            start_date=datetime.datetime(2023, 2, 15),
            end_date=datetime.datetime(2023, 3, 15),
            member_id=1,
            reimbursement_wallet_id=5,
            cost_breakdown_id=cost_breakdown_mr_100_for_reversal.id,
            procedure_type=TreatmentProcedureType.MEDICAL,
        ),
    ]


@pytest.fixture(scope="function")
def accumulation_treatment_mappings(uhc_file_generator, treatment_procedures):
    return AccumulationTreatmentMappingFactory.create_batch(
        size=4,
        payer_id=uhc_file_generator.payer_id,
        treatment_procedure_uuid=factory.Iterator(
            [
                treatment_procedures[0].uuid,
                treatment_procedures[1].uuid,
                treatment_procedures[2].uuid,
                treatment_procedures[3].uuid,
            ]
        ),
        treatment_accumulation_status=factory.Iterator(
            [
                TreatmentAccumulationStatus.PAID,
                TreatmentAccumulationStatus.PAID,
                TreatmentAccumulationStatus.WAITING,
                TreatmentAccumulationStatus.REFUNDED,
            ]
        ),
        created_at=factory.Iterator(
            [
                datetime.datetime(2023, 1, 1, 12, 10, 1),
                datetime.datetime(2023, 1, 1, 12, 10, 2),
                datetime.datetime(2023, 1, 1, 12, 10, 3),
                datetime.datetime(2023, 1, 1, 12, 10, 4),
            ]
        ),
        deductible=factory.Iterator([None, None, None, -10000]),
        oop_applied=factory.Iterator([None, None, None, -10000]),
    )


@pytest.fixture(scope="function")
def uhc_payer():
    return PayerFactory.create(id=1, payer_name=PayerName.UHC, payer_code="00192")


@pytest.fixture(scope="function")
def expected_header():
    return {
        "record_code": "0",
        "sender_id": "MAVEN" + " " * 5,
        "processor_name": "Maven" + " " * 15,
        "processor_address": "160 Varick St 6th Fl",
        "processor_city": "New York" + " " * 10,
        "processor_state": "NY",
        "processor_zip": "10013" + " " * 4,
        "processor_phone": "2124571790",
        "receiver_id": "UHG" + " " * 7,
        "run_date": "20231024",
        "run_time": "13:20:09",
        "file_content_type": "T",
        "version_number": "001",
        "filler": " " * 480,
    }


@pytest.fixture(scope="function")
def expected_detail():
    return {
        "record_code": "4",
        "batch_number": "23297",
        "transaction_id": "20231024132009000001",
        "record_type_code": "2",
        "carrier_number": "123456" + " " * 2,
        "adjustment_type": "1",
        "adjustment_code": " " * 2,
        "adjustment_reason_code": " " * 3,
        "group_id": " " * 16,
        "service_reference_number": " " * 9,
        "fill_number": "00",
        "adjudication_date": "20231024",
        "first_date_of_service": "20230215",
        "last_date_of_service": "20230215",
        "cardholder_id": "U1234567801" + " " * 9,
        "cardholder_id_qualifier": "99",
        "patient_id": " " * 20,
        "patient_first_name": "alice" + " " * 20,
        "patient_middle_name": " " * 25,
        "patient_last_name": "paul" + " " * 31,
        "patient_gender": "2",
        "patient_dob": "20000101",
        "patient_relationship_code": "1",
        "service_provider_id_qualifier": " " * 2,
        "service_provider_id": " " * 10,
        "pharmacy_chain": " " * 4,
        "provider_name": " " * 35,
        "provider_address": " " * 55,
        "provider_city": " " * 30,
        "provider_state": " " * 2,
        "provider_zip": " " * 15,
        "provider_phone_number": " " * 10,
        "provider_tax_id_number": " " * 9,
        "pharmacy_county_code": " " * 3,
        "pharmacy_class_code": " ",
        "in_or_out_network_indicator": "I",
        "client_amount_due": "0000000{",
        "other_payer_amount_paid": "0000000{",
        "copay_coinsurance": "0000000{",
        "deductible_apply_amount": "0001000{",
        "deductible_total_accumulated_amount": "000000000{",
        "deductible_remaining_amount": "000000000{",
        "oop_apply_amount": "0001000{",
        "oop_total_accumulated_amount": "000000000{",
        "oop_remaining_amount": "000000000{",
        "plan_year": "20230215",
        "subscriber_last_name": " " * 35,
        "type_of_benefit_ind": " ",
        "filler": " " * 70,
    }


@pytest.fixture
def uhc_structured_detail_row_snippet():
    return {
        "record_code": "4",
        "patient_dob": "20000101",
        "cardholder_id": "U1234567801",
        "deductible_apply_amount": "0000010{",
        "oop_apply_amount": "0000010{",
    }


@pytest.fixture(scope="function")
def expected_trailer():
    return {
        "record_code": "8",
        "sender_id": "MAVEN" + " " * 5,
        "transaction_count": "0" * 9 + "9",
        "total_record_count": "0" * 8 + "11",
        "filler": " " * 569,
    }


class TestAccumulationFileGeneratorUHC:
    def test_generate_header(self, uhc_file_generator, expected_header):
        header = uhc_file_generator._generate_header()
        for index, value in enumerate(uhc_file_generator.header_config.values()):
            start_pos = value["start_pos"] - 1
            end_pos = value["end_pos"]
            assert header[start_pos:end_pos] == list(expected_header.values())[index]

    def test_generate_detail(
        self,
        uhc_file_generator,
        treatment_procedures,
        cost_breakdown_mr_100,
        member_health_plans,
        expected_detail,
    ):
        treatment_procedure = treatment_procedures[0]
        member_health_plan = member_health_plans[0]
        detail_wrapper = uhc_file_generator._generate_detail(
            record_id=treatment_procedure.id,
            record_type=TreatmentProcedureType(treatment_procedure.procedure_type),
            cost_breakdown=cost_breakdown_mr_100,
            service_start_date=datetime.datetime.combine(
                treatment_procedure.start_date, datetime.time.min
            ),
            deductible=10000,
            oop_applied=10000,
            hra_applied=0,
            member_health_plan=member_health_plan,
        )
        detail = detail_wrapper.line
        for index, value in enumerate(uhc_file_generator.detail_config.values()):
            start_pos = value["start_pos"] - 1
            end_pos = value["end_pos"]
            assert detail[start_pos:end_pos] == list(expected_detail.values())[index]

    def test_get_record_count_from_buffer(
        self,
        uhc_file_generator,
    ):
        # given
        acc_file = "header_row\r\ndetail_row_one\r\ndetail_row_two\r\ntrailer_row\r\n"
        buffer = StringIO(acc_file)
        # when
        record_count = uhc_file_generator.get_record_count_from_buffer(buffer=buffer)
        expected_record_count = 2
        # then
        assert record_count == expected_record_count

    def test_generate_detail_from_reimbursement_request(
        self,
        uhc_file_generator,
        uhc_payer,
        make_new_reimbursement_request_for_report_row,
        make_treatment_procedure_equivalent_to_reimbursement_request,
    ):
        reimbursement_request = make_new_reimbursement_request_for_report_row()
        member_health_plan = reimbursement_request.wallet.member_health_plan[0]

        detail = uhc_file_generator.detail_to_dict(
            uhc_file_generator._generate_detail(
                record_id=reimbursement_request.id,
                record_type=TreatmentProcedureType.MEDICAL,
                cost_breakdown=None,
                service_start_date=reimbursement_request.service_start_date,
                member_health_plan=member_health_plan,
                deductible=200,
                oop_applied=300,
                hra_applied=0,
            ).line
        )
        (
            treatment_procedure,
            cost_breakdown,
        ) = make_treatment_procedure_equivalent_to_reimbursement_request(
            reimbursement_request=reimbursement_request,
            record_type=TreatmentProcedureType.MEDICAL,
            deductible_apply_amount=200,
            oop_apply_amount=300,
        )
        procedure_detail = uhc_file_generator.detail_to_dict(
            uhc_file_generator._generate_detail(
                record_id=treatment_procedure.id,
                record_type=TreatmentProcedureType(treatment_procedure.procedure_type),
                cost_breakdown=cost_breakdown,
                service_start_date=datetime.datetime.combine(
                    treatment_procedure.start_date, datetime.time.min
                ),
                deductible=200,
                oop_applied=300,
                hra_applied=0,
                member_health_plan=member_health_plan,
            ).line
        )
        # keys that should not match here:
        procedure_detail["transaction_id"] = ANY
        procedure_detail["in_or_out_network_indicator"] = "I"
        # assert for all keys that should match
        assert detail == procedure_detail

    def test_generate_trailer(self, uhc_file_generator, expected_trailer):
        trailer = uhc_file_generator._generate_trailer(9)
        for index, value in enumerate(uhc_file_generator.trailer_config.values()):
            start_pos = value["start_pos"] - 1
            end_pos = value["end_pos"]
            assert trailer[start_pos:end_pos] == list(expected_trailer.values())[index]

    def test_file_name(self, uhc_file_generator):
        file_name = uhc_file_generator.file_name
        file_name_component = file_name.split("_")
        assert len(file_name_component) == 6
        assert file_name_component[0] == "Maven"
        assert file_name_component[1] == uhc_file_generator.payer_name.name
        assert file_name_component[2] == "Accumulator"
        assert file_name_component[3] == "File"
        assert file_name_component[4] == "20231024"
        assert file_name_component[5] == "132009"

    def test_get_run_date(self, uhc_file_generator):
        assert uhc_file_generator.get_run_date() == "20231024"

    def test_get_run_time(self, uhc_file_generator):
        assert (
            uhc_file_generator._get_header_required_fields()["run_time"] == "13:20:09"
        )

    def test_get_batch_number(self, uhc_file_generator):
        assert uhc_file_generator.get_batch_number() == "23297"

    def test_get_record_type_code(self):
        assert (
            AccumulationFileGeneratorUHC.get_record_type_code(
                TreatmentProcedureType.PHARMACY
            )
            == "1"
        )
        assert (
            AccumulationFileGeneratorUHC.get_record_type_code(
                TreatmentProcedureType.MEDICAL
            )
            == "2"
        )

    def test_get_patient_gender(self, uhc_file_generator, member_health_plans):
        assert uhc_file_generator.get_patient_gender(member_health_plans[0]) == "2"
        assert uhc_file_generator.get_patient_gender(member_health_plans[1]) == "1"
        assert uhc_file_generator.get_patient_gender(member_health_plans[2]) == "0"

    def test_get_patient_relationship_code(
        self, uhc_file_generator, member_health_plans
    ):
        assert (
            uhc_file_generator.get_patient_relationship_code(member_health_plans[0])
            == "1"
        )
        assert (
            uhc_file_generator.get_patient_relationship_code(member_health_plans[1])
            == "2"
        )
        assert (
            uhc_file_generator.get_patient_relationship_code(member_health_plans[2])
            == "3"
        )

    def test_add_signed_overpunch_success(self, uhc_file_generator):
        assert uhc_file_generator.add_signed_overpunch(0) == "00{"  # 0
        assert uhc_file_generator.add_signed_overpunch(50) == "05{"  # 0.50
        assert uhc_file_generator.add_signed_overpunch(15292) == "1529B"  # 152.92
        assert uhc_file_generator.add_signed_overpunch(1181) == "118A"  # 11.81
        assert uhc_file_generator.add_signed_overpunch(1000) == "100{"  # 10.00

    def test_add_signed_overpunch_failure(self, uhc_file_generator):
        with pytest.raises(Exception) as error:
            uhc_file_generator.add_signed_overpunch(100000000)
            assert (
                error.value
                == "Dollar amount larger than 999999.99 is not supported in the UHC accumulator"
            )

    def test_save_new_accumulation_report(self, uhc_file_generator):
        expected_filename = "Maven_UHC_Accumulator_File_20231024_132009"
        uhc_file_generator.create_new_accumulation_report(
            payer_id=uhc_file_generator.payer_id,
            file_name=uhc_file_generator.file_name,
            run_time=uhc_file_generator.run_time,
        )
        report = PayerAccumulationReports.query.filter_by(
            filename=expected_filename
        ).one_or_none()
        assert report is not None
        assert report.payer_id == uhc_file_generator.payer_id
        assert report.filename == expected_filename
        assert str(report.report_date) == "2023-10-24"
        assert report.status == PayerReportStatus.NEW
        assert report.id is not None

    def test_generate_detail_by_treatment_procedure_returns_non_empty_detail(
        self,
        uhc_file_generator,
        treatment_procedures,
        expected_detail,
        cost_breakdown_mr_100,
    ):
        detail_wrapper = uhc_file_generator._generate_detail_by_treatment_procedure(
            treatment_procedures[0],
            sequence_number=1,
            deductible=10000,
            oop_applied=10000,
            cost_breakdown=cost_breakdown_mr_100,
        )
        detail = detail_wrapper.line
        for index, value in enumerate(uhc_file_generator.detail_config.values()):
            start_pos = value["start_pos"] - 1
            end_pos = value["end_pos"]
            assert detail[start_pos:end_pos] == list(expected_detail.values())[index]

    def test_generate_detail_by_treatment_procedure_failure(
        self, uhc_file_generator, cost_breakdown_mr_100
    ):
        treatment_procedure = TreatmentProcedureFactory.create(
            cost_breakdown_id=cost_breakdown_mr_100.id
        )

        with pytest.raises(NoMemberHealthPlanError) as error:
            uhc_file_generator._generate_detail_by_treatment_procedure(
                treatment_procedure,
                sequence_number=1,
                deductible=cost_breakdown_mr_100.deductible,
                oop_applied=cost_breakdown_mr_100.oop_applied,
                cost_breakdown=cost_breakdown_mr_100,
            )
        assert str(error.value) == "No member health plan"

        org_settings = ReimbursementOrganizationSettingsFactory.create(
            id=9999,
            organization_id=9999,
            deductible_accumulation_enabled=True,
        )
        employer_health_plan = EmployerHealthPlanFactory.create(
            id=9999,
            reimbursement_org_settings_id=org_settings.id,
            reimbursement_organization_settings=org_settings,
        )
        wallet = ReimbursementWalletFactory.create(id=9999, state=WalletState.QUALIFIED)
        MemberHealthPlanFactory.create(
            employer_health_plan=employer_health_plan,
            member_id=treatment_procedure.member_id,
            reimbursement_wallet=wallet,
        )

    def test_generate_file(
        self, uhc_file_generator, treatment_procedures, accumulation_treatment_mappings
    ):
        file = uhc_file_generator.generate_file_contents()
        rows = file.getvalue().split("\r\n")
        sample_file_path = os.path.join(
            os.path.dirname(__file__), f"../test_files/{uhc_file_generator.file_name}"
        )
        with open(sample_file_path, "r") as reader:
            content = reader.read()
            sample_rows = content.split("\n")
            assert len(rows) == len(sample_rows)
            for _, (row, expected_row) in enumerate(zip(rows, sample_rows)):
                assert row == expected_row

        payer_accumulation_report = PayerAccumulationReports.query.filter_by(
            filename=uhc_file_generator.file_name
        ).one()
        updated_accumulation_treatment_mapping = (
            AccumulationTreatmentMapping.query.filter_by(
                id=accumulation_treatment_mappings[0].id
            ).one()
        )
        assert (
            updated_accumulation_treatment_mapping.treatment_accumulation_status
            == TreatmentAccumulationStatus.PROCESSED
        )
        assert (
            updated_accumulation_treatment_mapping.report_id
            == payer_accumulation_report.id
        )

    def test_get_cardholder_id_from_detail_dict(
        self, uhc_file_generator, uhc_structured_detail_row_snippet
    ):
        assert (
            uhc_file_generator.get_cardholder_id_from_detail_dict(
                detail_row_dict=uhc_structured_detail_row_snippet
            )
            == "U1234567801"
        )

    def test_get_dob_from_report_row(
        self, uhc_file_generator, uhc_structured_detail_row_snippet
    ):
        assert uhc_file_generator.get_dob_from_report_row(
            detail_row_dict=uhc_structured_detail_row_snippet
        ) == datetime.date(2000, 1, 1)
