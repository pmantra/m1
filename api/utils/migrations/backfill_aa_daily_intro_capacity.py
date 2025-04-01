import click

from care_advocates.models.assignable_advocates import AssignableAdvocate
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def backfill_aa_daily_intro_capacity():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Backfill AssignableAdvocate.daily_intro_capacity with AssignableAdvocate.max_capacity
    """
    all_assignable_advocates = AssignableAdvocate.query.all()
    for aa in AssignableAdvocate.query.all():
        aa.daily_intro_capacity = aa.max_capacity

    return all_assignable_advocates


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
            all_aa = backfill_aa_daily_intro_capacity()
            db.session.bulk_save_objects(all_aa)
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
