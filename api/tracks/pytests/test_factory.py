from models.tracks import TrackName


def test_enterprise_user_enabled_tracks(factories):
    # Given
    enabled = {TrackName.ADOPTION, TrackName.BREAST_MILK_SHIPPING}
    # When
    user = factories.EnterpriseUserFactory.create(enabled_tracks=enabled)
    # TODO: [multitrack] use a loop over user.active_tracks
    enabled.add(user.current_member_track.name)
    # Then
    assert {ct.track for ct in user.organization.client_tracks} == enabled
