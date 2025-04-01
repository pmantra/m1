import datetime
import os
from unittest import mock

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
from payer_accumulator.edi.edi_837_accumulation_file_generator import (
    EDI837AccumulationFileGenerator,
)
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
    EmployerHealthPlanFactory,
    MemberHealthPlanFactory,
    ReimbursementOrganizationSettingsFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementRequestFactory,
    ReimbursementServiceCategoryFactory,
    ReimbursementWalletFactory,
    WalletExpenseSubtypeFactory,
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
def treatment_procedures(member_health_plan):
    cbs = CostBreakdownFactory.create_batch(
        size=5,
        deductible=factory.Iterator([10000, 10000, 10000, 10000, 0]),
        oop_applied=factory.Iterator([10000, 10000, 10000, 10000, 0]),
    )
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
def treatment_procedures_dependent(member_health_plan_dependent):
    cbs = CostBreakdownFactory.create_batch(
        size=5,
        deductible=factory.Iterator([10000, 10000, 10000, 10000, 0]),
        oop_applied=factory.Iterator([10000, 10000, 10000, 10000, 0]),
    )
    return TreatmentProcedureFactory.create_batch(
        size=5,
        start_date=datetime.datetime(2024, 1, 1),
        end_date=datetime.datetime(2024, 2, 1),
        completed_date=datetime.datetime(2024, 2, 1),
        member_id=member_health_plan_dependent.member_id,
        reimbursement_wallet_id=member_health_plan_dependent.reimbursement_wallet_id,
        cost_breakdown_id=factory.Iterator([cb.id for cb in cbs]),
        status=TreatmentProcedureStatus.COMPLETED,
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
    )
    CostBreakdownFactory.create_batch(
        size=5,
        deductible=factory.Iterator([10000, 10000, 10000, 10000, 0]),
        oop_applied=factory.Iterator([10000, 10000, 10000, 10000, 0]),
        reimbursement_request_id=factory.Iterator([rr.id for rr in rrs]),
    )
    return rrs


@pytest.fixture(scope="function")
def accumulation_treatment_mappings(aetna_payer, treatment_procedures):
    return AccumulationTreatmentMappingFactory.create_batch(
        size=5,
        payer_id=aetna_payer.id,
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
def accumulation_treatment_mappings_dependent(
    aetna_payer, treatment_procedures_dependent
):
    return AccumulationTreatmentMappingFactory.create_batch(
        size=5,
        payer_id=aetna_payer.id,
        treatment_procedure_uuid=factory.Iterator(
            [tp.uuid for tp in treatment_procedures_dependent]
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
    aetna_payer, reimbursement_requests
):
    return AccumulationTreatmentMappingFactory.create_batch(
        size=5,
        payer_id=aetna_payer.id,
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
def accumulation_treatment_mappings_reversal(aetna_payer, treatment_procedures):
    AccumulationTreatmentMappingFactory.create_batch(
        size=5,
        payer_id=aetna_payer.id,
        treatment_procedure_uuid=factory.Iterator(
            [tp.uuid for tp in treatment_procedures]
        ),
        treatment_accumulation_status=factory.Iterator(
            [
                TreatmentAccumulationStatus.PROCESSED,
                TreatmentAccumulationStatus.PROCESSED,
                TreatmentAccumulationStatus.PROCESSED,
                TreatmentAccumulationStatus.PROCESSED,
                TreatmentAccumulationStatus.PROCESSED,
            ]
        ),
        deductible=factory.Iterator([100, 100, 100, 100, 0]),
        oop_applied=factory.Iterator([100, 100, 100, 100, 0]),
        accumulation_unique_id=factory.Iterator(
            [
                "20250101000000000001",
                "20250101000000000002",
                "20250101000000000003",
                "20250101000000000004",
                "20250101000000000005",
            ]
        ),
    )
    return AccumulationTreatmentMappingFactory.create_batch(
        size=5,
        payer_id=aetna_payer.id,
        treatment_procedure_uuid=factory.Iterator(
            [tp.uuid for tp in treatment_procedures]
        ),
        treatment_accumulation_status=factory.Iterator(
            [
                TreatmentAccumulationStatus.REFUNDED,
                TreatmentAccumulationStatus.REFUNDED,
                TreatmentAccumulationStatus.WAITING,
                TreatmentAccumulationStatus.PROCESSED,
                TreatmentAccumulationStatus.REFUNDED,
            ]
        ),
        deductible=factory.Iterator([100, 100, 100, 100, 0]),
        oop_applied=factory.Iterator([100, 100, 100, 100, 0]),
    )


@pytest.fixture(scope="function")
def accumulation_treatment_mappings_regenerate(aetna_payer, reimbursement_requests):
    return AccumulationTreatmentMappingFactory.create_batch(
        size=3,
        payer_id=aetna_payer.id,
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
@freeze_time("2024-10-01 00:00:00")
def aetna_file_generator(aetna_payer):
    return EDI837AccumulationFileGenerator(payer_name=PayerName.AETNA)


@pytest.fixture(scope="function")
def test_file() -> str:
    file_path = os.path.join(
        os.path.dirname(__file__),
        "../test_files/Maven_Aetna_Accumulation_File_20241001_000000.edi",
    )
    with open(file_path, "r") as file:
        content = file.read()
    return content


@pytest.fixture(scope="function")
def test_file_dependent() -> str:
    file_path = os.path.join(
        os.path.dirname(__file__),
        "../test_files/Maven_Aetna_Accumulation_File_20241101_000000.edi",
    )
    with open(file_path, "r") as file:
        content = file.read()
    return content


@pytest.fixture(scope="function")
def test_file_reversal() -> str:
    file_path = os.path.join(
        os.path.dirname(__file__),
        "../test_files/Maven_Aetna_Accumulation_File_20241201_000000.edi",
    )
    with open(file_path, "r") as file:
        content = file.read()
    return content


@pytest.fixture(scope="function")
def build_test_file() -> str:
    def make_test_file(report_id: int) -> str:
        file_path = os.path.join(
            os.path.dirname(__file__),
            "../test_files/Maven_Aetna_Accumulation_File_20250101_000000.edi",
        )
        with open(file_path, "r") as file:
            content = file.read()
            content = content.replace("100000030", str(10**8 + report_id))
        return content

    return make_test_file


class TestGenerateFileContents:
    @mock.patch(
        "common.global_procedures.procedure.ProcedureService.get_procedure_by_id"
    )
    def test_success(
        self,
        mock_procedure_code,
        aetna_file_generator,
        accumulation_treatment_mappings,
        test_file,
    ):
        mock_procedure_code.return_value = {"hcpcs_code": "G0151"}
        content = aetna_file_generator.generate_file_contents().read()
        assert (
            content.split("\n")[4:-3] == test_file.split("\n")[4:-3]
        )  # control number depends on report id
        report_cnt = 0
        for mapping in accumulation_treatment_mappings:
            if mapping.report_id is not None:
                report_cnt += 1
        assert report_cnt == 2
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
            TreatmentAccumulationStatus.SKIP,
        }

    @mock.patch(
        "common.global_procedures.procedure.ProcedureService.get_procedure_by_id"
    )
    def test_all_rows_skipped(
        self, mock_procedure_code, aetna_file_generator, member_health_plan
    ):
        mock_procedure_code.return_value = {"hcpcs_code": "G0151"}
        tp = TreatmentProcedureFactory.create(
            start_date=datetime.datetime(2024, 1, 1),
            end_date=datetime.datetime(2024, 2, 1),
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            status=TreatmentProcedureStatus.COMPLETED,
        )
        atm = AccumulationTreatmentMappingFactory.create(
            payer_id=aetna_file_generator.payer_id,
            treatment_procedure_uuid=tp.uuid,
            treatment_accumulation_status=TreatmentAccumulationStatus.PAID,
            deductible=0,
            oop_applied=0,
        )
        assert aetna_file_generator.generate_file_contents().read() == ""
        assert (
            atm.treatment_accumulation_status == TreatmentAccumulationStatus.ROW_ERROR
        )

    @mock.patch(
        "common.global_procedures.procedure.ProcedureService.get_procedure_by_id"
    )
    def test_bad_member_subscriber_id(
        self, mock_procedure_code, aetna_file_generator, member_health_plan
    ):
        mock_procedure_code.return_value = {"hcpcs_code": "G0151"}
        member_health_plan.subscriber_insurance_id = "123 456"
        tp = TreatmentProcedureFactory.create(
            start_date=datetime.datetime(2024, 1, 1),
            end_date=datetime.datetime(2024, 2, 1),
            member_id=member_health_plan.member_id,
            reimbursement_wallet_id=member_health_plan.reimbursement_wallet_id,
            status=TreatmentProcedureStatus.COMPLETED,
        )
        atm = AccumulationTreatmentMappingFactory.create(
            payer_id=aetna_file_generator.payer_id,
            treatment_procedure_uuid=tp.uuid,
            treatment_accumulation_status=TreatmentAccumulationStatus.PAID,
            deductible=100,
            oop_applied=100,
        )
        assert aetna_file_generator.generate_file_contents().read() == ""
        assert (
            atm.treatment_accumulation_status == TreatmentAccumulationStatus.ROW_ERROR
        )

    @mock.patch(
        "common.global_procedures.procedure.ProcedureService.get_procedure_by_id"
    )
    def test_row_error(
        self,
        mock_procedure_code,
        aetna_file_generator,
        member_health_plan,
        treatment_procedures,
        accumulation_treatment_mappings,
        test_file,
    ):
        tp = TreatmentProcedureFactory.create(
            start_date=datetime.datetime(2024, 1, 1),
            end_date=datetime.datetime(2024, 2, 1),
            status=TreatmentProcedureStatus.COMPLETED,
        )
        atm = AccumulationTreatmentMappingFactory.create(
            payer_id=aetna_file_generator.payer_id,
            treatment_procedure_uuid=tp.uuid,
            treatment_accumulation_status=TreatmentAccumulationStatus.PAID,
            deductible=200,
            oop_applied=200,
        )
        mock_procedure_code.return_value = {"hcpcs_code": "G0151"}
        accumulation_treatment_mappings.append(atm)
        content = aetna_file_generator.generate_file_contents().read()
        assert (
            content.split("\n")[4:-3] == test_file.split("\n")[4:-3]
        )  # control number depends on report id
        report_cnt = 0
        for mapping in accumulation_treatment_mappings:
            if mapping.report_id is not None:
                report_cnt += 1
        assert report_cnt == 2
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
            TreatmentAccumulationStatus.SKIP,
            TreatmentAccumulationStatus.ROW_ERROR,
        }

    def test_empty(self, aetna_file_generator):
        content = aetna_file_generator.generate_file_contents().read()
        assert content == ""

    @mock.patch(
        "common.global_procedures.procedure.ProcedureService.get_procedure_by_id"
    )
    def test_reimbursement_requests(
        self,
        mock_procedure_code,
        aetna_file_generator,
        accumulation_treatment_mappings_reimbursement_request,
        test_file,
    ):
        mock_procedure_code.return_value = {"hcpcs_code": "G0151"}
        content = aetna_file_generator.generate_file_contents().read()
        assert (
            content.split("\n")[4:-3] == test_file.split("\n")[4:-3]
        )  # control number depends on report id
        report_cnt = 0
        for mapping in accumulation_treatment_mappings_reimbursement_request:
            if mapping.report_id is not None:
                report_cnt += 1
        assert report_cnt == 2
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
            TreatmentAccumulationStatus.SKIP,
        }

    def test_pharmacy_reimbursement_request(
        self, aetna_file_generator, reimbursement_requests, aetna_payer
    ):
        # SMP does not save deductible/oop to mappings
        AccumulationTreatmentMappingFactory.create(
            payer_id=aetna_payer.id,
            reimbursement_request_id=reimbursement_requests[0].id,
            treatment_accumulation_status=TreatmentAccumulationStatus.PAID,
            deductible=None,
            oop_applied=None,
        )
        with mock.patch(
            "common.global_procedures.procedure.ProcedureService.get_procedure_by_id",
            return_value={"hcpcs_code": "G0151"},
        ):
            aetna_file_generator.generate_file_contents().read()

    @mock.patch(
        "common.global_procedures.procedure.ProcedureService.get_procedure_by_id"
    )
    def test_patient_not_subscriber(
        self,
        mock_procedure_code,
        aetna_file_generator,
        accumulation_treatment_mappings_dependent,
        test_file_dependent,
    ):
        mock_procedure_code.return_value = {"hcpcs_code": "G0151"}
        content = aetna_file_generator.generate_file_contents().read()
        assert (
            content.split("\n")[4:-3] == test_file_dependent.split("\n")[4:-3]
        )  # control number depends on report id
        report_cnt = 0
        for mapping in accumulation_treatment_mappings_dependent:
            if mapping.report_id is not None:
                report_cnt += 1
        assert report_cnt == 2
        assert set(
            [
                atm.treatment_accumulation_status
                for atm in accumulation_treatment_mappings_dependent
            ]
        ) == {
            TreatmentAccumulationStatus.PROCESSED,
            TreatmentAccumulationStatus.PROCESSED,
            TreatmentAccumulationStatus.WAITING,
            TreatmentAccumulationStatus.PROCESSED,
            TreatmentAccumulationStatus.SKIP,
        }

    @mock.patch(
        "common.global_procedures.procedure.ProcedureService.get_procedure_by_id"
    )
    def test_reversal(
        self,
        mock_procedure_code,
        aetna_file_generator,
        accumulation_treatment_mappings_reversal,
        test_file_reversal,
    ):
        mock_procedure_code.return_value = {"hcpcs_code": "G0151"}
        content = aetna_file_generator.generate_file_contents().read()
        assert (
            content.split("\n")[4:-3] == test_file_reversal.split("\n")[4:-3]
        )  # control number depends on report id
        report_cnt = 0
        for mapping in accumulation_treatment_mappings_reversal:
            if mapping.report_id is not None:
                report_cnt += 1
        assert report_cnt == 2
        assert set(
            [
                atm.treatment_accumulation_status
                for atm in accumulation_treatment_mappings_reversal
            ]
        ) == {
            TreatmentAccumulationStatus.PROCESSED,
            TreatmentAccumulationStatus.PROCESSED,
            TreatmentAccumulationStatus.WAITING,
            TreatmentAccumulationStatus.PROCESSED,
            TreatmentAccumulationStatus.SKIP,
        }


class TestRegenerateFileContentsFromReport:
    @mock.patch(
        "common.global_procedures.procedure.ProcedureService.get_procedure_by_id"
    )
    def test_regenerate_file_contents_from_report__success(
        self,
        mock_procedure_code,
        aetna_payer,
        aetna_file_generator,
        accumulation_treatment_mappings_regenerate,
        build_test_file,
    ):
        # given
        report = PayerAccumulationReportsFactory.create(payer_id=aetna_payer.id)
        report.treatment_mappings = accumulation_treatment_mappings_regenerate
        mock_procedure_code.return_value = {"hcpcs_code": "G0151"}
        # when
        content = aetna_file_generator.regenerate_file_contents_from_report(report)
        # then
        assert content.getvalue() == build_test_file(report_id=report.id)

    @mock.patch(
        "common.global_procedures.procedure.ProcedureService.get_procedure_by_id"
    )
    def test_regenerate_file_contents_from_report__no_mappings(
        self,
        mock_procedure_code,
        aetna_payer,
        aetna_file_generator,
    ):
        # given
        report = PayerAccumulationReportsFactory.create(payer_id=aetna_payer.id)
        mock_procedure_code.return_value = {"hcpcs_code": "G0151"}
        # when
        content = aetna_file_generator.regenerate_file_contents_from_report(report)
        # then
        assert content.getvalue() == ""
