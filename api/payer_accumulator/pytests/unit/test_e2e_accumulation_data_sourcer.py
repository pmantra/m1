# test cases aligned with cases found in spreadsheet
# https://docs.google.com/spreadsheets/d/1LenoDKMdjnaMoFzxykpOyS2uEmMVGbGN9FjGDrqyVxk/edit#gid=2064877279

from datetime import date, datetime

import pytest as pytest
from maven import feature_flags

from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.billing.billing_service import BillingService
from direct_payment.billing.models import BillStatus, PayorType
from direct_payment.billing.pytests.factories import (
    BillFactory,
    BillProcessingRecordFactory,
)
from direct_payment.billing.repository.bill import BillRepository
from direct_payment.billing.repository.bill_processing_record import (
    BillProcessingRecordRepository,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from payer_accumulator.accumulation_data_sourcer import AccumulationDataSourcer
from payer_accumulator.common import PayerName, TreatmentAccumulationStatus
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.pytests.conftest import TP_UUID_2, TP_UUID_3
from payer_accumulator.pytests.factories import AccumulationTreatmentMappingFactory
from wallet.models.constants import (
    FamilyPlanType,
    MemberHealthPlanPatientRelationship,
    MemberHealthPlanPatientSex,
    WalletState,
)
from wallet.pytests.factories import (
    EmployerHealthPlanFactory,
    MemberHealthPlanFactory,
    ReimbursementWalletFactory,
)
from wallet.repository.health_plan import HEALTH_PLAN_YOY_FLAG, NEW_BEHAVIOR

dt_fmt = "%d/%m/%Y %H:%M"
date_fmt = "%d/%m/%Y"


@pytest.fixture(scope="function")
def bill_repo(session):
    return BillRepository(session=session, is_in_uow=True)


@pytest.fixture(scope="function")
def bill_processing_record_repo(session):
    return BillProcessingRecordRepository(session=session, is_in_uow=True)


@pytest.fixture(scope="function")
def bill_svc(session, bill_repo, bill_processing_record_repo):
    bs = BillingService(session=session, is_in_uow=True)
    bs.bill_repo = bill_repo
    bs.bill_processing_record_repo = bill_processing_record_repo
    return bs


@pytest.fixture(scope="function")
def data_sourcer(uhc_payer, session, bill_svc):
    with feature_flags.test_data() as ff_test_data:
        ff_test_data.update(
            ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(NEW_BEHAVIOR)
        )
        acc = AccumulationDataSourcer(PayerName.UHC, session)
        acc.billing_service = bill_svc
        yield acc


@pytest.fixture(scope="function")
def integration_wallet():
    return ReimbursementWalletFactory.create(
        id=3,
        state=WalletState.QUALIFIED,
        reimbursement_organization_settings__id=45,
        reimbursement_organization_settings__organization_id=45,
        reimbursement_organization_settings__deductible_accumulation_enabled=True,
    )


@pytest.fixture(scope="function")
def integration_employer_health_plan(uhc_payer, integration_wallet):
    ehp = EmployerHealthPlanFactory.create(
        id=45,
        reimbursement_org_settings_id=45,
        reimbursement_organization_settings=integration_wallet.reimbursement_organization_settings,
        start_date=date(2010, 1, 1),
        end_date=date(2025, 1, 1),
        ind_deductible_limit=200_000,
        ind_oop_max_limit=400_000,
        fam_deductible_limit=400_000,
        fam_oop_max_limit=600_000,
        benefits_payer_id=uhc_payer.id,
        rx_integrated=False,
    )
    return ehp


@pytest.fixture(scope="function")
def plan_member(integration_employer_health_plan, integration_wallet):
    return MemberHealthPlanFactory.create(
        employer_health_plan_id=integration_employer_health_plan.id,
        reimbursement_wallet=integration_wallet,
        employer_health_plan=integration_employer_health_plan,
        reimbursement_wallet_id=integration_wallet.id,
        plan_type=FamilyPlanType.INDIVIDUAL,
        is_subscriber=True,
        patient_sex=MemberHealthPlanPatientSex.FEMALE,
        patient_relationship=MemberHealthPlanPatientRelationship.CARDHOLDER,
        subscriber_insurance_id="123456",
        plan_start_at=datetime(2010, 1, 1),
        plan_end_at=datetime(2025, 1, 1),
    )


@pytest.fixture(scope="function")
def scheduled_tp(integration_wallet):
    return TreatmentProcedureFactory.create(
        id=2,
        cost_breakdown_id=2,
        uuid=TP_UUID_2,
        status=TreatmentProcedureStatus.SCHEDULED,
        reimbursement_wallet_id=integration_wallet.id,
        start_date=datetime.strptime("15/01/2018", date_fmt),
        end_date=datetime.strptime("15/11/2018", date_fmt),
        completed_date=datetime.strptime("15/11/2018 15:30", dt_fmt),
        procedure_type=TreatmentProcedureType.MEDICAL,
        member_id=integration_wallet.user_id,
    )


@pytest.fixture(scope="function")
def completed_tp(integration_wallet):
    return TreatmentProcedureFactory.create(
        id=2,
        cost_breakdown_id=2,
        uuid=TP_UUID_2,
        status=TreatmentProcedureStatus.COMPLETED,
        reimbursement_wallet_id=integration_wallet.id,
        start_date=datetime.strptime("15/01/2018", date_fmt),
        end_date=datetime.strptime("15/11/2018", date_fmt),
        completed_date=datetime.strptime("15/11/2018 15:30", dt_fmt),
        procedure_type=TreatmentProcedureType.MEDICAL,
        member_id=integration_wallet.user_id,
    )


def setup_cost_breakdown(cb_id, amount, first_cb):
    if first_cb:
        created_time = datetime.strptime("12/11/2018 00:00", "%d/%m/%Y %H:%M")
    else:
        created_time = datetime.strptime("12/12/2018 00:00", "%d/%m/%Y %H:%M")
    CostBreakdownFactory.create(
        treatment_procedure_uuid=TP_UUID_2,
        wallet_id=3,
        id=cb_id,
        total_member_responsibility=amount,
        deductible=amount,
        oop_applied=amount,
        created_at=created_time,
    )


def update_tp_cb_id(completed_tp, cb_id, data_sourcer):
    completed_tp.cost_breakdown_id = cb_id
    data_sourcer.treatment_procedure_repo.session.add(completed_tp)


def setup_bill(bill_repo, bill_processing_repo, amount, bill_id, status):
    bill = BillFactory.build(
        id=bill_id,
        payor_id=1,
        procedure_id=2,
        amount=amount,
        payor_type=PayorType.MEMBER,
        status=status,
        created_at=datetime.strptime("12/11/2018 00:00", dt_fmt),
    )
    bpr = BillProcessingRecordFactory.build(
        bill_id=bill_id,
        bill_status=status.value,
        processing_record_type="payment_gateway_request",
    )
    bill_repo.create(instance=bill)
    bill_processing_repo.create(instance=bpr)


def test_no_complete_treatment_procedure(
    plan_member, scheduled_tp, cost_breakdown_mr_100, accumulation_data_sourcer, logs
):
    error_msg = "No ready treatment procedures"
    accumulation_data_sourcer.data_source_preparation_for_file_generation()
    logs = next((r for r in logs if error_msg in r["event"]), None)
    assert logs is not None


def test_only_one_cb(
    plan_member,
    completed_tp,
    data_sourcer,
    bill_repo,
    bill_processing_record_repo,
):
    setup_cost_breakdown(cb_id=2, amount=10_000, first_cb=True)
    setup_bill(
        bill_repo,
        bill_processing_record_repo,
        amount=10_000,
        bill_id=1,
        status=BillStatus.PAID,
    )
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=completed_tp.uuid)
        .one_or_none()
    )
    assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.PAID


def test_completed_cb2_more_than_cb1(
    plan_member,
    completed_tp,
    data_sourcer,
    bill_repo,
    bill_processing_record_repo,
):
    setup_cost_breakdown(cb_id=2, amount=10_000, first_cb=True)
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=completed_tp.uuid)
        .one_or_none()
    )
    assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.WAITING
    setup_bill(
        bill_repo,
        bill_processing_record_repo,
        amount=10_000,
        bill_id=2,
        status=BillStatus.PAID,
    )
    setup_cost_breakdown(cb_id=3, amount=15_000, first_cb=False)
    update_tp_cb_id(completed_tp=completed_tp, cb_id=3, data_sourcer=data_sourcer)
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=completed_tp.uuid)
        .one_or_none()
    )
    assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.WAITING
    setup_bill(
        bill_repo,
        bill_processing_record_repo,
        amount=5_000,
        bill_id=3,
        status=BillStatus.PAID,
    )
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=completed_tp.uuid)
        .one_or_none()
    )
    assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.PAID


def test_completed_cb1_more_than_cb2(
    plan_member,
    completed_tp,
    data_sourcer,
    bill_repo,
    bill_processing_record_repo,
):
    setup_cost_breakdown(cb_id=2, amount=20_000, first_cb=True)
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=completed_tp.uuid)
        .one_or_none()
    )
    assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.WAITING
    setup_bill(
        bill_repo,
        bill_processing_record_repo,
        amount=20_000,
        bill_id=4,
        status=BillStatus.PAID,
    )
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=completed_tp.uuid)
        .one_or_none()
    )
    assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.PAID
    setup_cost_breakdown(cb_id=3, amount=15_000, first_cb=False)
    update_tp_cb_id(completed_tp=completed_tp, cb_id=3, data_sourcer=data_sourcer)
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=completed_tp.uuid)
        .one_or_none()
    )
    assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.PAID


def test_completed_cb2_more_than_cb1_with_failed_first_bill(
    plan_member,
    completed_tp,
    data_sourcer,
    bill_repo,
    bill_processing_record_repo,
):
    setup_cost_breakdown(cb_id=2, amount=10_000, first_cb=True)
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=completed_tp.uuid)
        .one_or_none()
    )
    setup_bill(
        bill_repo,
        bill_processing_record_repo,
        amount=10_000,
        bill_id=5,
        status=BillStatus.FAILED,
    )
    assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.WAITING
    setup_cost_breakdown(cb_id=3, amount=15_000, first_cb=False)
    update_tp_cb_id(completed_tp=completed_tp, cb_id=3, data_sourcer=data_sourcer)
    setup_bill(
        bill_repo,
        bill_processing_record_repo,
        amount=5_000,
        bill_id=6,
        status=BillStatus.PAID,
    )
    setup_bill(
        bill_repo,
        bill_processing_record_repo,
        amount=10_000,
        bill_id=7,
        status=BillStatus.PROCESSING,
    )
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=completed_tp.uuid)
        .one_or_none()
    )
    assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.WAITING
    setup_bill(
        bill_repo,
        bill_processing_record_repo,
        amount=10_000,
        bill_id=8,
        status=BillStatus.PAID,
    )
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=completed_tp.uuid)
        .one_or_none()
    )
    assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.PAID


def test_completed_cb2_more_than_cb1_with_failed_second_bill(
    plan_member,
    completed_tp,
    data_sourcer,
    bill_repo,
    bill_processing_record_repo,
):
    setup_cost_breakdown(cb_id=2, amount=10_000, first_cb=True)
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=completed_tp.uuid)
        .one_or_none()
    )
    setup_bill(
        bill_repo,
        bill_processing_record_repo,
        amount=10_000,
        bill_id=9,
        status=BillStatus.PAID,
    )
    assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.WAITING
    setup_cost_breakdown(cb_id=3, amount=15_000, first_cb=False)
    update_tp_cb_id(completed_tp=completed_tp, cb_id=3, data_sourcer=data_sourcer)
    setup_bill(
        bill_repo,
        bill_processing_record_repo,
        amount=5_000,
        bill_id=10,
        status=BillStatus.FAILED,
    )
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=completed_tp.uuid)
        .one_or_none()
    )
    assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.WAITING
    setup_bill(
        bill_repo,
        bill_processing_record_repo,
        amount=5_000,
        bill_id=11,
        status=BillStatus.PAID,
    )
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=completed_tp.uuid)
        .one_or_none()
    )
    assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.PAID


def test_completed_cb1_more_than_cb2_with_failed_first_bill(
    plan_member,
    completed_tp,
    data_sourcer,
    bill_repo,
    bill_processing_record_repo,
):
    setup_cost_breakdown(cb_id=2, amount=10_000, first_cb=True)
    setup_bill(
        bill_repo,
        bill_processing_record_repo,
        amount=10_000,
        bill_id=12,
        status=BillStatus.FAILED,
    )
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=completed_tp.uuid)
        .one_or_none()
    )
    assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.WAITING
    setup_cost_breakdown(cb_id=3, amount=5_000, first_cb=False)
    update_tp_cb_id(completed_tp=completed_tp, cb_id=3, data_sourcer=data_sourcer)
    setup_bill(
        bill_repo,
        bill_processing_record_repo,
        amount=-5_000,
        bill_id=13,
        status=BillStatus.REFUNDED,
    )
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=completed_tp.uuid)
        .one_or_none()
    )
    assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.WAITING
    setup_bill(
        bill_repo,
        bill_processing_record_repo,
        amount=10_000,
        bill_id=14,
        status=BillStatus.PAID,
    )
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=completed_tp.uuid)
        .one_or_none()
    )
    assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.PAID


def test_completed_cb1_more_than_cb2_with_failed_second_bill(
    plan_member,
    completed_tp,
    data_sourcer,
    bill_repo,
    bill_processing_record_repo,
):
    setup_cost_breakdown(cb_id=2, amount=10_000, first_cb=True)
    setup_bill(
        bill_repo,
        bill_processing_record_repo,
        amount=10_000,
        bill_id=15,
        status=BillStatus.PAID,
    )
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=completed_tp.uuid)
        .one_or_none()
    )
    assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.PAID
    setup_cost_breakdown(cb_id=3, amount=5_000, first_cb=False)
    update_tp_cb_id(completed_tp=completed_tp, cb_id=3, data_sourcer=data_sourcer)
    setup_bill(
        bill_repo,
        bill_processing_record_repo,
        amount=-5_000,
        bill_id=16,
        status=BillStatus.FAILED,
    )
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=completed_tp.uuid)
        .one_or_none()
    )
    assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.PAID
    setup_bill(
        bill_repo,
        bill_processing_record_repo,
        amount=-5_000,
        bill_id=17,
        status=BillStatus.REFUNDED,
    )
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=completed_tp.uuid)
        .one_or_none()
    )
    assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.PAID


def test_completed_cb1_equals_cb2(
    plan_member,
    completed_tp,
    data_sourcer,
    bill_repo,
    bill_processing_record_repo,
):
    setup_cost_breakdown(cb_id=2, amount=10_000, first_cb=True)
    setup_bill(
        bill_repo,
        bill_processing_record_repo,
        amount=10_000,
        bill_id=18,
        status=BillStatus.PAID,
    )
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=completed_tp.uuid)
        .one_or_none()
    )
    assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.PAID
    setup_cost_breakdown(cb_id=3, amount=10_000, first_cb=False)
    update_tp_cb_id(completed_tp=completed_tp, cb_id=3, data_sourcer=data_sourcer)
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=completed_tp.uuid)
        .one_or_none()
    )
    assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.PAID


def test_partially_completed_tp(
    plan_member,
    integration_wallet,
    data_sourcer,
    bill_repo,
    bill_processing_record_repo,
):
    scheduled_tp = TreatmentProcedureFactory.create(
        id=2,
        cost_breakdown_id=2,
        uuid=TP_UUID_2,
        status=TreatmentProcedureStatus.SCHEDULED,
        reimbursement_wallet_id=integration_wallet.id,
        start_date=datetime.strptime("15/01/2018", date_fmt),
        end_date=datetime.strptime("15/11/2018", date_fmt),
        completed_date=datetime.strptime("15/11/2018 15:30", dt_fmt),
        procedure_type=TreatmentProcedureType.MEDICAL,
        member_id=integration_wallet.user_id,
    )
    setup_cost_breakdown(cb_id=2, amount=10_000, first_cb=True)
    setup_bill(
        bill_repo,
        bill_processing_record_repo,
        amount=10_000,
        bill_id=19,
        status=BillStatus.PAID,
    )
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=scheduled_tp.uuid)
        .one_or_none()
    )
    assert mapping is None
    scheduled_tp.status = TreatmentProcedureStatus.CANCELLED
    setup_bill(
        bill_repo,
        bill_processing_record_repo,
        amount=-10_000,
        bill_id=2,
        status=BillStatus.REFUNDED,
    )
    data_sourcer.treatment_procedure_repo.session.add(scheduled_tp)

    partially_completed_tp = TreatmentProcedureFactory.create(
        id=3,
        cost_breakdown_id=4,
        uuid=TP_UUID_3,
        status=TreatmentProcedureStatus.PARTIALLY_COMPLETED,
        reimbursement_wallet_id=integration_wallet.id,
        start_date=datetime.strptime("15/01/2018", date_fmt),
        end_date=datetime.strptime("15/11/2018", date_fmt),
        completed_date=datetime.strptime("15/11/2018 15:30", dt_fmt),
        procedure_type=TreatmentProcedureType.MEDICAL,
        member_id=integration_wallet.user_id,
    )
    CostBreakdownFactory.create(
        treatment_procedure_uuid=TP_UUID_3,
        wallet_id=3,
        id=4,
        total_member_responsibility=10_000,
        deductible=10_000,
        oop_applied=10_000,
        created_at=datetime.strptime("12/12/2018 00:00", "%d/%m/%Y %H:%M"),
    )
    bill = BillFactory.build(
        id=20,
        payor_id=1,
        procedure_id=3,
        amount=10_000,
        payor_type=PayorType.MEMBER,
        status=BillStatus.PAID,
        created_at=datetime.strptime("12/11/2018 00:00", dt_fmt),
    )
    bpr = BillProcessingRecordFactory.build(
        bill_id=20,
        bill_status=BillStatus.PAID.value,
        processing_record_type="payment_gateway_request",
    )
    bill_repo.create(instance=bill)
    bill_processing_record_repo.create(instance=bpr)
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=partially_completed_tp.uuid)
        .one_or_none()
    )
    assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.PAID


def test_completed_tp_no_member_responsibility(
    plan_member,
    completed_tp,
    data_sourcer,
    bill_repo,
    bill_processing_record_repo,
):
    setup_cost_breakdown(cb_id=3, amount=0, first_cb=True)
    setup_cost_breakdown(cb_id=2, amount=0, first_cb=False)
    setup_bill(
        bill_repo,
        bill_processing_record_repo,
        amount=0,
        bill_id=21,
        status=BillStatus.PAID,
    )
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=completed_tp.uuid)
        .one_or_none()
    )
    assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.SKIP


def test_completed_tp_no_member_responsibility_no_bills(
    plan_member,
    completed_tp,
    data_sourcer,
):
    setup_cost_breakdown(cb_id=3, amount=0, first_cb=True)
    setup_cost_breakdown(cb_id=2, amount=0, first_cb=False)
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=completed_tp.uuid)
        .one_or_none()
    )
    assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.SKIP


def test_completed_tp_no_member_responsibility_no_bills_wrong_cb_id_row_error(
    plan_member,
    completed_tp,
    data_sourcer,
):
    setup_cost_breakdown(cb_id=3, amount=0, first_cb=True)
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=completed_tp.uuid)
        .one_or_none()
    )
    assert (
        mapping.treatment_accumulation_status == TreatmentAccumulationStatus.ROW_ERROR
    )


def test_completed_tp_no_member_responsibility_tp_was_waiting(
    plan_member,
    completed_tp,
    data_sourcer,
    uhc_payer,
):
    setup_cost_breakdown(cb_id=3, amount=0, first_cb=True)
    setup_cost_breakdown(cb_id=2, amount=0, first_cb=False)
    AccumulationTreatmentMappingFactory.create(
        treatment_procedure_uuid=completed_tp.uuid,
        payer_id=uhc_payer.id,
        completed_at=datetime.strptime("12/12/2018 00:00", "%d/%m/%Y %H:%M"),
        treatment_accumulation_status=TreatmentAccumulationStatus.WAITING,
    )
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=completed_tp.uuid)
        .one_or_none()
    )
    assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.SKIP


def test_completed_tp_member_responsibility_no_bills_waiting(
    plan_member,
    completed_tp,
    data_sourcer,
    uhc_payer,
):
    setup_cost_breakdown(cb_id=3, amount=100, first_cb=True)
    setup_cost_breakdown(cb_id=2, amount=100, first_cb=False)
    AccumulationTreatmentMappingFactory.create(
        treatment_procedure_uuid=completed_tp.uuid,
        payer_id=uhc_payer.id,
        completed_at=datetime.strptime("12/12/2018 00:00", "%d/%m/%Y %H:%M"),
        treatment_accumulation_status=TreatmentAccumulationStatus.WAITING,
    )
    data_sourcer.data_source_preparation_for_file_generation()
    mapping = (
        data_sourcer.session.query(AccumulationTreatmentMapping)
        .filter_by(treatment_procedure_uuid=completed_tp.uuid)
        .one_or_none()
    )
    assert mapping.treatment_accumulation_status == TreatmentAccumulationStatus.WAITING
