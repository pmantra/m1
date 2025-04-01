import csv
from typing import Dict, List

import click

from direct_payment.billing.models import Bill, CardFunding
from direct_payment.billing.repository import BillRepository
from storage.connection import db
from utils.log import logger

log = logger(__name__)

SOURCE_CSV = "./utils/migrations/csvs/stripe_charges.csv"

# csv column names
REPORTING_CATEGORY = "reporting_category"
PAYMENT_METHOD_TYPE = "payment_method_type"
CARD_FUNDING = "card_funding"
ORIGINAL_BILL_UUID = "payment_metadata[bill_uuid]"
REFUND_BILL_UUID = "refund_metadata[bill_uuid]"
BILL_UUID = "bill_uuid"


def get_source(csv_string: str, csv_filename: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    return I/O from a csv string or a csv file if the string is undefined
    """
    return (
        csv_string.splitlines()
        if csv_string.strip()
        else open(csv_filename, newline="")
    )


def get_stripe_charges(test_data: str) -> List[Dict]:
    stripe_charge_information: List[Dict] = []

    # read from test data if available, else read from file
    source = get_source(test_data, SOURCE_CSV)

    reader = csv.DictReader(source)
    for row in reader:
        reporting_category = row[REPORTING_CATEGORY]
        payment_method_type = row[PAYMENT_METHOD_TYPE]

        if payment_method_type == "card":
            if reporting_category == "charge":
                stripe_charge_information.append(
                    {
                        CARD_FUNDING: row[CARD_FUNDING],
                        BILL_UUID: row[ORIGINAL_BILL_UUID],
                    }
                )
            elif reporting_category == "refund":
                stripe_charge_information.append(
                    {CARD_FUNDING: row[CARD_FUNDING], BILL_UUID: row[REFUND_BILL_UUID]}
                )

    return stripe_charge_information


def backfill_card_funding(test_data: str) -> List[Bill]:
    stripe_charges = get_stripe_charges(test_data)
    bill_repo = BillRepository()
    bills_updated = []

    log.info(f"Found {len(stripe_charges)} charges to backfill")
    for stripe_charge in stripe_charges:
        card_funding = stripe_charge.get(CARD_FUNDING, "").upper()

        if hasattr(CardFunding, card_funding):
            bill = bill_repo.get_by_uuid(stripe_charge.get(BILL_UUID, ""))

            if bill:
                bill.card_funding = card_funding
                bill_repo.update(instance=bill)
                bills_updated.append(bill)
            else:
                log.warn(
                    f"Failed to find matching bill in database for uuid: {stripe_charge.get(BILL_UUID)}"
                )

    log.info(f"Backfilled {len(bills_updated)} bills")
    return bills_updated


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
def backfill(dry_run: bool = True, test_data: str = ""):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            backfill_card_funding(test_data)
        except Exception as e:
            db.session.rollback()
            log.exception("Got an exception while backfilling.", exception=e)
            return

        if dry_run:
            log.info("Dry run requested. Rolling back changes.")
            db.session.rollback()
            return

        log.debug("Committing changes...")
        db.session.commit()
        log.debug("Finished.")


if __name__ == "__main__":
    backfill()
