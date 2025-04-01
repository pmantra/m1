from uuid import UUID

import pytest

from direct_payment.billing.models import BillStatus
from direct_payment.billing.pytests.factories import BillFactory
from direct_payment.billing.repository import (
    BillProcessingRecordRepository,
    BillRepository,
)
from utils.migrations.refund_debit_card_fees import (
    get_stripe_charges,
    refund_debit_card_fees,
)

TEST_CSV = (
    "reporting_category,balance_transaction_id,charge_id,payment_method_type,card_funding,payment_metadata["
    "bill_uuid],payment_metadata[copay_passthrough],payment_metadata[recouped_fee],refund_metadata[bill_uuid],"
    "refund_metadata[recouped_fee]\n"
    "charge,str_txn_1,ch_1,card,prepaid,9267ccfc-b56a-41f2-a22a-9b24f7118098,200.00,6.00,\n"
    "charge,str_txn_2,ch_2,card,debit,5c8d83a2-e381-4147-bdd5-8b4cac89b40a,48.15,1.44,\n"
    "refund,str_txn_3,ch_1,card,debit,ff3e43f7-2272-41bb-8f63-3dafa0750c2d,-20,,44daa8ab-6a9b-46b7-bc21-bac896d1317c,"
    "-1\n"
    "charge,str_txn_4,ch_3,ach,,0594397c-7578-4b26-804a-89ef5fe5ac27,50,,"
)


class TestRefundDebitCardFees:
    def test_get_stripe_charges(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        stripe_charges = get_stripe_charges(TEST_CSV)
        assert stripe_charges == {
            "ch_1": {
                "payment_metadata[bill_uuid]": "9267ccfc-b56a-41f2-a22a-9b24f7118098",
                "payment_metadata[recouped_fee]": 600,
                "refund_metadata[bill_uuid]": "44daa8ab-6a9b-46b7-bc21-bac896d1317c",
                "refund_metadata[recouped_fee]": -100,
            },
            "ch_2": {
                "payment_metadata[bill_uuid]": "5c8d83a2-e381-4147-bdd5-8b4cac89b40a",
                "payment_metadata[recouped_fee]": 144,
            },
        }

    @pytest.mark.parametrize(
        argnames="bill_uuid,bill_status,fee_charged,refund_bill_uuid,refund_bill_status,fee_refunded,refund_bill_created,expected_refund_amount",
        argvalues=[
            (
                "9267ccfc-b56a-41f2-a22a-9b24f7118098",
                BillStatus.PAID,
                10.0,
                None,
                None,
                None,
                True,
                -1000,
            ),
            (
                "b52b9a02-603d-4cb8-b6b3-a617d618c98f",
                BillStatus.PAID,
                10.0,
                "6780c9f8-5371-4ddc-ba41-b6ebd4681cb8",
                BillStatus.FAILED,
                -5.0,
                True,
                -1000,
            ),
            (
                "a2ad52a0-1cef-4944-84f6-14d8963d28d1",
                BillStatus.PAID,
                10.0,
                "cff799e0-e2e8-4064-8ac3-9a652c767f85",
                BillStatus.REFUNDED,
                -5.0,
                True,
                -500,
            ),
            (
                "6d8459ae-c3a1-4d3b-89fb-8dae2d6b3ec9",
                BillStatus.PAID,
                10.0,
                "120a57ec-8a17-4e69-9b65-b5e04a192fde",
                BillStatus.REFUNDED,
                -11.0,
                False,
                None,
            ),
            (
                "709d7bd6-c94c-469d-aadc-73f1eacc0ead",
                BillStatus.FAILED,
                10.0,
                "c78ca85c-525e-4042-a225-178e26368354",
                BillStatus.PAID,
                -5.0,
                False,
                None,
            ),
            (
                "9267ccfc-b56a-41f2-a22a-9b24f7118099",
                BillStatus.PAID,
                0.3,
                None,
                None,
                None,
                True,
                -50,
            ),
        ],
        ids=[
            "refund a bill without existing refunds should refund full fee amount",
            "refund a bill with existing refund but bad state should return full fee amount",
            "refund a bill with existing refund should return fee charged minus fee refunded",
            "refund a bill that was fully refunded should not create any refund bill",
            "refund a bill not in paid status should return nothing",
            "refund a bill with less than 50 cents",
        ],
    )
    def test_refund_debit_card_fees(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        bill_uuid,
        bill_status,
        fee_charged,
        refund_bill_uuid,
        refund_bill_status,
        fee_refunded,
        refund_bill_created,
        expected_refund_amount,
    ):
        # generate test data
        header = (
            "reporting_category,balance_transaction_id,charge_id,payment_method_type,card_funding,payment_metadata["
            "bill_uuid],payment_metadata[copay_passthrough],payment_metadata[recouped_fee],refund_metadata[bill_uuid],"
            "refund_metadata[recouped_fee]\n"
        )

        bill_row = (
            f"charge,str_txn_1,ch_1,card,prepaid,{bill_uuid},200.00,{fee_charged}\n"
        )
        refund_row = (
            f"refund,str_txn_3,ch_1,card,debit,{refund_bill_uuid},-20,,{refund_bill_uuid},{fee_refunded}\n"
            if refund_bill_uuid
            else ""
        )
        test_data = header + bill_row + refund_row

        # create test bills
        repo = BillRepository()
        bill_processing_record_repo = BillProcessingRecordRepository()
        original_bill = repo.create(
            instance=BillFactory.build(
                uuid=UUID(bill_uuid), amount=20000, status=bill_status
            )
        )

        if refund_row:
            repo.create(
                instance=BillFactory.build(
                    uuid=UUID(refund_bill_uuid), amount=-2000, status=refund_bill_status
                )
            )

        bills = refund_debit_card_fees(test_data)

        assert (len(bills) == 1) == refund_bill_created

        if refund_bill_created:
            # assert on key refund bill data
            refund_bill = repo.get_by_uuid(str(bills[0].uuid))

            assert refund_bill is not None
            assert refund_bill.amount == expected_refund_amount
            assert refund_bill.last_calculated_fee == 0
            assert refund_bill.label == "debit card fee refund"
            assert refund_bill.payor_type == original_bill.payor_type
            assert refund_bill.payor_id == original_bill.payor_id
            assert refund_bill.payment_method == original_bill.payment_method
            assert (
                refund_bill.payment_method_label == original_bill.payment_method_label
            )
            assert refund_bill.procedure_id == original_bill.procedure_id
            assert refund_bill.cost_breakdown_id == original_bill.cost_breakdown_id
            assert refund_bill.status == BillStatus.NEW
            assert refund_bill.payment_method_id == original_bill.payment_method_id
            assert refund_bill.payment_method_type == original_bill.payment_method_type

            # assert on key bill processing record data
            bill_processing_record = bill_processing_record_repo.get_bill_processing_records(
                bill_ids=[refund_bill.id]  # type: ignore[list-item] # List item 0 has incompatible type "Optional[int]"; expected "int"
            )
            assert len(bill_processing_record) == 1
            assert bill_processing_record[0].bill_id == refund_bill.id
            assert bill_processing_record[0].bill_status == "NEW"
            assert (
                bill_processing_record[0].processing_record_type
                == "manual_billing_correction"
            )
            assert bill_processing_record[0].body == {
                "to_refund_bill": original_bill.id
            }
