from __future__ import annotations

import csv

import click

from direct_payment.clinic.models.clinic import (
    FertilityClinicLocation,
    FertilityClinicLocationContact,
)
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def get_correct_clinic_location(
    name: str,
    city: str,
    subdivision_code: str,
    postal_code: str,
    address: str,
    clinic_locations: list[FertilityClinicLocation],
) -> FertilityClinicLocation | None:
    for location in clinic_locations:
        if (
            (location.name and location.name.strip().lower() == name)
            and (location.city and location.city.strip().lower() == city)
            and (
                location.subdivision_code
                and location.subdivision_code.strip().lower() == subdivision_code
            )
            and (
                location.postal_code
                and location.postal_code.strip().lower() == postal_code
            )
            and (location.address_1 and location.address_1.strip().lower() == address)
        ):
            # Winner!
            return location
    return None


def populate_fertility_clinic_location_contacts(is_dry_run: bool = True):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # Yes, this is very inefficient, but it is meant only for a 1-time backfill.
    all_clinic_locations = FertilityClinicLocation.query.all()

    count = 0
    with open(
        "./utils/migrations/csvs/2024_01_fertility_location_contacts.csv", newline=""
    ) as csvfile:
        reader = csv.DictReader(csvfile)
        row_ids = []
        for row in reader:
            # DEPENDS ON COLUMN NAMES AND HOW WE'RE LOADING THE DATA
            # parse
            address = row["Full Address"].strip().lower()
            contact_name = row["Name"].strip().lower()
            city = row["City"].strip().lower()
            subdivision_code = row["Subdivision Code"].strip().lower()
            postal_code = row["Postal Code"].strip().lower()
            # affiliated_network = row["Affiliated Network"].strip().lower()
            email = row["Point of Contact Email(s)"].strip().lower()
            clinic_name = row["Fertility Clinic Location Name"].strip().lower()
            row_id = row["id"].strip().lower()

            correct_fertility_clinic_location = get_correct_clinic_location(
                clinic_name,
                city,
                subdivision_code,
                postal_code,
                address,
                all_clinic_locations,
            )
            if correct_fertility_clinic_location is not None:
                location_contact = FertilityClinicLocationContact(
                    uuid=str(correct_fertility_clinic_location.uuid),
                    fertility_clinic_location_id=correct_fertility_clinic_location.id,
                    name=contact_name or None,
                    phone_number=None,
                    email=email,
                )
                if not is_dry_run:
                    db.session.add(location_contact)
                    if count % 50 == 0:
                        db.session.commit()
                row_ids.append(row_id)
                count += 1

        if count % 50 != 0 and not is_dry_run:
            db.session.commit()
        print(f"Job complete - Added row ids: {', '.join(str(id) for id in row_ids)}")
    print(f"Added {count} rows to the fertility_clinic_location_contact table.")


@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
def populate(dry_run: bool = True):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from app import create_app

    with create_app(task_instance=True).app_context():
        if dry_run:
            log.info("Dry run requested")
        try:
            populate_fertility_clinic_location_contacts(dry_run)
        except Exception as e:
            db.session.rollback()
            log.exception("Got an exception while backfilling.", exception=e)
            return


if __name__ == "__main__":
    populate()
