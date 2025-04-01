"""
This script is intended to migrate partner fertility track length from 182 days to 364 days,
but can be used to migrate any length of any client tracks to another of same type.

There are three parts to the process:

1. Create 364 days Partner Fertility tracks, and de-activate the 182 days counterpart.
2. Migrate member tracks referencing 182 days Partner Fertility tracks to 364 days ones.
3. Cancel any pending renewals for the member tracks that have been migrated.
"""


from datetime import datetime
from typing import Dict, List

from models.tracks import TrackName
from models.tracks.client_track import ClientTrack
from models.tracks.member_track import MemberTrack
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def execute():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # example run specifically for partner fertility migration
    id_mapping = create_tracks(182, 364, TrackName.PARTNER_FERTILITY, dry_run=False)
    mt_ids = update_existing_member_tracks(id_mapping, False)
    terminate_pending_renewals(mt_ids, TrackName.PARTNER_FERTILITY, False)


# create client tracks and return member tracks affected
def create_tracks(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from_days: int,
    to_days: int,
    track_name: TrackName,
    ids: List[int] = None,  # type: ignore[assignment] # Incompatible default for argument "ids" (default has type "None", argument has type "List[int]")
    dry_run: bool = True,
    org_id: int = None,  # type: ignore[assignment] # Incompatible default for argument "org_id" (default has type "None", argument has type "int")
):
    id_mapping = {}

    query = db.session.query(ClientTrack).filter(
        ClientTrack.track == track_name.value,
        ClientTrack.length_in_days == from_days,
        ClientTrack.ended_at.is_(None),
    )

    if ids is not None:
        query = query.filter(ClientTrack.id.in_(ids))

    if not org_id:
        query = query.filter(ClientTrack.organization_id == org_id)

    client_tracks_existing = query.order_by(ClientTrack.organization_id).all()

    log.info(
        "total number of client tracks", client_tracks_size=len(client_tracks_existing)
    )
    client_track_inserts = []
    client_track_updates = []
    if len(client_tracks_existing) > 0:
        for client_track in client_tracks_existing:
            # create new client track of same name
            client_track_inserts.append(
                {
                    "track": track_name.value,
                    "length_in_days": to_days,
                    "organization_id": client_track.organization_id,
                    "active": True,
                }
            )

            # update to deactivate original client tracks
            client_track_updates.append(
                {
                    "id": client_track.id,
                    "active": False,
                    "ended_at": datetime.utcnow().date(),
                    "organization_id": client_track.organization_id,
                }
            )

    if dry_run:
        log.info("inserting client tracks", client_track_inserts=client_track_inserts)
        log.info("updating client tracks", client_track_updates=client_track_updates)

    log.info(
        "total client tracks to be updated",
        client_tracks_size=len(client_track_updates),
    )
    log.info(
        "total client tracks to be created",
        client_tracks_size=len(client_track_inserts),
    )

    if client_track_inserts and client_track_updates and not dry_run:
        db.session.bulk_insert_mappings(ClientTrack, client_track_inserts)
        db.session.bulk_update_mappings(ClientTrack, client_track_updates)
        db.session.commit()

        # client tracks are unique with (track, length_in_days, active, organization_id)
        # so this should return created client tracks
        client_tracks_new = (
            db.session.query(ClientTrack)
            .filter(
                ClientTrack.track == track_name.value,
                ClientTrack.length_in_days == to_days,
                ClientTrack.active,
                ClientTrack.organization_id.in_(
                    [ct["organization_id"] for ct in client_track_inserts]
                ),
            )
            .order_by(ClientTrack.organization_id)
            .all()
        )

        log.info(
            "newly created client tracks", client_tracks_new_size=len(client_tracks_new)
        )
        new_ids = dict((ct.organization_id, ct.id) for ct in client_tracks_new)

        if len(client_track_updates) == len(new_ids):
            id_mapping = dict(
                (ct["id"], new_ids[ct["organization_id"]])
                for ct in client_track_updates
            )
        else:
            log.error(
                "old_ids size not equal to new ids",
                client_track_updates_size=len(client_track_updates),
                new_ids_size=len(new_ids),
            )

    return id_mapping


def update_existing_member_tracks(id_mapping: Dict[int, int], dry_run: bool = True):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    member_track_updates = []
    log.info("client tracks to check ", keys=list(id_mapping.keys()))
    mts = (
        db.session.query(MemberTrack)
        .filter(
            MemberTrack.active, MemberTrack.client_track_id.in_(list(id_mapping.keys()))
        )
        .all()
    )

    for mt in mts:
        # update member track to new one
        member_track_updates.append(
            {"id": mt.id, "client_track_id": id_mapping[mt.client_track_id]}
        )

    log.info(
        "total member tracks to be updated",
        member_tracks_size=len(member_track_updates),
    )

    if dry_run:
        log.info("updating member tracks", member_track_updates=member_track_updates)

    if member_track_updates and not dry_run:
        db.session.bulk_update_mappings(MemberTrack, member_track_updates)
        db.session.commit()

    return [mt.id for mt in mts]


def terminate_pending_renewals(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    mt_ids: List[int], track_name: TrackName, dry_run: bool = True
):
    member_track_updates = []

    # inactive tracks that haven't ended that start in the future = pending renewal
    mts = (
        db.session.query(MemberTrack)
        .join(ClientTrack)
        .filter(
            MemberTrack.name == track_name.value,
            MemberTrack.scheduled,
            MemberTrack.start_date > datetime.utcnow().date(),
            MemberTrack.previous_member_track_id.in_(mt_ids),
        )
        .all()
    )

    for mt in mts:
        member_track_updates.append({"id": mt.id, "ended_at": datetime.utcnow()})

    log.info(
        "total member tracks to be terminate",
        member_tracks_size=len(member_track_updates),
    )

    if dry_run:
        log.info("terminating member tracks", member_track_updates=member_track_updates)

    if member_track_updates and not dry_run:
        db.session.bulk_update_mappings(MemberTrack, member_track_updates)
        db.session.commit()
