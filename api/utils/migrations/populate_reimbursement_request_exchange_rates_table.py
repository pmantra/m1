import csv
from datetime import datetime
from decimal import Decimal

import click

from storage.connection import db
from utils.log import logger
from wallet.models.reimbursement import ReimbursementRequestExchangeRates

log = logger(__name__)


def populate_reimbursement_request_exchange_rates_table():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    count = 0
    with open(
        "./utils/migrations/csvs/currency_backfill_2023.csv", newline=""
    ) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            source_currency = row["source_currency"]
            target_currency = row["target_currency"]
            trading_date = datetime.strptime(row["trading_date"], "%m/%d/%Y").date()
            exchange_rate = Decimal(row["exchange_rate"])

            new_rate = ReimbursementRequestExchangeRates(
                source_currency=source_currency,
                target_currency=target_currency,
                trading_date=trading_date,
                exchange_rate=exchange_rate,
            )
            db.session.add(new_rate)
            count += 1

    print(f"Adding {count} rows to the ReimbursementRequestExchangeRates table.")


@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
def populate(dry_run: bool = False):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            populate_reimbursement_request_exchange_rates_table()
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
    populate()
