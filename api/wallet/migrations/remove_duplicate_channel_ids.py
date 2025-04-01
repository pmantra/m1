from __future__ import annotations

import click

from storage.connection import db
from utils.log import logger

log = logger(__name__)

QUERY = """
update maven.reimbursement_wallet_users
set channel_id=null
where id in (select * from (
    select rwu_denied.id
    from maven.reimbursement_wallet_users rwu_active
    inner join maven.reimbursement_wallet_users rwu_denied
    on rwu_active.channel_id=rwu_denied.channel_id
    and rwu_active.id <> rwu_denied.id
    and rwu_denied.status = 'DENIED'
) as rwus_to_nullify);
"""

COUNT_QUERY = """
SELECT ROW_COUNT() AS affected_rows;
"""


def remove_duplicate_channel_id() -> None:
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
            remove_duplicate_channel_id()
            affected_rows: int = get_affected_count()
        except Exception as e:
            db.session.rollback()
            log.exception("Got an exception while running script.", error=str(e))
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
