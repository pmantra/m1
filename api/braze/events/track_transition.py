from __future__ import annotations

from braze import client
from models.tracks.track import TrackName
from tasks.queues import job


@job(team_ns="enrollments")
def send_track_transition_event(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    user_esp_id: str,
    source: TrackName,
    target: TrackName,
    as_auto_transition: bool,
):
    braze_client = client.BrazeClient()
    braze_client.track_user(
        events=[
            client.BrazeEvent(
                external_id=user_esp_id,
                name="track_transition",
                properties={
                    "source": TrackName(source).value,
                    "target": TrackName(target).value,
                    "as_auto_transition": as_auto_transition,
                },
            )
        ]
    )
