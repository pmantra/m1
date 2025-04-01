from __future__ import annotations

import click

from storage.connection import db
from utils.log import logger

log = logger(__name__)

QUERY = """
insert into member_benefit (user_id, benefit_id)
select
    u.id,
    CONCAT('M', LPAD(FLOOR(RAND(u.id) * 999999999), 9, '0'))
from user u
left join member_benefit mb
    on u.id = mb.user_id
where mb.id is null
on duplicate key update member_benefit.id=member_benefit.id;
"""

COUNT_QUERY = """
SELECT ROW_COUNT() AS affected_rows;
"""


def backfill_member_benefit():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
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
            backfill_member_benefit()
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
