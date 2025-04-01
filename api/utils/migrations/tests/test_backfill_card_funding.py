import csv
from uuid import UUID

import pytest

from direct_payment.billing.models import CardFunding
from direct_payment.billing.pytests.factories import BillFactory
from direct_payment.billing.repository import BillRepository
from utils.migrations.backfill_card_funding import (
    backfill,
    get_source,
    get_stripe_charges,
)

TEST_CSV = (
    "reporting_category,balance_transaction_id,charge_id,payment_method_type,card_funding,payment_metadata["
    "bill_uuid],payment_metadata[copay_passthrough],payment_metadata[recouped_fee],refund_metadata["
    "recouped_fee],refund_metadata[bill_uuid]\n"
    "charge,str_txn_1,ch_1,card,prepaid,9267ccfc-b56a-41f2-a22a-9b24f7118098,200.00,6.00,\n"
    "charge,str_txn_2,ch_2,card,debit,5c8d83a2-e381-4147-bdd5-8b4cac89b40a,48.15,1.44,\n"
    "refund,str_txn_3,,card,debit,ff3e43f7-2272-41bb-8f63-3dafa0750c2d,-20,,-1,c78ca85c-525e-4042-a225-178e26368354\n"
    "charge,str_txn_4,,ach,,0594397c-7578-4b26-804a-89ef5fe5ac27,50,,"
)

TEST_CSV_FILE = "../csvs/test_stripe_charges.csv"


class TestBackfillCardFunding:
    @pytest.mark.parametrize(
        argnames="use_csv_string, txn_id_prefix",
        argvalues=[(True, "str_"), (False, "file_")],
        ids=["source from csv string", "source from file"],
    )
    def test_get_source(self, use_csv_string, txn_id_prefix):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        data = get_source(
            csv_string=TEST_CSV if use_csv_string else "", csv_filename=TEST_CSV_FILE
        )
        reader = csv.DictReader(data)
        expected_data = {
            f"{txn_id_prefix}txn_1": {
                "card_funding": "prepaid",
                "charge_id": "ch_1",
                "balance_transaction_id": f"{txn_id_prefix}txn_1",
                "payment_metadata[bill_uuid]": "9267ccfc-b56a-41f2-a22a-9b24f7118098",
                "payment_metadata[copay_passthrough]": "200.00",
                "payment_metadata[recouped_fee]": "6.00",
                "payment_method_type": "card",
                "refund_metadata[recouped_fee]": "",
                "refund_metadata[bill_uuid]": None,
                "reporting_category": "charge",
            },
            f"{txn_id_prefix}txn_2": {
                "balance_transaction_id": f"{txn_id_prefix}txn_2",
                "card_funding": "debit",
                "charge_id": "ch_2",
                "payment_metadata[bill_uuid]": "5c8d83a2-e381-4147-bdd5-8b4cac89b40a",
                "payment_metadata[copay_passthrough]": "48.15",
                "payment_metadata[recouped_fee]": "1.44",
                "payment_method_type": "card",
                "refund_metadata[recouped_fee]": "",
                "refund_metadata[bill_uuid]": None,
                "reporting_category": "charge",
            },
            f"{txn_id_prefix}txn_3": {
                "balance_transaction_id": f"{txn_id_prefix}txn_3",
                "card_funding": "debit",
                "charge_id": "",
                "payment_metadata[bill_uuid]": "ff3e43f7-2272-41bb-8f63-3dafa0750c2d",
                "payment_metadata[copay_passthrough]": "-20",
                "payment_metadata[recouped_fee]": "",
                "payment_method_type": "card",
                "refund_metadata[recouped_fee]": "-1",
                "refund_metadata[bill_uuid]": "c78ca85c-525e-4042-a225-178e26368354",
                "reporting_category": "refund",
            },
            f"{txn_id_prefix}txn_4": {
                "balance_transaction_id": f"{txn_id_prefix}txn_4",
                "card_funding": "",
                "charge_id": "",
                "payment_metadata[bill_uuid]": "0594397c-7578-4b26-804a-89ef5fe5ac27",
                "payment_metadata[copay_passthrough]": "50",
                "payment_metadata[recouped_fee]": "",
                "payment_method_type": "ach",
                "refund_metadata[recouped_fee]": "",
                "refund_metadata[bill_uuid]": None,
                "reporting_category": "charge",
            },
        }
        for row in reader:
            transaction_id = row["balance_transaction_id"]
            assert row == expected_data[transaction_id]

    def test_get_stripe_charges(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        stripe_charges = get_stripe_charges(TEST_CSV)
        assert stripe_charges == [
            {
                "card_funding": "prepaid",
                "bill_uuid": "9267ccfc-b56a-41f2-a22a-9b24f7118098",
            },
            {
                "card_funding": "debit",
                "bill_uuid": "5c8d83a2-e381-4147-bdd5-8b4cac89b40a",
            },
            {
                "card_funding": "debit",
                "bill_uuid": "c78ca85c-525e-4042-a225-178e26368354",
            },
        ]

    def test_backfill_card_funding(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        repo = BillRepository()

        repo.create(
            instance=BillFactory.build(
                uuid=UUID("9267ccfc-b56a-41f2-a22a-9b24f7118098"), amount=200
            )
        )

        repo.create(
            instance=BillFactory.build(
                uuid=UUID("5c8d83a2-e381-4147-bdd5-8b4cac89b40a"), amount=48.15
            )
        )

        repo.create(
            instance=BillFactory.build(
                uuid=UUID("c78ca85c-525e-4042-a225-178e26368354"), amount=-20
            )
        )

        backfill(False, TEST_CSV)
        bill_1 = BillRepository().get_by_uuid("c78ca85c-525e-4042-a225-178e26368354")
        bill_2 = BillRepository().get_by_uuid("9267ccfc-b56a-41f2-a22a-9b24f7118098")
        bill_3 = BillRepository().get_by_uuid("5c8d83a2-e381-4147-bdd5-8b4cac89b40a")

        assert bill_1 is not None and bill_1.card_funding is CardFunding.DEBIT
        assert bill_2 is not None and bill_2.card_funding is CardFunding.PREPAID
        assert bill_3 is not None and bill_3.card_funding is CardFunding.DEBIT
