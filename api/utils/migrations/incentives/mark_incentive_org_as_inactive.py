from __future__ import absolute_import

import click

from incentives.models.incentive import IncentiveAction
from incentives.repository.incentive_organization import IncentiveOrganizationRepository
from models.tracks import TrackName
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def print_header(header_text):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.info("\n=================================================")
    log.info(f"{header_text}\n=================================================\n")


def mark_incentive_org_as_inactive(track_name: TrackName, action: IncentiveAction):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # get incentive organizations based on track
    organizations = IncentiveOrganizationRepository().get_incentive_orgs_by_track_action_and_active_status(
        track_name=track_name, action=IncentiveAction(action).name, is_active=True
    )

    log.info(f"Number of rows to update: {len(organizations)}")

    for org in organizations:
        org.active = False


def mark_incentive_org_as_inactive_wrapper(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    track_name: TrackName, action: IncentiveAction, dry_run: bool
):
    try:
        print_header("Starting updates")
        mark_incentive_org_as_inactive(track_name, action)
    except Exception as e:
        db.session.rollback()
        log.info("Got an exception while updating.", exception=e)  # noqa
        return

    if dry_run:
        log.info("Dry run requested. Rolling back changes.")  # noqa
        db.session.rollback()
        return

    log.info("Committing changes...")  # noqa
    db.session.commit()
    log.info("Finished.")  # noqa


@click.command()
@click.option(
    "--track",
    required=True,
    prompt="Track name used to filter incentive organizations",
    help="The track name associated with the incentive organization entries that you want to mark as inactive.",
    type=click.Choice([track.value for track in TrackName], case_sensitive=True),
)
@click.option(
    "--action",
    required=True,
    prompt="Incentive action name that will be used to create the incentive organizations",
    type=click.Choice(
        [action.value for action in IncentiveAction], case_sensitive=True
    ),
)
@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
def main(track: TrackName, action: IncentiveAction, dry_run: bool = False):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from app import create_app

    with create_app(task_instance=True).app_context():
        mark_incentive_org_as_inactive_wrapper(track, action, dry_run)


if __name__ == "__main__":
    main()
