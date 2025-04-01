import pytest

from direct_payment.billing.models import BillStateMachine, BillStatus
from direct_payment.billing.pytests import factories


class TestBillModel:
    @pytest.mark.parametrize(
        argvalues=[
            (BillStatus.NEW, BillStatus.PROCESSING, "processing_at"),
            (BillStatus.PROCESSING, BillStatus.PAID, "paid_at"),
            (BillStatus.PROCESSING, BillStatus.REFUNDED, "refunded_at"),
            (BillStatus.NEW, BillStatus.CANCELLED, "cancelled_at"),
            (BillStatus.FAILED, BillStatus.CANCELLED, "cancelled_at"),
        ],
        argnames="old_status,new_status,time_field",
    )
    def test_linear_status_change(
        self, billing_service, old_status, new_status, time_field
    ):
        bill = factories.BillFactory.build(status=old_status)
        assert bill.__getattribute__(time_field) is None

        updated_bill = billing_service._update_bill_status(bill, new_status)

        assert updated_bill.status == new_status
        assert updated_bill.__getattribute__(time_field) is not None

    def test_failure_status_requires_message(self, billing_service):
        bill = factories.BillFactory.build(status=BillStatus.PROCESSING)
        new_status = BillStatus.FAILED
        assert bill.failed_at is None

        with pytest.raises(ValueError):
            billing_service._update_bill_status(bill, new_status)

        updated_bill = billing_service._update_bill_status(
            bill, new_status, "mock_error_type"
        )

        assert updated_bill.status == new_status
        assert updated_bill.failed_at is not None

    def test_retry_failed_status_change(self, billing_service):
        bill = factories.BillFactory.build(
            status=BillStatus.FAILED, error_type="mock_error_type"
        )
        new_status = BillStatus.PROCESSING

        updated_bill = billing_service._update_bill_status(bill, new_status)
        assert updated_bill.status == new_status
        assert updated_bill.processing_at is not None

    @pytest.mark.parametrize(
        argvalues=[
            (
                BillStatus.PAID,
                BillStatus.PROCESSING,
            ),
            (
                BillStatus.NEW,
                BillStatus.PAID,
            ),
            (
                BillStatus.PAID,
                BillStatus.REFUNDED,
            ),
            (
                BillStatus.FAILED,
                BillStatus.NEW,
            ),
        ],
        argnames="old_status,new_status",
    )
    def test_invalid_status_change(self, billing_service, old_status, new_status):
        bill = factories.BillFactory.build(status=old_status)

        with pytest.raises(ValueError):
            billing_service._update_bill_status(bill, new_status)


class TestBillStateMachine:
    @pytest.mark.parametrize(
        argvalues=[
            (BillStatus.PAID, BillStatus.PROCESSING, False),
            (BillStatus.NEW, BillStatus.PAID, False),
            (BillStatus.PAID, BillStatus.REFUNDED, False),
            (BillStatus.FAILED, BillStatus.NEW, False),
            (BillStatus.NEW, BillStatus.PROCESSING, True),
            (BillStatus.PROCESSING, BillStatus.PAID, True),
            (BillStatus.PROCESSING, BillStatus.FAILED, True),
            (BillStatus.FAILED, BillStatus.PROCESSING, True),
            (BillStatus.CANCELLED, BillStatus.CANCELLED, True),
        ],
        argnames="old_status,new_status, expected",
    )
    def test_is_valid_transition(self, old_status, new_status, expected):
        result = BillStateMachine.is_valid_transition(old_status, new_status)
        assert expected == result
