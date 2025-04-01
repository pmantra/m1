import click as click

from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from storage.connection import db
from utils.log import logger
from wallet.models.reimbursement import ReimbursementClaim

log = logger(__name__)

""""
    This backfill is running to deprecate the reimbursement request id on the Accumulation Treatment Mapping Table. 
    
    We are looking for any records in the Accumulation Mapping Table where reimbursement claim id is not null and
    populating the associated reimbursement request id from which the claim came from.
"""


def map_reimbursement_request_id_from_claim_id():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    count = 0
    accumulation_treatment_mappings_map = (
        db.session.query(
            AccumulationTreatmentMapping, ReimbursementClaim.reimbursement_request_id
        )
        .join(
            ReimbursementClaim,
            AccumulationTreatmentMapping.reimbursement_claim_id
            == ReimbursementClaim.id,
        )
        .all()
    )
    log.info(
        f"Total Accumulation Treatment Mapping records with claim ids: {len(accumulation_treatment_mappings_map)}"
    )
    for mapping, reimbursement_request_id in accumulation_treatment_mappings_map:
        mapping.reimbursement_request_id = reimbursement_request_id
        db.session.add(mapping)
        count += 1
    log.info(f"{count} accumulation_treatment_mappings processed.")


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
            map_reimbursement_request_id_from_claim_id()
        except Exception as e:
            db.session.rollback()
            log.error("Got an exception while backfilling.", error=e)
        if dry_run:
            log.info("Dry run requested. Rolling back changes.")
            db.session.rollback()
            return

        log.debug("Committing changes...")
        db.session.commit()
        log.debug("Finished.")


if __name__ == "__main__":
    backfill()
