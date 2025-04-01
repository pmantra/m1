import click

from direct_payment.clinic.models.clinic import FertilityClinicLocation
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def backfill_fertility_clinic_location_country_codes():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    All country_code right now should be "US"
    Backfilling due to bug in flask admin not saving the displayed value
    """
    null_country_code_fc_locations = FertilityClinicLocation.query.filter_by(
        country_code=None
    )
    log.info(
        f"There are {null_country_code_fc_locations.count()} fertility clinic locations with null country_code"
    )

    for clinic_location in null_country_code_fc_locations.all():
        log.info(f"Backfilling country code for clinic_id: {clinic_location.id}")
        clinic_location.country_code = "US"
        db.session.add(clinic_location)


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
            backfill_fertility_clinic_location_country_codes()
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


if __name__ == "__main__":
    backfill()
