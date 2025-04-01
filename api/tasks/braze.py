from __future__ import annotations

from authn.models.user import User
from braze import client
from storage.connection import db
from tasks.helpers import get_user
from tasks.queues import job
from utils import braze, braze_events
from utils.log import logger

log = logger(__name__)


@job(traced_parameters=("user_id",))
def send_password_setup(user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    user = User.query.get(user_id)
    braze.track_user(user)
    braze_events.new_user_password_set(user)


@job
def sync_practitioner_with_braze(user_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info("Syncing provider with Braze")
    user = db.session.query(User).get(user_id)

    if not user:
        log.debug(f"User with id {user_id} does not exist.")
        return

    if not user.is_practitioner:
        log.debug(
            f"User with id {user_id} does not have a practitioner profile. Not syncing with braze."
        )
        return

    braze.sync_practitioners([user])
    log.info("Provider sync with Braze completed")


@job(team_ns="enrollments", service_ns="member_profile")
def unsubscribe_from_member_communications(user_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info("Unsubscribing member from communications", user_id=user_id)
    user = db.session.query(User).get(user_id)

    if not user:
        log.debug("User does not exist", user_id=user_id)

    braze_client = client.BrazeClient()
    braze_client.unsubscribe_email(email=user.email)


@job(team_ns="enrollments", service_ns="member_profile")
def opt_into_member_communications(user_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info("Member opted-in to communications", user_id=user_id)
    user = db.session.query(User).get(user_id)

    if not user:
        log.debug("User does not exist", user_id=user_id)

    braze_client = client.BrazeClient()
    braze_client.opt_in_email(email=user.email)


@job(team_ns="enrollments")
def report_last_eligible_through_organization(user_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info("Reporting organization associated to user", user_id=user_id)
    user = db.session.query(User).get(user_id)

    if not user:
        log.debug("User does not exist", user_id=user_id)
        return

    # Grab the organization this user is associated with - avoid circular import
    from tracks import service as tracks_svc

    track_svc = tracks_svc.TrackSelectionService()
    organization = track_svc.get_organization_for_user(user_id=user_id)

    if organization is None:
        log.debug("Organization setting does not exist", user_id=user_id)
    else:
        braze.send_last_eligible_through_organization(user.esp_id, organization.name)


@job
def update_bulk_messaging_attrs_in_braze(user_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    user = get_user(user_id=user_id)
    if not user:
        log.warning("User id not found", user_id=user_id)
        return

    braze.update_bulk_messaging_attrs(user=user)


@job(team_ns="care_discovery")
def update_care_advocate_attrs(user_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    attrs = {}
    user = db.session.query(User).get(user_id)
    braze._populate_care_coordinator_attrs(attrs, user)
    log.info("Updating care coordinator attributes in braze", user_id=user.id)
    braze_client = client.BrazeClient()
    braze_user_attributes = client.BrazeUserAttributes(
        external_id=user.esp_id,
        attributes=attrs,
    )
    braze_client.track_user(user_attributes=braze_user_attributes)
