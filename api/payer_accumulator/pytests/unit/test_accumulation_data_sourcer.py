from datetime import datetime
from unittest.mock import patch

import pytest
from maven import feature_flags

from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from payer_accumulator.accumulation_data_sourcer import ProcedureToAccumulationData
from payer_accumulator.common import TreatmentAccumulationStatus
from payer_accumulator.errors import RefundTreatmentAccumulationError
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.pytests.conftest import (
    TP_UUID_2,
    TP_UUID_3,
    TP_UUID_4,
    TP_UUID_5,
    TP_UUID_6,
)
from payer_accumulator.pytests.factories import AccumulationTreatmentMappingFactory
from wallet.repository.health_plan import (
    HEALTH_PLAN_YOY_FLAG,
    NEW_BEHAVIOR,
    OLD_BEHAVIOR,
)


@pytest.fixture(scope="function")
def treatment_procedure(enterprise_user, cost_breakdown_mr_100):
    return TreatmentProcedureFactory.create(
        start_date=datetime(2023, 2, 15),
        end_date=datetime(2023, 3, 15),
        member_id=enterprise_user.id,
        cost_breakdown_id=cost_breakdown_mr_100.id,
        procedure_type=TreatmentProcedureType.MEDICAL,
        status=TreatmentProcedureStatus.COMPLETED,
    )


@pytest.fixture(scope="function")
def accumulation_treatment_mapping(
    uhc_payer, treatment_procedure, cost_breakdown_mr_100
):
    return AccumulationTreatmentMappingFactory.create(
        treatment_procedure_uuid=treatment_procedure.uuid,
        payer_id=uhc_payer.id,
        deductible=cost_breakdown_mr_100.deductible,
        oop_applied=cost_breakdown_mr_100.oop_applied,
        hra_applied=cost_breakdown_mr_100.hra_applied,
        treatment_accumulation_status=TreatmentAccumulationStatus.SUBMITTED,
    )


def test_get_latest_treatment_procedure_statuses(
    accumulation_data_sourcer,
    treatment_procedures,
    latest_treatment_procedure_to_bills,
    cost_breakdown_mr_100,
    cost_breakdown_mr_200,
):
    with patch(
        "direct_payment.billing.billing_service.BillingService.get_member_paid_by_procedure_ids",
        return_value=latest_treatment_procedure_to_bills,
    ), patch(
        "direct_payment.treatment_procedure.repository.treatment_procedure."
        "TreatmentProcedureRepository.get_treatments_since_datetime_from_statuses_type_wallet_ids",
        return_value=treatment_procedures,
    ), patch(
        "payer_accumulator.accumulation_data_sourcer.AccumulationDataSourcer._get_cost_breakdowns",
        return_value=[cost_breakdown_mr_100, cost_breakdown_mr_200],
    ):
        result = accumulation_data_sourcer._get_latest_treatment_procedure_statuses(
            medical_wallet_ids=[3],
            rx_wallet_ids=[7],
            cutoff=datetime.strptime("15/11/2018 15:29", "%d/%m/%Y %H:%M"),
        )
        for procedure in treatment_procedures:
            assert result[procedure.uuid].completed_date == procedure.completed_date
            assert result[procedure.uuid].start_date == procedure.start_date
            assert result[procedure.uuid].wallet_id == procedure.reimbursement_wallet_id
            assert result[procedure.uuid].member_id == procedure.member_id

        assert result[TP_UUID_2].status == TreatmentAccumulationStatus.PAID
        assert result[TP_UUID_3].status == TreatmentAccumulationStatus.PAID
        assert result[TP_UUID_4].status == TreatmentAccumulationStatus.WAITING
        assert result[TP_UUID_5].status == TreatmentAccumulationStatus.WAITING
        assert result[TP_UUID_6].status == TreatmentAccumulationStatus.WAITING


def test_get_latest_treatment_procedure_statuses_no_cost_breakdown(
    accumulation_data_sourcer, treatment_procedures, latest_treatment_procedure_to_bills
):
    with patch(
        "direct_payment.billing.billing_service.BillingService.get_member_paid_by_procedure_ids",
        return_value=latest_treatment_procedure_to_bills,
    ), patch(
        "direct_payment.treatment_procedure.repository.treatment_procedure."
        "TreatmentProcedureRepository.get_treatments_since_datetime_from_statuses_type_wallet_ids",
        return_value=treatment_procedures,
    ):
        result = accumulation_data_sourcer._get_latest_treatment_procedure_statuses(
            medical_wallet_ids=[3],
            rx_wallet_ids=[7],
            cutoff=datetime.strptime("15/11/2018 15:29", "%d/%m/%Y %H:%M"),
        )
        assert result[TP_UUID_2].status == TreatmentAccumulationStatus.WAITING
        assert result[TP_UUID_2].completed_date == datetime(2018, 11, 15, 15, 30)
        assert result[TP_UUID_3].status == TreatmentAccumulationStatus.WAITING
        assert result[TP_UUID_3].completed_date == datetime(2018, 11, 15, 16, 30)
        assert result[TP_UUID_4].status == TreatmentAccumulationStatus.WAITING
        assert result[TP_UUID_4].completed_date == datetime(2018, 11, 15, 15, 30)
        assert result[TP_UUID_5].status == TreatmentAccumulationStatus.WAITING
        assert result[TP_UUID_5].completed_date == datetime(2018, 11, 15, 18, 30)
        assert result[TP_UUID_6].status == TreatmentAccumulationStatus.WAITING
        assert result[TP_UUID_6].completed_date == datetime(2018, 11, 15, 18, 30)


@pytest.mark.parametrize(
    argnames="feature_flag_variation", argvalues=[OLD_BEHAVIOR, NEW_BEHAVIOR]
)
def test_get_medical_and_rx_accumulation_wallet_ids(
    accumulation_data_sourcer,
    employer_health_plan2,
    employer_health_plan,
    member_health_plans,
    feature_flag_variation,
    ff_test_data,
):
    with feature_flags.test_data() as ff_test_data:
        ff_test_data.update(
            ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(feature_flag_variation)
        )
        (
            medical_ids,
            rx_ids,
        ) = accumulation_data_sourcer._get_medical_and_rx_accumulation_wallet_ids()
    assert len(medical_ids) == 3
    assert 5 in medical_ids
    assert 6 in medical_ids
    assert 7 in medical_ids
    assert len(rx_ids) == 1
    assert 7 in rx_ids


def test_get_treatment_procedure_cutoff(
    accumulation_data_sourcer, accumulation_treatment_mappings
):
    assert (
        accumulation_data_sourcer._get_treatment_procedure_cutoff()
        == datetime.strptime("15/11/2019 14:33", "%d/%m/%Y %H:%M")
    )


def test_get_treatment_procedure_cutoff_none(
    accumulation_data_sourcer, accumulation_treatment_mappings
):
    accumulation_data_sourcer.payer_id = 123
    assert accumulation_data_sourcer._get_treatment_procedure_cutoff() is None


def test_get_paid_waiting_treatment_procedure_statuses(
    accumulation_data_sourcer,
    accumulation_treatment_mappings,
    treatment_procedures,
    waiting_treatment_procedure_to_bills,
    cost_breakdown_mr_100,
    cost_breakdown_mr_200,
):
    with patch(
        "direct_payment.billing.billing_service.BillingService.get_member_paid_by_procedure_ids",
        return_value=waiting_treatment_procedure_to_bills,
    ), patch(
        "payer_accumulator.accumulation_data_sourcer.AccumulationDataSourcer._get_cost_breakdowns",
        return_value=[cost_breakdown_mr_100, cost_breakdown_mr_200],
    ):
        waiting_tps = (
            accumulation_data_sourcer._get_paid_waiting_treatment_procedure_statuses()
        )
        assert len(waiting_tps) == 1
        assert waiting_tps[TP_UUID_2].status == TreatmentAccumulationStatus.PAID
        assert waiting_tps[TP_UUID_2].completed_date == datetime(2018, 11, 15, 15, 30)


def test_get_paid_waiting_treatment_procedure_statuses_row_error(
    accumulation_data_sourcer,
    accumulation_treatment_mappings,
    treatment_procedures,
    waiting_treatment_procedure_to_bills,
    cost_breakdown_mr_100,
    cost_breakdown_mr_150,
):
    with patch(
        "direct_payment.billing.billing_service.BillingService.get_member_paid_by_procedure_ids",
        return_value=waiting_treatment_procedure_to_bills,
    ), patch(
        "payer_accumulator.accumulation_data_sourcer.AccumulationDataSourcer._get_cost_breakdowns",
        return_value=[cost_breakdown_mr_150, cost_breakdown_mr_100],
    ):
        waiting_tps = (
            accumulation_data_sourcer._get_paid_waiting_treatment_procedure_statuses()
        )
        assert len(waiting_tps) == 2
        assert waiting_tps[TP_UUID_2].status == TreatmentAccumulationStatus.ROW_ERROR
        assert waiting_tps[TP_UUID_2].completed_date == datetime(2018, 11, 15, 15, 30)
        assert waiting_tps[TP_UUID_5].status == TreatmentAccumulationStatus.ROW_ERROR
        assert waiting_tps[TP_UUID_5].completed_date == datetime(2018, 11, 15, 18, 30)


def test_get_accumulation_treatment_procedure_statuses(
    accumulation_data_sourcer,
    treatment_procedures,
    latest_treatment_procedure_to_bills,
    cost_breakdown_mr_100,
    cost_breakdown_mr_200,
):
    with patch(
        "direct_payment.billing.billing_service.BillingService.get_member_paid_by_procedure_ids",
        return_value=latest_treatment_procedure_to_bills,
    ), patch(
        "payer_accumulator.accumulation_data_sourcer.AccumulationDataSourcer._get_cost_breakdowns",
        return_value=[cost_breakdown_mr_100, cost_breakdown_mr_200],
    ):
        tp_statuses = (
            accumulation_data_sourcer._get_accumulation_treatment_procedure_statuses(
                treatment_procedures=treatment_procedures
            )
        )
        assert len(tp_statuses) == 5
        assert tp_statuses[TP_UUID_2].status == TreatmentAccumulationStatus.PAID
        assert tp_statuses[TP_UUID_2].completed_date == datetime(2018, 11, 15, 15, 30)

        assert tp_statuses[TP_UUID_3].status == TreatmentAccumulationStatus.PAID
        assert tp_statuses[TP_UUID_3].completed_date == datetime(2018, 11, 15, 16, 30)

        assert tp_statuses[TP_UUID_4].status == TreatmentAccumulationStatus.WAITING
        assert tp_statuses[TP_UUID_4].completed_date == datetime(2018, 11, 15, 15, 30)

        assert tp_statuses[TP_UUID_5].status == TreatmentAccumulationStatus.WAITING
        assert tp_statuses[TP_UUID_5].completed_date == datetime(2018, 11, 15, 18, 30)


def test_update_accumulation_treatment_mapping(
    accumulation_data_sourcer, accumulation_treatment_mappings
):
    tp_statuses = {
        TP_UUID_5: ProcedureToAccumulationData(
            status=TreatmentAccumulationStatus.ROW_ERROR,
            completed_date=datetime(2019, 11, 15, 14, 33),
            wallet_id=3,
            member_id=-1,
            start_date=datetime(2024, 1, 1),
        ),
        TP_UUID_2: ProcedureToAccumulationData(
            status=TreatmentAccumulationStatus.PAID,
            completed_date=datetime(2019, 11, 15, 14, 33),
            wallet_id=3,
            member_id=-1,
            start_date=datetime(2024, 1, 1),
        ),
    }

    with patch(
        "payer_accumulator.accumulation_data_sourcer.AccumulationDataSourcer._mapping_is_this_payer",
        return_value=True,
    ):
        accumulation_data_sourcer._update_accumulation_treatment_mapping(tp_statuses)

    row_error = AccumulationTreatmentMapping.query.filter(
        AccumulationTreatmentMapping.treatment_procedure_uuid == TP_UUID_5
    ).one_or_none()
    paid = AccumulationTreatmentMapping.query.filter(
        AccumulationTreatmentMapping.treatment_procedure_uuid == TP_UUID_2
    ).one_or_none()
    assert (
        row_error.treatment_accumulation_status == TreatmentAccumulationStatus.ROW_ERROR
    )
    assert row_error.completed_at == datetime.strptime(
        "15/11/2018 14:30", "%d/%m/%Y %H:%M"
    )
    assert paid.treatment_accumulation_status == TreatmentAccumulationStatus.PAID
    assert paid.completed_at == datetime.strptime("15/11/2019 14:30", "%d/%m/%Y %H:%M")
    not_updated = AccumulationTreatmentMapping.query.filter(
        AccumulationTreatmentMapping.treatment_procedure_uuid == TP_UUID_3
    ).one_or_none()
    assert not_updated.treatment_accumulation_status == TreatmentAccumulationStatus.PAID


def test_insert_accumulation_treatment_mapping(
    accumulation_data_sourcer, accumulation_treatment_mappings, logs
):
    TP_UUID_6 = "a8651a5e-f4e4-4acf-bbf3-072a4c5b5a76"
    TP_UUID_7 = "b2319d7f-d77a-41b3-98e6-d47b86a5d1c7"
    tp_statuses = {
        TP_UUID_5: ProcedureToAccumulationData(
            status=TreatmentAccumulationStatus.ROW_ERROR,
            completed_date=datetime(2019, 11, 15, 14, 33),
            wallet_id=3,
            member_id=-1,
            start_date=datetime(2024, 1, 1),
        ),
        "a8651a5e-f4e4-4acf-bbf3-072a4c5b5a76": ProcedureToAccumulationData(
            status=TreatmentAccumulationStatus.PAID,
            completed_date=datetime(2019, 11, 15, 14, 33),
            wallet_id=3,
            member_id=-1,
            start_date=datetime(2024, 1, 1),
        ),
        "b2319d7f-d77a-41b3-98e6-d47b86a5d1c7": ProcedureToAccumulationData(
            status=TreatmentAccumulationStatus.REFUNDED,
            completed_date=datetime(2019, 11, 15, 14, 33),
            wallet_id=3,
            member_id=-1,
            start_date=datetime(2024, 1, 1),
        ),
    }
    with patch(
        "payer_accumulator.accumulation_data_sourcer.AccumulationDataSourcer._mapping_is_this_payer",
        return_value=True,
    ):
        accumulation_data_sourcer._insert_accumulation_treatment_mapping(tp_statuses)

    skip_log = next((r for r in logs if "Skipping insert" in r["event"]), None)
    assert skip_log is not None
    row_waiting = AccumulationTreatmentMapping.query.filter(
        AccumulationTreatmentMapping.treatment_procedure_uuid == TP_UUID_5
    ).one_or_none()
    assert (
        row_waiting.treatment_accumulation_status == TreatmentAccumulationStatus.WAITING
    )
    assert not row_waiting.is_refund
    row_new = AccumulationTreatmentMapping.query.filter(
        AccumulationTreatmentMapping.treatment_procedure_uuid == TP_UUID_6
    ).one_or_none()
    assert row_new.treatment_accumulation_status == TreatmentAccumulationStatus.PAID
    assert not row_new.is_refund
    row_refund = AccumulationTreatmentMapping.query.filter(
        AccumulationTreatmentMapping.treatment_procedure_uuid == TP_UUID_7
    ).one_or_none()
    assert (
        row_refund.treatment_accumulation_status == TreatmentAccumulationStatus.REFUNDED
    )
    assert row_refund.is_refund


def test_accumulation_employer_health_plans(
    accumulation_data_sourcer,
    employer_health_plan,
    employer_health_plan2,
    employer_health_plan3,
):
    ehps = accumulation_data_sourcer._accumulation_employer_health_plans
    assert len(ehps) == 2
    assert employer_health_plan in ehps
    assert employer_health_plan2 in ehps
    assert employer_health_plan3 not in ehps


def test_determine_tp_accumulation_status_one_cost_breakdown(
    accumulation_data_sourcer,
    treatment_procedures,
    latest_treatment_procedure_to_bills,
    cost_breakdown_mr_100,
):
    assert (
        TreatmentAccumulationStatus.PAID
        == accumulation_data_sourcer._determine_tp_accumulation_status(
            treatment_procedure=treatment_procedures[0],
            bills=latest_treatment_procedure_to_bills.get(2),
        )
    )


def test_determine_tp_accumulation_status_two_cost_breakdown_not_paid(
    accumulation_data_sourcer,
    treatment_procedures,
    latest_treatment_procedure_to_bills,
    cost_breakdown_mr_100,
    cost_breakdown_mr_150,
):
    tp = treatment_procedures[0]
    tp.cost_breakdown_id = 4
    assert (
        TreatmentAccumulationStatus.WAITING
        == accumulation_data_sourcer._determine_tp_accumulation_status(
            treatment_procedure=treatment_procedures[0],
            bills=latest_treatment_procedure_to_bills.get(2),
        )
    )


def test_determine_tp_accumulation_status_two_cost_breakdown_latest_paid(
    accumulation_data_sourcer,
    treatment_procedures,
    latest_treatment_procedure_to_bills,
    cost_breakdown_mr_100,
    cost_breakdown_mr_200,
):
    assert (
        TreatmentAccumulationStatus.PAID
        == accumulation_data_sourcer._determine_tp_accumulation_status(
            treatment_procedure=treatment_procedures[0],
            bills=latest_treatment_procedure_to_bills.get(2),
        )
    )


def test_determine_tp_accumulation_status_two_cost_breakdown_bad_data(
    accumulation_data_sourcer,
    treatment_procedures,
    latest_treatment_procedure_to_bills,
    cost_breakdown_mr_100,
    cost_breakdown_mr_200,
):
    tp = treatment_procedures[0]
    tp.cost_breakdown_id = 3
    assert (
        TreatmentAccumulationStatus.ROW_ERROR
        == accumulation_data_sourcer._determine_tp_accumulation_status(
            treatment_procedure=treatment_procedures[0],
            bills=latest_treatment_procedure_to_bills.get(2),
        )
    )


def test_determine_tp_accumulation_status_no_cost_breakdown(
    accumulation_data_sourcer, treatment_procedures, latest_treatment_procedure_to_bills
):
    assert (
        TreatmentAccumulationStatus.WAITING
        == accumulation_data_sourcer._determine_tp_accumulation_status(
            treatment_procedure=treatment_procedures[0],
            bills=latest_treatment_procedure_to_bills.get(2),
        )
    )


def test_determine_partially_completed_tp_accumulation_status_one_cost_breakdown(
    accumulation_data_sourcer,
    treatment_procedures,
    latest_treatment_procedure_to_bills,
    cost_breakdown_mr_100,
):
    tp = treatment_procedures[0]
    tp.status = TreatmentProcedureStatus.PARTIALLY_COMPLETED
    tp.cost_breakdown_id = 2
    assert (
        TreatmentAccumulationStatus.PAID
        == accumulation_data_sourcer._determine_tp_accumulation_status(
            treatment_procedure=treatment_procedures[0],
            bills=latest_treatment_procedure_to_bills.get(2),
        )
    )


class TestRevertTreatmentAccumulation:
    def test_not_sent_to_payer_yet(
        self,
        accumulation_data_sourcer,
        treatment_procedure,
        accumulation_treatment_mapping,
    ):
        accumulation_treatment_mapping.treatment_accumulation_status = (
            TreatmentAccumulationStatus.PAID
        )
        mapping = accumulation_data_sourcer.revert_treatment_accumulation(
            treatment_procedure
        )
        assert mapping is None
        assert (
            accumulation_treatment_mapping.treatment_accumulation_status
            == TreatmentAccumulationStatus.SKIP
        )

    def test_already_sent_to_payer(
        self,
        accumulation_data_sourcer,
        treatment_procedure,
        accumulation_treatment_mapping,
    ):
        mapping = accumulation_data_sourcer.revert_treatment_accumulation(
            treatment_procedure
        )
        assert mapping is not None
        assert (
            mapping.treatment_accumulation_status
            == TreatmentAccumulationStatus.REFUNDED
        )
        assert mapping.payer_id == accumulation_data_sourcer.payer_id
        assert mapping.completed_at == treatment_procedure.completed_date
        assert mapping.deductible == -10000
        assert mapping.oop_applied == -10000
        assert mapping.hra_applied == -5000

    @pytest.mark.parametrize(
        argnames="status",
        argvalues=(
            TreatmentAccumulationStatus.REFUNDED,
            TreatmentAccumulationStatus.PROCESSED,
            TreatmentAccumulationStatus.SUBMITTED,
        ),
    )
    def test_refund_mapping_already_existed(
        self,
        status,
        accumulation_data_sourcer,
        treatment_procedure,
        accumulation_treatment_mapping,
        cost_breakdown_mr_100,
    ):
        AccumulationTreatmentMappingFactory.create(
            treatment_procedure_uuid=treatment_procedure.uuid,
            payer_id=accumulation_data_sourcer.payer_id,
            deductible=-cost_breakdown_mr_100.deductible,
            oop_applied=-cost_breakdown_mr_100.oop_applied,
            hra_applied=-cost_breakdown_mr_100.hra_applied,
            treatment_accumulation_status=status,
        )
        with pytest.raises(RefundTreatmentAccumulationError):
            accumulation_data_sourcer.revert_treatment_accumulation(treatment_procedure)

    def test_negative_amount_sent_to_payer(
        self,
        accumulation_data_sourcer,
        treatment_procedure,
        cost_breakdown_mr_100,
    ):
        AccumulationTreatmentMappingFactory.create(
            treatment_procedure_uuid=treatment_procedure.uuid,
            payer_id=accumulation_data_sourcer.payer_id,
            deductible=-cost_breakdown_mr_100.deductible,
            oop_applied=-cost_breakdown_mr_100.oop_applied,
            treatment_accumulation_status=TreatmentAccumulationStatus.SUBMITTED,
        )
        with pytest.raises(RefundTreatmentAccumulationError):
            accumulation_data_sourcer.revert_treatment_accumulation(treatment_procedure)
