import click
from sqlalchemy import func

from authn.models.user import User
from common.services.api import chunk
from models.enterprise import (
    Organization,
    OrganizationEmployee,
    UserOrganizationEmployee,
)
from storage.connection import db
from utils import braze
from utils.braze import BrazeEligibleThroughOrganization
from utils.log import logger

log = logger(__name__)


def report_last_eligible_through_organization_to_braze(dry_run, page_size, page_limit):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if dry_run:
        log.info(
            "Dry run of reporting last_eligible_through_organization to Braze",
            page_size=page_size,
            page_limit=page_limit,
        )
    else:
        log.info(
            "Reporting last_eligible_through_organization to Braze",
            page_size=page_size,
            page_limit=page_limit,
        )

    last_eligible_through_organizations = (
        db.session.query(User.id, User.esp_id, Organization.name)
        .join(
            UserOrganizationEmployee,
            User.id == UserOrganizationEmployee.user_id,
        )
        .join(
            OrganizationEmployee,
            UserOrganizationEmployee.organization_employee_id
            == OrganizationEmployee.id,
        )
        .join(
            Organization,
            OrganizationEmployee.organization_id == Organization.id,
        )
        .all()
    )

    for page_number, page in enumerate(
        chunk(last_eligible_through_organizations, page_size)
    ):
        if not dry_run:
            mapped_last_eligible_through_organizations = [
                BrazeEligibleThroughOrganization(
                    last_eligible_through_organization=row.name,
                    external_id=row.esp_id,
                )
                for row in page
            ]
            braze.send_last_eligible_through_organizations(
                mapped_last_eligible_through_organizations
            )

        if page_limit and page_number >= page_limit - 1:
            log.info("Reached page limit, exiting", page_limit=page_limit)
            break
        log.info(f"Finished processing page number {page_number}")


def backfill(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    dry_run: bool = False,
    page_limit: int = None,  # type: ignore[assignment] # Incompatible default for argument "page_limit" (default has type "None", argument has type "int")
    page_size: int = 50,
):
    log.info(
        "Running last_eligible_through_organization backfill",
        dry_run=dry_run,
        page_limit=page_limit,
        page_size=page_size,
    )
    from app import create_app

    with create_app(task_instance=True).app_context():
        if dry_run:
            count = (
                db.session.query(func.count(User.id))
                .join(
                    UserOrganizationEmployee,
                    User.id == UserOrganizationEmployee.user_id,
                )
                .join(
                    OrganizationEmployee,
                    UserOrganizationEmployee.organization_employee_id
                    == OrganizationEmployee.id,
                )
                .join(
                    Organization,
                    OrganizationEmployee.organization_id == Organization.id,
                )
                .scalar()
            )
            log.info(
                "Statistics on last_eligible_through_organization",
                count=count,
            )

        report_last_eligible_through_organization_to_braze(
            dry_run, page_size, page_limit
        )


@click.command()
@click.option(
    "--dry_run",
    "-d",
    is_flag=True,
    help="Retrieves the data from the database without updating Braze",
)
def main(dry_run: bool = False):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    backfill(dry_run=dry_run)


if __name__ == "__main__":
    main()
