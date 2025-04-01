from sqlalchemy import asc, func

from models.tracks import MemberTrack
from utils.log import logger

log = logger(__name__)


class PatientTracks:
    """Queries and retrieves user track information.
    returns a dictionary with keys 'active_track and 'inactive_track'
    """

    @classmethod
    def get_tracks_by_user_id(cls, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        active_tracks = (
            MemberTrack.query.filter(
                MemberTrack.user_id == user_id, MemberTrack.active.is_(True)
            )
            .order_by(asc(func.lower(MemberTrack.name)))
            .all()
        )
        inactive_tracks = (
            MemberTrack.query.filter(
                MemberTrack.user_id == user_id, MemberTrack.active.is_(False)
            )
            .order_by(asc(func.lower(MemberTrack.name)))
            .all()
        )
        return {"active_tracks": active_tracks, "inactive_tracks": inactive_tracks}
