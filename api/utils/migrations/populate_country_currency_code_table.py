import csv

import click

from storage.connection import db
from utils.log import logger
from wallet.models.reimbursement_wallet import CountryCurrencyCode

log = logger(__name__)


def populate_country_currency_code_table():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    count = 0
    with open(
        "./utils/migrations/csvs/country_currency_mapping.csv", newline=""
    ) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            country_code = row["country_alpha_2"]
            currency_code = row["currency_code"]
            print(country_code)
            country_currency = CountryCurrencyCode(
                country_alpha_2=country_code,
                currency_code=currency_code,
            )
            db.session.add(country_currency)
            count += 1

    print(f"Adding {count} rows to the CountryCurrencyCode table.")


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
            populate_country_currency_code_table()
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
