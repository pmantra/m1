from typing import Optional

from storage.connection import db
from tracks.models_v2.member_track import (
    ActiveMemberTrack,
    InactiveMemberTrack,
    ScheduledMemberTrack,
)
from tracks.repository_v2.member_track import MemberTrackRepository
from utils.log import logger

log = logger(__name__)


class TrackService:
    def get_active_tracks(self, user_id: int) -> list[ActiveMemberTrack]:
        repository = MemberTrackRepository(session=db.session)
        active_member_tracks_repo = repository.get_active_member_tracks(user_id)
        active_member_tracks = [
            ActiveMemberTrack.from_member_track_data(track)
            for track in active_member_tracks_repo
        ]
        return active_member_tracks

    def get_inactive_tracks(self, user_id: int) -> list[InactiveMemberTrack]:
        repository = MemberTrackRepository(session=db.session)
        active_member_tracks_repo = repository.get_inactive_member_tracks(user_id)
        active_member_tracks = [
            InactiveMemberTrack.from_member_track_data(track)
            for track in active_member_tracks_repo
        ]
        return active_member_tracks

    def get_scheduled_tracks(self, user_id: int) -> list[ScheduledMemberTrack]:
        repository = MemberTrackRepository(session=db.session)
        scheduled_member_tracks_repo = repository.get_scheduled_member_tracks(user_id)
        scheduled_member_tracks = [
            ScheduledMemberTrack.from_member_track_data(track)
            for track in scheduled_member_tracks_repo
        ]
        return scheduled_member_tracks

    def get_organization_id_for_user(self, user_id: int) -> Optional[int]:
        """
        Determine which organization a user belongs to, based their most recent active track. If
        no active tracks are found, it will return the organization ID of the most recent inactive
        track. The sorting of the tracks is handled by the get_all_enrolled_tracks function.

        We will need to update this when overeligibility allows users to register for multiple orgs
        """
        # TODO: Overeligibility- when a user can be enrolled in two orgs, will need to re-write this logic

        most_recent_org_id: Optional[int] = None

        repository = MemberTrackRepository(session=db.session)
        enrolled_tracks = repository.get_all_enrolled_tracks(user_id, False)

        # Get all active tracks
        active_tracks = [track for track in enrolled_tracks if track.is_active]

        # If we have at least one active track
        if active_tracks:
            most_recent_org_id = active_tracks[-1].org_id

            # Grab the unique orgs from these tracks to check for enrollment in multiple orgs
            org_ids = {track.org_id for track in active_tracks}
            if len(org_ids) > 1:
                log.warn(
                    "Detected user enrolled in tracks for multiple organizations",
                    user_id=user_id,
                )
        # No active tracks - do we have any inactive ones?
        elif enrolled_tracks:
            most_recent_org_id = enrolled_tracks[-1].org_id

        return most_recent_org_id
