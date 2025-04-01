from storage.connection import db
from utils.log import logger

log = logger(__name__)


def backfill_member_health_plan_plan_type():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info("Setting `plan_type` value")
    session = db.session().using_bind("default")
    session.execute(
        """
            UPDATE member_health_plan
            SET plan_type = CASE
                WHEN is_family_plan = 1 THEN 'FAMILY'
                ELSE 'INDIVIDUAL'
            END
            WHERE is_family_plan IN (0, 1);
        """,
    )


def backfill(dry_run: bool = False):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info(
        "Running MemberHealthPlan plan_type backfill.",
        dry_run=dry_run,
    )
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            with db.session.no_autoflush:
                backfill_member_health_plan_plan_type()
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
