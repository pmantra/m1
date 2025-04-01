import click
from sqlalchemy import select, update

from models.marketing import URLRedirect, URLRedirectPath
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def update_dest_url_path_ids():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    db.session.execute(
        update(URLRedirect).values(  # type: ignore[arg-type] # Argument 1 to "Update" has incompatible type "Type[URLRedirect]"; expected "Union[str, Selectable]"
            dest_url_path_id=select([URLRedirectPath.id]).where(
                URLRedirectPath.path == URLRedirect.dest_url_path
            )
        )
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
            update_dest_url_path_ids()
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
