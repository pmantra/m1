from __future__ import annotations

import click

from storage.connection import db
from utils.log import logger

log = logger(__name__)

QUERY_PRE_2024 = """
update reimbursement_request
set state = 'PENDING_MEMBER_INPUT'
where state = 'NEW'
    -- submitted in 2024
    and YEAR(created_at) < 2024;
"""

QUERY_2024 = """
update reimbursement_request
set state = 'PENDING_MEMBER_INPUT'
where state = 'NEW'
    -- submitted in 2024
    and YEAR(created_at) = 2024
    -- more than 30 days old
    and created_at <= '5/11/2024 19:11:58'
    -- need in the description
    and lower(description) like '%need%';
"""

COUNT_QUERY = """
SELECT ROW_COUNT() AS affected_rows;
"""


def get_affected_count() -> int:
    return db.session.execute(COUNT_QUERY).scalar()


def update_pre_2024():
    db.session.execute(QUERY_PRE_2024)


def update_2024():
    db.session.execute(QUERY_2024)


key_to_function = {"2024": update_2024, "pre_2024": update_pre_2024}


@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
def backfill(key: str, dry_run: bool = True):
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            fn = key_to_function.get(key, None)
            if fn is None:
                log.info("Function not found")
                return

            fn()
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
