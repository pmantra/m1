import datetime
import os

import factory
import pytest
from freezegun import freeze_time

from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from payer_accumulator.common import PayerName, TreatmentAccumulationStatus
from payer_accumulator.errors import NoHealthPlanFoundError
from payer_accumulator.file_generators.csv.bcbs_ma import (
    AccumulationCSVFileGeneratorBCBSMA,
)
from payer_accumulator.pytests.factories import (
    AccumulationTreatmentMappingFactory,
    PayerFactory,
)
from pytests import factories
from wallet.models.constants import MemberHealthPlanPatientSex
from wallet.pytests.factories import (
    EmployerHealthPlanFactory,
    MemberHealthPlanFactory,
    ReimbursementWalletFactory,
)


@pytest.fixture(scope="function")
def cost_breakdown_not_met_deductible():
    return CostBreakdownFactory.create(deductible=12300, oop_applied=12390)


@pytest.fixture(scope="function")
def cost_breakdown_met_deductible():
    return CostBreakdownFactory.create(deductible=0, oop_applied=12300)


@pytest.fixture(scope="function")
def cost_breakdown_mr_0():
    return CostBreakdownFactory.create(deductible=0, oop_applied=0)


@pytest.fixture(scope="function")
def member_health_plans(enterprise_user, employer_health_plan):
    return [
        MemberHealthPlanFactory.create(
            employer_health_plan_id=employer_health_plan.id,
            reimbursement_wallet=ReimbursementWalletFactory.create(id=5),
            employer_health_plan=employer_health_plan,
            reimbursement_wallet_id=5,
            is_subscriber=True,
            patient_sex=MemberHealthPlanPatientSex.FEMALE,
            member_id=enterprise_user.id,
            subscriber_insurance_id="U12345678",
            patient_first_name="ALICE",
            patient_last_name="PAUL",
            patient_date_of_birth=datetime.datetime(2000, 1, 1),
        )
    ]


@pytest.fixture(scope="function")
def treatment_procedures_file_gen(
    member_health_plans,
    cost_breakdown_not_met_deductible,
    cost_breakdown_mr_0,
    cost_breakdown_met_deductible,
):
    return [
        TreatmentProcedureFactory.create(
            start_date=datetime.datetime(2023, 1, 15),
            end_date=datetime.datetime(2023, 2, 15),
            member_id=member_health_plans[0].member_id,
            reimbursement_wallet_id=member_health_plans[0].reimbursement_wallet_id,
            cost_breakdown_id=cost_breakdown_not_met_deductible.id,
        ),
        TreatmentProcedureFactory.create(
            start_date=datetime.datetime(2023, 6, 10),
            end_date=datetime.datetime(2023, 8, 25),
            member_id=member_health_plans[0].member_id,
            reimbursement_wallet_id=member_health_plans[0].reimbursement_wallet_id,
            cost_breakdown_id=cost_breakdown_mr_0.id,
        ),
        TreatmentProcedureFactory.create(
            start_date=datetime.datetime(2023, 9, 9),
            end_date=datetime.datetime(2023, 11, 1),
            member_id=member_health_plans[0].member_id,
            reimbursement_wallet_id=member_health_plans[0].reimbursement_wallet_id,
        ),
        TreatmentProcedureFactory.create(
            start_date=datetime.datetime(2023, 3, 15),
            end_date=datetime.datetime(2023, 4, 15),
            member_id=member_health_plans[0].member_id,
            reimbursement_wallet_id=member_health_plans[0].reimbursement_wallet_id,
            cost_breakdown_id=cost_breakdown_met_deductible.id,
        ),
    ]


@pytest.fixture(scope="function")
def accumulation_treatment_mappings_file_gen(
    bcbs_ma_file_generator, treatment_procedures_file_gen
):
    return AccumulationTreatmentMappingFactory.create_batch(
        size=4,
        payer_id=bcbs_ma_file_generator.payer_id,
        treatment_procedure_uuid=factory.Iterator(
            [
                treatment_procedures_file_gen[
                    0
                ].uuid,  # Will be PAID -> generates "New" row
                treatment_procedures_file_gen[
                    1
                ].uuid,  # Will be PAID -> generates "New" row
                treatment_procedures_file_gen[2].uuid,  # Will be WAITING -> no row
                treatment_procedures_file_gen[
                    3
                ].uuid,  # Will be REFUNDED -> generates "Reversal" row
            ]
        ),
        treatment_accumulation_status=factory.Iterator(
            [
                TreatmentAccumulationStatus.PAID,  # Generates "New" row with values from CB
                TreatmentAccumulationStatus.PAID,  # Skipped because CB has 0 deductible and oop
                TreatmentAccumulationStatus.WAITING,  # Skipped
                TreatmentAccumulationStatus.REFUNDED,  # Generates "Reversal" row
            ]
        ),
        deductible=factory.Iterator([None, None, None, 10000]),
        oop_applied=factory.Iterator([None, None, None, 10000]),
    )


@pytest.fixture(scope="function")
def bcbs_ma_payer():
    return PayerFactory.create(payer_name=PayerName.BCBS_MA, payer_code="00193")


@pytest.fixture(scope="function")
@freeze_time("2023-11-09 14:08:09")
def bcbs_ma_file_generator(bcbs_ma_payer):
    return AccumulationCSVFileGeneratorBCBSMA()


@pytest.fixture(scope="function")
@freeze_time("2023-11-09 14:08:09")
def bcbs_ma_file_generator_with_health_plan(bcbs_ma_payer):
    return AccumulationCSVFileGeneratorBCBSMA(health_plan_name="HUGHP")


@pytest.fixture(scope="function")
def bcbs_ma_hughp_health_plan(bcbs_ma_payer):
    return EmployerHealthPlanFactory.create(
        name="TestHUGHPEmployerPlan", benefits_payer_id=bcbs_ma_payer.id
    )


@pytest.fixture(scope="function")
def sample_file_path(bcbs_ma_file_generator):
    return os.path.join(
        os.path.dirname(__file__),
        f"../test_files/{bcbs_ma_file_generator.file_name}",
    )


class TestAccumulationFileGeneratorBCBSMA:
    def test_file_name(self, bcbs_ma_file_generator):
        expected_file_name = "Maven_20231109140809.csv"
        assert bcbs_ma_file_generator.file_name == expected_file_name

    def test_file_name_with_health_plan(self, bcbs_ma_file_generator_with_health_plan):
        expected_file_name = "Maven_HUGHP20231109140809.csv"
        assert bcbs_ma_file_generator_with_health_plan.file_name == expected_file_name

    def test_generate_header(self, bcbs_ma_file_generator):
        expected_header = (
            "MemberID,MemberFirstName,MemberLastName,MemberDateofBirth,CalendarYearOfAccum,"
            'DateOfService,"InNetworkIndividualDeductibleAppliedby""Vendor""",'
            '"InNetworkFamilyDeductibleAppliedby""Vendor""",'
            '"InNetworkIndividualOOPAppliedby""Vendor""",'
            '"InNetworkFamilyOOPAppliedby""Vendor""",'
            '"OutOfNetworkIndividualDeductibleAppliedby""Vendor""",'
            '"OutOfNetworkFamilyDeductibleAppliedby""Vendor""",'
            '"OutOfNetworkIndividualOOPAppliedby""Vendor""",'
            '"OutOfNetworkFamilyOOPAppliedby""Vendor""",Notes,TypeOfClaim'
        )
        assert bcbs_ma_file_generator._generate_header() == expected_header

    def test_generate_detail_not_met_deductible(
        self,
        bcbs_ma_file_generator,
        member_health_plans,
        cost_breakdown_not_met_deductible,
    ):
        detail = bcbs_ma_file_generator._generate_detail(
            record_id=1,
            record_type=TreatmentProcedureType.MEDICAL,
            cost_breakdown=cost_breakdown_not_met_deductible,
            service_start_date=datetime.datetime(2023, 1, 15),
            deductible=12300,
            oop_applied=12390,
            hra_applied=0,
            member_health_plan=member_health_plans[0],
            is_reversal=False,
            is_regeneration=False,
            sequence_number=1,
        ).line

        expected_fields = [
            "U12345678",  # MemberID
            "ALICE",  # MemberFirstName
            "PAUL",  # MemberLastName
            "01/01/2000",  # MemberDateofBirth
            "2023",  # CalendarYearOfAccum
            "01/15/2023",  # DateOfService
            "123.00",  # InNetworkIndividualDeductible
            "",  # InNetworkFamilyDeductible
            "123.90",  # InNetworkIndividualOOP
            "",  # InNetworkFamilyOOP
            "",  # OutOfNetworkIndividualDeductible
            "",  # OutOfNetworkFamilyDeductible
            "",  # OutOfNetworkIndividualOOP
            "",  # OutOfNetworkFamilyOOP
            "",  # Notes
            "New",  # TypeOfClaim
        ]
        assert detail == ",".join(expected_fields)

    def test_generate_detail_met_deductible(
        self,
        bcbs_ma_file_generator,
        member_health_plans,
        cost_breakdown_met_deductible,
    ):
        detail = bcbs_ma_file_generator._generate_detail(
            record_id=1,
            record_type=TreatmentProcedureType.MEDICAL,
            cost_breakdown=cost_breakdown_met_deductible,
            service_start_date=datetime.datetime(2023, 1, 15),
            deductible=0,
            oop_applied=12300,
            hra_applied=0,
            member_health_plan=member_health_plans[0],
            is_reversal=False,
            is_regeneration=False,
            sequence_number=1,
        ).line

        expected_fields = [
            "U12345678",  # MemberID
            "ALICE",  # MemberFirstName
            "PAUL",  # MemberLastName
            "01/01/2000",  # MemberDateofBirth
            "2023",  # CalendarYearOfAccum
            "01/15/2023",  # DateOfService
            "0.00",  # InNetworkIndividualDeductible
            "",  # InNetworkFamilyDeductible
            "123.00",  # InNetworkIndividualOOP
            "",  # InNetworkFamilyOOP
            "",  # OutOfNetworkIndividualDeductible
            "",  # OutOfNetworkFamilyDeductible
            "",  # OutOfNetworkIndividualOOP
            "",  # OutOfNetworkFamilyOOP
            "",  # Notes
            "New",  # TypeOfClaim
        ]
        assert detail == ",".join(expected_fields)

    def test_generate_detail_reversal(
        self,
        bcbs_ma_file_generator,
        member_health_plans,
        cost_breakdown_not_met_deductible,
    ):
        detail = bcbs_ma_file_generator._generate_detail(
            record_id=1,
            record_type=TreatmentProcedureType.MEDICAL,
            cost_breakdown=cost_breakdown_not_met_deductible,
            service_start_date=datetime.datetime(2023, 1, 15),
            deductible=12300,
            oop_applied=12390,
            hra_applied=0,
            member_health_plan=member_health_plans[0],
            is_reversal=True,
            is_regeneration=False,
            sequence_number=1,
        ).line

        expected_fields = [
            "U12345678",  # MemberID
            "ALICE",  # MemberFirstName
            "PAUL",  # MemberLastName
            "01/01/2000",  # MemberDateofBirth
            "2023",  # CalendarYearOfAccum
            "01/15/2023",  # DateOfService
            "-123.00",  # InNetworkIndividualDeductible
            "",  # InNetworkFamilyDeductible
            "-123.90",  # InNetworkIndividualOOP
            "",  # InNetworkFamilyOOP
            "",  # OutOfNetworkIndividualDeductible
            "",  # OutOfNetworkFamilyDeductible
            "",  # OutOfNetworkIndividualOOP
            "",  # OutOfNetworkFamilyOOP
            "",  # Notes
            "Reversal",  # TypeOfClaim
        ]
        assert detail == ",".join(expected_fields)

    def test_generate_file(
        self,
        bcbs_ma_file_generator,
        member_health_plans,
        treatment_procedures_file_gen,
        cost_breakdown_not_met_deductible,
        accumulation_treatment_mappings_file_gen,
        sample_file_path,
    ):
        file = bcbs_ma_file_generator.generate_file_contents()
        # Strip any whitespace and newlines, then split on newlines and filter empty rows
        rows = [row.strip() for row in file.getvalue().split("\n") if row.strip()]
        rows.sort()  # ensure same order for testing against our file

        with open(sample_file_path, "r") as reader:
            content = reader.read()
            # Strip any whitespace and newlines from expected rows too
            expected_rows = [row.strip() for row in content.split("\n") if row.strip()]
            expected_rows.sort()
            assert len(rows) == len(expected_rows)
            for _, (row, expected_row) in enumerate(zip(rows, expected_rows)):
                assert row == expected_row
        for mapping in accumulation_treatment_mappings_file_gen:
            if mapping.treatment_accumulation_status in (
                TreatmentAccumulationStatus.PAID,
                TreatmentAccumulationStatus.REFUNDED,
            ):
                assert (
                    mapping.accumulation_transaction_id
                    == mapping.treatment_procedure_uuid
                )

    def test_generate_file_contents_with_health_plan(
        self,
        bcbs_ma_file_generator_with_health_plan,
        cost_breakdown_not_met_deductible,
        cost_breakdown_met_deductible,
        bcbs_ma_payer,
        enterprise_user,
        employer_health_plan,
    ):
        second_enterprise_user = factories.EnterpriseUserFactory.create()
        # Create a second health plan that matches the health plan name
        second_health_plan = EmployerHealthPlanFactory.create(
            name="HUGHP",
            reimbursement_org_settings_id=employer_health_plan.reimbursement_org_settings_id,
            start_date=datetime.datetime(2023, 1, 1),
            end_date=datetime.datetime(2023, 12, 31),
            benefits_payer_id=bcbs_ma_payer.id,
        )

        # Create member health plans for both health plans
        member_health_plan_1 = MemberHealthPlanFactory.create(
            member_id=second_enterprise_user.id,
            employer_health_plan=employer_health_plan,
            reimbursement_wallet=ReimbursementWalletFactory.create(),
            is_subscriber=True,
        )
        member_health_plan_2 = MemberHealthPlanFactory.create(
            member_id=enterprise_user.id,
            employer_health_plan=second_health_plan,
            reimbursement_wallet=ReimbursementWalletFactory.create(),
            is_subscriber=True,
        )

        # Create treatment procedures for both health plans
        treatment_procedure_1 = TreatmentProcedureFactory.create(
            member_id=second_enterprise_user.id,
            reimbursement_wallet_id=member_health_plan_1.reimbursement_wallet_id,  # HUGHP health plan
            start_date=datetime.datetime(2023, 11, 9),
            end_date=datetime.datetime(2023, 11, 9),
            cost_breakdown_id=cost_breakdown_met_deductible.id,
        )
        treatment_procedure_2 = TreatmentProcedureFactory.create(
            member_id=enterprise_user.id,
            reimbursement_wallet_id=member_health_plan_2.reimbursement_wallet_id,  # Original health plan
            start_date=datetime.datetime(2023, 11, 9),
            end_date=datetime.datetime(2023, 11, 9),
            cost_breakdown_id=cost_breakdown_not_met_deductible.id,
        )

        # Create accumulation mappings for both procedures
        AccumulationTreatmentMappingFactory.create(
            treatment_procedure_uuid=treatment_procedure_1.uuid,
            payer_id=bcbs_ma_payer.id,
            treatment_accumulation_status=TreatmentAccumulationStatus.PAID,
            deductible=0,
            oop_applied=12390,
        )
        AccumulationTreatmentMappingFactory.create(
            treatment_procedure_uuid=treatment_procedure_2.uuid,
            payer_id=bcbs_ma_payer.id,
            treatment_accumulation_status=TreatmentAccumulationStatus.PAID,
            deductible=12300,
            oop_applied=12300,
        )

        # Generate file contents - should only include records for employer_health_plan
        file_contents = bcbs_ma_file_generator_with_health_plan.generate_file_contents()

        # Verify file structure
        lines = file_contents.getvalue().strip().split("\n")
        assert len(lines) == 2  # Header + 1 detail record (not 2)

        # Verify header
        header = lines[0]
        assert "MemberID" in header
        assert "DateOfService" in header

        # Verify detail record is for the correct health plan
        detail = lines[1].split(",")
        assert len(detail) > 0
        assert (
            str(member_health_plan_2.subscriber_insurance_id) in detail[0]
        )  # Member ID from HUGHP health plan
        assert "11/09/2023" in detail[5]  # Date of service
        assert (
            "123.00" in detail[6]
        )  # Deductible amount from cost_breakdown_not_met_deductible

    def test_get_health_plan_ids_valid(
        self, bcbs_ma_file_generator, bcbs_ma_hughp_health_plan
    ):
        health_plan_name = "HUGHP"
        health_plan_ids = bcbs_ma_file_generator._get_health_plan_ids(health_plan_name)
        assert len(health_plan_ids) == 1  # Ensure that health plan IDs are returned

    def test_get_health_plan_ids_invalid(
        self, bcbs_ma_file_generator, bcbs_ma_hughp_health_plan
    ):
        health_plan_name = "InvalidHealthPlan"
        with pytest.raises(NoHealthPlanFoundError):
            bcbs_ma_file_generator._get_health_plan_ids(health_plan_name)
