import click

from storage.connection import db
from utils.log import logger

log = logger(__name__)


def update_bms_order_statuses():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    db.session.execute(
        """
        UPDATE bms_order
        SET status=CASE
            WHEN (is_cancelled = 1) THEN "CANCELLED"
            WHEN (fulfilled_at IS NOT NULL) THEN "FULFILLED"
            ELSE "NEW"
        END
        WHERE status="NEW"
        """
    )
    db.session.flush()


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
            update_bms_order_statuses()
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
