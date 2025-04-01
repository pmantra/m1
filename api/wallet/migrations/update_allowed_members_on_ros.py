from __future__ import annotations

import click

from storage.connection import db
from utils.log import logger

log = logger(__name__)


def update_roses(dry_run=True):
    query_1 = """
    UPDATE maven.reimbursement_organization_settings
    SET maven.reimbursement_organization_settings.allowed_members = 'SHAREABLE'
    WHERE id = 1162521922516338956
    """

    db.session.execute(query_1)
    query_2 = """
    UPDATE maven.reimbursement_organization_settings
    SET maven.reimbursement_organization_settings.allowed_members = 'SINGLE_DEPENDENT_ONLY'
    WHERE id = 1377399590874605137
    """

    db.session.execute(query_2)
    affected_count = _get_affected_count()

    log.info("Update completed (not committed)", affected_count=affected_count)
    if dry_run:
        log.info("Dry run requested. Rolling back changes. ")
        db.session.rollback()
    else:
        log.info("Committing changes...", affected_count=affected_count)
        db.session.commit()
        log.info("Finished", affected_count=affected_count)


def _get_affected_count() -> int:
    my_query = """ 
    SELECT ROW_COUNT() AS affected_rows 
    """
    cnt = db.session.execute(my_query).scalar()
    if not cnt:
        log.info(f"{cnt} rows were updated.")
    return cnt


@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
def update_data(dry_run: bool = True):
    log.info("Begun.")
    try:
        update_roses(dry_run=dry_run)
    except Exception as e:
        db.session.rollback()
        log.exception("Got an exception while updating.", error=str(e))
        return
    log.info("Ended.")


if __name__ == "__main__":
    from app import create_app

    with create_app(task_instance=True).app_context():
        update_data(False)
