from __future__ import absolute_import

import click

from airflow.utils import with_app_context
from incentives.models.incentive import (
    IncentiveAction,
    IncentiveOrganization,
    IncentiveOrganizationCountry,
)
from incentives.repository.incentive import IncentiveRepository
from models.enterprise import Organization
from models.tracks import TrackName
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def add_incentive_orgs(track: TrackName, action: IncentiveAction, incentive_name: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from incentives.services.incentive_organization import (
        IncentiveOrgAlreadyExistsException,
        IncentiveOrganizationService,
    )

    log.info("Finding incentive")
    incentive = IncentiveRepository().get_incentive_by_name(incentive_name)

    if not incentive:
        log.info(
            f"Could not find incentive with name {incentive_name}. Please try again"
        )
        return

    log.info(
        f"Found incentive using name {incentive_name}. Incentive has id of {incentive.id}"
    )

    # get organizations where gift card is enabled
    organizations = (
        db.session.query(Organization)
        .filter(Organization.gift_card_allowed == True)
        .all()
    )

    log.info(
        f"Number of organizations where gift cards is allowed: {len(organizations)}"
    )

    incentive_orgs = []
    for org in organizations:
        try:
            IncentiveOrganizationService().check_for_duplicates(
                organization=org,
                action=IncentiveAction(action).name,
                track_name=track,
                active=True,
            )

            incentive_org = IncentiveOrganization(
                action=IncentiveAction(action).name,
                track_name=track,
                incentive_id=incentive.id,
                organization_id=org.id,
                active=True,
            )
            db.session.add(incentive_org)
            incentive_orgs.append(incentive_org)

        except IncentiveOrgAlreadyExistsException:
            log.error(
                f"Found a duplicate. Will not create incentive organizations for organization {org.id}"
            )
            continue

    return incentive_orgs


def add_gift_card_incentive_org_wrapper(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    track: TrackName,
    action: IncentiveAction,
    incentive_name: str,
    dry_run: bool = False,
):
    try:
        log.info("\n=================================================")
        log.info(
            "Starting updates\n=================================================\n"
        )

        incentive_orgs = add_incentive_orgs(track, action, incentive_name)
    except Exception as e:
        db.session.rollback()
        log.info("Got an exception while updating.", exception=e)  # noqa
        return

    if dry_run:
        log.info("Dry run requested. Rolling back changes.")  # noqa
        db.session.rollback()
        return

    log.info("Committing incentive organization changes...")  # noqa
    db.session.commit()

    if incentive_orgs:
        # need to add countries only after the first commit

        # United Arab Emirates, Australia, Canada, Germany, Spain, France, United Kingdom, Italy, Japan, Mexico, Sweden, Singapore, United States
        country_codes = [
            "AE",
            "AU",
            "CA",
            "DE",
            "ES",
            "FR",
            "GB",
            "IT",
            "JP",
            "MX",
            "SE",
            "SG",
            "US",
        ]
        log.info(
            f"Will create incentive organizations using these countries: {', '.join(country_codes)}"
        )

        for incentive_org in incentive_orgs:
            for country_code in country_codes:
                new_incentive_org_country = IncentiveOrganizationCountry(
                    incentive_organization_id=incentive_org.id,
                    country_code=country_code,
                )
                db.session.add(new_incentive_org_country)

        db.session.commit()
        log.info("Committing incentive organization country changes...")  # noqa

    log.info("Finished.")  # noqa


@click.command()
@click.option(
    "--track",
    required=True,
    prompt="Track name that will be used to create the incentive organizations",
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
    "--incentive",
    required=True,
    prompt="Incentive that will be used to create the incentive organizations",
    type=click.Choice(
        ["$25 Amazon Gift Card", "$20 Amazon Gift Card"], case_sensitive=True
    ),
)
@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
@with_app_context()
def main(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    track: TrackName, action: IncentiveAction, incentive: str, dry_run: bool = False
):
    add_gift_card_incentive_org_wrapper(track, action, incentive, dry_run)


if __name__ == "__main__":
    main()
