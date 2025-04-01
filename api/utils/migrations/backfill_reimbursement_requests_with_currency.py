from __future__ import annotations

import click

from storage.connection import db
from utils.log import logger

log = logger(__name__)


QUERY = """
UPDATE reimbursement_request
SET usd_amount = amount,
    transaction_amount = amount,
    transaction_to_benefit_rate = 1.0,
    transaction_to_usd_rate = 1.0,
    benefit_currency_code = "USD",
    transaction_currency_code = "USD"
WHERE benefit_currency_code IS NULL
AND transaction_currency_code IS NULL
AND transaction_amount IS NULL
AND usd_amount IS NULL
AND transaction_to_benefit_rate IS NULL
AND transaction_to_usd_rate IS NULL
"""

COUNT_QUERY = """
SELECT ROW_COUNT() AS affected_rows;
"""


def backfill_reimbursement_requests():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    db.session.execute(QUERY)


def get_affected_count() -> int:
    return db.session.execute(COUNT_QUERY).scalar()


@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
def backfill(dry_run: bool = True):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            backfill_reimbursement_requests()
            affected_rows: int = get_affected_count()
        except Exception as e:
            db.session.rollback()
            log.exception("Got an exception while backfilling.", error=str(e))
            return

        if dry_run:
            log.info("Dry run requested. Rolling back changes.", count=affected_rows)
            db.session.rollback()
            return

        log.info("Committing changes...", count=affected_rows)
        db.session.commit()
        log.info("Finished.")


if __name__ == "__main__":
    backfill()
