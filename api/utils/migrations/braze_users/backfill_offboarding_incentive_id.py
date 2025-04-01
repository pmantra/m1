import datetime
from collections import defaultdict

from sqlalchemy import or_
from sqlalchemy.orm import Load

from authn.models.user import User
from incentives.models.incentive import (
    IncentiveAction,
    IncentiveOrganization,
    IncentiveOrganizationCountry,
)
from models.tracks import MemberTrack
from models.tracks.client_track import ClientTrack
from storage.connection import db
from tracks.service import TrackSelectionService
from utils import braze
from utils.braze import BrazeUserIncentives
from utils.log import logger

log = logger(__name__)

"""
We have two new Braze attributes to identify which incentives a user
is eligible for, "incentive_id_ca_intro" and "incentive_id_offboarding".
Both incentives will be populated during onboarding, and updated any time
the Incentive-Organization model changes. For current users who have already
gone through onboarding, we only need to backfill "incentive_id_offboarding".

This script will overwrite incentive_id_ca_intro to None if the user already
has it, but the script will be run prior to the project launch, so
incentive_id_ca_intro will not populated on any users at the time of running
the script.
"""


def report_incentive_id_offboarding_to_braze(org_ids, dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if dry_run:
        log.info(
            "Dry run of reporting offboarding incentive id's to Braze",
            org_list=org_ids,
        )
    else:
        log.info(
            "Reporting offboarding incentive id's to Braze",
            org_list=org_ids,
        )

    # we know we backfilled incentives only on these 4 tracks
    incentive_tracks = ["pregnancy", "fertility", "postpartum", "egg_freezing"]
    braze_incentives = []

    # for every active user in one of the potential incentive tracks
    # who is also in one of the org_ids passed in
    active_users = (
        db.session.query(User)
        .filter(
            User.active == True,
            User.country_code != None,
        )
        .join(MemberTrack)
        .filter(
            or_(
                MemberTrack.ended_at == None,
                MemberTrack.ended_at > datetime.datetime(2023, 11, 18, 0, 0, 0),
            ),
            MemberTrack.name.in_(incentive_tracks),
        )
        .join(ClientTrack)
        .filter(
            ClientTrack.organization_id.in_(org_ids),
        )
        .options(
            Load(MemberTrack).load_only(  # type: ignore[attr-defined] # "Load" has no attribute "load_only"
                MemberTrack.active,
                MemberTrack.name,
            ),
            Load(ClientTrack).load_only(  # type: ignore[attr-defined] # "Load" has no attribute "load_only"
                ClientTrack.organization_id,
            ),
        )
        .all()
    )

    offboarding_incentive_orgs = (
        db.session.query(
            IncentiveOrganization.id,
            IncentiveOrganization.organization_id,
            IncentiveOrganization.incentive_id,
            IncentiveOrganization.track_name,
        )
        .filter(
            IncentiveOrganization.active == True,
            IncentiveOrganization.action == IncentiveAction.OFFBOARDING_ASSESSMENT.name,
        )
        .all()
    )
    offboarding_incentive_orgs_dict = defaultdict(lambda: defaultdict(dict))
    for incentive_org in offboarding_incentive_orgs:
        offboarding_incentive_orgs_dict[incentive_org.organization_id][
            incentive_org.track_name
        ] = {"id": incentive_org.id, "incentive_id": incentive_org.incentive_id}

    # needs to be done separately or we will run out of memory
    incentive_org_countries = (
        db.session.query(
            IncentiveOrganizationCountry.incentive_organization_id,
            IncentiveOrganizationCountry.country_code,
            IncentiveOrganizationCountry.id,
        )
    ).all()
    incentive_org_country_dict = defaultdict(lambda: defaultdict(dict))
    for incentive_org_country in incentive_org_countries:
        incentive_org_country_dict[incentive_org_country.incentive_organization_id][
            incentive_org_country.country_code
        ] = incentive_org_country.id

    for user in active_users:
        # get highest priority track
        num_active_tracks = len(user.active_tracks)
        if num_active_tracks > 1:
            highest_priority_track = TrackSelectionService().get_highest_priority_track(
                user.active_tracks
            )
            highest_priority_track_name = highest_priority_track.name  # type: ignore[union-attr] # Item "None" of "Optional[MemberTrack]" has no attribute "name"
        elif num_active_tracks == 1:
            highest_priority_track_name = user.active_tracks[0].name
        # no active tracks, must be recently transitioned so check inactive tracks
        else:
            highest_priority_track = TrackSelectionService().get_highest_priority_track(
                user.inactive_tracks
            )
            highest_priority_track_name = highest_priority_track.name  # type: ignore[union-attr] # Item "None" of "Optional[MemberTrack]" has no attribute "name"
        if highest_priority_track_name in incentive_tracks and user.organization:
            # look for an incentive_org match
            incentive_org_match = offboarding_incentive_orgs_dict[
                user.organization_v2.id
            ][highest_priority_track_name]
            if incentive_org_match and user.country_code:
                # confirm there's also an incentive_org_country match
                incentive_org_country_match = incentive_org_country_dict[
                    incentive_org_match["id"]
                ][user.country_code]
                if incentive_org_country_match:
                    log.info(
                        "Adding incentive to Braze list.",
                        user_id=user.id,
                        org_id=user.organization.id,
                        track=highest_priority_track_name,
                        country=user.country_code,
                        incentive_id=incentive_org_match["incentive_id"],
                    )
                    """
                    We are only populating incentive_id_offboarding in this backfill but
                    need to include incentive_id_ca_intro in the BrazeUserIncentives obj.
                    This would override a user's incentive_id_ca_intro on Braze to None,
                    but this script will be run prior to any users having incentive_id_ca_intro
                    populated.
                    """
                    braze_incentives.append(
                        BrazeUserIncentives(
                            incentive_id_ca_intro=None,  # type: ignore[arg-type] # Argument "incentive_id_ca_intro" to "BrazeUserIncentives" has incompatible type "None"; expected "int"
                            incentive_id_offboarding=incentive_org_match[
                                "incentive_id"
                            ],
                            external_id=user.esp_id,
                        )
                    )
                else:
                    log.info(
                        "No country match found for incentive_org and user's country.",
                        user_id=user.id,
                        org_id=user.organization.id,
                        track=highest_priority_track_name,
                        country=user.country_code,
                    )
            else:
                log.info(
                    "No incentive-org match found.",
                    user_id=user.id,
                    org_id=user.organization.id,
                    track=highest_priority_track_name,
                    country=user.country_code,
                )
        else:
            log.info(
                "There are no incentives set up for user's highest priority track",
                user_id=user.id,
                track=highest_priority_track_name,
            )

    log.info(
        f"Found {len(braze_incentives)} total incentives. Breaking into groups to send to Braze."
    )

    split_lists = [
        braze_incentives[i : i + 75] for i in range(0, len(braze_incentives), 75)
    ]
    for i, incentive_list in enumerate(split_lists):
        num_braze_calls = len(split_lists)
        num_records_in_call = len(incentive_list)
        log.info(
            f"Sending incentive group {i+1}/{num_braze_calls}. Group contains {num_records_in_call} records."
        )
        if dry_run:
            log.info(
                f"Dry run. Would have sent {num_records_in_call} incentives to Braze."
            )
        else:
            braze.send_incentives(incentive_list)
            log.info(f"Sent {num_records_in_call} incentives to Braze.")
