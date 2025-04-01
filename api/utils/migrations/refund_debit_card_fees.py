import csv
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List

import click

from direct_payment.billing import models
from direct_payment.billing.billing_service import TO_REFUND_BILL
from direct_payment.billing.models import Bill, BillProcessingRecord, BillStatus
from direct_payment.billing.repository import (
    BillProcessingRecordRepository,
    BillRepository,
)
from storage.connection import db
from utils.log import logger

REPORTING_CATEGORY = "reporting_category"
PAYMENT_METHOD_TYPE = "payment_method_type"
CARD_FUNDING = "card_funding"
CHARGE_ID = "charge_id"
ORIGINAL_BILL_UUID = "payment_metadata[bill_uuid]"
REFUND_BILL_UUID = "refund_metadata[bill_uuid]"
FEE_RECOUPED = "payment_metadata[recouped_fee]"
FEE_REFUNDED = "refund_metadata[recouped_fee]"
SOURCE_CSV = "./utils/migrations/csvs/stripe_charges.csv"

log = logger(__name__)


def get_source(csv_string: str, csv_filename: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    return I/O from a csv string or a csv file if the string is undefined
    """
    return (
        csv_string.splitlines()
        if csv_string.strip()
        else open(csv_filename, newline="")
    )


def get_stripe_charges(test_data: str) -> Dict:
    stripe_charge_information: Dict = {}

    # read from test data if available, else read from file
    source = get_source(test_data, SOURCE_CSV)
    reader = csv.DictReader(source)

    for row in reader:
        reporting_category = row[REPORTING_CATEGORY]
        card_funding = row[CARD_FUNDING]
        charge_id = row[CHARGE_ID]

        # refunding only debit/prepaid card fees
        if reporting_category in ("charge", "refund") and card_funding in (
            "debit",
            "prepaid",
        ):
            if not stripe_charge_information.get(charge_id):
                stripe_charge_information[charge_id] = {}

            if reporting_category == "charge":
                stripe_charge_information[charge_id][ORIGINAL_BILL_UUID] = row[
                    ORIGINAL_BILL_UUID
                ]
                stripe_charge_information[charge_id][FEE_RECOUPED] = int(
                    Decimal(row[FEE_RECOUPED]) * 100
                )
            elif reporting_category == "refund":
                stripe_charge_information[charge_id][REFUND_BILL_UUID] = row[
                    REFUND_BILL_UUID
                ]
                stripe_charge_information[charge_id][FEE_REFUNDED] = int(
                    Decimal(row[FEE_REFUNDED]) * 100
                )

    return stripe_charge_information


def refund_debit_card_fees(test_data: str) -> List[Bill]:
    refund_bills = []
    total_refunded_amount = 0
    bill_repo = BillRepository(session=db.session, is_in_uow=True)
    bill_processing_record_repo = BillProcessingRecordRepository(
        session=db.session, is_in_uow=True
    )
    now = datetime.now(timezone.utc)

    stripe_charges = get_stripe_charges(test_data)
    log.info(f"Found {len(stripe_charges)} charges to refund")

    for stripe_charge in stripe_charges.values():
        bill = bill_repo.get_by_uuid(stripe_charge.get(ORIGINAL_BILL_UUID, ""))
        prev_refund_bill = (
            bill_repo.get_by_uuid(stripe_charge[REFUND_BILL_UUID])
            if stripe_charge.get(REFUND_BILL_UUID)
            else None
        )

        if bill and bill.status == BillStatus.PAID:
            fee_to_refund = stripe_charge[FEE_RECOUPED]

            # if we already partially refunded the fee, then calculate it
            # by subtract the refunded amount from the total fee
            if prev_refund_bill and prev_refund_bill.status == BillStatus.REFUNDED:
                fee_to_refund += stripe_charge[FEE_REFUNDED]

            # stripe only accepts amount >= 50 cents, bump it to 50 cents if less than that for the refund
            if 0 < fee_to_refund <= 50:
                fee_to_refund = 50

            if fee_to_refund > 0:
                refund_bill = models.Bill(
                    uuid=uuid.uuid4(),
                    amount=fee_to_refund * -1,
                    last_calculated_fee=0,
                    label="debit card fee refund",
                    payor_type=bill.payor_type,
                    payor_id=bill.payor_id,
                    payment_method=bill.payment_method,
                    payment_method_label=bill.payment_method_label,
                    procedure_id=bill.procedure_id,
                    cost_breakdown_id=bill.cost_breakdown_id,
                    status=BillStatus.NEW,
                    created_at=now,
                    modified_at=now,
                    payment_method_id=bill.payment_method_id,
                    payment_method_type=bill.payment_method_type,
                )

                created_refund_bill = bill_repo.create(instance=refund_bill)

                bill_processing_record = BillProcessingRecord(
                    processing_record_type="manual_billing_correction",
                    body={TO_REFUND_BILL: bill.id},
                    bill_id=created_refund_bill.id,
                    bill_status=BillStatus.NEW.value,  # type: ignore[arg-type] # Argument "bill_status" to "BillProcessingRecord" has incompatible type "str"; expected "BillStatus"
                    transaction_id=None,
                    created_at=now,
                )

                bill_processing_record_repo.create(instance=bill_processing_record)
                log.info(
                    f"Created refund bill: {refund_bill.uuid} to refund ${fee_to_refund} fee to bill: {bill.uuid}"
                )

                refund_bills.append(refund_bill)
                total_refunded_amount += fee_to_refund
            else:
                log.info(
                    f"Bill {bill.id} was not refunded, because amount {fee_to_refund} is less or equal to zero"
                )

    log.info(f"Refunded total:, ${total_refunded_amount/100}")
    return refund_bills


@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
@click.option(
    "--test-data",
    "-T",
    is_flag=False,
    help="Run the migration on the test data instead from file",
)
def refund(dry_run: bool = True, test_data: str = ""):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            with db.session.no_autoflush:
                refund_debit_card_fees(test_data)
        except Exception as e:
            db.session.rollback()
            log.exception("Got an exception while refunding.", exception=e)
            return

        if dry_run:
            log.info("Dry run requested. Rolling back changes.")
            db.session.rollback()
            return

        log.debug("Committing changes...")
        db.session.commit()
        log.debug("Finished.")


if __name__ == "__main__":
    refund()
