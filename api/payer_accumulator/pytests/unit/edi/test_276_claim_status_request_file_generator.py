import datetime
import os

import factory
import pytest

from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from payer_accumulator.common import PayerName, TreatmentAccumulationStatus
from payer_accumulator.edi.edi_276_claim_status_request_generator import (
    EDI276ClaimStatusRequestFileGenerator,
)
from payer_accumulator.edi.errors import EDI276ClaimStatusRequestGeneratorException
from payer_accumulator.pytests.factories import (
    AccumulationTreatmentMappingFactory,
    PayerFactory,
)
from pytests.freezegun import freeze_time
from wallet.models.constants import (
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


@pytest.fixture(scope="function")
def aetna_payer(app_context):
    return PayerFactory.create(id=1, payer_name=PayerName.AETNA, payer_code="01234")


@pytest.fixture(scope="function")
def employer_health_plan(aetna_payer):
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
        benefits_payer_id=aetna_payer.id,
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
def member_health_plan_dependent(enterprise_user, employer_health_plan):
    return MemberHealthPlanFactory.create(
        employer_health_plan_id=1,
        reimbursement_wallet=ReimbursementWalletFactory.create(
            id=5, state=WalletState.QUALIFIED
        ),
        employer_health_plan=employer_health_plan,
        reimbursement_wallet_id=5,
        is_subscriber=False,
        patient_sex=MemberHealthPlanPatientSex.MALE,
        patient_relationship=MemberHealthPlanPatientRelationship.SPOUSE,
        member_id=enterprise_user.id,
        subscriber_insurance_id="u1234567801",
    )


@pytest.fixture(scope="function")
@freeze_time("2024-10-01 00:00:00")
def file_generator(aetna_payer):
    return EDI276ClaimStatusRequestFileGenerator(payer_name=PayerName.AETNA)


@pytest.fixture(scope="function")
def treatment_procedures(member_health_plan):
    cbs = CostBreakdownFactory.create_batch(size=3, deductible=10000, oop_applied=10000)
    return TreatmentProcedureFactory.create_batch(
        size=2,
        start_date=datetime.datetime(2024, 1, 1),
        end_date=datetime.datetime(2024, 2, 1),
        completed_date=datetime.datetime(2024, 2, 1),
        member_id=member_health_plan.member_id,
        reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
        cost_breakdown_id=factory.Iterator([cb.id for cb in cbs]),
        status=TreatmentProcedureStatus.COMPLETED,
    )


@pytest.fixture(scope="function")
def treatment_procedures_dependent(member_health_plan_dependent):
    cbs = CostBreakdownFactory.create_batch(size=3, deductible=10000, oop_applied=10000)
    return TreatmentProcedureFactory.create_batch(
        size=2,
        start_date=datetime.datetime(2024, 1, 1),
        end_date=datetime.datetime(2024, 2, 1),
        completed_date=datetime.datetime(2024, 2, 1),
        member_id=member_health_plan_dependent.member_id,
        reimbursement_wallet_id=member_health_plan_dependent.reimbursement_wallet_id,
        cost_breakdown_id=factory.Iterator([cb.id for cb in cbs]),
        status=TreatmentProcedureStatus.COMPLETED,
    )


@pytest.fixture(scope="function")
def accumulation_treatment_mappings(aetna_payer, treatment_procedures):
    return AccumulationTreatmentMappingFactory.create_batch(
        size=2,
        payer_id=aetna_payer.id,
        treatment_procedure_uuid=factory.Iterator(
            [tp.uuid for tp in treatment_procedures]
        ),
        treatment_accumulation_status=factory.Iterator(
            [TreatmentAccumulationStatus.PAID, TreatmentAccumulationStatus.SUBMITTED]
        ),
        deductible=100,
        oop_applied=100,
        accumulation_unique_id=factory.Iterator(["unique_id_1", "unique_id_2"]),
    )


@pytest.fixture(scope="function")
def accumulation_treatment_mappings_dependent(
    aetna_payer, treatment_procedures_dependent
):
    return AccumulationTreatmentMappingFactory.create_batch(
        size=2,
        payer_id=aetna_payer.id,
        treatment_procedure_uuid=factory.Iterator(
            [tp.uuid for tp in treatment_procedures_dependent]
        ),
        treatment_accumulation_status=factory.Iterator(
            [
                TreatmentAccumulationStatus.PAID,
                TreatmentAccumulationStatus.SUBMITTED,
            ]
        ),
        deductible=100,
        oop_applied=100,
        accumulation_unique_id=factory.Iterator(["unique_id_1", "unique_id_2"]),
    )


@pytest.fixture(scope="function")
def test_file() -> str:
    file_path = os.path.join(
        os.path.dirname(__file__),
        "../../test_files/Maven_aetna_276_status_request_20241001_000000.edi",
    )
    with open(file_path, "r") as file:
        content = file.read()
    return content


@pytest.fixture(scope="function")
def test_file_dependent() -> str:
    file_path = os.path.join(
        os.path.dirname(__file__),
        "../../test_files/Maven_aetna_276_status_request_20241101_000000.edi",
    )
    with open(file_path, "r") as file:
        content = file.read()
    return content


class TestGenerateFileContents:
    def test_success(self, file_generator, accumulation_treatment_mappings, test_file):
        content = file_generator.generate_file_contents().getvalue()
        assert content == test_file

    def test_no_row_included(self, file_generator):
        content = file_generator.generate_file_contents().getvalue()
        assert content == ""

    def test_missing_unique_id(self, file_generator, accumulation_treatment_mappings):
        for mapping in accumulation_treatment_mappings:
            mapping.accumulation_unique_id = None
        with pytest.raises(EDI276ClaimStatusRequestGeneratorException):
            file_generator.generate_file_contents().getvalue()

    def test_dependent(
        self,
        file_generator,
        accumulation_treatment_mappings_dependent,
        test_file_dependent,
    ):
        content = file_generator.generate_file_contents().getvalue()
        assert content == test_file_dependent
