import datetime
import os

import pytest
from freezegun import freeze_time

from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from payer_accumulator.common import (
    OrganizationName,
    PayerName,
    TreatmentAccumulationStatus,
)
from payer_accumulator.file_generators import AccumulationCSVFileGeneratorCigna
from payer_accumulator.pytests.factories import (
    AccumulationTreatmentMappingFactory,
    PayerFactory,
)
from pytests.factories import OrganizationFactory
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
def cigna_payer(app_context):
    return PayerFactory.create(
        id=1, payer_name=PayerName.CIGNA_TRACK_1, payer_code="00001"
    )


@pytest.fixture(scope="function")
def org_setting():
    amazon_org = OrganizationFactory.create(name="Amazon US")
    return ReimbursementOrganizationSettingsFactory.create(
        organization_id=amazon_org.id,
        deductible_accumulation_enabled=True,
    )


@pytest.fixture(scope="function")
def employer_health_plan(cigna_payer, org_setting):
    ehp = EmployerHealthPlanFactory.create(
        id=1,
        reimbursement_organization_settings=org_setting,
        start_date=datetime.date(2024, 1, 1),
        end_date=datetime.date(2024, 12, 30),
        ind_deductible_limit=200_000,
        ind_oop_max_limit=400_000,
        fam_deductible_limit=400_000,
        fam_oop_max_limit=600_000,
        benefits_payer_id=cigna_payer.id,
        rx_integrated=False,
    )
    return ehp


@pytest.fixture(scope="function")
def wallet(org_setting):
    return ReimbursementWalletFactory.create(
        id=5,
        state=WalletState.QUALIFIED,
        reimbursement_organization_settings=org_setting,
    )


@pytest.fixture(scope="function")
def member_health_plan(enterprise_user, employer_health_plan, wallet):
    return MemberHealthPlanFactory.create(
        employer_health_plan=employer_health_plan,
        reimbursement_wallet=wallet,
        is_subscriber=True,
        patient_sex=MemberHealthPlanPatientSex.FEMALE,
        patient_relationship=MemberHealthPlanPatientRelationship.CARDHOLDER,
        member_id=enterprise_user.id,
        subscriber_insurance_id="u1234567801",
    )


@pytest.fixture(scope="function")
def treatment_procedure(member_health_plan):
    cost_breakdown = CostBreakdownFactory.create(
        deductible=100, coinsurance=200, oop_applied=300
    )
    return TreatmentProcedureFactory.create(
        start_date=datetime.datetime(2024, 1, 1),
        end_date=datetime.datetime(2024, 2, 1),
        completed_date=datetime.datetime(2024, 2, 1),
        member_id=member_health_plan.member_id,
        reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
        status=TreatmentProcedureStatus.COMPLETED,
        cost_breakdown_id=cost_breakdown.id,
    )


@pytest.fixture(scope="function")
def reimbursement_request(member_health_plan):
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    rr = ReimbursementRequestFactory.create(
        service_start_date=datetime.datetime(2024, 1, 1),
        service_end_date=datetime.datetime(2024, 2, 1),
        person_receiving_service_id=member_health_plan.member_id,
        reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
        reimbursement_request_category_id=category.id,
        procedure_type="MEDICAL",
        state=ReimbursementRequestState.APPROVED,
    )
    CostBreakdownFactory.create(
        deductible=100,
        copay=200,
        oop_applied=300,
        reimbursement_request_id=rr.id,
    )
    return rr


@pytest.fixture(scope="function")
def accumulation_treatment_mapping(cigna_payer, treatment_procedure):
    return AccumulationTreatmentMappingFactory.create(
        payer_id=cigna_payer.id,
        treatment_procedure_uuid=treatment_procedure.uuid,
        treatment_accumulation_status=TreatmentAccumulationStatus.PAID,
        deductible=100,
        oop_applied=300,
    )


@pytest.fixture(scope="function")
def accumulation_treatment_mapping_refund(cigna_payer, treatment_procedure):
    return AccumulationTreatmentMappingFactory.create(
        payer_id=cigna_payer.id,
        treatment_procedure_uuid=treatment_procedure.uuid,
        treatment_accumulation_status=TreatmentAccumulationStatus.REFUNDED,
        deductible=-100,
        oop_applied=-300,
    )


@pytest.fixture(scope="function")
def accumulation_treatment_mapping_reimbursement_request(
    cigna_payer, reimbursement_request
):
    return AccumulationTreatmentMappingFactory.create(
        payer_id=cigna_payer.id,
        reimbursement_request_id=reimbursement_request.id,
        treatment_accumulation_status=TreatmentAccumulationStatus.PAID,
        deductible=100,
        oop_applied=300,
    )


@pytest.fixture(scope="function")
@freeze_time("2024-10-01 00:00:00")
def cigna_file_generator(cigna_payer):
    return AccumulationCSVFileGeneratorCigna(organization_name=OrganizationName.AMAZON)


@pytest.fixture(scope="function")
def test_file() -> str:
    file_path = os.path.join(
        os.path.dirname(__file__),
        "../test_files/Maven_Accum_Amazon_US_20241001000000.csv",
    )
    with open(file_path, "r") as file:
        content = file.read()
    return content


@pytest.fixture(scope="function")
def test_file_refund() -> str:
    file_path = os.path.join(
        os.path.dirname(__file__),
        "../test_files/Maven_Accum_Amazon_US_20240128000000.csv",
    )
    with open(file_path, "r") as file:
        content = file.read()
    return content


def test_file_name(cigna_file_generator):
    sample_file_name = "Maven_Accum_Amazon_US_20241001000000.csv"
    file_name = cigna_file_generator.file_name
    assert sample_file_name == file_name


class TestGenerateFileContents:
    def test_empty(self, cigna_file_generator, member_health_plan):
        content = cigna_file_generator.generate_file_contents().getvalue()
        assert (
            content
            == "Member ID,Last Name,First Name,Date of Birth,Date of Service,Deductible Applied,Coinsurance Applied\n"
        )

    def test_success(
        self, cigna_file_generator, accumulation_treatment_mapping, test_file
    ):
        content = cigna_file_generator.generate_file_contents().getvalue()
        assert content == test_file

    def test_success_refund(
        self,
        cigna_file_generator,
        accumulation_treatment_mapping_refund,
        test_file_refund,
    ):
        content = cigna_file_generator.generate_file_contents().getvalue()
        assert content == test_file_refund

    def test_reimbursement_request(
        self,
        cigna_file_generator,
        accumulation_treatment_mapping_reimbursement_request,
        test_file,
    ):
        content = cigna_file_generator.generate_file_contents().getvalue()
        assert content == test_file
