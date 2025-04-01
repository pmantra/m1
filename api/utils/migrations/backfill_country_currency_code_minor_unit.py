from __future__ import annotations

import csv
from typing import Dict, List

import click

from storage.connection import db
from utils.log import logger
from wallet.models.reimbursement_wallet import CountryCurrencyCode

log = logger(__name__)

SOURCE_CSV = "./utils/migrations/csvs/currency_code_minor_unit.csv"


def get_country_code_to_minor_unit_mapping() -> Dict:
    country_code_to_minor_unit: Dict = {}

    with open(SOURCE_CSV, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            country_code = row["country_code"]
            minor_unit = row["minor_unit"]

            if (
                country_code in country_code_to_minor_unit
                and minor_unit != country_code_to_minor_unit[country_code]
            ):
                raise Exception(
                    f"Contradicting duplicated country code in source file: {country_code}"
                )

            country_code_to_minor_unit[country_code] = minor_unit

    return country_code_to_minor_unit


def backfill_country_currency_code_minor_unit():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    mapping = get_country_code_to_minor_unit_mapping()

    country_codes: List[CountryCurrencyCode] = db.session.query(CountryCurrencyCode)

    for country_code in country_codes:
        minor_unit: int | None = mapping.get(country_code.currency_code, None)

        if minor_unit is None:
            log.warning(f"Currency code not found for {country_code.currency_code}")
            continue

        country_code.minor_unit = minor_unit


@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
def backfill(dry_run: bool = False):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            backfill_country_currency_code_minor_unit()
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
