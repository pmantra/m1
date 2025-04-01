import csv
import time

import click
from flask.cli import with_appcontext

from appointments.models.appointment import Appointment
from provider_matching.services.matching_engine import calculate_state_match_type
from storage.connection import db
from utils.log import logger
from utils.query import paginate

log = logger(__name__)


@click.command()
@with_appcontext
@click.option(
    "--filename", "-F", type=str, help="Output file path ('csv') to track results."
)
@click.option(
    "--dry-run", "-D", is_flag=True, help="Run the script but do not save the result."
)
@click.option(
    "--created_at",
    "-c",
    type=str,
    help="Filter appointments created on and after date (YYYY-MM-DD)",
)
def main(filename: str, dry_run: bool = True, created_at: str = None):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[assignment] # Incompatible default for argument "created_at" (default has type "None", argument has type "str")

    start_time = time.time()

    with open(filename, "w") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "state_match_type", "created_at"])
        writer.writeheader()

        if created_at:
            exp = Appointment.created_at >= created_at
        else:
            exp = Appointment.state_match_type.is_(None)

        total_records = Appointment.query.filter(exp).count()
        log.info(f"Found {total_records} records to update.")

        size = 1000
        mappings = []
        idx = 0

        for appointment in paginate(
            db.session.query(Appointment).filter(exp), Appointment.id, size=size
        ):
            state_match_type = calculate_state_match_type(
                appointment.practitioner.profile, appointment.member
            )
            writer.writerow(
                {
                    "id": appointment.id,
                    "state_match_type": state_match_type,
                    "created_at": appointment.created_at,
                }
            )
            mappings.append(dict(id=appointment.id, state_match_type=state_match_type))
            idx += 1

            if idx % size == 0 and not dry_run:
                log.info(f"Committing chunk size: {idx}")
                db.session.bulk_update_mappings(Appointment, mappings)
                db.session.commit()
                mappings.clear()

    if not dry_run:
        remainder = len(mappings)
        log.info(f"Committing remaining {remainder} bulk mappings.")
        db.session.bulk_update_mappings(Appointment, mappings)
        db.session.commit()

    elapsed = time.time() - start_time
    log.info(f"Total execution time in seconds: {elapsed}")


if __name__ == "__main__":
    main()
