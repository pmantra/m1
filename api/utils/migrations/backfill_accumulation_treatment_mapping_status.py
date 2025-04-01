import click

from payer_accumulator.common import TreatmentAccumulationStatus
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from storage.connection import db
from utils.log import logger

BATCH_SIZE = 50

log = logger(__name__)


def _get_accumulation_treatment_mappings():
    return AccumulationTreatmentMapping.query.filter(
        (
            (
                (AccumulationTreatmentMapping.accumulation_transaction_id.is_(None))
                & (AccumulationTreatmentMapping.payer_id in (2, 3))
            )
            | (
                (AccumulationTreatmentMapping.oop_applied.is_(None))
                & (AccumulationTreatmentMapping.deductible.is_(None))
            )
            | (AccumulationTreatmentMapping.payer_id.is_(None))
        ),
        AccumulationTreatmentMapping.treatment_accumulation_status
        == TreatmentAccumulationStatus.SUBMITTED,
    ).all()


def update_treatment_accumulation_status():
    log.info("Backfill for treatment_accumulation_status that to ROW_ERROR starting")
    rows = _get_accumulation_treatment_mappings()
    offset = 0
    accumulation_treatment_mapping_batch = rows[offset : offset + BATCH_SIZE]
    while accumulation_treatment_mapping_batch:
        for treatment_mapping in accumulation_treatment_mapping_batch:
            treatment_mapping.treatment_accumulation_status = (
                TreatmentAccumulationStatus.ROW_ERROR
            )
            db.session.add(treatment_mapping)
        log.info(f"Backfill processed for batch {offset} - {offset + BATCH_SIZE}")
        offset += BATCH_SIZE
        accumulation_treatment_mapping_batch = rows[offset : offset + BATCH_SIZE]

    log.info(f"Backfilled {len(rows)} accumulation_treatment_mappings")


@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
def backfill(dry_run: bool = True):
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            update_treatment_accumulation_status()
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
