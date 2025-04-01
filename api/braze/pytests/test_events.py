from datetime import datetime
from unittest.mock import patch

from braze.client import constants
from braze.events import send_track_transition_event
from models.tracks import TrackName
from pytests.freezegun import freeze_time

FAKE_EVENT_DATETIME = datetime(2050, 1, 1, 1, 1).isoformat()


@patch("braze.client.BrazeClient._make_request")
@freeze_time(FAKE_EVENT_DATETIME)
def test_send_track_transition(mock_request):
    user_esp_id = "abc"
    source = TrackName.TRYING_TO_CONCEIVE
    target = TrackName.PREGNANCY

    send_track_transition_event(
        user_esp_id=user_esp_id,
        source=source,
        target=target,
        as_auto_transition=False,
    )

    mock_request.assert_called_with(
        endpoint=constants.USER_TRACK_ENDPOINT,
        data={
            "events": [
                {
                    "external_id": user_esp_id,
                    "name": "track_transition",
                    "time": FAKE_EVENT_DATETIME,
                    "properties": {
                        "source": source.value,
                        "target": target.value,
                        "as_auto_transition": False,
                    },
                }
            ]
        },
    )
