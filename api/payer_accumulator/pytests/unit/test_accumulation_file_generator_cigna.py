import datetime
import os
from io import StringIO

import factory
import overpunch
import pytest

from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from payer_accumulator.common import PayerName, TreatmentAccumulationStatus
from payer_accumulator.errors import InvalidPatientSexError, InvalidSubscriberIdError
from payer_accumulator.file_generators import AccumulationFileGeneratorCigna
from payer_accumulator.file_generators.fixedwidth.cigna import AccumulatorType
from payer_accumulator.pytests.factories import (
    AccumulationTreatmentMappingFactory,
    PayerFactory,
)
from pytests.freezegun import freeze_time
from wallet.models.constants import MemberHealthPlanPatientSex
from wallet.pytests.factories import MemberHealthPlanFactory


@pytest.fixture(scope="function")
def cost_breakdown_not_met_deductible():
    return CostBreakdownFactory.create(deductible=12_300, oop_applied=12_390)


@pytest.fixture(scope="function")
def cost_breakdown_met_deductible():
    return CostBreakdownFactory.create(deductible=0, oop_applied=12_300)


@pytest.fixture(scope="function")
def cost_breakdown_mr_0():
    return CostBreakdownFactory.create(deductible=0, oop_applied=0)


@pytest.fixture(scope="function")
def treatment_procedures_file_gen(
    member_health_plans,
    cost_breakdown_not_met_deductible,
    cost_breakdown_mr_0,
    cost_breakdown_met_deductible,
):
    return [
        TreatmentProcedureFactory.create(
            id=2001,
            start_date=datetime.datetime(2023, 1, 15),
            end_date=datetime.datetime(2023, 2, 15),
            member_id=1,
            reimbursement_wallet_id=5,
            cost_breakdown_id=cost_breakdown_not_met_deductible.id,
        ),
        TreatmentProcedureFactory.create(
            id=2002,
            start_date=datetime.datetime(2023, 6, 10),
            end_date=datetime.datetime(2023, 8, 25),
            member_id=1,
            reimbursement_wallet_id=5,
            cost_breakdown_id=cost_breakdown_mr_0.id,
        ),
        TreatmentProcedureFactory.create(
            id=2003,
            start_date=datetime.datetime(2023, 9, 9),
            end_date=datetime.datetime(2023, 11, 1),
            member_id=1,
            reimbursement_wallet_id=5,
        ),
        TreatmentProcedureFactory.create(
            id=2004,
            start_date=datetime.datetime(2023, 3, 15),
            end_date=datetime.datetime(2023, 4, 15),
            member_id=1,
            reimbursement_wallet_id=5,
            cost_breakdown_id=cost_breakdown_met_deductible.id,
        ),
    ]


@pytest.fixture(scope="function")
def accumulation_treatment_mappings_file_gen(
    cigna_file_generator, treatment_procedures_file_gen
):
    return AccumulationTreatmentMappingFactory.create_batch(
        size=4,
        payer_id=cigna_file_generator.payer_id,
        treatment_procedure_uuid=factory.Iterator(
            [
                treatment_procedures_file_gen[0].uuid,
                treatment_procedures_file_gen[1].uuid,
                treatment_procedures_file_gen[2].uuid,
                treatment_procedures_file_gen[3].uuid,
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
def cigna_payer():
    return PayerFactory.create(payer_name=PayerName.Cigna, payer_code="00192")


@pytest.fixture(scope="function")
@freeze_time("2023-11-09 14:08:09")
def cigna_file_generator(cigna_payer):
    return AccumulationFileGeneratorCigna()


@pytest.fixture(scope="function")
def expected_row_prefix():
    return {
        "member_pid": "U12345678" + " " * 6,
        "employee_pid": " " * 15,
        "employee_id": "0" * 9,
        "member_first_name": "ALICE" + " " * 10,
        "member_last_name": "PAUL" + " " * 31,
        "member_dob": "2000-01-01",
        "member_sex": "F",
        "relationship_code": "EE",
        "id_card_extension": "00",
        "date_of_service": "20230115",
        "client_number": "0" * 7,
        "account": "0" * 7,
        "branch": " " * 6,
        "benefit_option": " " * 5,
        "message_date": "20231109",
        "message_time": "14080900",
        "source_system": "M",
        "accumulation_counter": "0" * 3 + "2",
    }


def expected_row_accumulation(accumulator_type: AccumulatorType, amount: int):
    formatted_amount = overpunch.format(amount)
    return {
        "network_code": "I",
        "member_family_code": "M",
        "accumulator_type": accumulator_type.value,
        "oop_indicator": " ",
        "units_indicator": "D",
        "amount": "0" * (9 - len(str(formatted_amount))) + formatted_amount,
        "accumulation_balance": "00000000{",
    }


@pytest.fixture
def cigna_structured_detail_row():
    return {
        "member_pid": "U1234567801",
        "member_dob": "2000-01-01",
        "accumulation_counter": "0002",
        "accumulations": [
            {
                "accumulator_type": "D",
                "amount": "00000000{",
            },
            {
                "accumulator_type": "O",
                "amount": "00000725{",
            },
            {
                "accumulator_type": "D",
                "amount": "00000725{",
            },
            {
                "accumulator_type": "O",
                "amount": "00000725{",
            },
        ],
    }


@pytest.fixture
def cigna_structured_report_snippet(cigna_structured_detail_row):
    return [
        cigna_structured_detail_row,
        cigna_structured_detail_row,
        cigna_structured_detail_row,
    ]


class TestAccumulationFileGeneratorCigna:
    def test_generate_row_prefix(
        self,
        cigna_file_generator,
        treatment_procedures_file_gen,
        member_health_plans,
        cost_breakdown_not_met_deductible,
        expected_row_prefix,
    ):
        row_prefix = cigna_file_generator._generate_row_prefix(
            TreatmentProcedureType(treatment_procedures_file_gen[0].procedure_type),
            member_health_plans[0],
            treatment_procedures_file_gen[0].start_date,
        )
        for index, value in enumerate(cigna_file_generator.detail_config.values()):
            start_pos = value["start_pos"] - 1
            end_pos = value["end_pos"]
            assert (
                row_prefix[start_pos:end_pos]
                == list(expected_row_prefix.values())[index]
            )

    def test_generate_row_accumulations_not_met_deductible(
        self,
        cigna_file_generator,
        member_health_plans,
        cost_breakdown_not_met_deductible,
    ):
        row_accumulations = cigna_file_generator._generate_row_accumulations(
            cost_breakdown_not_met_deductible.deductible,
            cost_breakdown_not_met_deductible.oop_applied
            - cost_breakdown_not_met_deductible.deductible,
        )

        deductible_row_accumulation = cigna_file_generator._generate_row_accumulation(
            AccumulatorType.DEDUCTIBLE,
            cost_breakdown_not_met_deductible.deductible / 100,
        )

        oop_row_accumulation = cigna_file_generator._generate_row_accumulation(
            AccumulatorType.OOP, 0.9
        )

        assert row_accumulations == deductible_row_accumulation + oop_row_accumulation

    def test_generate_row_accumulations_met_deductible(
        self, cigna_file_generator, member_health_plans, cost_breakdown_met_deductible
    ):
        row_accumulations = cigna_file_generator._generate_row_accumulations(
            cost_breakdown_met_deductible.deductible,
            cost_breakdown_met_deductible.oop_applied
            - cost_breakdown_met_deductible.deductible,
        )

        deductible_row_accumulation = cigna_file_generator._generate_row_accumulation(
            AccumulatorType.DEDUCTIBLE,
            0,
        )

        oop_row_accumulation = cigna_file_generator._generate_row_accumulation(
            AccumulatorType.OOP,
            cost_breakdown_met_deductible.oop_applied / 100,
        )

        assert row_accumulations == deductible_row_accumulation + oop_row_accumulation

    def test_generate_row_accumulations_none_deductible_and_none_oop(
        self, cigna_file_generator
    ):
        row_accumulations = cigna_file_generator._generate_row_accumulations(None, None)

        deductible_row_accumulation = cigna_file_generator._generate_row_accumulation(
            AccumulatorType.DEDUCTIBLE,
            0,
        )

        oop_row_accumulation = cigna_file_generator._generate_row_accumulation(
            AccumulatorType.OOP, 0
        )

        assert row_accumulations == deductible_row_accumulation + oop_row_accumulation

    @pytest.mark.parametrize(
        argnames="accumulator_type",
        argvalues=(AccumulatorType.DEDUCTIBLE, AccumulatorType.OOP),
    )
    def test_generate_row_accumulation(self, cigna_file_generator, accumulator_type):
        amount = 123456
        row_accumulation = cigna_file_generator._generate_row_accumulation(
            accumulator_type, amount
        )
        expected_accumulation = expected_row_accumulation(accumulator_type, amount)
        for index, value in enumerate(
            cigna_file_generator.accumulation_config.values()
        ):
            start_pos = value["start_pos"] - 1
            end_pos = value["end_pos"]
            assert (
                row_accumulation[start_pos:end_pos]
                == list(expected_accumulation.values())[index]
            )

    def test_generate_detail(
        self,
        cigna_file_generator,
        treatment_procedures,
        member_health_plans,
        cost_breakdown_not_met_deductible,
    ):
        treatment_procedure = treatment_procedures[0]
        member_health_plan = member_health_plans[0]
        row_prefix = cigna_file_generator._generate_row_prefix(
            TreatmentProcedureType(treatment_procedure.procedure_type),
            member_health_plan,
            treatment_procedure.start_date,
        )
        row_accumulations = cigna_file_generator._generate_row_accumulations(
            cost_breakdown_not_met_deductible.deductible,
            cost_breakdown_not_met_deductible.oop_applied
            - cost_breakdown_not_met_deductible.deductible,
        )

        expected_detail = row_prefix + row_accumulations + "\r\n"

        detail = cigna_file_generator._generate_detail(
            record_id=treatment_procedures[0].id,
            record_type=TreatmentProcedureType(treatment_procedures[0].procedure_type),
            cost_breakdown=cost_breakdown_not_met_deductible,
            service_start_date=datetime.datetime.combine(
                treatment_procedures[0].start_date, datetime.time.min
            ),
            deductible=12_300,
            oop_applied=cigna_file_generator.get_oop_to_submit(12_300, 12_390),
            hra_applied=0,
            member_health_plan=member_health_plans[0],
        ).line
        assert expected_detail == detail

    def test_generate_detail_from_reimbursement_request(
        self,
        cigna_file_generator,
        cigna_payer,
        make_new_reimbursement_request_for_report_row,
        make_treatment_procedure_equivalent_to_reimbursement_request,
    ):
        reimbursement_request = make_new_reimbursement_request_for_report_row()
        member_health_plan = reimbursement_request.wallet.member_health_plan[0]

        (
            procedure,
            cost_breakdown,
        ) = make_treatment_procedure_equivalent_to_reimbursement_request(
            reimbursement_request=reimbursement_request,
            record_type=TreatmentProcedureType.MEDICAL,
            deductible_apply_amount=12_000,
            oop_apply_amount=12_300,
        )

        detail = cigna_file_generator.detail_to_dict(
            cigna_file_generator._generate_detail(
                record_id=reimbursement_request.id,
                record_type=TreatmentProcedureType.MEDICAL,
                cost_breakdown=cost_breakdown,
                service_start_date=reimbursement_request.service_start_date,
                member_health_plan=member_health_plan,
                deductible=12_000,
                oop_applied=12_300,
                hra_applied=0,
            ).line
        )

        procedure_detail = cigna_file_generator.detail_to_dict(
            cigna_file_generator._generate_detail(
                record_id=procedure.id,
                record_type=TreatmentProcedureType(procedure.procedure_type),
                cost_breakdown=cost_breakdown,
                service_start_date=datetime.datetime.combine(
                    procedure.start_date, datetime.time.min
                ),
                deductible=12_000,
                oop_applied=12_300,
                hra_applied=0,
                member_health_plan=member_health_plan,
            ).line
        )
        # assert for all keys that should match
        detail_accumulations = detail.pop("accumulations")
        procedure_accumulations = procedure_detail.pop("accumulations")
        assert detail == procedure_detail
        assert len(detail_accumulations) == len(procedure_accumulations)

    def test_get_record_count_from_buffer(
        self,
        cigna_file_generator,
    ):
        # given
        acc_file = "detail_row_one\r\ndetail_row_two\r\n"
        buffer = StringIO(acc_file)
        # when
        record_count = cigna_file_generator.get_record_count_from_buffer(buffer=buffer)
        expected_record_count = 2
        # then
        assert record_count == expected_record_count

    def test_file_name(self, cigna_file_generator):
        expected_file_name = "QXJ1000__qxj0001i.93827.20231109_140809.edi"
        assert cigna_file_generator.file_name == expected_file_name

    def test_get_member_sex(self):
        with pytest.raises(InvalidPatientSexError) as error:
            AccumulationFileGeneratorCigna.get_member_sex(
                MemberHealthPlanPatientSex.UNKNOWN
            )
        assert str(error.value) == "Patient sex must be female or male for Cigna"

        assert (
            AccumulationFileGeneratorCigna.get_member_sex(
                MemberHealthPlanPatientSex.FEMALE
            )
            == "F"
        )
        assert (
            AccumulationFileGeneratorCigna.get_member_sex(
                MemberHealthPlanPatientSex.MALE
            )
            == "M"
        )

    def test_generate_file(
        self,
        cigna_file_generator,
        member_health_plans,
        treatment_procedures_file_gen,
        cost_breakdown_not_met_deductible,
        accumulation_treatment_mappings_file_gen,
    ):
        file = cigna_file_generator.generate_file_contents()
        rows = file.getvalue().split("\r\n")
        rows.sort()  # ensure same order for testing against our file
        sample_file_path = os.path.join(
            os.path.dirname(__file__), f"../test_files/{cigna_file_generator.file_name}"
        )
        with open(sample_file_path, "r") as reader:
            content = reader.read()
            expected_rows = content.split("\n")
            expected_rows.sort()
            assert len(rows) == len(expected_rows)
            for _, (row, expected_row) in enumerate(zip(rows, expected_rows)):
                assert row == expected_row
        for mapping in accumulation_treatment_mappings_file_gen:
            if (
                mapping.treatment_accumulation_status
                == TreatmentAccumulationStatus.PROCESSED
            ):
                assert (
                    mapping.accumulation_transaction_id
                    == mapping.treatment_procedure_uuid
                )

    def test_file_contents_to_dicts(
        self,
        cigna_file_generator,
        member_health_plans,
        treatment_procedures_file_gen,
        cost_breakdown_not_met_deductible,
        accumulation_treatment_mappings_file_gen,
    ):
        file = cigna_file_generator.generate_file_contents()
        file_contents = file.getvalue()
        file_dicts = cigna_file_generator.file_contents_to_dicts(file_contents)
        file_dicts.sort(reverse=True, key=lambda x: x["accumulations"][0]["amount"])
        assert file_dicts == [
            {
                "account": "0000000",
                "accumulation_counter": "0002",
                "accumulations": [
                    {
                        "accumulation_balance": "00000000{",
                        "accumulator_type": "D",
                        "amount": "00001230{",
                        "member_family_code": "M",
                        "network_code": "I",
                        "oop_indicator": " ",
                        "units_indicator": "D",
                    },
                    {
                        "accumulation_balance": "00000000{",
                        "accumulator_type": "O",
                        "amount": "00000009{",
                        "member_family_code": "M",
                        "network_code": "I",
                        "oop_indicator": " ",
                        "units_indicator": "D",
                    },
                ],
                "benefit_option": "",
                "branch": "",
                "client_number": "0000000",
                "date_of_service": "20230115",
                "employee_id": "000000000",
                "employee_pid": "",
                "id_card_extension": "00",
                "member_dob": "2000-01-01",
                "member_first_name": "ALICE",
                "member_last_name": "PAUL",
                "member_pid": "U12345678",
                "member_sex": "F",
                "message_date": "20231109",
                "message_time": "14080900",
                "relationship_code": "EE",
                "source_system": "M",
            },
            {
                "account": "0000000",
                "accumulation_counter": "0002",
                "accumulations": [
                    {
                        "accumulation_balance": "00000000{",
                        "accumulator_type": "D",
                        "amount": "00001000}",
                        "member_family_code": "M",
                        "network_code": "I",
                        "oop_indicator": " ",
                        "units_indicator": "D",
                    },
                    {
                        "accumulation_balance": "00000000{",
                        "accumulator_type": "O",
                        "amount": "00001000}",
                        "member_family_code": "M",
                        "network_code": "I",
                        "oop_indicator": " ",
                        "units_indicator": "D",
                    },
                ],
                "benefit_option": "",
                "branch": "",
                "client_number": "0000000",
                "date_of_service": "20230315",
                "employee_id": "000000000",
                "employee_pid": "",
                "id_card_extension": "00",
                "member_dob": "2000-01-01",
                "member_first_name": "ALICE",
                "member_last_name": "PAUL",
                "member_pid": "U12345678",
                "member_sex": "F",
                "message_date": "20231109",
                "message_time": "14080900",
                "relationship_code": "EE",
                "source_system": "M",
            },
        ]

    def test__trim_employee_id(self, employer_health_plan):
        mhp = MemberHealthPlanFactory.create(
            subscriber_insurance_id="U1234567801",
            employer_health_plan=employer_health_plan,
            employer_health_plan_id=employer_health_plan.id,
        )
        assert AccumulationFileGeneratorCigna.get_cardholder_id(mhp) == "U12345678"

    def test__trim_employee_id_fails(self, employer_health_plan):
        mhp = MemberHealthPlanFactory.create(
            subscriber_insurance_id="U1234567891011",
            employer_health_plan=employer_health_plan,
            employer_health_plan_id=employer_health_plan.id,
        )
        with pytest.raises(InvalidSubscriberIdError) as e:
            AccumulationFileGeneratorCigna.get_cardholder_id(mhp)
        assert str(e.value) == "Cigna subscriber_insurance_id should be 11 digits."

    def test_get_cardholder_id_from_detail_dict(
        self, cigna_file_generator, cigna_structured_detail_row
    ):
        assert "U1234567801" == cigna_file_generator.get_cardholder_id_from_detail_dict(
            detail_row_dict=cigna_structured_detail_row
        )

    def test_get_dob_from_report_row(
        self, cigna_file_generator, cigna_structured_detail_row
    ):
        assert cigna_file_generator.get_dob_from_report_row(
            detail_row_dict=cigna_structured_detail_row
        ) == datetime.date(2000, 1, 1)

    def test_get_detail_rows(
        self, cigna_file_generator, cigna_structured_report_snippet
    ):
        assert 3 == len(
            cigna_file_generator.get_detail_rows(
                report_rows=cigna_structured_report_snippet
            )
        )
