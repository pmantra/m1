import datetime
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
from payer_accumulator.file_generators import AccumulationFileGeneratorLuminare
from payer_accumulator.models.payer_accumulation_reporting import (
    PayerAccumulationReports,
    PayerReportStatus,
)
from payer_accumulator.pytests.factories import (
    AccumulationTreatmentMappingFactory,
    PayerFactory,
)
from pytests.freezegun import freeze_time
from wallet.models.constants import WalletState
from wallet.pytests.factories import (
    EmployerHealthPlanFactory,
    MemberHealthPlanFactory,
    ReimbursementOrganizationSettingsFactory,
    ReimbursementWalletFactory,
)


@pytest.fixture(scope="function")
def cost_breakdown_mr_100():
    return CostBreakdownFactory.create(
        deductible=10000,
        oop_applied=10000,
        calc_config='{"tier": 1}',
    )


@pytest.fixture(scope="function")
def cost_breakdown_mr_0():
    return CostBreakdownFactory.create(
        deductible=0, oop_applied=0, calc_config='{"tier": 1}'
    )


@pytest.fixture(scope="function")
def treatment_procedures(
    member_health_plans, cost_breakdown_mr_100, cost_breakdown_mr_0
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
    ]


@pytest.fixture(scope="function")
def accumulation_treatment_mappings(luminare_file_generator, treatment_procedures):
    return AccumulationTreatmentMappingFactory.create_batch(
        size=4,
        payer_id=luminare_file_generator.payer_id,
        treatment_procedure_uuid=factory.Iterator(
            [
                treatment_procedures[0].uuid,
                treatment_procedures[1].uuid,
                treatment_procedures[2].uuid,
                treatment_procedures[0].uuid,
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
        deductible=factory.Iterator([None, None, None, -10000]),
        oop_applied=factory.Iterator([None, None, None, -10000]),
    )


@pytest.fixture(scope="function")
def luminare_payer():
    return PayerFactory.create(id=1, payer_name=PayerName.LUMINARE, payer_code="12345")


@pytest.fixture(scope="function")
@freeze_time("2023-11-09 14:08:09")
def luminare_file_generator(luminare_payer):
    return AccumulationFileGeneratorLuminare()


@pytest.fixture(scope="function")
def expected_header():
    return {
        "record_type": "HDR",
        "unique_batch_file_identifier": "23313" + " " * 17,
        "record_response_status_code": " ",
        "reject_code": " " * 3,
        "data_file_sender_id": "MAVEN",
        "data_file_sender_name": "MAVEN" + " " * 10,
        "data_file_receiver_id": "LH" + " " * 3,
        "data_file_receiver_name": "LUMINAREHEALTH" + " ",
        "production_or_test_data": "P",
        "transmission_type": "DQ",
        "file_counter": "000",
        "file_creation_date": "20231109",
        "file_creation_time": "1408090000",
        "processing_period_start_date": "20230101",
        "processing_period_start_time": "1200000000",
        "processing_period_end_date": "20231109",
        "processing_period_end_time": "1159590000",
        "filler": " " * 291,
    }


@pytest.fixture(scope="function")
def expected_detail():
    return {
        "record_type": "DTL",
        "unique_record_identifier": "100120231109140809" + " " * 32,
        "claim_source": "P",
        "transmission_type": "DQ",
        "record_response_status_code": " ",
        "production_or_test_data": "P",
        "record_counter": "000",
        "claim_reject_code": " " * 3,
        "data_file_sender_id": "MAVEN",
        "data_file_sender_name": "MAVEN" + " " * 10,
        "data_file_receiver_id": "LH" + " " * 3,
        "data_file_receiver_name": "LUMINAREHEALTH" + " ",
        "client_id_name": "OhioHealthy" + " " * 19,
        "patient_id": "U1234567801" + " " * 9,
        "patient_date_of_birth": "20000101",
        "patient_first_name": "alice" + " " * 10,
        "patient_middle_initial": " ",
        "patient_last_name": "paul" + " " * 16,
        "patient_gender": "F",
        "patient_relationship_code": "1",
        "carrier_number": "123456" + " " * 9,
        "participant_account_number": " " * 15,
        "group_number": "123456" + " " * 9,
        "claim_id": "1001" + " " * 21,
        "claim_sequence_number": "001",
        "claim_transaction_type": "P",
        "claim_date_of_service": "20230215",
        "claim_post_date": "20230215",
        "claim_post_time": "0000000000",
        "dollars_or_flag_indicator": "D",
        "deductible_amount_sign": "+",
        "deductible_amount": "0000010000",
        "total_medical_and_pharmacy_deductible_sign": "+",
        "total_medical_and_pharmacy_deductible": "0000000000",
        "patient_pay_excluding_deductible_amount_sign": "+",
        "patient_pay_excluding_deductible_amount": "0000000000",
        "out_of_pocket_amount_sign": "+",
        "out_of_pocket_amount": "0000010000",
        "total_medical_and_pharmacy_member_oop_sign": "+",
        "total_medical_and_pharmacy_member_oop": "0000000000",
        "sponsor_plan_paid_amount_sign": "+",
        "sponsor_plan_paid_amount": "0000000000",
        "participant_deductible_flag_met": "N",
        "family_deductible_flag_met": "N",
        "participant_oop_flag_met": "N",
        "family_oop_flag_met": "N",
        "plan_benefit_begin_date": " " * 8,
        "plan_benefit_end_date": " " * 8,
        "network": "1",
        "filler": " " * 32,
    }


@pytest.fixture
def luminare_structured_detail_row_snippet():
    return {
        "patient_date_of_birth": "20000101",
        "patient_id": "U1234567801",
        "deductible_amount_sign": "+",
        "deductible_amount": "0000010000",
        "out_of_pocket_amount_sign": "+",
        "out_of_pocket_amount": "0000010000",
    }


@pytest.fixture(scope="function")
def expected_trailer():
    return {
        "record_type": "TRL",
        "total_oop_amount_sign": "+",
        "total_oop_amount": "000000000100",
        "control_record_count": "00000009",
        "filler": " " * 396,
    }


class TestAccumulationFileGeneratorLuminare:
    def test_generate_header(self, luminare_file_generator, expected_header):
        header = luminare_file_generator._generate_header()
        for index, value in enumerate(luminare_file_generator.header_config.values()):
            start_pos = value["start_pos"] - 1
            end_pos = value["end_pos"]
            assert header[start_pos:end_pos] == list(expected_header.values())[index]

    def test_generate_detail(
        self,
        luminare_file_generator,
        treatment_procedures,
        cost_breakdown_mr_100,
        member_health_plans,
        expected_detail,
    ):
        treatment_procedure = treatment_procedures[0]
        member_health_plan = member_health_plans[0]
        detail_wrapper = luminare_file_generator._generate_detail(
            record_id=treatment_procedure.id,
            record_type=TreatmentProcedureType(treatment_procedure.procedure_type),
            sequence_number=1,
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
        for index, value in enumerate(luminare_file_generator.detail_config.values()):
            start_pos = value["start_pos"] - 1
            end_pos = value["end_pos"]
            assert detail[start_pos:end_pos] == list(expected_detail.values())[index]

    def test_generate_detail_without_calc_config_errors(
        self,
        luminare_file_generator,
        treatment_procedures,
        cost_breakdown_mr_100,
        member_health_plans,
        expected_detail,
    ):
        treatment_procedure = treatment_procedures[0]
        member_health_plan = member_health_plans[0]
        cost_breakdown_mr_100.calc_config = None
        with pytest.raises(Exception) as error:
            luminare_file_generator._generate_detail(
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
            assert (
                str(error.value)
                == f"Missing calc config information in cost breakdown ({cost_breakdown_mr_100.id}) for luminare accumulation on record: {treatment_procedure.id}"
            )

    def test_get_record_count_from_buffer(
        self,
        luminare_file_generator,
    ):
        # given
        acc_file = "header_row\r\ndetail_row_one\r\ndetail_row_two\r\ntrailer_row\r\n"
        buffer = StringIO(acc_file)
        # when
        record_count = luminare_file_generator.get_record_count_from_buffer(
            buffer=buffer
        )
        expected_record_count = 2
        # then
        assert record_count == expected_record_count

    def test_generate_detail_from_reimbursement_request(
        self,
        luminare_file_generator,
        luminare_payer,
        make_new_reimbursement_request_for_report_row,
        cost_breakdown_mr_100,
        make_treatment_procedure_equivalent_to_reimbursement_request,
    ):
        reimbursement_request = make_new_reimbursement_request_for_report_row()
        member_health_plan = reimbursement_request.wallet.member_health_plan[0]

        detail = luminare_file_generator.detail_to_dict(
            luminare_file_generator._generate_detail(
                record_id=reimbursement_request.id,
                record_type=TreatmentProcedureType.MEDICAL,
                sequence_number=1,
                cost_breakdown=cost_breakdown_mr_100,
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
        cost_breakdown.calc_config = '{"tier": 1}'
        procedure_detail = luminare_file_generator.detail_to_dict(
            luminare_file_generator._generate_detail(
                record_id=treatment_procedure.id,
                record_type=TreatmentProcedureType(treatment_procedure.procedure_type),
                sequence_number=1,
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
        procedure_detail["claim_id"] = ANY
        procedure_detail["unique_record_identifier"] = ANY

        # assert for all keys that should match
        assert detail == procedure_detail

    def test_generate_trailer(self, luminare_file_generator, expected_trailer):
        trailer = luminare_file_generator._generate_trailer(9, 100)
        for index, value in enumerate(luminare_file_generator.trailer_config.values()):
            start_pos = value["start_pos"] - 1
            end_pos = value["end_pos"]
            assert trailer[start_pos:end_pos] == list(expected_trailer.values())[index]

    def test_file_name(self, luminare_file_generator):
        file_name = luminare_file_generator.file_name
        file_name_component = file_name.split("_")
        assert len(file_name_component) == 5
        assert file_name_component[0] == "Maven"
        assert file_name_component[1] == "Luminare"
        assert file_name_component[2] == "Accumulator"
        assert file_name_component[3] == "File"
        assert file_name_component[4] == "20231109140809"

    def test_get_run_date(self, luminare_file_generator):
        assert luminare_file_generator.get_run_date() == "20231109"

    def test_get_run_time(self, luminare_file_generator):
        assert luminare_file_generator.get_run_time(length=10) == "1408090000"

    def test_get_batch_number(self, luminare_file_generator):
        assert luminare_file_generator.get_batch_number() == "23313"

    def test_get_patient_gender(self, luminare_file_generator, member_health_plans):
        assert luminare_file_generator.get_patient_gender(member_health_plans[0]) == "F"
        assert luminare_file_generator.get_patient_gender(member_health_plans[1]) == "M"
        assert luminare_file_generator.get_patient_gender(member_health_plans[2]) == "U"

    def test_get_patient_relationship_code(
        self, luminare_file_generator, member_health_plans
    ):
        assert (
            luminare_file_generator.get_patient_relationship_code(
                member_health_plans[0]
            )
            == "1"
        )
        assert (
            luminare_file_generator.get_patient_relationship_code(
                member_health_plans[1]
            )
            == "2"
        )
        assert (
            luminare_file_generator.get_patient_relationship_code(
                member_health_plans[2]
            )
            == "3"
        )

    def test_get_amount_sign(self, luminare_file_generator):
        assert luminare_file_generator.get_amount_sign(0) == "+"
        assert luminare_file_generator.get_amount_sign(50) == "+"
        assert luminare_file_generator.get_amount_sign(-15292) == "-"

    def test_save_new_accumulation_report(self, luminare_file_generator):
        expected_filename = "Maven_Luminare_Accumulator_File_20231109140809"
        luminare_file_generator.create_new_accumulation_report(
            payer_id=luminare_file_generator.payer_id,
            file_name=luminare_file_generator.file_name,
            run_time=luminare_file_generator.run_time,
        )
        report = PayerAccumulationReports.query.filter_by(
            filename=expected_filename
        ).one_or_none()
        assert report is not None
        assert report.payer_id == luminare_file_generator.payer_id
        assert report.filename == expected_filename
        assert str(report.report_date) == "2023-11-09"
        assert report.status == PayerReportStatus.NEW
        assert report.id is not None

    def test_generate_detail_by_treatment_procedure_returns_non_empty_detail(
        self,
        luminare_file_generator,
        treatment_procedures,
        expected_detail,
        cost_breakdown_mr_100,
    ):
        detail_wrapper = (
            luminare_file_generator._generate_detail_by_treatment_procedure(
                treatment_procedures[0],
                sequence_number=1,
                deductible=10000,
                oop_applied=10000,
                cost_breakdown=cost_breakdown_mr_100,
            )
        )
        detail = detail_wrapper.line
        for index, value in enumerate(luminare_file_generator.detail_config.values()):
            start_pos = value["start_pos"] - 1
            end_pos = value["end_pos"]
            assert detail[start_pos:end_pos] == list(expected_detail.values())[index]

    def test_generate_detail_by_treatment_procedure_failure(
        self, luminare_file_generator, cost_breakdown_mr_100
    ):
        treatment_procedure = TreatmentProcedureFactory.create(
            cost_breakdown_id=cost_breakdown_mr_100.id
        )

        with pytest.raises(NoMemberHealthPlanError) as error:
            luminare_file_generator._generate_detail_by_treatment_procedure(
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

    def test_get_cardholder_id_from_detail_dict(
        self, luminare_file_generator, luminare_structured_detail_row_snippet
    ):
        assert (
            luminare_file_generator.get_cardholder_id_from_detail_dict(
                detail_row_dict=luminare_structured_detail_row_snippet
            )
            == "U1234567801"
        )

    def test_get_dob_from_report_row(
        self, luminare_file_generator, luminare_structured_detail_row_snippet
    ):
        assert luminare_file_generator.get_dob_from_report_row(
            detail_row_dict=luminare_structured_detail_row_snippet
        ) == datetime.date(2000, 1, 1)

    def test_update_trailer_oop_amount(
        self,
        luminare_file_generator,
        luminare_structured_detail_row_snippet,
        treatment_procedures,
        cost_breakdown_mr_100,
        member_health_plans,
    ):
        treatment_procedure = treatment_procedures[0]
        member_health_plan = member_health_plans[0]
        detail_wrapper = luminare_file_generator._generate_detail(
            record_id=treatment_procedure.id,
            record_type=TreatmentProcedureType(treatment_procedure.procedure_type),
            sequence_number=1,
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
        header = luminare_file_generator._generate_header()
        trailer = luminare_file_generator._generate_trailer(1, 10000)
        contents = header + detail + trailer
        report_json = luminare_file_generator.file_contents_to_dicts(contents)

        # Update oop in detail row
        report_json[1]["out_of_pocket_amount"] = "7777"
        updated_report = luminare_file_generator.generate_file_contents_from_json(
            report_json
        )
        updated_report.seek(0)
        updated_report_json = luminare_file_generator.file_contents_to_dicts(
            updated_report.read()
        )
        # Detail oop is the correct amount
        assert updated_report_json[1]["out_of_pocket_amount"] == "0000007777"
        assert updated_report_json[1]["out_of_pocket_amount_sign"] == "+"
        assert updated_report_json[2]["total_oop_amount"] == "000000007777"
        assert updated_report_json[2]["total_oop_amount_sign"] == "+"

    @pytest.mark.parametrize(
        argnames="file_name, expected",
        argvalues=[
            ("Maven_Luminare_Accumulator_File_DR_20241015_123456.txt", True),
            ("Maven_RxAccums_20241015123456", False),
            ("Maven_Luminare_Accumulator_File_DR_20241015123456.txt", False),
        ],
    )
    def test_match_response_filename(
        self, luminare_file_generator, file_name, expected
    ):
        result = luminare_file_generator.match_response_filename(file_name)
        assert result == expected

    @pytest.mark.parametrize(
        argnames="file_name, expected",
        argvalues=[
            ("Maven_Luminare_Accumulator_File_DR_20241015_123456.txt", "20241015"),
            ("Maven_RxAccums_20241015123456", None),
            ("Maven_Luminare_Accumulator_File_DR_20241015123456.txt", None),
        ],
    )
    def test_get_response_file_date(self, luminare_file_generator, file_name, expected):
        result = luminare_file_generator.get_response_file_date(file_name)
        assert result == expected

    @pytest.mark.parametrize(
        "sequence_number,expected_sequence",
        [
            (0, "000"),
            (1, "001"),
            (999, "999"),
            (1000, "000"),
            (1001, "001"),
            (1999, "999"),
            (2000, "000"),
            (12345, "345"),
        ],
    )
    def test_sequence_number_wrapping(
        self,
        luminare_file_generator,
        treatment_procedures,
        cost_breakdown_mr_100,
        member_health_plans,
        sequence_number,
        expected_sequence,
    ):
        treatment_procedure = treatment_procedures[0]
        member_health_plan = member_health_plans[0]
        detail_wrapper = luminare_file_generator._generate_detail(
            record_id=treatment_procedure.id,
            record_type=TreatmentProcedureType(treatment_procedure.procedure_type),
            sequence_number=sequence_number,
            cost_breakdown=cost_breakdown_mr_100,
            service_start_date=datetime.datetime.combine(
                treatment_procedure.start_date, datetime.time.min
            ),
            deductible=10000,
            oop_applied=10000,
            hra_applied=0,
            member_health_plan=member_health_plan,
        )
        detail = luminare_file_generator.detail_to_dict(detail_wrapper.line)
        assert detail["claim_sequence_number"] == expected_sequence

    @pytest.mark.parametrize(
        argnames="detail_record, expected_metadata",
        argvalues=[
            (
                # accepted
                {
                    "transmission_type": "DR",
                    "unique_record_identifier": "20241015123456789#cb_1",
                    "record_response_status_code": "S",
                    "claim_reject_code": "",
                    "patient_id": "12345",
                    "patient_first_name": "Stephen",
                    "patient_last_name": "Curry",
                    "patient_date_of_birth": "19880314",
                    "claim_date_of_service": "20241001",
                },
                {
                    "is_response": True,
                    "is_rejection": False,
                    "unique_id": "20241015123456789#cb_1",
                    "response_code": "",
                },
            ),
            (
                # rejected (mapped)
                {
                    "transmission_type": "DR",
                    "unique_record_identifier": "20241015123456789#cb_3",
                    "record_response_status_code": "F",
                    "claim_reject_code": "119",
                    "patient_id": "12345",
                    "patient_first_name": "Stephen",
                    "patient_last_name": "Curry",
                    "patient_date_of_birth": "19880314",
                    "claim_date_of_service": "20241001",
                },
                {
                    "is_response": True,
                    "is_rejection": True,
                    "should_update": True,
                    "unique_id": "20241015123456789#cb_3",
                    "response_code": "119",
                    "response_reason": "PATIENT'S RELATIONSHIP CODE IS NOT VALID",
                },
            ),
            (
                # rejected (unmapped)
                {
                    "transmission_type": "DR",
                    "unique_record_identifier": "20241015123456789#cb_3",
                    "record_response_status_code": "F",
                    "claim_reject_code": "369",
                    "patient_id": "12345",
                    "patient_first_name": "Stephen",
                    "patient_last_name": "Curry",
                    "patient_date_of_birth": "19880314",
                    "claim_date_of_service": "20241001",
                },
                {
                    "is_response": True,
                    "is_rejection": True,
                    "should_update": True,
                    "unique_id": "20241015123456789#cb_3",
                    "response_code": "369",
                    "response_reason": "369",
                },
            ),
        ],
    )
    def test_get_detail_metadata(
        self,
        luminare_file_generator,
        detail_record,
        expected_metadata,
        member_health_plans,
    ):
        member_health_plan = member_health_plans[0]
        member_health_plan.patient_first_name = "Stephen"
        member_health_plan.patient_last_name = "Curry"
        member_health_plan.patient_date_of_birth = datetime.date(1988, 3, 14)
        member_health_plan.subscriber_insurance_id = "12345"
        member_health_plan.plan_start_at = datetime.datetime(2024, 1, 1)
        member_health_plan.plan_end_at = datetime.datetime(2099, 1, 1)
        metadata = luminare_file_generator.get_detail_metadata(detail_record)
        for k, v in expected_metadata.items():
            assert getattr(metadata, k) == v
        assert str(member_health_plan.member_id) == metadata.member_id

    @pytest.mark.parametrize(
        argnames="detail_record, expected_metadata",
        argvalues=[
            (
                # accepted
                {
                    "transmission_type": "DR",
                    "unique_record_identifier": "20241015123456789#cb_1",
                    "record_response_status_code": "S",
                    "claim_reject_code": "",
                    "patient_id": "12345",
                    "patient_first_name": "Stephen",
                    "patient_last_name": "Curry",
                    "patient_date_of_birth": "19880314",
                    "claim_date_of_service": "20241001",
                },
                {
                    "is_response": True,
                    "is_rejection": False,
                    "unique_id": "20241015123456789#cb_1",
                    "response_code": "",
                },
            ),
            (
                # rejected
                {
                    "transmission_type": "DR",
                    "unique_record_identifier": "20241015123456789#cb_3",
                    "record_response_status_code": "F",
                    "claim_reject_code": "102",
                    "patient_id": "12345",
                    "patient_first_name": "Stephen",
                    "patient_last_name": "Curry",
                    "patient_date_of_birth": "19880314",
                    "claim_date_of_service": "20241001",
                },
                {
                    "is_response": True,
                    "is_rejection": True,
                    "should_update": True,
                    "unique_id": "20241015123456789#cb_3",
                    "response_code": "102",
                },
            ),
        ],
    )
    def test_get_detail_metadata_yoy_feature_flag_enabled(
        self,
        luminare_file_generator,
        detail_record,
        expected_metadata,
        member_health_plans,
        mhp_yoy_feature_flag_enabled,
    ):
        member_health_plan = member_health_plans[0]
        member_health_plan.patient_first_name = "Stephen"
        member_health_plan.patient_last_name = "Curry"
        member_health_plan.patient_date_of_birth = datetime.date(1988, 3, 14)
        member_health_plan.subscriber_insurance_id = "12345"
        member_health_plan.plan_start_at = datetime.datetime(2024, 1, 1)
        member_health_plan.plan_end_at = datetime.datetime(2099, 1, 1)
        metadata = luminare_file_generator.get_detail_metadata(detail_record)
        for k, v in expected_metadata.items():
            assert getattr(metadata, k) == v
        assert str(member_health_plan.member_id) == metadata.member_id
