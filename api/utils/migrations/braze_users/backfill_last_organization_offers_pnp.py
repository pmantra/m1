from dataclasses import dataclass

import click
from sqlalchemy import func, true

from authn.models.user import User
from braze import client
from common.services.api import chunk
from models.enterprise import Organization
from models.tracks import ClientTrack, MemberTrack, TrackName
from storage.connection import db
from utils.braze import BrazeUser
from utils.log import logger

log = logger(__name__)


"""
We have a Braze campaign that needs to know if a member with a track that recently ended
is associated to an organization that offers P&P. The campaign is configured to send emails
to users at three points in time - when the track ends, 1 week later, and 1 month later. 
Therefore, this backfill is scoped to send the last_organization_offers_pnp custom attribute for
users that have had a track end in the last month (plus a couple days). 
"""

TRACK_ENDED_DAYS_AGO = 32


@dataclass(frozen=True)
class BrazeLastOrganizationOffersPnp(BrazeUser):
    last_organization_offers_pnp: bool


def build_query(query):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return (
        query.join(MemberTrack, MemberTrack.user_id == User.id)
        .join(ClientTrack, ClientTrack.id == MemberTrack.client_track_id)
        .filter(
            MemberTrack.ended_at > func.subdate(func.now(), TRACK_ENDED_DAYS_AGO),
            ClientTrack.organization_id.in_(
                db.session.query(Organization.id)
                .join(ClientTrack, ClientTrack.organization_id == Organization.id)
                .filter(
                    ClientTrack.active == true(),
                    ClientTrack.track == TrackName.PARENTING_AND_PEDIATRICS,
                )
            ),
        )
    )


def report_last_organization_offers_pnp_to_braze(dry_run, page_size, page_limit):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if dry_run:
        log.info(
            "Dry run of reporting last_organization_offers_pnp to Braze",
            page_size=page_size,
            page_limit=page_limit,
        )
    else:
        log.info(
            "Reporting last_organization_offers_pnp to Braze",
            page_size=page_size,
            page_limit=page_limit,
        )

    last_organization_offers_pnp = build_query(db.session.query(User.esp_id)).all()

    braze_client = client.BrazeClient()
    for page_number, page in enumerate(chunk(last_organization_offers_pnp, page_size)):
        if not dry_run:
            user_attributes = [
                client.BrazeUserAttributes(
                    external_id=row.esp_id,
                    attributes={"last_organization_offers_pnp": True},
                )
                for row in page
            ]
            braze_client.track_users(user_attributes=user_attributes)

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
        "Running last_organization_offers_pnp backfill",
        dry_run=dry_run,
        page_limit=page_limit,
        page_size=page_size,
    )
    from app import create_app

    with create_app(task_instance=True).app_context():
        if dry_run:
            count = build_query(db.session.query(func.count(User.esp_id))).scalar()
            log.info(
                "Statistics on last_organization_offers_pnp",
                count=count,
            )

        report_last_organization_offers_pnp_to_braze(dry_run, page_size, page_limit)


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
