import csv

import click
from flask.cli import with_appcontext

from appointments.models.appointment import Appointment
from services.common import calculate_privilege_type
from storage.connection import db
from utils.query import paginate


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
    mapping = {"basic": "standard", "full_access": "standard"}

    with open(filename, "w") as f:
        writer = csv.DictWriter(
            f, fieldnames=["id", "privacy", "privilege_type", "created_at"]
        )
        writer.writeheader()

        if created_at:
            exp = Appointment.created_at >= created_at
        else:
            exp = Appointment.privilege_type.is_(None)

        for appointment in paginate(
            db.session.query(Appointment).filter(exp), Appointment.id, size=100
        ):
            if created_at:
                privilege_type = calculate_privilege_type(
                    appointment.practitioner, appointment.member
                )
            else:
                privilege_type = mapping.get(appointment.privacy) or appointment.privacy

            appointment.privilege_type = privilege_type

            writer.writerow(
                {
                    "id": appointment.id,
                    "privacy": appointment.privacy,
                    "privilege_type": privilege_type,
                    "created_at": appointment.created_at,
                }
            )
            if not dry_run:
                db.session.add(appointment)

    if not dry_run:
        db.session.commit()


if __name__ == "__main__":
    main()
