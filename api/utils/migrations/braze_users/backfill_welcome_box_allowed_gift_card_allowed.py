import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Load

from authn.models.user import User
from braze import client
from models.enterprise import Organization
from models.tracks import MemberTrack
from models.tracks.client_track import ClientTrack
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def report_welcome_box_allowed_gift_card_allowed_to_braze(org_ids, dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if dry_run:
        log.info(
            "Dry run of reporting welcome_box_allowed and gift_card_allowed to Braze",
            org_list=org_ids,
        )
    else:
        log.info(
            "Reporting welcome_box_allowed and gift_card_allowed to Braze",
            org_list=org_ids,
        )

    user_incentives_allowed = (
        db.session.query(
            User.esp_id,
            Organization.welcome_box_allowed,
            Organization.gift_card_allowed,
        )
        .filter(User.active == True)
        .join(MemberTrack)
        .filter(
            or_(
                MemberTrack.ended_at == None,
                MemberTrack.ended_at > datetime.datetime(2024, 1, 1, 0, 0, 0),
            ),
        )
        .join(ClientTrack)
        .join(Organization)
        .filter(
            Organization.id.in_(org_ids),
            or_(
                Organization.welcome_box_allowed == True,
                Organization.gift_card_allowed == True,
            ),
        )
        .options(
            Load(MemberTrack).load_only(  # type: ignore[attr-defined] # "Load" has no attribute "load_only"
                MemberTrack.ended_at,
            ),
        )
        .all()
    )

    braze_client = client.BrazeClient()
    braze_incentives_allowed = [
        client.BrazeUserAttributes(
            external_id=user_incentive.esp_id,
            attributes={
                "welcome_box_allowed": user_incentive.welcome_box_allowed,
                "gift_card_allowed": user_incentive.gift_card_allowed,
            },
        )
        for user_incentive in user_incentives_allowed
    ]
    num_sent_to_braze = len(braze_incentives_allowed)
    if dry_run:
        log.info(
            "Dry run. Would have sent welcome_box_allowed and gift_card_allowed to Braze.",
            num_sent_to_braze=num_sent_to_braze,
            organization_ids=org_ids,
        )
    else:
        braze_client.track_users(user_attributes=braze_incentives_allowed)
        log.info(
            "Sent welcome_box_allowed and gift_card_allowed to Braze.",
            num_sent_to_braze=num_sent_to_braze,
            organization_ids=org_ids,
        )
