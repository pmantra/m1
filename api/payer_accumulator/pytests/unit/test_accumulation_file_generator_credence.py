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
from payer_accumulator.errors import SkipAccumulationDueToMissingInfo
from payer_accumulator.file_generators import AccumulationFileGeneratorCredence
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
def credence_payer():
    return PayerFactory.create(id=1, payer_name=PayerName.CREDENCE, payer_code="01234")


@pytest.fixture(scope="function")
@freeze_time("2023-01-01 00:00:00")
def credence_file_generator(credence_payer):
    return AccumulationFileGeneratorCredence()


@pytest.fixture(scope="function")
def cost_breakdown():
    return CostBreakdownFactory.create(
        deductible=10000, coinsurance=10000, oop_applied=20000
    )


@pytest.fixture(scope="function")
def cost_breakdown_no_deductible():
    return CostBreakdownFactory.create(
        deductible=0, coinsurance=10000, oop_applied=10000
    )


@pytest.fixture(scope="function")
@freeze_time("2023-01-01 00:00:00")
def treatment_procedure(member):
    return TreatmentProcedureFactory.create(
        start_date=date.today(),
        end_date=date.today() + datetime.timedelta(days=1),
        member_id=member.id,
    )


@pytest.fixture(scope="function")
def employer_health_plan(member, credence_payer):
    org_settings = ReimbursementOrganizationSettingsFactory.create(
        organization_id=member.organization.id,
    )
    return EmployerHealthPlanFactory.create(
        reimbursement_organization_settings=org_settings,
        benefits_payer_id=credence_payer.id,
    )


@pytest.fixture(scope="function")
def member_health_plan(employer_health_plan):
    plan = MemberHealthPlanFactory.create(
        employer_health_plan=employer_health_plan,
        patient_sex=MemberHealthPlanPatientSex.MALE,
        subscriber_insurance_id="12345",
        patient_relationship=MemberHealthPlanPatientRelationship.CARDHOLDER,
        patient_date_of_birth=datetime.date(1988, 3, 14),
        patient_first_name="Stephen",
        patient_last_name="Curry",
        subscriber_first_name="Stephen",
        subscriber_last_name="Curry",
        plan_start_at=datetime.datetime(2024, 1, 1),
        plan_end_at=datetime.datetime(2034, 1, 1),
    )
    return plan


@pytest.fixture(scope="function")
def detail_report(cost_breakdown, treatment_procedure, member, member_health_plan):
    return {
        "record_type": "01",
        "transaction_type": "00",
        "sender_id": "MAVEN" + " " * 20,
        "sender_name": "MAVEN" + " " * 55,
        "receiver_id": "BCBSAL" + " " * 19,
        "receiver_name": "BCBSAL" + " " * 54,
        "unique_record_identifier": f"20230101000000#cb_{cost_breakdown.id}"
        + " " * (57 - len(str(cost_breakdown.id))),
        "benefit_type": "04",
        "subscriber_ssn": " " * 9,
        "subscriber_last_name": member_health_plan.subscriber_last_name + " " * 30,
        "relationship_code": "1",
        "patient_ssn": " " * 9,
        "patient_first_name": "Stephen" + " " * 18,
        "patient_last_name": "Curry" + " " * 30,
        "patient_date_of_birth": "19880314",
        "patient_gender": "1",
        "claim_number": str(treatment_procedure.id)
        + " " * (60 - len(str(treatment_procedure.id))),
        "claim_line_number": "00",
        "claim_start_date": "20230101",
        "claim_end_date": "20230101",
        "family_or_individual": "I",
        "group_number": "0000000",
        "procedure_code": " " * 10,
        "primacy_diagnosis_code": " " * 10,
        "place_of_treatment": " " * 2,
        "type_service": " " * 2,
        "number_days_service": " " * 3,
        "paid_amount": " " * 12,
        "filler_1": " ",
        "contract_number": "12345" + " " * 10,
        "prescription_number": " " * 11,
        "ndc_code": " " * 11,
        "pharmacy_npi": " " * 10,
        "division": " " * 3,
        "filler_2": " " * 47,
        "oop_eob_applied_amount": "0" * 12,
        "filler_3": " " * 151,
        "type_of_accumulator_1": "1",
        "type_of_coverage_1": "1",
        "accumulator_amount_1": "00000001000{",
        "filler_4": " " * 20,
        "type_of_accumulator_2": "4",
        "type_of_coverage_2": "1",
        "accumulator_amount_2": "00000002000{",
        "filler_5": " " * 20,
        "type_of_accumulator_3": "2",
        "type_of_coverage_3": "1",
        "accumulator_amount_3": "00000001000{",
        "filler_6": " " * 20,
        "type_of_accumulator_4": " ",
        "type_of_coverage_4": " ",
        "accumulator_amount_4": "000000000000",
        "filler_7": " " * 20,
        "type_of_accumulator_5": " ",
        "type_of_coverage_5": " ",
        "accumulator_amount_5": "000000000000",
        "filler_8": " " * 20,
        "type_of_accumulator_6": " ",
        "type_of_coverage_6": " ",
        "accumulator_amount_6": "000000000000",
        "filler_9": " " * 20,
        "type_of_accumulator_7": " ",
        "type_of_coverage_7": " ",
        "accumulator_amount_7": "000000000000",
        "filler_10": " " * 20,
        "type_of_accumulator_8": " ",
        "type_of_coverage_8": " ",
        "accumulator_amount_8": "000000000000",
        "filler_11": " " * 20,
        "type_of_accumulator_9": " ",
        "type_of_coverage_9": " ",
        "accumulator_amount_9": "000000000000",
        "filler_12": " " * 20,
        "type_of_accumulator_10": " ",
        "type_of_coverage_10": " ",
        "accumulator_amount_10": "000000000000",
        "filler_13": " " * 4,
        "out_of_pocket_amount": "000000000000",
        "acknowledgement_code": "00",
        "acknowledgement_sub_code": " " * 2,
    }


@pytest.fixture(scope="function")
def trailer_report():
    return {
        "record_type": "TRAILER",
        "record_count": "0" * 9 + "5",
        "file_date": "20230101",
        "file_time": "000000",
        "transaction_count": "0" * 9 + "3",
        "filler": " " * 1059,
    }


@pytest.fixture(scope="function")
def header_report():
    return {
        "record_type": "HEADER ",
        "test_production_indicator": "P",
        "sender_id": "MAVEN" + " " * 15,
        "file_date": "20230101",
        "file_time": "000000",
        "receiver_of_transmission": "CREDENCE" + " " * 17,
        "unique_file_id": "MAVEN_ACCUM_20230101_000000" + " " * 13,
        "filler": " " * 993,
    }


@pytest.fixture
def credence_structured_report_snippet():
    return [
        {
            "record_type": "HEADER",
            "file_date": "20230101",
            "file_time": "000000",
            "unique_file_id": "MAVEN_ACCUM_20230101_000000",
        },
        {
            "record_type": "01",
            "unique_record_identifier": "20240226010800237#cb_570",
            "claim_number": "cb_570",
            "contract_number": "727348445",
            "patient_date_of_birth": "20000101",
            "type_of_accumulator_1": "1",
            "type_of_coverage_1": "1",
            "accumulator_amount_1": "000000005{",
            "type_of_accumulator_2": "4",
            "type_of_coverage_2": "1",
            "accumulator_amount_2": "000000005{",
            "type_of_accumulator_3": "2",
            "type_of_coverage_3": "1",
            "accumulator_amount_3": "000000000{",
        },
        {
            "record_type": "01",
            "unique_record_identifier": "20240226010800237#cb_571",
            "claim_number": "cb_571",
            "contract_number": "727348445",
            "patient_date_of_birth": "20000101",
            "type_of_accumulator_1": "1",
            "type_of_coverage_1": "1",
            "accumulator_amount_1": "000000010{",
            "type_of_accumulator_2": "4",
            "type_of_coverage_2": "1",
            "accumulator_amount_2": "000000000{",
            "type_of_accumulator_3": "2",
            "type_of_coverage_3": "1",
            "accumulator_amount_3": "000000010{",
        },
        {
            "record_type": "TRAILER",
            "record_count": "0000000004",
            "file_date": "20230101",
            "file_time": "000000",
            "transaction_count": "0000000002",
        },
    ]


class TestAccumulationFileGeneratorCredence:
    def test_file_name(self, credence_file_generator):
        assert credence_file_generator.file_name == "MAVEN_ACCUM_20230101_000000.txt"

    def test_generate_trailer(self, credence_file_generator, trailer_report):
        trailer = credence_file_generator._generate_trailer(record_count=3)
        for index, value in enumerate(credence_file_generator.trailer_config.values()):
            start_pos = value["start_pos"] - 1
            end_pos = value["end_pos"]
            assert trailer[start_pos:end_pos] == list(trailer_report.values())[index]

    def test_generate_header(self, credence_file_generator, header_report):
        header = credence_file_generator._generate_header()
        for index, value in enumerate(credence_file_generator.header_config.values()):
            start_pos = value["start_pos"] - 1
            end_pos = value["end_pos"]
            assert header[start_pos:end_pos] == list(header_report.values())[index]

    def test_get_record_count_from_buffer(
        self,
        credence_file_generator,
    ):
        # given
        acc_file = "header_row\r\ndetail_row_one\r\ndetail_row_two\r\ntrailer_row\r\n"
        buffer = StringIO(acc_file)
        # when
        record_count = credence_file_generator.get_record_count_from_buffer(
            buffer=buffer
        )
        expected_record_count = 2
        # then
        assert record_count == expected_record_count

    def test_generate_detail_deductible_and_oop_applied(
        self,
        credence_file_generator,
        cost_breakdown,
        treatment_procedure,
        member_health_plan,
        detail_report,
    ):
        treatment_procedure.cost_breakdown_id = cost_breakdown.id
        detail_wrapper = credence_file_generator._generate_detail(
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
        for index, value in enumerate(credence_file_generator.detail_config.values()):
            start_pos = value["start_pos"] - 1
            end_pos = value["end_pos"]
            assert detail[start_pos:end_pos] == list(detail_report.values())[index]

    def test_generate_detail_oop_applied_only(
        self,
        credence_file_generator,
        cost_breakdown_no_deductible,
        treatment_procedure,
        member_health_plan,
        detail_report,
    ):
        treatment_procedure.cost_breakdown_id = cost_breakdown_no_deductible.id
        # Remove deductible entry and only send OOP and Coinsurance
        detail_report.update(
            {
                "type_of_accumulator_1": "4",
                "accumulator_amount_1": "00000001000{",
                "type_of_accumulator_2": "2",
                "accumulator_amount_2": "00000001000{",
                "type_of_accumulator_3": " ",
                "type_of_coverage_3": " ",
                "accumulator_amount_3": "000000000000",
                "unique_record_identifier": f"20230101000000#cb_{cost_breakdown_no_deductible.id}"
                + " " * (57 - len(str(cost_breakdown_no_deductible.id))),
            }
        )

        detail_wrapper = credence_file_generator._generate_detail(
            record_id=treatment_procedure.id,
            record_type=TreatmentProcedureType(treatment_procedure.procedure_type),
            cost_breakdown=cost_breakdown_no_deductible,
            service_start_date=datetime.datetime.combine(
                treatment_procedure.start_date, datetime.time.min
            ),
            deductible=0,
            oop_applied=10000,
            hra_applied=0,
            member_health_plan=member_health_plan,
        )
        detail = detail_wrapper.line
        for index, value in enumerate(credence_file_generator.detail_config.values()):
            start_pos = value["start_pos"] - 1
            end_pos = value["end_pos"]
            assert detail[start_pos:end_pos] == list(detail_report.values())[index]

    @pytest.mark.parametrize(
        argnames="gender, expected_gender_code",
        argvalues=[
            (MemberHealthPlanPatientSex.MALE, "1"),
            (MemberHealthPlanPatientSex.FEMALE, "2"),
            (MemberHealthPlanPatientSex.UNKNOWN, "3"),
        ],
    )
    def test_generate_detail_patient_gender(
        self,
        gender,
        expected_gender_code,
        credence_file_generator,
        cost_breakdown,
        treatment_procedure,
        member_health_plan,
        detail_report,
        member,
    ):
        treatment_procedure.cost_breakdown_id = cost_breakdown.id
        member_health_plan.patient_sex = gender
        detail_report["patient_gender"] = expected_gender_code
        detail_wrapper = credence_file_generator._generate_detail(
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
        for index, value in enumerate(credence_file_generator.detail_config.values()):
            start_pos = value["start_pos"] - 1
            end_pos = value["end_pos"]
            assert detail[start_pos:end_pos] == list(detail_report.values())[index]

    def test_generate_detail_from_reimbursement_request(
        self,
        credence_file_generator,
        credence_payer,
        make_new_reimbursement_request_for_report_row,
        make_treatment_procedure_equivalent_to_reimbursement_request,
        cost_breakdown,
    ):
        reimbursement_request = make_new_reimbursement_request_for_report_row(
            payer=credence_payer
        )
        member_health_plan = reimbursement_request.wallet.member_health_plan[0]
        member_health_plan.patient_relationship = (
            MemberHealthPlanPatientRelationship.SPOUSE
        )

        detail = credence_file_generator.detail_to_dict(
            credence_file_generator._generate_detail(
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
        (
            treatment_procedure,
            _,
        ) = make_treatment_procedure_equivalent_to_reimbursement_request(
            reimbursement_request=reimbursement_request,
            record_type=TreatmentProcedureType.MEDICAL,
            deductible_apply_amount=200,
            oop_apply_amount=300,
        )
        procedure_detail = credence_file_generator.detail_to_dict(
            credence_file_generator._generate_detail(
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
        procedure_detail["claim_number"] = ANY
        procedure_detail["unique_record_identifier"] = ANY
        # assert for all keys that should match
        assert detail == procedure_detail

    def test_invalid_patient_relationship(
        self,
        credence_file_generator,
        credence_payer,
        make_new_reimbursement_request_for_report_row,
        cost_breakdown,
    ):
        reimbursement_request = make_new_reimbursement_request_for_report_row(
            payer=credence_payer
        )
        member_health_plan = reimbursement_request.wallet.member_health_plan[0]

        with pytest.raises(SkipAccumulationDueToMissingInfo):
            credence_file_generator.detail_to_dict(
                credence_file_generator._generate_detail(
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

    def test_get_dob_from_report_row(
        self, credence_file_generator, credence_structured_report_snippet
    ):
        assert credence_file_generator.get_dob_from_report_row(
            detail_row_dict=credence_structured_report_snippet[1]
        ) == date(2000, 1, 1)

    def test_get_deductible_from_row(
        self, credence_file_generator, credence_structured_report_snippet
    ):
        assert 50 == credence_file_generator.get_deductible_from_row(
            credence_structured_report_snippet[1]
        )

    def test_get_oop_from_row(
        self, credence_file_generator, credence_structured_report_snippet
    ):
        assert 50 == credence_file_generator.get_oop_from_row(
            credence_structured_report_snippet[1]
        )
        assert 0 == credence_file_generator.get_oop_from_row(
            credence_structured_report_snippet[2]
        )

    def test_get_detail_rows(
        self,
        credence_payer,
        credence_file_generator,
        credence_structured_report_snippet,
    ):
        assert 2 == len(
            credence_file_generator.get_detail_rows(
                report_rows=credence_structured_report_snippet
            )
        )

    def test_get_accumulations(
        self,
        credence_file_generator,
        credence_structured_report_snippet,
        cost_breakdown,
    ):
        accumulations = credence_file_generator._get_accumulation_balances(
            10000, 20000, cost_breakdown, False
        )
        assert accumulations == [
            ("1", "1", "1000{"),
            ("4", "1", "2000{"),
            ("2", "1", "1000{"),
        ]

    def test_get_accumulations_reversal(
        self,
        credence_file_generator,
        credence_structured_report_snippet,
        cost_breakdown,
    ):
        accumulations = credence_file_generator._get_accumulation_balances(
            -10000, -20000, cost_breakdown, True
        )
        assert accumulations == [
            ("1", "1", "1000}"),
            ("4", "1", "2000}"),
            ("2", "1", "1000}"),
        ]

    def test_get_accumulations_no_deductible(
        self,
        credence_file_generator,
        credence_structured_report_snippet,
        cost_breakdown_no_deductible,
    ):
        accumulations = credence_file_generator._get_accumulation_balances(
            0, 10000, cost_breakdown_no_deductible, False
        )

        assert accumulations == [
            ("4", "1", "1000{"),
            ("2", "1", "1000{"),
        ]

    def test_get_accumulations_no_deductible_reversal(
        self,
        credence_file_generator,
        credence_structured_report_snippet,
        cost_breakdown_no_deductible,
    ):
        accumulations = credence_file_generator._get_accumulation_balances(
            0, -10000, cost_breakdown_no_deductible, True
        )

        assert accumulations == [
            ("4", "1", "1000}"),
            ("2", "1", "1000}"),
        ]

    @pytest.mark.parametrize(
        argnames="file_name, expected",
        argvalues=[
            ("MAVEN_MED_ACK_20241015_123456.txt", False),
            ("MAVEN_ACCUM_20241015123456.txt", False),
            ("MAVEN_MED_ACK_20241015_123456", True),
        ],
    )
    def test_match_response_filename(
        self, credence_file_generator, file_name, expected
    ):
        result = credence_file_generator.match_response_filename(file_name)
        assert result == expected

    @pytest.mark.parametrize(
        argnames="file_name, expected",
        argvalues=[
            ("MAVEN_MED_ACK_20241015_123456", "20241015"),
            ("MAVEN_MED_ACK_20241015_123456.txt", None),
            ("MAVEN_ACCUM_20241015123456.txt", None),
        ],
    )
    def test_get_response_file_date(self, credence_file_generator, file_name, expected):
        result = credence_file_generator.get_response_file_date(file_name)
        assert result == expected

    @pytest.mark.parametrize(
        argnames="detail_record, expected_metadata",
        argvalues=[
            (
                # accepted
                {
                    "transaction_type": "01",
                    "unique_record_identifier": "20241015123456789#cb_1",
                    "acknowledgement_code": "10",
                    "contract_number": "12345",
                    "patient_first_name": "Stephen",
                    "patient_last_name": "Curry",
                    "patient_date_of_birth": "19880314",
                    "subscriber_last_name": "Curry",
                    "claim_start_date": "20241001",
                },
                {
                    "is_response": True,
                    "is_rejection": False,
                    "unique_id": "20241015123456789#cb_1",
                    "response_code": "10",
                },
            ),
            (
                # rejected (mapped)
                {
                    "transaction_type": "01",
                    "unique_record_identifier": "20241015123456789#cb_2",
                    "acknowledgement_code": "42",
                    "contract_number": "12345",
                    "patient_first_name": "Stephen",
                    "patient_last_name": "Curry",
                    "patient_date_of_birth": "19880314",
                    "subscriber_last_name": "Curry",
                    "claim_start_date": "20241001",
                },
                {
                    "is_response": True,
                    "is_rejection": True,
                    "should_update": True,
                    "unique_id": "20241015123456789#cb_2",
                    "response_code": "42",
                    "response_reason": "Invalid Sender ID",
                },
            ),
            (
                # rejected (Other)
                {
                    "transaction_type": "01",
                    "unique_record_identifier": "20241015123456789#cb_3",
                    "acknowledgement_code": "99",
                    "contract_number": "12345",
                    "patient_first_name": "Stephen",
                    "patient_last_name": "Curry",
                    "patient_date_of_birth": "19880314",
                    "subscriber_last_name": "Curry",
                    "claim_start_date": "20241001",
                },
                {
                    "is_response": True,
                    "is_rejection": True,
                    "should_update": True,
                    "unique_id": "20241015123456789#cb_3",
                    "response_code": "99",
                    "response_reason": "Other error encountered",
                },
            ),
            (
                # Not response file
                {
                    "transaction_type": "00",
                    "unique_record_identifier": "20241015123456789#cb_7",
                    "acknowledgement_code": "00",
                    "contract_number": "12345",
                    "patient_first_name": "Stephen",
                    "patient_last_name": "Curry",
                    "patient_date_of_birth": "19880314",
                    "subscriber_last_name": "Curry",
                    "claim_start_date": "20241001",
                },
                {
                    "is_response": False,
                    "is_rejection": False,
                    "unique_id": "20241015123456789#cb_7",
                },
            ),
        ],
    )
    def test_get_detail_metadata(
        self,
        credence_file_generator,
        detail_record,
        expected_metadata,
        member_health_plan,
    ):
        metadata = credence_file_generator.get_detail_metadata(detail_record)
        for k, v in expected_metadata.items():
            assert getattr(metadata, k) == v
        assert metadata.member_id == str(member_health_plan.member_id)

    @pytest.mark.parametrize(
        argnames="detail_record, expected_metadata",
        argvalues=[
            (
                # accepted
                {
                    "transaction_type": "01",
                    "unique_record_identifier": "20241015123456789#cb_1",
                    "acknowledgement_code": "10",
                    "contract_number": "12345",
                    "patient_first_name": "Stephen",
                    "patient_last_name": "Curry",
                    "patient_date_of_birth": "19880314",
                    "subscriber_last_name": "Curry",
                    "claim_start_date": "20241001",
                },
                {
                    "is_response": True,
                    "is_rejection": False,
                    "unique_id": "20241015123456789#cb_1",
                    "response_code": "10",
                },
            ),
            (
                # rejected (mapped)
                {
                    "transaction_type": "01",
                    "unique_record_identifier": "20241015123456789#cb_2",
                    "acknowledgement_code": "42",
                    "contract_number": "12345",
                    "patient_first_name": "Stephen",
                    "patient_last_name": "Curry",
                    "patient_date_of_birth": "19880314",
                    "subscriber_last_name": "Curry",
                    "claim_start_date": "20241001",
                },
                {
                    "is_response": True,
                    "is_rejection": True,
                    "should_update": True,
                    "unique_id": "20241015123456789#cb_2",
                    "response_code": "42",
                    "response_reason": "Invalid Sender ID",
                },
            ),
            (
                # rejected (Other)
                {
                    "transaction_type": "01",
                    "unique_record_identifier": "20241015123456789#cb_3",
                    "acknowledgement_code": "99",
                    "contract_number": "12345",
                    "patient_first_name": "Stephen",
                    "patient_last_name": "Curry",
                    "patient_date_of_birth": "19880314",
                    "subscriber_last_name": "Curry",
                    "claim_start_date": "20241001",
                },
                {
                    "is_response": True,
                    "is_rejection": True,
                    "should_update": True,
                    "unique_id": "20241015123456789#cb_3",
                    "response_code": "99",
                    "response_reason": "Other error encountered",
                },
            ),
            (
                # Not response file
                {
                    "transaction_type": "00",
                    "unique_record_identifier": "20241015123456789#cb_7",
                    "acknowledgement_code": "00",
                    "contract_number": "12345",
                    "patient_first_name": "Stephen",
                    "patient_last_name": "Curry",
                    "patient_date_of_birth": "19880314",
                    "subscriber_last_name": "Curry",
                    "claim_start_date": "20241001",
                },
                {
                    "is_response": False,
                    "is_rejection": False,
                    "unique_id": "20241015123456789#cb_7",
                },
            ),
        ],
    )
    def test_get_detail_metadata_yoy_feature_flag_enabled(
        self,
        credence_file_generator,
        detail_record,
        expected_metadata,
        member_health_plan,
        mhp_yoy_feature_flag_enabled,
    ):
        metadata = credence_file_generator.get_detail_metadata(detail_record)
        for k, v in expected_metadata.items():
            assert getattr(metadata, k) == v
        assert metadata.member_id == str(member_health_plan.member_id)
