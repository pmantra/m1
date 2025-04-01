import datetime
from datetime import date
from io import StringIO
from unittest.mock import ANY

import pytest

from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from payer_accumulator.common import PayerName
from payer_accumulator.errors import InvalidGroupIdError, InvalidPayerError
from payer_accumulator.file_generators import ESIAccumulationFileGenerator
from payer_accumulator.pytests.factories import PayerFactory
from pytests.factories import HealthProfileFactory
from pytests.freezegun import freeze_time
from wallet.models.constants import (
    MemberHealthPlanPatientRelationship,
    MemberHealthPlanPatientSex,
)
from wallet.pytests.factories import (
    EmployerHealthPlanFactory,
    MemberHealthPlanFactory,
    ReimbursementOrganizationSettingsFactory,
)


@pytest.fixture(scope="function")
def member(enterprise_user):
    HealthProfileFactory.create(
        user=enterprise_user, json={"gender": "Male", "birthday": "2000-01-01"}
    )
    return enterprise_user


@pytest.fixture(scope="function")
def esi_payer():
    return PayerFactory.create(payer_name=PayerName.ESI, payer_code="esi")


@pytest.fixture(scope="function")
@freeze_time("2023-01-01 00:00:00")
def esi_file_generator(esi_payer):
    return ESIAccumulationFileGenerator()


@pytest.fixture(scope="function")
def cost_breakdown():
    return CostBreakdownFactory.create(deductible=10000, oop_applied=20000)


@pytest.fixture(scope="function")
@freeze_time("2023-01-01 00:00:00")
def treatment_procedure(member):
    return TreatmentProcedureFactory.create(
        start_date=date.today(),
        end_date=date.today() + datetime.timedelta(days=1),
        member_id=member.id,
    )


@pytest.fixture(scope="function")
def employer_health_plan(member, esi_payer):
    org_settings = ReimbursementOrganizationSettingsFactory.create(
        organization_id=member.organization.id,
    )
    return EmployerHealthPlanFactory.create(
        reimbursement_organization_settings=org_settings,
        benefits_payer_id=esi_payer.id,
    )


@pytest.fixture(scope="function")
def member_health_plan(employer_health_plan):
    plan = MemberHealthPlanFactory.create(
        employer_health_plan=employer_health_plan,
        patient_sex=MemberHealthPlanPatientSex.MALE,
        patient_relationship=MemberHealthPlanPatientRelationship.CARDHOLDER,
    )
    return plan


@pytest.fixture(scope="function")
def header_report():
    return {
        "processor_routing_identification": " " * 200,
        "record_type": "HD",
        "transmission_type": "T",
        "creation_date": "20230101",
        "creation_time": "0000",
        "sender_id": f'{"MAVN":<30}',
        "receiver_id": f'{"MHS":<30}',
        "batch_number": "1".zfill(7),
        "file_type": "T",
        "version_number": "10",
        "reserved": " " * 1415,
    }


@pytest.fixture(scope="function")
def detail_report(cost_breakdown, treatment_procedure, member, member_health_plan):
    return {
        "processor_routing_identification": " " * 200,
        "record_type": "DT",
        "transmission_file_type": "DQ",
        "version_number": "10",
        "sender_id": f'{"MAVN":<30}',
        "receiver_id": f'{"MHS":<30}',
        "submission_number": "0000",
        "transaction_response_status": " ",
        "reject_code": " " * 3,
        "record_length": "01700",
        "reserved": " " * 20,
        "transmission_date": "20230101",
        "transmission_time": "00000000",
        "date_of_service": "20230101",
        "service_provider_id_qualifier": " " * 2,
        "service_provider_id": " " * 15,
        "document_reference_identifier_qualifier": "05",
        "document_reference_identifer": "999999999999999",
        "transmission_id": f"{f'20230101000000000#cb_{cost_breakdown.id}':<50}",
        "benefit_type": "9",
        "in_network_indicator": "1",
        "formulary_status": " ",
        "accumulator_action_code": "00",
        "sender_reference_number": str(member_health_plan.member_id).ljust(30, " "),
        "insurance_code": " " * 20,
        "accumulator_balance_benefit_type": "I",
        "benefit_effective_date": " " * 8,
        "benefit_termination_date": " " * 8,
        "accumulator_change_source_code": " ",
        "transaction_id": f"{treatment_procedure.id:<30}",
        "transaction_id_cross_reference": "0" * 30,
        "adjustment_reason_code": " ",
        "accumulator_reference_time_stamp": " " * 26,
        "reserved_2": " " * 13,
        "cardholder_id": f"{'ABCDEFG':<20}",
        "group_id": str(member_health_plan.employer_health_plan.group_id).ljust(
            15, " "
        ),
        "patient_first_name": f"{'ALICE':<25}",
        "middle_initial": " ",
        "patient_last_name": f"{'PAUL':<35}",
        "patient_relationship_code": "1",
        "date_of_birth": "20000101",
        "patient_gender_code": "1",
        "patient_state_province_address": " " * 2,
        "cardholder_last_name": f"{'PAUL':<35}",
        "carrier_number": " " * 9,
        "contract_number": " " * 15,
        "client_pass_through": " " * 50,
        "family_id": " " * 20,
        "cardholder_id_(alternate)": f"{'ABCDEFG':<20}",
        "group_id_(alternate)": " " * 15,
        "patient_id": " " * 20,
        "person_code": " " * 3,
        "reserved_3": " " * 90,
        "accumulator_balance_count": "02",
        "accumulator_specific_category_type": " " * 2,
        "reserved_4": " " * 20,
        "accumulator_balance_qualifier_1": "04",
        "accumulator_network_indicator_1": "1",
        "accumulator_applied_amount_1": "0000010000",
        "action_code_1": "+",
        "accumulator_benefit_period_amount_1": "0" * 10,
        "action_code_1_2": " ",
        "accumulator_remaining_balance_1": "0" * 10,
        "action_code_1_3": " ",
        "accumulator_balance_qualifier_2": "05",
        "accumulator_network_indicator_2": "1",
        "accumulator_applied_amount_2": "0000020000",
        "action_code_2": "+",
        "accumulator_benefit_period_amount_2": "0" * 10,
        "action_code_2_2": " ",
        "accumulator_remaining_balance_2": "0" * 10,
        "action_code_2_3": " ",
        "accumulator_balance_qualifier_3": "  ",
        "accumulator_network_indicator_3": " ",
        "accumulator_applied_amount_3": "0" * 10,
        "action_code_3": " ",
        "accumulator_benefit_period_amount_3": "0" * 10,
        "action_code_3_2": " ",
        "accumulator_remaining_balance_3": "0" * 10,
        "action_code_3_3": " ",
        "accumulator_balance_qualifier_4": "  ",
        "accumulator_network_indicator_4": " ",
        "accumulator_applied_amount_4": "0" * 10,
        "action_code_4": " ",
        "accumulator_benefit_period_amount_4": "0" * 10,
        "action_code_4_2": " ",
        "accumulator_remaining_balance_4": "0" * 10,
        "action_code_4_3": " ",
        "accumulator_balance_qualifier_5": "  ",
        "accumulator_network_indicator_5": " ",
        "accumulator_applied_amount_5": "0" * 10,
        "action_code_5": " ",
        "accumulator_benefit_period_amount_5": "0" * 10,
        "action_code_5_2": " ",
        "accumulator_remaining_balance_5": "0" * 10,
        "action_code_5_3": " ",
        "accumulator_balance_qualifier_6": "  ",
        "accumulator_network_indicator_6": " ",
        "accumulator_applied_amount_6": "0" * 10,
        "action_code_6": " ",
        "accumulator_benefit_period_amount_6": "0" * 10,
        "action_code_6_2": " ",
        "accumulator_remaining_balance_6": "0" * 10,
        "action_code_6_3": " ",
        "reserved_5": " " * 24,
        "accumulator_balance_qualifier_7": "  ",
        "accumulator_network_indicator_7": " ",
        "accumulator_applied_amount_7": "0" * 10,
        "action_code_7": " ",
        "accumulator_benefit_period_amount_7": "0" * 10,
        "action_code_7_2": " ",
        "accumulator_remaining_balance_7": "0" * 10,
        "action_code_7_3": " ",
        "accumulator_balance_qualifier_8": "  ",
        "accumulator_network_indicator_8": " ",
        "accumulator_applied_amount_8": "0" * 10,
        "action_code_8": " ",
        "accumulator_benefit_period_amount_8": "0" * 10,
        "action_code_8_2": " ",
        "accumulator_remaining_balance_8": "0" * 10,
        "action_code_8_3": " ",
        "accumulator_balance_qualifier_9": "  ",
        "accumulator_network_indicator_9": " ",
        "accumulator_applied_amount_9": "0" * 10,
        "action_code_9": " ",
        "accumulator_benefit_period_amount_9": "0" * 10,
        "action_code_9_2": " ",
        "accumulator_remaining_balance_9": "0" * 10,
        "action_code_9_3": " ",
        "accumulator_balance_qualifier_10": "  ",
        "accumulator_network_indicator_10": " ",
        "accumulator_applied_amount_10": "0" * 10,
        "action_code_10": " ",
        "accumulator_benefit_period_amount_10": "0" * 10,
        "action_code_10_2": " ",
        "accumulator_remaining_balance_10": "0" * 10,
        "action_code_10_3": " ",
        "accumulator_balance_qualifier_11": "  ",
        "accumulator_network_indicator_11": " ",
        "accumulator_applied_amount_11": "0" * 10,
        "action_code_11": " ",
        "accumulator_benefit_period_amount_11": "0" * 10,
        "action_code_11_2": " ",
        "accumulator_remaining_balance_11": "0" * 10,
        "action_code_11_3": " ",
        "accumulator_balance_qualifier_12": "  ",
        "accumulator_network_indicator_12": " ",
        "accumulator_applied_amount_12": "0" * 10,
        "action_code_12": " ",
        "accumulator_benefit_period_amount_12": "0" * 10,
        "action_code_12_2": " ",
        "accumulator_remaining_balance_12": "0" * 10,
        "action_code_12_3": " ",
        "optional_data_indicator": " ",
        "total_amount_paid": "0" * 10,
        "action_code_1_4": " ",
        "amount_of_copay": "0" * 10,
        "action_code_2_4": " ",
        "patient_pay_amount": "0" * 10,
        "action_code_3_4": " ",
        "amount_attributed_to_product_selection_brand": "0" * 10,
        "action_code_4_4": " ",
        "amount_attributed_to_sales_tax": "0" * 10,
        "action_code_5_4": " ",
        "amount_attributed_to_processor_fee": "0" * 10,
        "action_code_6_4": " ",
        "gross_amount_due": "0" * 10,
        "action_code_7_4": " ",
        "invoiced_amount": "0" * 10,
        "action_code_8_4": " ",
        "penalty_amount": "0" * 10,
        "action_code_9_4": " ",
        "reserved_6": " " * 23,
        "product_service_id_qualifier": " " * 2,
        "product_service_id": " " * 19,
        "days_supply": "0" * 3,
        "quantity_dispense": "0" * 10,
        "product_service_name": " " * 30,
        "brand_generic_indicator": " ",
        "therapeutic_class_code_qualifier": " ",
        "therapeutic_class_code_–_specific": " " * 17,
        "dispensed_as_written_product_selection": " ",
        "reserved_7": " " * 48,
    }


@pytest.fixture(scope="function")
def trailer_report():
    return {
        "processor_routing_identification": " " * 200,
        "record_type": "TR",
        "batch_number": "1".zfill(7),
        "record_count": "5".zfill(10),
        "message": " " * 80,
        "reserved": " " * 1401,
    }


@pytest.fixture
def esi_structured_report_snippet():
    return [
        {
            "record_type": "HD",
        },
        {
            "record_type": "DT",
            "transmission_id": "20240226010800237#cb_570",
            "transaction_id": "645",
            "cardholder_id": "727348445",
            "date_of_birth": "20000101",
            "accumulator_balance_count": "01",
            "accumulator_balance_qualifier_1": "04",
            "accumulator_applied_amount_1": "0000005000",
        },
        {
            "record_type": "DT",
            "transmission_id": "20240226010800237#cb_571",
            "transaction_id": "647",
            "cardholder_id": "727348445",
            "date_of_birth": "20000101",
            "accumulator_balance_count": "02",
            "accumulator_balance_qualifier_1": "04",
            "accumulator_applied_amount_1": "0000005000",
            "accumulator_balance_qualifier_2": "05",
            "accumulator_applied_amount_2": "0000005983",
        },
        {
            "record_type": "DT",
            "transmission_id": "20240226010800237#cb_577",
            "transaction_id": "648",
            "cardholder_id": "727320321",
            "date_of_birth": "20000101",
            "accumulator_balance_count": "02",
            "accumulator_balance_qualifier_1": "04",
            "accumulator_applied_amount_1": "0000001704",
            "accumulator_balance_qualifier_2": "05",
            "accumulator_applied_amount_2": "0000001704",
        },
        {
            "record_type": "DT",
            "transmission_id": "20240226010800237#cb_564",
            "in_network_indicator": "1",
            "transaction_id": "649",
            "cardholder_id": "727369392",
            "date_of_birth": "20000101",
            "accumulator_balance_count": "02",
            "accumulator_balance_qualifier_1": "04",
            "accumulator_applied_amount_1": "0000001704",
            "accumulator_balance_qualifier_2": "05",
            "accumulator_applied_amount_2": "0000001704",
        },
        {
            "record_type": "TR",
            "record_count": "0000000004",
        },
    ]


class TestESIAccumulationFileGenerator:
    def test_file_name(self, esi_file_generator):
        assert esi_file_generator.file_name == "MAVN_MedAccum_20230101_000000"

    def test_generate_header(self, esi_file_generator, header_report):
        header = esi_file_generator._generate_header()
        for index, value in enumerate(esi_file_generator.header_config.values()):
            start_pos = value["start_pos"] - 1
            end_pos = value["end_pos"]
            assert header[start_pos:end_pos] == list(header_report.values())[index]

    def test_generate_trailer(self, esi_file_generator, trailer_report):
        trailer = esi_file_generator._generate_trailer(record_count=5)
        for index, value in enumerate(esi_file_generator.trailer_config.values()):
            start_pos = value["start_pos"] - 1
            end_pos = value["end_pos"]
            assert trailer[start_pos:end_pos] == list(trailer_report.values())[index]

    def test_get_record_count_from_buffer(
        self,
        esi_file_generator,
    ):
        # given
        acc_file = "header_row\r\ndetail_row_one\r\ndetail_row_two\r\ntrailer_row\r\n"
        buffer = StringIO(acc_file)
        # when
        record_count = esi_file_generator.get_record_count_from_buffer(buffer=buffer)
        expected_record_count = 2
        # then
        assert record_count == expected_record_count

    def test_generate_detail_deductible_and_oop_applied(
        self,
        esi_file_generator,
        cost_breakdown,
        treatment_procedure,
        member_health_plan,
        detail_report,
    ):
        treatment_procedure.cost_breakdown_id = cost_breakdown.id
        detail_wrapper = esi_file_generator._generate_detail(
            record_id=treatment_procedure.id,
            record_type=TreatmentProcedureType(treatment_procedure.procedure_type),
            cost_breakdown=cost_breakdown,
            service_start_date=datetime.datetime.combine(
                treatment_procedure.start_date, datetime.time.min
            ),
            deductible=10000,
            oop_applied=20000,
            hra_applied=0,
            member_health_plan=member_health_plan,
        )
        detail = detail_wrapper.line
        for index, value in enumerate(esi_file_generator.detail_config.values()):
            start_pos = value["start_pos"] - 1
            end_pos = value["end_pos"]
            assert detail[start_pos:end_pos] == list(detail_report.values())[index]

    def test_generate_detail_negative_deductible_and_oop_applied(
        self,
        esi_file_generator,
        cost_breakdown,
        treatment_procedure,
        member_health_plan,
        detail_report,
    ):
        treatment_procedure.cost_breakdown_id = cost_breakdown.id

        detail_wrapper = esi_file_generator._generate_detail(
            record_id=treatment_procedure.id,
            record_type=TreatmentProcedureType(treatment_procedure.procedure_type),
            cost_breakdown=cost_breakdown,
            service_start_date=datetime.datetime.combine(
                treatment_procedure.start_date, datetime.time.min
            ),
            deductible=-10000,
            oop_applied=-20000,
            hra_applied=0,
            member_health_plan=member_health_plan,
            is_reversal=True,
        )
        detail = detail_wrapper.line
        for index, value in enumerate(esi_file_generator.detail_config.values()):
            start_pos = value["start_pos"] - 1
            end_pos = value["end_pos"]
            action_code_1_end_pos = esi_file_generator.detail_config["action_code_1"][
                "end_pos"
            ]
            action_code_2_end_pos = esi_file_generator.detail_config["action_code_2"][
                "end_pos"
            ]
            accumulator_action_code_end_pos = esi_file_generator.detail_config[
                "accumulator_action_code"
            ]["end_pos"]
            if end_pos == action_code_1_end_pos or end_pos == action_code_2_end_pos:
                assert detail[start_pos:end_pos] == "-"
            elif end_pos == accumulator_action_code_end_pos:
                assert detail[start_pos:end_pos] == "11"
            else:
                assert detail[start_pos:end_pos] == list(detail_report.values())[index]

    def test_generate_detail_oop_applied_only(
        self,
        esi_file_generator,
        cost_breakdown,
        treatment_procedure,
        member_health_plan,
        detail_report,
    ):
        treatment_procedure.cost_breakdown_id = cost_breakdown.id
        cost_breakdown.deductible = 0
        detail_report["accumulator_balance_qualifier_1"] = "05"
        detail_report["accumulator_applied_amount_1"] = "0000020000"
        detail_report["accumulator_balance_qualifier_2"] = "  "
        detail_report["accumulator_applied_amount_2"] = "0000000000"
        detail_report["accumulator_balance_count"] = "01"
        detail_wrapper = esi_file_generator._generate_detail(
            record_id=treatment_procedure.id,
            record_type=TreatmentProcedureType(treatment_procedure.procedure_type),
            cost_breakdown=cost_breakdown,
            service_start_date=datetime.datetime.combine(
                treatment_procedure.start_date, datetime.time.min
            ),
            deductible=0,
            oop_applied=20000,
            hra_applied=0,
            member_health_plan=member_health_plan,
        )
        detail = detail_wrapper.line
        for index, value in enumerate(esi_file_generator.detail_config.values()):
            start_pos = value["start_pos"] - 1
            end_pos = value["end_pos"]
            assert detail[start_pos:end_pos] == list(detail_report.values())[index]

    @pytest.mark.parametrize(
        argnames="gender, expected_gender_code",
        argvalues=[
            (MemberHealthPlanPatientSex.MALE, "1"),
            (MemberHealthPlanPatientSex.FEMALE, "2"),
            (MemberHealthPlanPatientSex.UNKNOWN, "0"),
        ],
    )
    def test_generate_detail_patient_gender(
        self,
        gender,
        expected_gender_code,
        esi_file_generator,
        cost_breakdown,
        treatment_procedure,
        member_health_plan,
        detail_report,
        member,
    ):
        treatment_procedure.cost_breakdown_id = cost_breakdown.id
        member_health_plan.patient_sex = gender
        detail_report["patient_gender_code"] = expected_gender_code
        detail_wrapper = esi_file_generator._generate_detail(
            record_id=treatment_procedure.id,
            record_type=TreatmentProcedureType(treatment_procedure.procedure_type),
            cost_breakdown=cost_breakdown,
            service_start_date=datetime.datetime.combine(
                treatment_procedure.start_date, datetime.time.min
            ),
            deductible=10000,
            oop_applied=20000,
            hra_applied=0,
            member_health_plan=member_health_plan,
        )
        detail = detail_wrapper.line
        for index, value in enumerate(esi_file_generator.detail_config.values()):
            start_pos = value["start_pos"] - 1
            end_pos = value["end_pos"]
            assert detail[start_pos:end_pos] == list(detail_report.values())[index]

    def test_generate_detail_from_reimbursement_request_no_benefit_payer_id(
        self,
        esi_file_generator,
        esi_payer,
        make_new_reimbursement_request_for_report_row,
        make_treatment_procedure_equivalent_to_reimbursement_request,
        cost_breakdown,
    ):
        reimbursement_request = make_new_reimbursement_request_for_report_row()
        member_health_plan = reimbursement_request.wallet.member_health_plan[0]

        with pytest.raises(InvalidPayerError) as e:
            esi_file_generator.detail_to_dict(
                esi_file_generator._generate_detail(
                    record_id=reimbursement_request.id,
                    record_type=TreatmentProcedureType.MEDICAL,
                    cost_breakdown=cost_breakdown,
                    service_start_date=reimbursement_request.service_start_date,
                    member_health_plan=member_health_plan,
                    deductible=200,
                    oop_applied=300,
                    hra_applied=0,
                ).line
            )
        assert str(e.value) == "Payer not found for benefit_payer_id"

    def test_generate_detail_from_reimbursement_request(
        self,
        esi_file_generator,
        esi_payer,
        make_new_reimbursement_request_for_report_row,
        make_treatment_procedure_equivalent_to_reimbursement_request,
    ):
        reimbursement_request = make_new_reimbursement_request_for_report_row(
            payer=esi_payer
        )
        member_health_plan = reimbursement_request.wallet.member_health_plan[0]

        (
            treatment_procedure,
            cost_breakdown,
        ) = make_treatment_procedure_equivalent_to_reimbursement_request(
            reimbursement_request=reimbursement_request,
            record_type=TreatmentProcedureType.MEDICAL,
            deductible_apply_amount=200,
            oop_apply_amount=300,
        )

        detail = esi_file_generator.detail_to_dict(
            esi_file_generator._generate_detail(
                record_id=reimbursement_request.id,
                record_type=TreatmentProcedureType.MEDICAL,
                cost_breakdown=cost_breakdown,
                service_start_date=reimbursement_request.service_start_date,
                member_health_plan=member_health_plan,
                deductible=200,
                oop_applied=300,
                hra_applied=0,
            ).line
        )

        procedure_detail = esi_file_generator.detail_to_dict(
            esi_file_generator._generate_detail(
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
        procedure_detail["cardholder_id_(alternate)"] = "U1234567801"
        # keys that should not match here:
        procedure_detail["transmission_id"] = ANY
        procedure_detail["transaction_id"] = ANY
        procedure_detail["in_network_indicator"] = "1"
        procedure_detail["group_id"] = member_health_plan.employer_health_plan.group_id
        # assert for all keys that should match
        assert detail == procedure_detail

    def test_generate_detail_from_reimbursement_request_service_date_defaults(
        self,
        esi_file_generator,
        esi_payer,
        make_new_reimbursement_request_for_report_row,
        cost_breakdown,
    ):
        reimbursement_request = make_new_reimbursement_request_for_report_row(
            payer=esi_payer
        )
        start_date = datetime.datetime.today()
        reimbursement_request.service_start_date = start_date
        # reimbursement_request.service_end_date = None
        member_health_plan = reimbursement_request.wallet.member_health_plan[0]

        detail = esi_file_generator.detail_to_dict(
            esi_file_generator._generate_detail(
                record_id=reimbursement_request.id,
                record_type=TreatmentProcedureType.MEDICAL,
                cost_breakdown=cost_breakdown,
                service_start_date=reimbursement_request.service_start_date,
                member_health_plan=member_health_plan,
                deductible=200,
                oop_applied=300,
                hra_applied=0,
            ).line
        )

        assert detail["date_of_service"] == start_date.strftime("%Y%m%d")

    def test_generate_detail_from_reimbursement_request_group_id_default(
        self,
        esi_file_generator,
        esi_payer,
        make_new_reimbursement_request_for_report_row,
        cost_breakdown,
    ):
        reimbursement_request = make_new_reimbursement_request_for_report_row(
            payer=esi_payer
        )
        member_health_plan = reimbursement_request.wallet.member_health_plan[0]
        # if the employer health plan's group id is None, raise error
        member_health_plan.employer_health_plan.group_id = None

        with pytest.raises(InvalidGroupIdError) as e:
            esi_file_generator.detail_to_dict(
                esi_file_generator._generate_detail(
                    record_id=reimbursement_request.id,
                    record_type=TreatmentProcedureType.MEDICAL,
                    cost_breakdown=cost_breakdown,
                    service_start_date=reimbursement_request.service_start_date,
                    member_health_plan=member_health_plan,
                    deductible=200,
                    oop_applied=300,
                    hra_applied=0,
                ).line
            )
        assert (
            str(e.value)
            == "Group ID required for non rx integrated employer health plan"
        )

    def test_get_dob_from_report_row(
        self, esi_file_generator, esi_structured_report_snippet
    ):
        assert esi_file_generator.get_dob_from_report_row(
            detail_row_dict=esi_structured_report_snippet[1]
        ) == date(2000, 1, 1)

    def test_get_deductible_from_row(
        self, esi_file_generator, esi_structured_report_snippet
    ):
        assert 5000 == esi_file_generator.get_deductible_from_row(
            esi_structured_report_snippet[1]
        )

    def test_get_oop_from_row(self, esi_file_generator, esi_structured_report_snippet):
        assert 0 == esi_file_generator.get_oop_from_row(
            esi_structured_report_snippet[1]
        )
        assert 5983 == esi_file_generator.get_oop_from_row(
            esi_structured_report_snippet[2]
        )

    def test_get_detail_rows(self, esi_file_generator, esi_structured_report_snippet):
        assert 4 == len(
            esi_file_generator.get_detail_rows(
                report_rows=esi_structured_report_snippet
            )
        )
