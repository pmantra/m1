from unittest import mock

from models.tracks.client_track import TrackModifiers
from tracks.utils.common import get_active_member_track_modifiers


@mock.patch("models.tracks.client_track.should_enable_doula_only_track")
def test_get_active_member_track_modifiers(
    mock_should_enable_doula_only_track, create_doula_only_member
):
    # Given

    # member with valid an active track that has a `doula_only` track modifiers
    member = create_doula_only_member
    active_tracks = member.active_tracks

    # When
    modifiers = get_active_member_track_modifiers(active_tracks)

    # Then
    assert TrackModifiers.DOULA_ONLY in modifiers
