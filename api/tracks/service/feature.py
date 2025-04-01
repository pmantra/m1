from __future__ import annotations

import dataclasses
from typing import Any, Dict, List

from models.tracks import track
from models.tracks.client_track import ClientTrack


@dataclasses.dataclass(frozen=True)
class Feature:
    name: track.TrackName
    display_name: str | None
    label: str
    description: str
    display_length: str | None
    length_in_days: int | None
    required_information: list[str]
    is_partner: bool
    life_stage: str | None
    track_selection_category: str | None
    organization_id: int | None
    rx_enabled: bool


def build_tracks_data(client_tracks: List[ClientTrack]) -> List[Dict[str, Any]]:
    tracks_data = []

    for client_track in client_tracks:
        track_config = track.TrackConfig.from_name(client_track.name)
        if track_config.onboarding.label and track_config.onboarding.label != "None":
            track_data = Feature(
                name=track_config.name,
                display_name=track_config.display_name,
                label=track_config.onboarding.label,
                description=track_config.description,
                display_length=track_config.display_length,
                length_in_days=client_track.length_in_days,
                required_information=[
                    r.value for r in track_config.required_information
                ],
                is_partner=bool(track_config.onboarding.as_partner),
                life_stage=track_config.life_stage,
                track_selection_category=track_config.track_selection_category,
                organization_id=client_track.organization_id,
                rx_enabled=client_track.organization.rx_enabled,
            )
            tracks_data.append(dataclasses.asdict(track_data))
    return tracks_data
