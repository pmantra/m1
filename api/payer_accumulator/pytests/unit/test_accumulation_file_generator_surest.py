import datetime
import os

import factory
import pytest
from freezegun import freeze_time

from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from payer_accumulator.common import PayerName, TreatmentAccumulationStatus
from payer_accumulator.file_generators import AccumulationFileGeneratorSurest
from payer_accumulator.pytests.factories import (
    AccumulationTreatmentMappingFactory,
    PayerFactory,
)
from wallet.models.constants import (
    MemberHealthPlanPatientRelationship,
    MemberHealthPlanPatientSex,
    ReimbursementRequestState,
    WalletState,
)
from wallet.pytests.factories import (
    EmployerHealthPlanFactory,
    MemberHealthPlanFactory,
    ReimbursementOrganizationSettingsFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementRequestFactory,
    ReimbursementWalletFactory,
)


@pytest.fixture(scope="function")
def surest_payer(app_context):
    return PayerFactory.create(id=1, payer_name=PayerName.SUREST, payer_code="01234")


@pytest.fixture(scope="function")
def employer_health_plan(surest_payer):
    org_settings = ReimbursementOrganizationSettingsFactory.create(
        organization_id=1,
        deductible_accumulation_enabled=True,
    )
    ehp = EmployerHealthPlanFactory.create(
        id=1,
        reimbursement_org_settings_id=1,
        reimbursement_organization_settings=org_settings,
        start_date=datetime.date(2024, 1, 1),
        end_date=datetime.date(2024, 12, 30),
        ind_deductible_limit=200_000,
        ind_oop_max_limit=400_000,
        fam_deductible_limit=400_000,
        fam_oop_max_limit=600_000,
        benefits_payer_id=surest_payer.id,
        rx_integrated=False,
    )
    return ehp


@pytest.fixture(scope="function")
def member_health_plan(enterprise_user, employer_health_plan):
    return MemberHealthPlanFactory.create(
        employer_health_plan_id=1,
        reimbursement_wallet=ReimbursementWalletFactory.create(
            id=5, state=WalletState.QUALIFIED
        ),
        employer_health_plan=employer_health_plan,
        reimbursement_wallet_id=5,
        is_subscriber=True,
        patient_sex=MemberHealthPlanPatientSex.FEMALE,
        patient_relationship=MemberHealthPlanPatientRelationship.CARDHOLDER,
        member_id=enterprise_user.id,
        subscriber_insurance_id="u1234567801",
    )


@pytest.fixture(scope="function")
def treatment_procedures(member_health_plan):
    cbs = CostBreakdownFactory.create_batch(size=5, deductible=10000, oop_applied=10000)
    return TreatmentProcedureFactory.create_batch(
        size=5,
        start_date=datetime.datetime(2024, 1, 1),
        end_date=datetime.datetime(2024, 2, 1),
        completed_date=datetime.datetime(2024, 2, 1),
        member_id=member_health_plan.member_id,
        reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
        cost_breakdown_id=factory.Iterator([cb.id for cb in cbs]),
        status=TreatmentProcedureStatus.COMPLETED,
    )


@pytest.fixture(scope="function")
def reimbursement_requests(member_health_plan):
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    rrs = ReimbursementRequestFactory.create_batch(
        size=5,
        service_start_date=datetime.datetime(2024, 1, 1),
        service_end_date=datetime.datetime(2024, 2, 1),
        person_receiving_service_id=member_health_plan.member_id,
        reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
        reimbursement_request_category_id=category.id,
        procedure_type="MEDICAL",
        state=ReimbursementRequestState.APPROVED,
    )
    CostBreakdownFactory.create_batch(
        size=5,
        deductible=10000,
        oop_applied=10000,
        reimbursement_request_id=factory.Iterator([rr.id for rr in rrs]),
    )
    return rrs


@pytest.fixture(scope="function")
def accumulation_treatment_mappings(surest_payer, treatment_procedures):
    return AccumulationTreatmentMappingFactory.create_batch(
        size=5,
        payer_id=surest_payer.id,
        treatment_procedure_uuid=factory.Iterator(
            [tp.uuid for tp in treatment_procedures]
        ),
        treatment_accumulation_status=factory.Iterator(
            [
                TreatmentAccumulationStatus.PAID,
                TreatmentAccumulationStatus.PAID,
                TreatmentAccumulationStatus.WAITING,
                TreatmentAccumulationStatus.PROCESSED,
                TreatmentAccumulationStatus.PAID,
            ]
        ),
        deductible=factory.Iterator([100, 100, 100, 100, 0]),
        oop_applied=factory.Iterator([100, 100, 100, 100, 0]),
    )


@pytest.fixture(scope="function")
def accumulation_treatment_mappings_reimbursement_request(
    surest_payer, reimbursement_requests
):
    return AccumulationTreatmentMappingFactory.create_batch(
        size=5,
        payer_id=surest_payer.id,
        reimbursement_request_id=factory.Iterator(
            [rr.id for rr in reimbursement_requests]
        ),
        treatment_accumulation_status=factory.Iterator(
            [
                TreatmentAccumulationStatus.PAID,
                TreatmentAccumulationStatus.PAID,
                TreatmentAccumulationStatus.WAITING,
                TreatmentAccumulationStatus.PROCESSED,
                TreatmentAccumulationStatus.PAID,
            ]
        ),
        deductible=factory.Iterator([100, 100, 100, 100, 0]),
        oop_applied=factory.Iterator([100, 100, 100, 100, 0]),
    )


@pytest.fixture(scope="function")
@freeze_time("2024-10-01 00:00:00")
def surest_file_generator(surest_payer):
    return AccumulationFileGeneratorSurest()


@pytest.fixture(scope="function")
def test_file() -> str:
    file_path = os.path.join(
        os.path.dirname(__file__),
        "../test_files/maven_surest_infertilityclaimspaid_prod_2024100100000000.csv",
    )
    with open(file_path, "r") as file:
        content = file.read()
    return content


class TestGenerateFileContents:
    def test_success(
        self, surest_file_generator, accumulation_treatment_mappings, test_file
    ):
        content = surest_file_generator.generate_file_contents().getvalue()
        assert test_file == content
        report_cnt = 0
        for mapping in accumulation_treatment_mappings:
            if mapping.report_id is not None:
                report_cnt += 1
        assert report_cnt == 3
        assert set(
            [
                atm.treatment_accumulation_status
                for atm in accumulation_treatment_mappings
            ]
        ) == {
            TreatmentAccumulationStatus.PROCESSED,
            TreatmentAccumulationStatus.PROCESSED,
            TreatmentAccumulationStatus.WAITING,
            TreatmentAccumulationStatus.PROCESSED,
            TreatmentAccumulationStatus.PROCESSED,
        }

    def test_all_rows_skipped(self, surest_file_generator, member_health_plan):
        tp = TreatmentProcedureFactory.create(
            start_date=datetime.datetime(2024, 1, 1),
            end_date=datetime.datetime(2024, 2, 1),
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            status=TreatmentProcedureStatus.COMPLETED,
        )
        AccumulationTreatmentMappingFactory.create(
            payer_id=surest_file_generator.payer_id,
            treatment_procedure_uuid=tp.uuid,
            treatment_accumulation_status=TreatmentAccumulationStatus.PAID,
            deductible=0,
            oop_applied=0,
        )
        content = surest_file_generator.generate_file_contents().getvalue()
        assert (
            content
            == "Policy/Group,Member ID,First Name,Last Name,Date of Birth,Relationship Code,Maven Claim Number,Date of Service,Network,OOP Applied,Claim Status,Accumulator Type\n"
        )

    def test_row_error(
        self,
        surest_file_generator,
        member_health_plan,
        treatment_procedures,
        accumulation_treatment_mappings,
        test_file,
    ):
        # no member health plan
        tp = TreatmentProcedureFactory.create(
            start_date=datetime.datetime(2024, 1, 1),
            end_date=datetime.datetime(2024, 2, 1),
            status=TreatmentProcedureStatus.COMPLETED,
        )
        atm = AccumulationTreatmentMappingFactory.create(
            payer_id=surest_file_generator.payer_id,
            treatment_procedure_uuid=tp.uuid,
            treatment_accumulation_status=TreatmentAccumulationStatus.PAID,
            deductible=200,
            oop_applied=200,
        )
        accumulation_treatment_mappings.append(atm)
        content = surest_file_generator.generate_file_contents().getvalue()
        assert test_file == content
        report_cnt = 0
        for mapping in accumulation_treatment_mappings:
            if mapping.report_id is not None:
                report_cnt += 1
        assert report_cnt == 3
        assert set(
            [
                atm.treatment_accumulation_status
                for atm in accumulation_treatment_mappings
            ]
        ) == {
            TreatmentAccumulationStatus.PROCESSED,
            TreatmentAccumulationStatus.PROCESSED,
            TreatmentAccumulationStatus.WAITING,
            TreatmentAccumulationStatus.PROCESSED,
            TreatmentAccumulationStatus.PROCESSED,
            TreatmentAccumulationStatus.ROW_ERROR,
        }

    def test_empty(self, surest_file_generator):
        content = surest_file_generator.generate_file_contents().getvalue()
        assert (
            content
            == "Policy/Group,Member ID,First Name,Last Name,Date of Birth,Relationship Code,Maven Claim Number,Date of Service,Network,OOP Applied,Claim Status,Accumulator Type\n"
        )

    def test_reimbursement_requests(
        self,
        surest_file_generator,
        accumulation_treatment_mappings_reimbursement_request,
        test_file,
    ):
        content = surest_file_generator.generate_file_contents().getvalue()
        assert test_file == content
        report_cnt = 0
        for mapping in accumulation_treatment_mappings_reimbursement_request:
            if mapping.report_id is not None:
                report_cnt += 1
        assert report_cnt == 3
        assert set(
            [
                atm.treatment_accumulation_status
                for atm in accumulation_treatment_mappings_reimbursement_request
            ]
        ) == {
            TreatmentAccumulationStatus.PROCESSED,
            TreatmentAccumulationStatus.PROCESSED,
            TreatmentAccumulationStatus.WAITING,
            TreatmentAccumulationStatus.PROCESSED,
            TreatmentAccumulationStatus.PROCESSED,
        }
