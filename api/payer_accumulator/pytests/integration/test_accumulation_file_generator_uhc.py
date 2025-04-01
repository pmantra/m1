import os
from datetime import datetime, timedelta
from unittest import mock

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
from payer_accumulator.file_generators import AccumulationFileGeneratorUHC
from payer_accumulator.file_handler import AccumulationFileHandler
from payer_accumulator.models.payer_accumulation_reporting import (
    PayerAccumulationReports,
)
from payer_accumulator.pytests.factories import (
    AccumulationTreatmentMappingFactory,
    PayerFactory,
)
from pytests.freezegun import freeze_time
from wallet.models.constants import (
    FamilyPlanType,
    MemberHealthPlanPatientRelationship,
    MemberHealthPlanPatientSex,
    WalletState,
)
from wallet.pytests.factories import (
    EmployerHealthPlanFactory,
    MemberHealthPlanFactory,
    ReimbursementOrganizationSettingsFactory,
    ReimbursementWalletFactory,
)

CURRENT_DIR = os.path.dirname(__file__)


@pytest.fixture(scope="function")
def payer(app_context):
    return PayerFactory.create(id=123457, payer_name=PayerName.UHC, payer_code="00192")


@pytest.fixture(scope="function")
def uhc_file_generator(payer):
    return AccumulationFileGeneratorUHC()


@pytest.fixture(scope="function")
def cost_breakdown_factory():
    def _cost_breakdown_factory(
        total_member_responsibility,
        deductible,
        oop_applied,
        oop_remaining,
        deductible_remaining,
    ):
        return CostBreakdownFactory.create(
            total_member_responsibility=total_member_responsibility,
            deductible=deductible,
            oop_applied=oop_applied,
            oop_remaining=oop_remaining,
            deductible_remaining=deductible_remaining,
        )

    return _cost_breakdown_factory


@pytest.fixture(scope="function")
def member_health_plan_factory():
    def _member_health_plan_factory(
        employer_health_plan,
        patient_is_subscriber,
        patient_is_on_individual_plan,
        patient_relationship,
        patient_sex,
    ):
        return MemberHealthPlanFactory.create(
            employer_health_plan_id=employer_health_plan.id,
            reimbursement_wallet=ReimbursementWalletFactory.create(
                id=5, state=WalletState.QUALIFIED
            ),
            employer_health_plan=employer_health_plan,
            reimbursement_wallet_id=5,
            plan_type=FamilyPlanType.INDIVIDUAL
            if patient_is_on_individual_plan
            else FamilyPlanType.FAMILY,
            is_subscriber=patient_is_subscriber,
            patient_sex=patient_sex,
            patient_date_of_birth=datetime.strptime("14/02/1987", "%d/%m/%Y"),
            patient_relationship=patient_relationship,
            member_id=1,
            subscriber_insurance_id="U1234567801",
        )

    return _member_health_plan_factory


@pytest.fixture(scope="function")
def employer_health_plan_factory():
    def _employer_health_plan_factory(
        ind_deductible_limit, ind_oop_max_limit, fam_deductible_limit, fam_oop_max_limit
    ):
        org_settings = ReimbursementOrganizationSettingsFactory.create(
            organization_id=987,
        )
        return EmployerHealthPlanFactory.create(
            reimbursement_organization_settings=org_settings,
            ind_deductible_limit=ind_deductible_limit,
            ind_oop_max_limit=ind_oop_max_limit,
            fam_deductible_limit=fam_deductible_limit,
            fam_oop_max_limit=fam_oop_max_limit,
        )

    return _employer_health_plan_factory


@pytest.fixture(scope="function")
def setup_factory(
    member_health_plan_factory,
    employer_health_plan_factory,
    cost_breakdown_factory,
):
    """
    This factory will set up the basic data need in order to generate an accumulation file with a header, detail, and trailer rows.

    NOTE: will only create at most one detail row. Can be modified to create multiple detail rows if needed.
    """

    def _setup_factory(
        payer_id,
        ind_deductible_limit,
        ind_oop_max_limit,
        fam_deductible_limit,
        fam_oop_max_limit,
        patient_is_subscriber,
        patient_is_on_individual_plan,
        total_member_responsibility,
        deductible,
        oop_applied,
        oop_remaining,
        deductible_remaining,
        patient_relationship,
        patient_sex,
    ):
        employer_health_plan = employer_health_plan_factory(
            ind_deductible_limit,
            ind_oop_max_limit,
            fam_deductible_limit,
            fam_oop_max_limit,
        )

        member_health_plan_factory(
            employer_health_plan,
            patient_is_subscriber,
            patient_is_on_individual_plan,
            patient_relationship,
            patient_sex,
        )

        cost_breakdown = cost_breakdown_factory(
            total_member_responsibility,
            deductible,
            oop_applied,
            oop_remaining,
            deductible_remaining,
        )

        treatment_procedure = TreatmentProcedureFactory.create(
            id=1001,
            start_date=datetime(2023, 2, 15),
            end_date=datetime(2023, 3, 15),
            member_id=1,
            reimbursement_wallet_id=5,
            cost_breakdown_id=cost_breakdown.id,
            procedure_type=TreatmentProcedureType.MEDICAL,
        )

        AccumulationTreatmentMappingFactory.create(
            payer_id=payer_id,
            treatment_procedure_uuid=treatment_procedure.uuid,
            treatment_accumulation_status=TreatmentAccumulationStatus.PAID,
        )

        return treatment_procedure

    return _setup_factory


@pytest.fixture(scope="function")
def treatment_procedures__use_case_multiple_rows():
    # Setup Employer Health Plan, Member Health Plan, and 8 Costbreakdowns
    individual_deductible_limit = 50000
    ind_oop_max = 200000
    family_deductible_limit = 300000
    family_oop_max = 500000

    org_settings = ReimbursementOrganizationSettingsFactory.create(
        organization_id=987,
    )
    employer_health_plan = EmployerHealthPlanFactory.create(
        reimbursement_organization_settings=org_settings,
        ind_deductible_limit=individual_deductible_limit,
        ind_oop_max_limit=ind_oop_max,
        fam_deductible_limit=family_deductible_limit,
        fam_oop_max_limit=family_oop_max,
    )

    patient_is_subscriber = True
    patient_is_on_family_plan = False
    member_id = 1
    MemberHealthPlanFactory.create(
        employer_health_plan_id=employer_health_plan.id,
        reimbursement_wallet=ReimbursementWalletFactory.create(
            id=5, state=WalletState.QUALIFIED
        ),
        employer_health_plan=employer_health_plan,
        reimbursement_wallet_id=5,
        plan_type=FamilyPlanType.FAMILY
        if patient_is_on_family_plan
        else FamilyPlanType.INDIVIDUAL,
        is_subscriber=patient_is_subscriber,
        patient_sex=MemberHealthPlanPatientSex.FEMALE,
        patient_date_of_birth=datetime.strptime("14/02/1987", "%d/%m/%Y"),
        patient_relationship=MemberHealthPlanPatientRelationship.CARDHOLDER,
        member_id=member_id,
        subscriber_insurance_id="U1234567801",
    )
    cost_breakdowns = CostBreakdownFactory.create_batch(
        size=8,
        deductible=factory.Iterator([-10000, 432100, -5292, 0, 3329, 120009, 0, 0]),
        oop_applied=factory.Iterator(
            [-10000, 432100, -5292, 1181, 3329, 0, 210105, 96102]
        ),
    )
    return TreatmentProcedureFactory.create_batch(
        size=len(cost_breakdowns),
        start_date=datetime(2023, 2, 15),
        end_date=datetime(2023, 3, 15),
        member_id=member_id,
        reimbursement_wallet_id=5,
        cost_breakdown_id=factory.Iterator([cb.id for cb in cost_breakdowns]),
        procedure_type=TreatmentProcedureType.MEDICAL,
    )


@pytest.fixture(scope="function")
def accumulation_treatment_mappings__use_case_multiple_rows(
    uhc_file_generator, treatment_procedures__use_case_multiple_rows
):
    def generate_timestamps(start_time: datetime, increment_by, count):
        current_time = start_time
        for _ in range(count):
            yield current_time
            current_time += increment_by

    time = datetime.utcnow()
    one_day = timedelta(days=1)

    return AccumulationTreatmentMappingFactory.create_batch(
        size=len(treatment_procedures__use_case_multiple_rows),
        payer_id=uhc_file_generator.payer_id,
        treatment_procedure_uuid=factory.Iterator(
            [txt_proc.uuid for txt_proc in treatment_procedures__use_case_multiple_rows]
        ),
        treatment_accumulation_status=factory.Iterator(
            [TreatmentAccumulationStatus.PAID for _ in range(8)]
        ),
        created_at=factory.Iterator(
            generate_timestamps(start_time=time, increment_by=one_day, count=8)
        ),
    )


@pytest.fixture(scope="function")
def uhc_file_generator_factory(uhc_payer):
    def uhc_file_generator(time_stamp):
        @freeze_time(time_to_freeze=time_stamp)
        def _uhc_file_generator():
            accumulation_file_generator_uhc = AccumulationFileGeneratorUHC()
            return accumulation_file_generator_uhc

        return _uhc_file_generator()

    return uhc_file_generator


@pytest.fixture(autouse=True)
def patch_local_file_bucket():
    with mock.patch(
        "payer_accumulator.file_handler.LOCAL_FILE_BUCKET",
        "./payer_accumulator/pytests/test_files/",
    ):
        yield


class TestAccumulationFileGeneratorUHC:
    """
    These tests are based off these use cases: https://docs.google.com/spreadsheets/d/1EnDthIOgcY83fFNro2P1q8qn--iH3PfDJKA3YvG2Zos/edit#gid=0
    """

    # fmt: off
    @pytest.mark.parametrize(
        argnames="time_stamp, patient_is_subscriber, patient_relationship, patient_is_on_family_plan, "
        "patient_sex, ind_deductible_limit, ind_oop_max, family_deductible_limit, family_oop_max, total_member_responsibility,deductible, oop_applied,oop_remaining,deductible_remaining, "
        "expected_file_name,expected_ded_apply_amount,expected_oop_apply_amount, expected_patient_relationship_code, expected_rows",
        argvalues=[
            (
                "2024-3-01 12:24:48", True, MemberHealthPlanPatientRelationship.CARDHOLDER, False,
                MemberHealthPlanPatientSex.FEMALE, 50000, 200000, 300000, 500000, 10000, 10000, 10000, 40000, 190000,
                "Maven_UHC_Accumulator_File_20240301_122448", "1000{", "1000{", "1", 3,
            ),
            (
                "2024-4-01 12:24:48", True, MemberHealthPlanPatientRelationship.CARDHOLDER, True,
                MemberHealthPlanPatientSex.FEMALE, 50000, 200000, 300000, 500000, 20000, 20000, 20000, 470000, 270000,
                "Maven_UHC_Accumulator_File_20240401_122448", "2000{", "2000{", "1", 3,
            ),
            (
                "2024-5-01 12:24:48", False, MemberHealthPlanPatientRelationship.OTHER, True,
                MemberHealthPlanPatientSex.FEMALE, 50000, 200000, 300000, 500000, 10000, 10000, 10000, 490000, 290000,
                "Maven_UHC_Accumulator_File_20240501_122448", "1000{", "1000{", "4", 3,
            ),
            (
                "2024-6-01 12:24:48", False, MemberHealthPlanPatientRelationship.CARDHOLDER, True,
                MemberHealthPlanPatientSex.UNKNOWN, 50000, 200000, 300000, 500000, 10000, 10000, 10000, 490000, 290000,
                "Maven_UHC_Accumulator_File_20240601_122448", "1000{", "1000{", "1", 3,
            ),
            (
                "2024-7-01 12:24:48", True, MemberHealthPlanPatientRelationship.CARDHOLDER, False,
                MemberHealthPlanPatientSex.FEMALE, 50000, 200000, 300000, 500000, 0, 0, 0, 200000, 50000,
                "Maven_UHC_Accumulator_File_20240701_122448", "", "", "", 2,
            ),
            (
                "2024-8-01 12:24:48", True, MemberHealthPlanPatientRelationship.CARDHOLDER, False,
                MemberHealthPlanPatientSex.FEMALE, 50000, 200000, 300000, 500000, 10000, 0, 10000, 140000, 0,
                "Maven_UHC_Accumulator_File_20240801_122448", "0000{", "1000{", "1", 3,
            ),
            (
                "2024-9-01 12:24:48", True, MemberHealthPlanPatientRelationship.CARDHOLDER, False,
                MemberHealthPlanPatientSex.FEMALE, 50000, 200000, 300000, 500000, 0, 0, 0, 0, 0,
                "Maven_UHC_Accumulator_File_20240901_122448", "", "", "", 2,
            ),
            (
                "2024-10-01 12:24:48", True, MemberHealthPlanPatientRelationship.CARDHOLDER, False,
                MemberHealthPlanPatientSex.FEMALE, None, 200000, None, 500000, 10000, 0, 10000, 190000, 0,
                "Maven_UHC_Accumulator_File_20241001_122448", "0000{", "1000{", "1", 3,
            ),
            (
                "2024-11-01 12:24:48", True, MemberHealthPlanPatientRelationship.CARDHOLDER, False,
                MemberHealthPlanPatientSex.FEMALE, None, None, None, None, 0, 0, 0, 0, 0,
                "Maven_UHC_Accumulator_File_20241101_122448", "", "", "", 2,
            ),
            (
                "2024-12-01 12:24:48", True, MemberHealthPlanPatientRelationship.CARDHOLDER, False,
                MemberHealthPlanPatientSex.FEMALE, 50000, 200000, 300000, 500000, -10000, -10000, -10000, 200000, 50000,
                "Maven_UHC_Accumulator_File_20241201_122448", "1000}", "1000}", "1", 3,
            ),
        ],
        # fmt: on
        ids=[
            "use_case_one", "use_case_two", "use_case_three",
            "use_case_four", "use_case_five", "use_case_six",
            "use_case_seven", "use_case_eight", "use_case_nine",
            "use_case_ten",
        ],
    )
    def test_file_generated__single_detail_row(
        self,
        uhc_file_generator_factory,
        setup_factory,
        time_stamp,
        patient_is_subscriber,
        patient_relationship,
        patient_is_on_family_plan,
        patient_sex,
        ind_deductible_limit,
        ind_oop_max,
        family_deductible_limit,
        family_oop_max,
        total_member_responsibility,
        deductible,
        oop_applied,
        oop_remaining,
        deductible_remaining,
        expected_file_name,
        expected_ded_apply_amount,
        expected_oop_apply_amount,
        expected_patient_relationship_code,
        expected_rows,
    ):
        # Given
        uhc_file_generator__use_case_one = uhc_file_generator_factory(
            time_stamp=time_stamp
        )

        setup_factory(
            payer_id=uhc_file_generator__use_case_one.payer_id,
            ind_deductible_limit=ind_deductible_limit,
            ind_oop_max_limit=ind_oop_max,
            fam_deductible_limit=family_deductible_limit,
            fam_oop_max_limit=family_oop_max,
            patient_is_subscriber=patient_is_subscriber,
            patient_is_on_individual_plan=patient_is_on_family_plan,
            patient_relationship=patient_relationship,
            patient_sex=patient_sex,
            total_member_responsibility=total_member_responsibility,
            deductible=deductible,
            oop_applied=oop_applied,
            oop_remaining=oop_remaining,
            deductible_remaining=deductible_remaining,
        )
        # When
        file_contents = uhc_file_generator__use_case_one.generate_file_contents()
        report = PayerAccumulationReports.query.filter_by(
            filename=expected_file_name
        ).one_or_none()

        assert report.filename == expected_file_name

        AccumulationFileHandler(force_local=True).upload_file(
            content=file_contents, filename=report.filename, bucket=""
        )

        file_path_for_use_case_one = os.path.join(
            os.path.dirname(CURRENT_DIR),
            f"test_files/{uhc_file_generator__use_case_one.file_name}",
        )

        # Then
        with open(file_path_for_use_case_one, "r") as reader:
            content = reader.read()
            file_rows = content.split("\n")
            file_rows.pop()  # remove empty row after trailer
            assert len(file_rows) == expected_rows
            detail_row = file_rows[1]
            assert detail_row[433:438].strip() == expected_ded_apply_amount
            assert detail_row[461:466].strip() == expected_oop_apply_amount
            assert detail_row[228:229].strip() == expected_patient_relationship_code

    def test_file_generated__multiple_detail_rows(
        self,
        uhc_file_generator_factory,
        treatment_procedures__use_case_multiple_rows,
        accumulation_treatment_mappings__use_case_multiple_rows,
    ):
        # Given
        uhc_file_generator__use_case_multiple_rows = uhc_file_generator_factory(
            time_stamp="2025-01-01 12:24:48"
        )
        # When
        expected_file_name = "Maven_UHC_Accumulator_File_20250101_122448"
        file_contents = (
            uhc_file_generator__use_case_multiple_rows.generate_file_contents()
        )
        report = PayerAccumulationReports.query.filter_by(
            filename=expected_file_name
        ).one_or_none()

        assert report.filename == expected_file_name
        AccumulationFileHandler(force_local=True).upload_file(
            content=file_contents, filename=expected_file_name, bucket=""
        )

        file_path_for_multiple_use_cases = os.path.join(
            os.path.dirname(CURRENT_DIR),
            f"test_files/{uhc_file_generator__use_case_multiple_rows.file_name}",
        )

        expected_rows_with_data_in_file = (
            10  # ONE header row, EIGHT detail rows, ONE trailer row
        )

        # oop_apply as unique key w/ ded_apply and patient_relationship_code as values, respectively
        expected_data = [
            ["01000}", "01000}", "1"],
            ["43210{", "43210{", "1"],
            ["00529K", "00529K", "1"],
            ["00000{", "00118A", "1"],
            ["00332I", "00332I", "1"],
            ["12000I", "00000{", "1"],
            ["00000{", "21010E", "1"],
            ["00000{", "09610B", "1"],
        ]

        # Then
        with open(file_path_for_multiple_use_cases, "r") as reader:
            content = reader.read()
            file_rows = content.split("\n")
            file_rows.pop()  # remove empty row after trailer
            assert len(file_rows) == expected_rows_with_data_in_file
            file_rows.pop(0)  # remove header row
            file_rows.pop()  # remove trailer row
            for _, (row, expected) in enumerate(zip(file_rows, expected_data)):
                assert row[432:438] == expected[0]  # ded_apply_amount
                assert row[460:466] == expected[1]  # oop_apply_amount
                assert row[228:229] == expected[2]  # patient_relationship_code
