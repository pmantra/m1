from csv import DictReader
from pathlib import Path

import click

from models.enterprise import Organization, OrganizationEligibilityType
from storage.connection import db
from utils.log import logger

log = logger(__name__)

default_file_path = (
    Path(__file__).absolute().parent
    / "Organization_eligibility_types_b2b2c_enrollment_organization_data_20220406T1547.csv"
)


def get_mapping(path: Path) -> DictReader:
    """
    Open a CSV file containing a mapping between organization name and ID to their expected eligibility type.
    :param path: path to CSV file
    :return: DictReader of the CSV file contents
    """
    log.info("Fetching organization elibility type mapping from file.", file=str(path))
    mapping = DictReader(path.open())
    log.info("Fetched mapping from file.", file=str(path))
    return mapping


def update_org_eligibility_type(mapping: DictReader):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Updates organization.eligibility_type which allows us to determine what
    eligibility flow an organization is set up for to optimize onboarding.
    :param mapping: DictReader containing mapping between organization name and ID to their expected eligibility type
    """
    types_by_org_id = {
        int(o["id"]): o["eligibility_type"].upper()
        for o in mapping
        if "eligibility_type" in o
    }
    orgs = db.session.query(Organization.id).filter(
        Organization.id.in_(types_by_org_id)
    )

    updates = []
    for org in orgs:
        try:
            eligibility_type = OrganizationEligibilityType(types_by_org_id[org.id])
            updates.append({"id": org.id, "eligibility_type": eligibility_type})
        except ValueError:
            log.warn("Unknown eligibility type found.", org_id=org.id)

    db.session.bulk_update_mappings(Organization, updates)
    db.session.flush()


@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    default=default_file_path,
    prompt="Path to CSV file",
    help="A path to a CSV which contains the mapping from `organization_name->eligibility_type`.",
)
@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
def backfill(file_path: str = default_file_path, dry_run: bool = False):  # type: ignore[assignment] # Incompatible default for argument "file_path" (default has type "Path", argument has type "str") #type: ignore[no-untyped-def] # Function is missing a return type annotation
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            mapping = get_mapping(Path(file_path))
            update_org_eligibility_type(mapping)
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
