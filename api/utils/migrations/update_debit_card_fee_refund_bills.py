from __future__ import annotations

import csv

import click

from storage.connection import db
from utils.log import logger

log = logger(__name__)

BPRS_ID_CSV = "./utils/migrations/csvs/debit_card_fee_bpr_ids.csv"

## Query to set the amount to the fee, since we don't support processing
## bills with 0 amount. In addition, bumping the amount to 50 cents since
## stripe won't process any amount that's less than 50
UPDATE_BILLS_QUERY = """
UPDATE bill
SET amount = IF(ABS(last_calculated_fee) >= 50, last_calculated_fee, -50), last_calculated_fee = 0
WHERE label = "debit card fee refund"
"""


## Query to remove bills created
DELETE_BILLS_QUERY = """
DELETE FROM bill WHERE label = "debit card fee refund"
"""


COUNT_QUERY = """
SELECT ROW_COUNT() AS affected_rows;
"""


def update_debit_card_fee_refund_bills():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    db.session.execute(UPDATE_BILLS_QUERY)


def remove_debit_card_fee_refund_bills():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    db.session.execute(DELETE_BILLS_QUERY)


def remove_debit_card_fee_refund_bprs(csv_file_path: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    data_source = open(csv_file_path, newline="")
    bprs_ids = []

    reader = csv.DictReader(data_source)
    for row in reader:
        bprs_ids.append(int(row["id"]))

    query = f"""
    DELETE FROM bill_processing_record WHERE id IN ({",".join(str(id) for id in bprs_ids)}) 
    """

    db.session.execute(query)


def get_affected_count() -> int:
    return db.session.execute(COUNT_QUERY).scalar()


@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
def update_bills(dry_run: bool = True):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            update_debit_card_fee_refund_bills()
            affected_rows: int = get_affected_count()
        except Exception as e:
            db.session.rollback()
            log.exception("Got an exception while updating.", error=str(e))
            return

        if dry_run:
            log.info("Dry run requested. Rolling back changes.", count=affected_rows)
            db.session.rollback()
            return

        log.info("Committing changes...", count=affected_rows)
        db.session.commit()
        log.info("Finished.")


@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
def delete_bprs(dry_run: bool = True, csv_file_path: str = BPRS_ID_CSV):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            remove_debit_card_fee_refund_bprs(csv_file_path)
            affected_rows: int = get_affected_count()
        except Exception as e:
            db.session.rollback()
            log.exception("Got an exception while updating.", error=str(e))
            return

        if dry_run:
            log.info("Dry run requested. Rolling back changes.", count=affected_rows)
            db.session.rollback()
            return

        log.info("Committing changes...", count=affected_rows)
        db.session.commit()
        log.info("Finished.")


@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
def delete_bills(dry_run: bool = True):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            remove_debit_card_fee_refund_bills()
            affected_rows: int = get_affected_count()
        except Exception as e:
            db.session.rollback()
            log.exception("Got an exception while updating.", error=str(e))
            return

        if dry_run:
            log.info("Dry run requested. Rolling back changes.", count=affected_rows)
            db.session.rollback()
            return

        log.info("Committing changes...", count=affected_rows)
        db.session.commit()
        log.info("Finished.")


if __name__ == "__main__":
    update_bills()
