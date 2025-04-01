from typing import List

from authn.models.user import User
from models.forums.config.category_groups import (
    CATEGORY_GROUPS,
    MULTITRACK_CATEGORY_GROUPS,
    CategoryGroup,
)


def get_category_groups_for_user(user: User) -> List[CategoryGroup]:
    user_is_multitrack = len(user.active_tracks) > 1

    if user_is_multitrack:
        active_track_name = next(
            iter(
                [
                    track.name
                    for track in user.active_tracks
                    if track.name != "parenting_and_pediatrics"
                ]
            ),
            "None",
        )
        return MULTITRACK_CATEGORY_GROUPS.get(
            active_track_name, MULTITRACK_CATEGORY_GROUPS.get("None", [])
        )
    else:
        active_track_name = user.active_tracks[0].name if user.active_tracks else "None"
        return CATEGORY_GROUPS.get(active_track_name, CATEGORY_GROUPS.get("None", []))
