import pathlib
import sys

import click
from sqlalchemy import text

from storage import connector


def repair_end_and_trailing_phases(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    db: connector.RoutingSQLAlchemy,
):
    """This repairs phases by:

    - Setting the correct started_at and ended_at
    - Deleting any duplicate end phases.
    - Deleting any phases which were created after the end phase started.
    - Update any phases with `ended_at` unset whose tracks have ended.
    """
    sql = (pathlib.Path(__file__).resolve().parent / "repair_phases.sql").read_text()
    return db.session.execute(text(sql))


def repair_phases_sql(*, dry_run: bool = True):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from storage.connection import db
    from utils import log

    logger = log.logger("repair-phases")
    log.configure()

    try:
        logger.info("Beginning phases repair.")
        results = repair_end_and_trailing_phases(db)
        logger.info("Done repairing phases.")

    except Exception:
        db.session.rollback()
        logger.exception("Got an error repairing phases.")
        raise

    if dry_run:
        logger.info("Dry-run, rolling back changes.")
        db.session.rollback()
    else:
        db.session.commit()
        logger.info("Changes saved.")

    return results


@click.command()
@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
def main(dry_run: bool = True):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from app import create_app

    app = create_app(task_instance=True)
    with app.app_context():
        try:
            repair_phases_sql(dry_run=dry_run)
        except Exception as e:
            ue = click.UsageError(str(e))
            ue.show()
            sys.exit(ue.exit_code)


if __name__ == "__main__":
    main()
