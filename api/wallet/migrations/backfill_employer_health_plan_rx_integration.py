from storage.connection import db
from utils.log import logger

log = logger(__name__)


def backfill_employer_health_plan_rx_integration():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info("Setting `rx_integration` value")
    session = db.session().using_bind("default")
    session.execute(
        """
            UPDATE employer_health_plan
            SET rx_integration = CASE
                WHEN rx_integrated = 1 THEN 'FULL'
                ELSE 'NONE'
            END
            WHERE rx_integrated IN (0, 1);
        """,
    )


def backfill(dry_run: bool = False):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info(
        "Running EmployerHealthPlan rx_integration backfill.",
        dry_run=dry_run,
    )
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            with db.session.no_autoflush:
                backfill_employer_health_plan_rx_integration()
        except Exception as e:
            db.session.rollback()
            log.exception("Got an exception while backfilling.", exception=e)
            return

        if dry_run:
            log.info("Dry run requested. Rolling back changes.")
            db.session.rollback()
            return

        log.info("Committing changes...")
        db.session.commit()
        log.info("Finished.")


def main(dry_run: bool = False):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    backfill(dry_run=dry_run)


if __name__ == "__main__":
    main()
