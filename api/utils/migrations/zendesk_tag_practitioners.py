"""
zendesk_tag_practitioners.py

Create and/or tag practitioner accounts in zendesk with a 'practitioner' tag.
All emails coming from that practitioner will thus be tagged alongside any relevant tickets.

Usage:
    zendesk_tag_practitioners.py [--force] (--all|--users=<users-email-csv>)

Options:
  -h --help     Show this screen.
  --all         Update all practitioners
  --users=<users-email-csv>       Provide a comma separated list of practitioners to update
  --force    Perform reassignments instead of showing what would happen.
"""

from docopt import docopt
from sqlalchemy import and_
from sqlalchemy.orm import joinedload
from zenpy.lib.exception import APIException

from app import create_app
from authn.models.user import User
from messaging.services.zendesk import (
    ZENDESK_PRACTITIONER_TAGS,
    get_or_create_zenpy_user,
    get_zenpy_user,
    tag_zendesk_user,
)
from models.profiles import (  # type: ignore[attr-defined] # Module "models.profiles" has no attribute "Vertical"
    PractitionerProfile,
    Vertical,
)
from models.verticals_and_specialties import CX_VERTICAL_NAME
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def tag_zendesk_users(users=None, force=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    tags = ZENDESK_PRACTITIONER_TAGS
    get_practitioners = PractitionerProfile.query.join(
        PractitionerProfile.verticals, PractitionerProfile.user
    ).options(joinedload(PractitionerProfile.user))
    if users:
        get_practitioners = get_practitioners.filter(
            and_(User.email.in_(users), Vertical.name != CX_VERTICAL_NAME)
        )
    else:
        get_practitioners = get_practitioners.filter(Vertical.name != CX_VERTICAL_NAME)
    practitioners = get_practitioners.all()
    if not practitioners:
        log.warning("Found no practitioners to tag.", requested_users=users)
    for profile in practitioners:
        if force is True:
            log.info(
                f"LIVE RUN: Attempting to tag practitioner {profile.user.email}",
                tags=tags,
            )
            try:
                zendesk_user = get_or_create_zenpy_user(profile.user)
                db.session.commit()
                result = tag_zendesk_user(zendesk_user, tags)
                if result:
                    log.info(
                        f"LIVE RUN: Tagged practitioner zendesk user {profile.user.email}.",
                        desired_tags=tags,
                        result_tags=result,
                    )
                else:
                    log.error(
                        f"LIVE RUN: Failed to tag Zendesk User {profile.user.email}."
                    )
            except APIException as e:
                log.error(
                    f"LIVE RUN: Failed to tag Practitioner {profile.user.email}",
                    exception=e,
                )
        else:
            log.info(
                f"DRY RUN: Attempting to tag practitioner {profile.user.email}",
                tags=tags,
            )
            zendesk_user = get_zenpy_user(profile.user)
            if zendesk_user:
                log.info(
                    f"DRY RUN: Zendesk user found for user {profile.user.email}",
                    zendesk_user=zendesk_user,
                )
            else:
                log.info(
                    f"DRY RUN: Zendesk user NOT found for user {profile.user.email}, live run will create user."
                )


if __name__ == "__main__":
    with create_app().app_context():
        args = docopt(__doc__)
        if args["--users"]:
            users = args["--users"].split(",")
            tag_zendesk_users(users, force=args["--force"])
        elif args["--all"]:
            tag_zendesk_users(None, force=args["--force"])
