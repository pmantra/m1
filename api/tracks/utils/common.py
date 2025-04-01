from typing import List

from models.tracks import MemberTrack
from models.tracks.client_track import TrackModifiers


def get_active_member_track_modifiers(
    active_tracks: List[MemberTrack],
) -> List[TrackModifiers]:
    active_member_track_modifiers = [
        modifier
        for track in active_tracks
        if track.track_modifiers is not None
        for modifier in track.track_modifiers
    ]
    return active_member_track_modifiers
