from typing import Dict, Iterator

import click

from models.enterprise import OrganizationEmployee, UserOrganizationEmployee
from models.tracks import MemberTrack
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def backfill_user_organization_employees(batch_size: int = 1_000):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for batch in create_batch(batch_size=batch_size):
        db.session.bulk_save_objects(batch)


def create_batch(batch_size: int = 1_000) -> Iterator[Dict[int, str]]:
    log.debug(
        "Fetching unique User/OrganizationEmployee instances from the member_track table..."
    )
    query = (
        db.session.query(
            MemberTrack.user_id,
            OrganizationEmployee.id,
            OrganizationEmployee.deleted_at,
        )
        .join(OrganizationEmployee)
        .order_by(MemberTrack.user_id, OrganizationEmployee.id)
        .distinct(MemberTrack.user_id, OrganizationEmployee.id)
        .execution_options(stream_results=True)
    )

    log.debug("Creating UserOrganizationEmployee instances...")
    batch_num = 0
    batch = query.limit(batch_size).all()
    to_add = []
    while batch:
        lastid = batch[-1].user_id
        batch_num += 1

        for user_id, org_emp_id, deleted_at in batch:
            user_organization_employee = UserOrganizationEmployee.query.filter_by(
                user_id=user_id,
                organization_employee_id=org_emp_id,
            ).one_or_none()

            if not user_organization_employee:
                user_organization_employee = UserOrganizationEmployee(
                    user_id=user_id,
                    organization_employee_id=org_emp_id,
                    ended_at=deleted_at,
                )
                to_add.append(user_organization_employee)

        if len(to_add) >= batch_size:
            yield to_add
            to_add = []
        else:
            log.debug("Still building batch...", batch=batch_num, size=len(batch))

        # Pull in the next batch
        batch = query.filter(MemberTrack.user_id > lastid).limit(batch_size).all()
    if to_add:
        yield to_add


def backfill(dry_run: bool = False, batch_size: int = 1_000):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info("Running UserOrganizationEmployee backfill.", dry_run=dry_run)
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            backfill_user_organization_employees(batch_size=batch_size)
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


@click.command()
@click.option(
    "--dry_run",
    "-d",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
@click.option(
    "--batch_size",
    "-b",
    default=1_000,
    help="The number of MemberTracks to pull into memory at a time.",
)
def main(dry_run: bool = False, batch_size: int = 1_000):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    backfill(dry_run=dry_run, batch_size=batch_size)


if __name__ == "__main__":
    main()
