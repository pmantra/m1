from typing import Dict

from models.tracks.member_track import ChangeReason, MemberTrack
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def update_member_id_and_subpop_id(
    update_mapping: Dict[int, Dict[str, int]], dry_run: bool = True
) -> None:
    member_track_updates = []

    # get existing member tracks
    mts = (
        db.session.query(MemberTrack)
        .filter(MemberTrack.id.in_(list(update_mapping.keys())))
        .all()
    )

    for mt in mts:
        mapping = update_mapping[mt.id]
        member_track_updates.append(
            {
                "id": mt.id,
                "eligibility_member_id": mapping["eligibility_member_id"],
                "sub_population_id": mapping["sub_population_id"],
                "change_reason": ChangeReason.MANUAL_UPDATE,
            }
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
