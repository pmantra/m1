import datetime
import os

import factory
import pytest
from freezegun import freeze_time

from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from payer_accumulator.common import PayerName, TreatmentAccumulationStatus
from payer_accumulator.file_generators import AccumulationCSVFileGeneratorCigna
from payer_accumulator.pytests.factories import (
    AccumulationTreatmentMappingFactory,
    PayerAccumulationReportsFactory,
    PayerFactory,
)
from wallet.models.constants import (
    MemberHealthPlanPatientRelationship,
    MemberHealthPlanPatientSex,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
    WalletState,
)
from wallet.pytests.factories import (
    MemberHealthPlanFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementRequestFactory,
    ReimbursementServiceCategoryFactory,
    ReimbursementWalletFactory,
    WalletExpenseSubtypeFactory,
)


@pytest.fixture(scope="function")
def cigna_payer(app_context):
    return PayerFactory.create(
        id=1, payer_name=PayerName.CIGNA_TRACK_1, payer_code="00001"
    )


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
def reimbursement_requests(member_health_plan):
    category = ReimbursementRequestCategoryFactory.create(label="fertility")
    rsc_fertility = ReimbursementServiceCategoryFactory(
        category="FERTILITY", name="Fertility"
    )
    wallet_expense_subtype = WalletExpenseSubtypeFactory.create(
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
        reimbursement_service_category=rsc_fertility,
        code="FIVF",
        description="IVF (with fresh transfer)",
    )
    rrs = ReimbursementRequestFactory.create_batch(
        size=5,
        service_start_date=datetime.datetime(2024, 1, 1),
        service_end_date=datetime.datetime(2024, 2, 1),
        person_receiving_service_id=member_health_plan.member_id,
        reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
        reimbursement_request_category_id=category.id,
        state=ReimbursementRequestState.APPROVED,
        wallet_expense_subtype_id=wallet_expense_subtype.id,
        procedure_type=TreatmentProcedureType.MEDICAL.value,
    )
    CostBreakdownFactory.create_batch(
        size=5,
        deductible=10000,
        oop_applied=10000,
        reimbursement_request_id=factory.Iterator([rr.id for rr in rrs]),
    )
    return rrs


@pytest.fixture(scope="function")
def accumulation_treatment_mappings_regenerate(cigna_payer, reimbursement_requests):
    return AccumulationTreatmentMappingFactory.create_batch(
        size=3,
        payer_id=cigna_payer.id,
        reimbursement_request_id=factory.Iterator(
            [rr.id for rr in reimbursement_requests]
        ),
        treatment_accumulation_status=factory.Iterator(
            [
                TreatmentAccumulationStatus.SUBMITTED,
                TreatmentAccumulationStatus.SUBMITTED,
                TreatmentAccumulationStatus.SUBMITTED,
            ]
        ),
        deductible=factory.Iterator([500, 300, 0]),
        oop_applied=factory.Iterator([400, 200, 0]),
    )


@pytest.fixture(scope="function")
def regenerated_cigna_track_1_test_file() -> str:
    file_path = os.path.join(
        os.path.dirname(__file__),
        "../test_files/regenerated_Maven_Accum_Amazon_US.csv",
    )
    with open(file_path, "r") as file:
        content = file.read()
    return content


class TestRegenerateFileContentsFromReport:
    @freeze_time("2025-01-08 20:00:00")
    def test_regenerate_file_contents_from_report__success(
        self,
        cigna_payer,
        accumulation_treatment_mappings_regenerate,
        regenerated_cigna_track_1_test_file,
    ):
        # given
        report = PayerAccumulationReportsFactory.create(payer_id=cigna_payer.id)
        report.treatment_mappings = accumulation_treatment_mappings_regenerate
        file_generator = AccumulationCSVFileGeneratorCigna()
        # when
        content = file_generator.regenerate_file_contents_from_report(report)
        regenerated_cigna_test_file_lines = regenerated_cigna_track_1_test_file.split(
            "\n"
        )
        content_lines = content.getvalue().split("\n")
        formatted_content_lines = [line.strip() for line in content_lines]
        # then the two mappings with non-zero oop_applied are written to the file
        assert formatted_content_lines == regenerated_cigna_test_file_lines

    def test_regenerate_file_contents_from_report__no_mappings(
        self,
        cigna_payer,
        regenerated_cigna_track_1_test_file,
    ):
        # given
        report = PayerAccumulationReportsFactory.create(payer_id=cigna_payer.id)
        file_generator = AccumulationCSVFileGeneratorCigna()
        # when
        content = file_generator.regenerate_file_contents_from_report(report)
        test_file_lines = regenerated_cigna_track_1_test_file.split("\n")
        formatted_test_file_lines = [line.strip() for line in test_file_lines]
        # then only the header is written to the file
        assert content.getvalue().strip() == formatted_test_file_lines[0]
