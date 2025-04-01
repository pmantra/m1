from storage.connection import db
from utils.log import logger

log = logger(__name__)


def backfill_treatment_procedures_needing_questionnaires() -> None:
    log.info("Beginning reatment_procedures_needing_questionnaires backfill.")
    session = db.session().using_bind("default")
    session.execute(
        """
        INSERT INTO treatment_procedures_needing_questionnaires (treatment_procedure_id)
            SELECT tp.id
            FROM treatment_procedure tp
            LEFT JOIN treatment_procedure_recorded_answer_set tpras ON tp.id = tpras.treatment_procedure_id
            LEFT JOIN treatment_procedures_needing_questionnaires tpnq ON tp.id = tpnq.treatment_procedure_id
            WHERE tpras.treatment_procedure_id IS NULL AND tpnq.treatment_procedure_id IS NULL;
        """
    )


def backfill(dry_run: bool = False) -> None:
    log.info(
        "Executing backfill_treatment_procedures_needing_questionnaires.",
        dry_run=dry_run,
    )
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            with db.session.no_autoflush:
                backfill_treatment_procedures_needing_questionnaires()
        except Exception as e:
            db.session.rollback()
            log.error("Got an exception while backfilling.", exception=e)
            return

        if dry_run:
            log.info("Dry run requested. Rolling back changes.")
            db.session.rollback()
            return

        log.info("Committing changes...")
        db.session.commit()
        log.info("Finished.")


def main(dry_run: bool = False) -> None:
    backfill(dry_run=dry_run)


if __name__ == "__main__":
    main()
