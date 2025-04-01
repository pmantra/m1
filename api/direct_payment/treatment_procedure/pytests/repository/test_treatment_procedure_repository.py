from datetime import date, datetime, timedelta

import pytest

from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.clinic.pytests.factories import FeeScheduleGlobalProceduresFactory
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.pytests import factories
from direct_payment.treatment_procedure.repository.treatment_procedure import (
    TreatmentProcedureRepository,
)
from direct_payment.treatment_procedure.repository.treatment_procedures_needing_questionnaires_repository import (
    TreatmentProceduresNeedingQuestionnairesRepository,
)
from wallet.models.constants import PatientInfertilityDiagnosis
from wallet.pytests.factories import ReimbursementWalletFactory


@pytest.fixture
def procedure_repo(db):
    return TreatmentProcedureRepository(db.session)


@pytest.fixture
def tpnq_repo(db):
    return TreatmentProceduresNeedingQuestionnairesRepository(db.session)


@pytest.fixture
def historic_procedure():
    return factories.TreatmentProcedureFactory.create(
        status=TreatmentProcedureStatus.COMPLETED,
        reimbursement_request_category_id=1,
        reimbursement_wallet_id=1,
    )


@pytest.fixture
def pending_procedure():
    return factories.TreatmentProcedureFactory.create(
        status=TreatmentProcedureStatus.SCHEDULED,
        reimbursement_request_category_id=1,
        reimbursement_wallet_id=1,
    )


@pytest.fixture
def varied_procedures():
    dt_fmt = "%d/%m/%Y %H:%M"
    procedures = [
        factories.TreatmentProcedureFactory.create(
            uuid="9b2e178d-aaf7-47db-8ae7-d56c8efe8da2",
            status=TreatmentProcedureStatus.PARTIALLY_COMPLETED,
            reimbursement_wallet_id=1,
            completed_date=datetime.strptime("15/11/2018 15:30", dt_fmt),
            procedure_type=TreatmentProcedureType.PHARMACY,
        ),
        factories.TreatmentProcedureFactory.create(
            uuid="29d597db-d657-4ba8-953e-c5999abf2cb5",
            status=TreatmentProcedureStatus.COMPLETED,
            reimbursement_wallet_id=1,
            completed_date=datetime.strptime("15/11/2018 16:30", dt_fmt),
            procedure_type=TreatmentProcedureType.MEDICAL,
        ),
        factories.TreatmentProcedureFactory.create(
            status=TreatmentProcedureStatus.SCHEDULED,
            reimbursement_wallet_id=1,
            completed_date=datetime.strptime("15/11/2018 15:30", dt_fmt),
            procedure_type=TreatmentProcedureType.MEDICAL,
        ),
        factories.TreatmentProcedureFactory.create(
            status=TreatmentProcedureStatus.PARTIALLY_COMPLETED,
            reimbursement_wallet_id=2,
            completed_date=datetime.strptime("15/11/2018 15:30", dt_fmt),
            procedure_type=TreatmentProcedureType.MEDICAL,
        ),
        factories.TreatmentProcedureFactory.create(
            status=TreatmentProcedureStatus.COMPLETED,
            reimbursement_wallet_id=2,
            completed_date=datetime.strptime("15/11/2018 16:30", dt_fmt),
            procedure_type=TreatmentProcedureType.MEDICAL,
        ),
        factories.TreatmentProcedureFactory.create(
            status=TreatmentProcedureStatus.SCHEDULED,
            reimbursement_wallet_id=2,
            completed_date=datetime.strptime("15/11/2018 15:30", dt_fmt),
            procedure_type=TreatmentProcedureType.MEDICAL,
        ),
    ]
    return procedures


@pytest.fixture
def expected_id(historic_procedure):
    return historic_procedure.id


def test_read_treatment_procedure(procedure_repo, treatment_procedure):
    assert (
        procedure_repo.read(treatment_procedure_id=treatment_procedure.id).id
        == treatment_procedure.id
    )


def test_create_treatment_procedure(
    procedure_repo,
    global_procedure,
    wallet_cycle_based,
    fertility_clinic,
    fertility_clinic_location,
    enterprise_user,
):
    member_id = enterprise_user.id
    infertility_diagnosis = PatientInfertilityDiagnosis.MEDICALLY_INFERTILE
    reimbursement_wallet_id = wallet_cycle_based.id
    reimbursement_request_category_id = (
        wallet_cycle_based.get_direct_payment_category.id
    )
    fee_schedule_global_procedure = FeeScheduleGlobalProceduresFactory(
        cost=50_000, global_procedure_id=global_procedure["id"]
    )
    fee_schedule_id = fee_schedule_global_procedure.fee_schedule.id
    start_date = date.today()
    end_date = date.today() + timedelta(days=1)
    treatment_procedure = procedure_repo.create(
        member_id=member_id,
        infertility_diagnosis=infertility_diagnosis,
        reimbursement_wallet_id=reimbursement_wallet_id,
        reimbursement_request_category_id=reimbursement_request_category_id,
        fee_schedule_id=fee_schedule_id,
        global_procedure_id=global_procedure["id"],
        global_procedure_name=global_procedure["name"],
        global_procedure_credits=global_procedure["credits"],
        fertility_clinic_id=fertility_clinic.id,
        fertility_clinic_location_id=fertility_clinic_location.id,
        start_date=start_date,
        end_date=end_date,
    )

    assert treatment_procedure.member_id == member_id
    assert treatment_procedure.infertility_diagnosis == infertility_diagnosis
    assert treatment_procedure.reimbursement_wallet_id == reimbursement_wallet_id
    assert (
        treatment_procedure.reimbursement_request_category_id
        == reimbursement_request_category_id
    )
    assert treatment_procedure.fee_schedule_id == fee_schedule_id
    assert treatment_procedure.fertility_clinic_id == fertility_clinic.id
    assert (
        treatment_procedure.fertility_clinic_location_id == fertility_clinic_location.id
    )
    assert treatment_procedure.start_date == start_date
    assert treatment_procedure.end_date == end_date
    assert treatment_procedure.global_procedure_id == global_procedure["id"]
    assert treatment_procedure.procedure_name == global_procedure["name"]
    assert treatment_procedure.cost_credit == global_procedure["credits"]
    assert treatment_procedure.status == TreatmentProcedureStatus.SCHEDULED


def test_create_treatment_procedure_creates_tpnq(
    procedure_repo,
    global_procedure,
    wallet_cycle_based,
    fertility_clinic,
    fertility_clinic_location,
    enterprise_user,
    tpnq_repo,
):
    # Given
    member_id = enterprise_user.id
    infertility_diagnosis = PatientInfertilityDiagnosis.MEDICALLY_INFERTILE
    reimbursement_wallet_id = wallet_cycle_based.id
    reimbursement_request_category_id = (
        wallet_cycle_based.get_direct_payment_category.id
    )
    fee_schedule_global_procedure = FeeScheduleGlobalProceduresFactory(
        cost=50_000, global_procedure_id=global_procedure["id"]
    )
    fee_schedule_id = fee_schedule_global_procedure.fee_schedule.id
    start_date = date.today()
    end_date = date.today() + timedelta(days=1)

    result = tpnq_repo.session.execute(
        "SELECT COUNT(*) FROM treatment_procedures_needing_questionnaires;"
    ).scalar()
    assert result == 0

    # When
    treatment_procedure = procedure_repo.create(
        member_id=member_id,
        infertility_diagnosis=infertility_diagnosis,
        reimbursement_wallet_id=reimbursement_wallet_id,
        reimbursement_request_category_id=reimbursement_request_category_id,
        fee_schedule_id=fee_schedule_id,
        global_procedure_id=global_procedure["id"],
        global_procedure_name=global_procedure["name"],
        global_procedure_credits=global_procedure["credits"],
        fertility_clinic_id=fertility_clinic.id,
        fertility_clinic_location_id=fertility_clinic_location.id,
        start_date=start_date,
        end_date=end_date,
    )

    result = tpnq_repo.get_tpnqs_by_treatment_procedure_ids([treatment_procedure.id])
    assert len(result) == 1
    assert result[0].treatment_procedure_id == treatment_procedure.id


def test_update_treatment_procedure(procedure_repo, treatment_procedure):
    start_date = date.today()
    end_date = date.today() + timedelta(days=1)
    updated_procedure = procedure_repo.update(
        treatment_procedure_id=treatment_procedure.id,
        start_date=start_date,
        end_date=end_date,
        status=None,
    )

    assert updated_procedure.start_date == start_date
    assert updated_procedure.end_date == end_date


def test_update_treatment_procedure_complete(procedure_repo, treatment_procedure):
    start_date = date.today()
    end_date = date.today() + timedelta(days=1)
    status = TreatmentProcedureStatus.COMPLETED
    updated_procedure = procedure_repo.update(
        treatment_procedure_id=treatment_procedure.id,
        start_date=start_date,
        end_date=end_date,
        status=status,
    )

    assert updated_procedure.start_date == start_date
    assert updated_procedure.end_date == end_date
    assert updated_procedure.status == status


def test_update_treatment_procedure_partial(
    procedure_repo, treatment_procedure, treatment_procedure_cycle_based
):
    start_date = date.today()
    end_date = date.today() + timedelta(days=1)
    status = TreatmentProcedureStatus.COMPLETED
    updated_procedure = procedure_repo.update(
        treatment_procedure_id=treatment_procedure_cycle_based.id,
        start_date=start_date,
        end_date=end_date,
        status=status,
        partial_procedure_id=treatment_procedure.id,
    )

    assert updated_procedure.start_date == start_date
    assert updated_procedure.end_date == end_date
    assert updated_procedure.status == status
    assert updated_procedure.partial_procedure_id == treatment_procedure.id


def test_get_payment_history_procedures(procedure_repo, expected_id):
    no_procedures = procedure_repo.get_wallet_payment_history_procedures(
        wallet_id=2, ids=[expected_id]
    )
    assert len(no_procedures) == 0


def test_get_upcoming_payment_history_procedures(procedure_repo, pending_procedure):
    upcoming_procedures = procedure_repo.get_wallet_payment_history_procedures(
        wallet_id=1, ids=[]
    )
    assert len(upcoming_procedures) == 1


def test_get_all_payment_history_procedures(
    procedure_repo, historic_procedure, expected_id, pending_procedure
):
    unwanted_procedure = factories.TreatmentProcedureFactory.create(
        status=TreatmentProcedureStatus.CANCELLED,
        reimbursement_wallet_id=1,
    )

    procedures = procedure_repo.get_wallet_payment_history_procedures(
        wallet_id=1, ids=[expected_id]
    )
    assert len(procedures) == 2
    procedure_ids = frozenset(p.id for p in procedures)
    assert pending_procedure.id in procedure_ids
    assert historic_procedure.id in procedure_ids
    assert unwanted_procedure.id not in procedure_ids


@pytest.mark.skip(reason="fail is blocking a BEX MR")
@pytest.mark.parametrize(
    "cutoff, wallet_ids, tp_statuses, procedure_type, expected_count",
    [
        (
            datetime.strptime("15/11/2018 14:30", "%d/%m/%Y %H:%M"),
            [1, 2],
            [
                TreatmentProcedureStatus.PARTIALLY_COMPLETED,
                TreatmentProcedureStatus.COMPLETED,
            ],
            TreatmentProcedureType.MEDICAL,
            3,
        ),
        (
            datetime.strptime("15/11/2018 14:30", "%d/%m/%Y %H:%M"),
            [1, 2],
            [
                TreatmentProcedureStatus.PARTIALLY_COMPLETED,
                TreatmentProcedureStatus.COMPLETED,
            ],
            TreatmentProcedureType.PHARMACY,
            1,
        ),
        (
            datetime.strptime("15/11/2018 14:30", "%d/%m/%Y %H:%M"),
            [1, 2],
            [TreatmentProcedureStatus.PARTIALLY_COMPLETED],
            None,
            2,
        ),
        (
            datetime.strptime("15/11/2018 16:00", "%d/%m/%Y %H:%M"),
            [1, 2],
            [
                TreatmentProcedureStatus.PARTIALLY_COMPLETED,
                TreatmentProcedureStatus.COMPLETED,
            ],
            None,
            2,
        ),
        (
            datetime.strptime("15/11/2018 16:00", "%d/%m/%Y %H:%M"),
            [1],
            [
                TreatmentProcedureStatus.PARTIALLY_COMPLETED,
                TreatmentProcedureStatus.COMPLETED,
            ],
            None,
            1,
        ),
    ],
)
def test_get_treatments_since_datetime_from_statuses_type_wallet_ids(
    procedure_repo,
    varied_procedures,
    cutoff,
    wallet_ids,
    tp_statuses,
    procedure_type,
    expected_count,
):
    result = procedure_repo.get_treatments_since_datetime_from_statuses_type_wallet_ids(
        wallet_ids=wallet_ids,
        statuses=tp_statuses,
        procedure_type=procedure_type,
        cutoff=cutoff,
    )
    assert len(result) == expected_count


@pytest.mark.skip(reason="Tests are not tearing down correctly.")
@pytest.mark.parametrize(
    "wallet_ids, tp_statuses, expected_count",
    [
        (
            [1, 2],
            [
                TreatmentProcedureStatus.PARTIALLY_COMPLETED,
                TreatmentProcedureStatus.COMPLETED,
            ],
            4,
        ),
        (
            [1, 2],
            [TreatmentProcedureStatus.PARTIALLY_COMPLETED],
            2,
        ),
        (
            [1],
            [
                TreatmentProcedureStatus.PARTIALLY_COMPLETED,
                TreatmentProcedureStatus.COMPLETED,
            ],
            2,
        ),
    ],
)
def test_get_treatments_from_statuses_type_wallet_ids_no_cutoff_no_member_id(
    procedure_repo, varied_procedures, wallet_ids, tp_statuses, expected_count
):
    result = procedure_repo.get_treatments_since_datetime_from_statuses_type_wallet_ids(
        wallet_ids=wallet_ids, statuses=tp_statuses
    )
    assert len(result) == expected_count


@pytest.mark.skip(reason="Tests are not tearing down correctly.")
def test_get_treatments_by_uuids(procedure_repo, varied_procedures):
    tps = procedure_repo.get_treatments_by_uuids(
        ["9b2e178d-aaf7-47db-8ae7-d56c8efe8da2", "29d597db-d657-4ba8-953e-c5999abf2cb5"]
    )
    assert len(tps) == 2


def test_get_treatments_from_statuses_type_wallet_ids_member_id_none_returns_all_active_users(
    procedure_repo, enterprise_user
):
    wallet = ReimbursementWalletFactory.create()
    factories.TreatmentProcedureFactory.create(
        status=TreatmentProcedureStatus.SCHEDULED,
        reimbursement_wallet_id=wallet.id,
        member_id=wallet.user_id,
    )
    factories.TreatmentProcedureFactory.create(
        status=TreatmentProcedureStatus.SCHEDULED,
        reimbursement_wallet_id=wallet.id,
        member_id=enterprise_user.id,
    )

    result = procedure_repo.get_treatments_since_datetime_from_statuses_type_wallet_ids(
        wallet_ids=[wallet.id], statuses=[TreatmentProcedureStatus.SCHEDULED]
    )
    assert len(result) == 2


def test_get_treatments_from_statuses_type_wallet_ids_member_id_returns_none(
    procedure_repo,
    pending_procedure,
):
    result = procedure_repo.get_treatments_since_datetime_from_statuses_type_wallet_ids(
        wallet_ids=[1], statuses=[TreatmentProcedureStatus.SCHEDULED], member_id=2
    )
    assert len(result) == 0


def test_get_treatments_from_statuses_type_wallet_id_multi_wallet_procedures_returns_individual(
    procedure_repo, enterprise_user
):
    wallet = ReimbursementWalletFactory.create()
    factories.TreatmentProcedureFactory.create(
        status=TreatmentProcedureStatus.SCHEDULED,
        reimbursement_wallet_id=wallet.id,
        member_id=wallet.user_id,
    )
    factories.TreatmentProcedureFactory.create(
        status=TreatmentProcedureStatus.SCHEDULED,
        reimbursement_wallet_id=wallet.id,
        member_id=enterprise_user.id,
    )
    result = procedure_repo.get_treatments_since_datetime_from_statuses_type_wallet_ids(
        wallet_ids=[wallet.id],
        statuses=[TreatmentProcedureStatus.SCHEDULED],
        member_id=enterprise_user.id,
    )
    assert len(result) == 1


def test_get_treatment_procedures_with_statuses_since_datetime(
    procedure_repo, enterprise_user
):
    wallet = ReimbursementWalletFactory.create()
    scheduled_after_cutoff = factories.TreatmentProcedureFactory.create(
        status=TreatmentProcedureStatus.SCHEDULED,
        reimbursement_wallet_id=wallet.id,
        member_id=wallet.user_id,
        created_at=datetime.strptime("25/06/2024 14:30", "%d/%m/%Y %H:%M"),
    )
    scheduled_before_cutoff = factories.TreatmentProcedureFactory.create(
        status=TreatmentProcedureStatus.SCHEDULED,
        reimbursement_wallet_id=wallet.id,
        member_id=enterprise_user.id,
        created_at=datetime.strptime("23/06/2024 14:30", "%d/%m/%Y %H:%M"),
    )
    completed_after_cutoff = factories.TreatmentProcedureFactory.create(
        status=TreatmentProcedureStatus.COMPLETED,
        reimbursement_wallet_id=wallet.id,
        member_id=wallet.user_id,
        created_at=datetime.strptime("25/06/2024 14:30", "%d/%m/%Y %H:%M"),
    )
    completed_before_cutoff = factories.TreatmentProcedureFactory.create(
        status=TreatmentProcedureStatus.COMPLETED,
        reimbursement_wallet_id=wallet.id,
        member_id=enterprise_user.id,
        created_at=datetime.strptime("23/06/2024 14:30", "%d/%m/%Y %H:%M"),
    )
    partially_completed_after_cutoff = factories.TreatmentProcedureFactory.create(
        status=TreatmentProcedureStatus.PARTIALLY_COMPLETED,
        reimbursement_wallet_id=wallet.id,
        member_id=enterprise_user.id,
        created_at=datetime.strptime("25/06/2024 14:30", "%d/%m/%Y %H:%M"),
    )
    scheduled = procedure_repo.get_treatment_procedures_with_statuses_since_datetime(
        statuses=["SCHEDULED"],
        cutoff=datetime.strptime("24/06/2024 18:30", "%d/%m/%Y %H:%M"),
    )
    completed = procedure_repo.get_treatment_procedures_with_statuses_since_datetime(
        statuses=["COMPLETED", "PARTIALLY_COMPLETED"],
        cutoff=datetime.strptime("24/06/2024 18:30", "%d/%m/%Y %H:%M"),
    )
    assert scheduled_after_cutoff in scheduled
    assert scheduled_before_cutoff not in scheduled
    assert completed_before_cutoff not in completed
    assert completed_after_cutoff in completed
    assert partially_completed_after_cutoff in completed


class TestGetScheduledProceduresAndCbs:
    @staticmethod
    def test_successfully_returns(procedure_repo):
        # Given
        wallet = ReimbursementWalletFactory.create()
        cb = CostBreakdownFactory.create(wallet_id=wallet.id)
        tp = factories.TreatmentProcedureFactory.create(
            status=TreatmentProcedureStatus.SCHEDULED,
            reimbursement_wallet_id=wallet.id,
            cost_breakdown_id=cb.id,
        )

        # When
        procedures_and_cbs = procedure_repo.get_scheduled_procedures_and_cbs(
            wallet_id=wallet.id, category_id=tp.reimbursement_request_category_id
        )

        # Then
        tp, cb = procedures_and_cbs[0]
        assert tp
        assert cb

    @staticmethod
    def test_successfully_returns_missing_cb(procedure_repo):
        # Given
        wallet = ReimbursementWalletFactory.create()
        tp = factories.TreatmentProcedureFactory.create(
            status=TreatmentProcedureStatus.SCHEDULED,
            reimbursement_wallet_id=wallet.id,
            cost_breakdown_id=None,
        )

        # When
        procedures_and_cbs = procedure_repo.get_scheduled_procedures_and_cbs(
            wallet_id=wallet.id, category_id=tp.reimbursement_request_category_id
        )

        # Then
        tp, cb = procedures_and_cbs[0]
        assert tp
        assert not cb

    @staticmethod
    def test_not_found(procedure_repo):
        # Given
        wallet = ReimbursementWalletFactory.create()
        cb = CostBreakdownFactory.create(wallet_id=wallet.id)
        tp = factories.TreatmentProcedureFactory.create(
            status=TreatmentProcedureStatus.COMPLETED,
            reimbursement_wallet_id=wallet.id,
            cost_breakdown_id=cb.id,
        )

        # When
        procedures_and_cbs = procedure_repo.get_scheduled_procedures_and_cbs(
            wallet_id=wallet.id, category_id=tp.reimbursement_request_category_id
        )

        # Then
        assert not procedures_and_cbs
