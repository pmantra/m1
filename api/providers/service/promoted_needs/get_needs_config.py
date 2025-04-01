from __future__ import annotations

from authn.models.user import User
from models.tracks import TrackName
from tracks import service as tracks_service

from .needs_configurations.config import configuration as NeedSlugConfig
from .needs_configurations.constants import MARKETPLACE_MEMBER


def get_member_active_track_name(user: User) -> TrackName | str | None:
    """
    If member is in marketplace, return 'marketplace'
    If member is in 1 track, return that name
    If member is in multiple tracks, return the non Parenting and Pediatrics track
    If all else fails (which should be close to never if not impossible), return None
    """
    track_svc = tracks_service.TrackSelectionService()
    if not track_svc.is_enterprise(user_id=user.id):
        return MARKETPLACE_MEMBER

    if len(user.active_tracks) == 1:
        return user.active_tracks[0].name

    for track in user.active_tracks:
        if track.name != TrackName.PARENTING_AND_PEDIATRICS:
            return track.name

    return None


def get_config():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Get configuration file that stores need file;
    Will return a dictionary with the top 3 needs per track.

    *Please note* that this is the MVP version of this feature.
    In the future ideally we store these configuration files in another format that
    makes this easier to manage and update
    """
    return NeedSlugConfig
