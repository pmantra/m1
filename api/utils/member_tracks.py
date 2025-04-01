from models import tracks
from models.tracks.member_track import ChangeReason, MemberTrack
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def terminate_track(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    member_track_id: int,
    revoke_billing: bool,
    user_id: int,
    modified_by: str = None,  # type: ignore[assignment] # Incompatible default for argument "modified_by" (default has type "None", argument has type "str")
    change_reason: ChangeReason = None,  # type: ignore[assignment] # Incompatible default for argument "change_reason" (default has type "None", argument has type "ChangeReason")
):
    member_track = db.session.query(MemberTrack).get(member_track_id)

    log.info(
        "Terminating MemberTrack.",
        member_track_id=member_track.id,
        revoke_billing=revoke_billing,
        terminated_by=user_id,
    )
    tracks.terminate(
        track=member_track, modified_by=modified_by, change_reason=change_reason
    )
    db.session.commit()
