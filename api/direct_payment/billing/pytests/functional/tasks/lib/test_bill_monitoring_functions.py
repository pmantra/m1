import uuid
from datetime import date, datetime
from unittest import mock

import pytest

from direct_payment.billing.models import BillStatus, PayorType
from direct_payment.billing.pytests import factories
from direct_payment.billing.tasks.lib.bill_monitoring_functions import (
    monitor_bills_completed_tps,
    monitor_bills_scheduled_tps,
    monitor_failed_bills,
    monitor_stale_new_member_bills,
)


class TestBillMonitoringFunctions:
    @pytest.mark.parametrize(
        ids=[
            "1. Bills with and without refunds logged with default levels.",
            "2. Cut off date earlier than all bills, nothing logged.",
            "3. Cut off date earlier than all bills except one bill without a refund. Only 1 logged at error level.",
        ],
        argvalues=[
            (
                date(2018, 11, 12),
                {5},
                {0, 1, 3},
                True,
                True,
            ),
            (
                date(2018, 10, 15),
                {},
                {},
                False,
                False,
            ),
            (
                date(2018, 11, 9),
                {5},
                {},
                True,
                False,
            ),
        ],
        argnames="date_cutoff, bill_wo_ref_indices, bill_with_ref_indices, error_logged, warning_logged",
    )
    def test_log_stale_new_member_bills(
        self,
        billing_service,
        bill_repository,
        date_cutoff,
        bill_wo_ref_indices,
        bill_with_ref_indices,
        error_logged,
        warning_logged,
    ):
        exp_bill_wo_ref_uuids = set()
        exp_bill_with_ref_uuids = set()
        bills_to_create = [
            # ---------------------------------------------------
            # bills with payor id 1 - one FAILED refund
            [datetime(2018, 11, 12), 1, BillStatus.NEW, 1000],
            [datetime(2018, 11, 11), 1, BillStatus.NEW, 1000],
            [datetime(2018, 11, 13), 1, BillStatus.FAILED, -1000],
            # ---------------------------------------------------
            # bills with payor id 2 - one PROCESSING refund
            [datetime(2018, 11, 10), 2, BillStatus.NEW, 1000],
            [datetime(2018, 11, 14), 2, BillStatus.PROCESSING, -1000],
            # ---------------------------------------------------
            # bills with payor id 3
            [datetime(2018, 11, 9), 3, BillStatus.NEW, 1000],
            # ---------------------------------------------------
        ]

        for i, item in enumerate(bills_to_create):
            bill = factories.BillFactory.build(
                created_at=item[0],
                payor_id=item[1],
                status=item[2],
                amount=item[3],
            )
            billing_service.bill_repo.create(instance=bill)
            if i in bill_wo_ref_indices:
                exp_bill_wo_ref_uuids.add(str(bill.uuid))
            elif i in bill_with_ref_indices:
                exp_bill_with_ref_uuids.add(str(bill.uuid))
        with mock.patch("structlog.stdlib.BoundLogger.error") as log_error:
            with mock.patch("structlog.stdlib.BoundLogger.warning") as log_warning:
                monitor_stale_new_member_bills(date_cutoff)
                assert bool(log_error.call_args) == error_logged
                assert bool(log_warning.call_args) == warning_logged
                # check logging of bills without refunds
                if error_logged:
                    log_error.call_args.kwargs["bill_count"] = len(
                        exp_bill_wo_ref_uuids
                    )
                    assert (
                        set(log_error.call_args.kwargs["uuids"].split(", "))
                        == exp_bill_wo_ref_uuids
                    )

                # check logging of bills with refunds
                if warning_logged:
                    log_warning.call_args.kwargs["bill_count"] = len(
                        exp_bill_with_ref_uuids
                    )
                    assert (
                        set(log_warning.call_args.kwargs["uuids"].split(", "))
                        == exp_bill_with_ref_uuids
                    )

    def test_monitor_failed_bills(
        self,
        billing_service,
        bill_repository,
    ):
        bills_to_create = [
            (PayorType.CLINIC, BillStatus.NEW, None),
            (PayorType.CLINIC, BillStatus.FAILED, ({"error_payload": {"A": "B"}})),
            (
                PayorType.CLINIC,
                BillStatus.FAILED,
                ({"error_payload": {"decline_code": "code"}}),
            ),
            (PayorType.CLINIC, BillStatus.FAILED, ({"error_detail": {}})),
            (PayorType.EMPLOYER, BillStatus.NEW, None),
            (PayorType.EMPLOYER, BillStatus.PROCESSING, None),
            (PayorType.EMPLOYER, BillStatus.REFUNDED, None),
            (
                PayorType.EMPLOYER,
                BillStatus.FAILED,
                ({"error_detail": {"message": "ABC"}}),
            ),
            (PayorType.MEMBER, BillStatus.NEW, None),
            (PayorType.MEMBER, BillStatus.FAILED, None),
            (PayorType.MEMBER, BillStatus.FAILED, None),
            (PayorType.MEMBER, BillStatus.PROCESSING, None),
        ]
        for payor_type, status, body in bills_to_create:
            bill = billing_service.bill_repo.create(
                instance=(
                    factories.BillFactory.build(payor_type=payor_type, status=status)
                )
            )
            if body:
                billing_service.bill_processing_record_repo.create(
                    instance=factories.BillProcessingRecordFactory.build(
                        bill_id=bill.id,
                        bill_status=bill.status.value,
                        transaction_id=uuid.uuid4(),
                        # these 2 fields do not matter
                        processing_record_type="payment_gateway_request",
                        body=body,
                    )
                )
        with mock.patch(
            "direct_payment.billing.tasks.lib.bill_monitoring_functions.log.info"
        ) as mocked_log:
            monitor_failed_bills()
            assert mocked_log.call_count == 3
            kw_0, kw_1, kw_2 = (ca.kwargs for ca in mocked_log.call_args_list)
            assert kw_0["bill_payor_type"] == PayorType.CLINIC.value
            assert kw_0["bill_failed_count"] == 3
            assert kw_1["bill_payor_type"] == PayorType.EMPLOYER.value
            assert kw_1["bill_failed_count"] == 1
            assert kw_2["bill_payor_type"] == PayorType.MEMBER.value
            assert kw_2["bill_failed_count"] == 2

    def test_monitor_bills_scheduled_tps(
        self,
        billing_service,
        bill_repository,
        caplog,
    ):
        bills_to_create = [
            [BillStatus.NEW, 3, True],
            [BillStatus.NEW, 4, True],
            [BillStatus.FAILED, 5, True],
            [BillStatus.NEW, 6, False],
            [BillStatus.NEW, 6, True],
        ]
        for item in bills_to_create:
            bill = factories.BillFactory.build(
                status=item[0],
                procedure_id=item[1],
                is_ephemeral=item[2],
            )
            billing_service.bill_repo.create(instance=bill)
        with mock.patch(
            "direct_payment.billing.tasks.lib.bill_monitoring_functions.log.info"
        ) as mocked_log_info, mock.patch(
            "direct_payment.billing.tasks.lib.bill_monitoring_functions.log.error"
        ) as mocked_log_error:
            with mock.patch(
                "direct_payment.billing.lib.legacy_mono.get_treatment_procedure_ids_with_status_since_bill_timing_change",
                return_value=[3, 4],
            ):
                monitor_bills_scheduled_tps()
                assert mocked_log_info.call_count == 2
            with mock.patch(
                "direct_payment.billing.lib.legacy_mono.get_treatment_procedure_ids_with_status_since_bill_timing_change",
                return_value=[5],
            ):
                monitor_bills_scheduled_tps()
                assert mocked_log_error.call_count == 1
            with mock.patch(
                "direct_payment.billing.lib.legacy_mono.get_treatment_procedure_ids_with_status_since_bill_timing_change",
                return_value=[6],
            ):
                monitor_bills_scheduled_tps()
                assert mocked_log_error.call_count == 2

    def test_monitor_bills_completed_tps(
        self,
        billing_service,
        bill_repository,
        caplog,
    ):
        bills_to_create = [
            [BillStatus.NEW, 3, True],
            [BillStatus.NEW, 3, False],
            [BillStatus.NEW, 4, False],
            [BillStatus.FAILED, 5, False],
            [BillStatus.NEW, 6, True],
        ]
        for item in bills_to_create:
            bill = factories.BillFactory.build(
                status=item[0],
                procedure_id=item[1],
                is_ephemeral=item[2],
            )
            billing_service.bill_repo.create(instance=bill)
        with mock.patch(
            "direct_payment.billing.tasks.lib.bill_monitoring_functions.log.info"
        ) as mocked_log_info, mock.patch(
            "direct_payment.billing.tasks.lib.bill_monitoring_functions.log.error"
        ) as mocked_log_error:
            with mock.patch(
                "direct_payment.billing.lib.legacy_mono.get_treatment_procedure_ids_with_status_since_bill_timing_change",
                return_value=[4, 5],
            ):
                monitor_bills_completed_tps()
                assert mocked_log_info.call_count == 2
            with mock.patch(
                "direct_payment.billing.lib.legacy_mono.get_treatment_procedure_ids_with_status_since_bill_timing_change",
                return_value=[3],
            ):
                monitor_bills_completed_tps()
                assert mocked_log_error.call_count == 1
            with mock.patch(
                "direct_payment.billing.lib.legacy_mono.get_treatment_procedure_ids_with_status_since_bill_timing_change",
                return_value=[6],
            ):
                monitor_bills_completed_tps()
                assert mocked_log_error.call_count == 2
