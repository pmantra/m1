from direct_payment.billing.pytests.factories import (
    BillFactory,
    BillProcessingRecordFactory,
)
from direct_payment.billing.repository import (
    BillProcessingRecordRepository,
    BillRepository,
)
from utils.migrations.update_debit_card_fee_refund_bills import (
    remove_debit_card_fee_refund_bills,
    remove_debit_card_fee_refund_bprs,
    update_debit_card_fee_refund_bills,
)


class TestUpdateDebitCardFeeRefundBills:
    def test_update_debit_card_fee_refund_bills(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
    ):
        repo = BillRepository()

        # bill 1 - should not be updated
        repo.create(
            instance=BillFactory.build(
                id=1, amount=55, last_calculated_fee=-20, label="bad-label"
            )
        )

        # bill 2 - abs(amount) >= 50 should update the amount to the fee
        repo.create(
            instance=BillFactory.build(
                id=2, amount=0, last_calculated_fee=-70, label="debit card fee refund"
            )
        )

        # bill 3 - abs(amount) < 50 should update amount to -50
        repo.create(
            instance=BillFactory.build(
                id=3, amount=0, last_calculated_fee=-20, label="debit card fee refund"
            )
        )

        update_debit_card_fee_refund_bills()

        updated_bill_1 = repo.get(id=1)
        assert updated_bill_1.amount == 55  # type: ignore[union-attr] # Item "None" of "Optional[Bill]" has no attribute "amount"
        assert updated_bill_1.last_calculated_fee == -20  # type: ignore[union-attr] # Item "None" of "Optional[Bill]" has no attribute "last_calculated_fee"
        updated_bill_2 = repo.get(id=2)
        assert updated_bill_2.amount == -70  # type: ignore[union-attr] # Item "None" of "Optional[Bill]" has no attribute "amount"
        assert updated_bill_2.last_calculated_fee == 0  # type: ignore[union-attr] # Item "None" of "Optional[Bill]" has no attribute "last_calculated_fee"
        updated_bill_3 = repo.get(id=3)
        assert updated_bill_3.amount == -50  # type: ignore[union-attr] # Item "None" of "Optional[Bill]" has no attribute "amount"
        assert updated_bill_3.last_calculated_fee == 0  # type: ignore[union-attr] # Item "None" of "Optional[Bill]" has no attribute "last_calculated_fee"

    def test_delete_debit_card_fee_refund_bills(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        repo = BillRepository()

        # bill 1 - should not be deleted
        repo.create(
            instance=BillFactory.build(
                id=11, amount=55, last_calculated_fee=-20, label="bad-label"
            )
        )

        repo.create(
            instance=BillFactory.build(
                id=22, amount=0, last_calculated_fee=-70, label="debit card fee refund"
            )
        )

        repo.create(
            instance=BillFactory.build(
                id=33, amount=0, last_calculated_fee=-20, label="debit card fee refund"
            )
        )

        assert repo.get(id=11) is not None
        assert repo.get(id=22) is not None
        assert repo.get(id=33) is not None

        remove_debit_card_fee_refund_bills()
        assert repo.get(id=11) is not None
        assert repo.get(id=22) is None
        assert repo.get(id=33) is None

    def test_delete_debit_card_fee_refund_bpr(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        repo = BillRepository()
        bprs_repo = BillProcessingRecordRepository()

        repo.create(
            instance=BillFactory.build(id=111, amount=55, last_calculated_fee=-20)
        )

        # bpr not in the csv, should not be deleted
        bprs_repo.create(
            instance=BillProcessingRecordFactory.build(
                id=1, bill_id=111, processing_record_type="debit card fee refund"
            )
        )

        bprs_repo.create(
            instance=BillProcessingRecordFactory.build(
                id=29469, bill_id=111, processing_record_type="debit card fee refund"
            )
        )

        bprs_repo.create(
            instance=BillProcessingRecordFactory.build(
                id=29476, bill_id=111, processing_record_type="debit card fee refund"
            )
        )

        assert bprs_repo.get(id=1) is not None
        assert bprs_repo.get(id=29469) is not None
        assert bprs_repo.get(id=29476) is not None

        remove_debit_card_fee_refund_bprs("../csvs/debit_card_fee_bpr_ids.csv")
        assert bprs_repo.get(id=1) is not None
        assert bprs_repo.get(id=29469) is None
        assert bprs_repo.get(id=29476) is None
