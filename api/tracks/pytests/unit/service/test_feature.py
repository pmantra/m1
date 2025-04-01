from models.tracks.track import TrackName
from pytests import factories
from tracks.service.feature import build_tracks_data


class TestBuildTracksData:
    @staticmethod
    def test_empty_input(track_service):
        res = build_tracks_data(client_tracks=[])
        assert res == []

    @staticmethod
    def test_build_tracks_data(track_service):
        org_1 = factories.OrganizationFactory.create()
        org_2 = factories.OrganizationFactory.create()
        track_a = factories.ClientTrackFactory.create(
            track=TrackName.ADOPTION,
            organization=org_1,
        )
        track_b = factories.ClientTrackFactory.create(
            track=TrackName.ADOPTION,
            organization=org_2,
        )
        res = build_tracks_data(client_tracks=[track_a, track_b])
        assert len(res) == 2

    @staticmethod
    def test_build_rx_enabled_tracks(track_service):
        org_1 = factories.OrganizationFactory.create(
            name="Big Bucks Big Biz Co", rx_enabled=True
        )
        org_2 = factories.OrganizationFactory.create(
            name="Krispy Kreme", rx_enabled=False
        )
        track_a = factories.ClientTrackFactory.create(
            track=TrackName.ADOPTION,
            organization=org_1,
        )
        track_b = factories.ClientTrackFactory.create(
            track=TrackName.ADOPTION,
            organization=org_2,
        )
        res = build_tracks_data(client_tracks=[track_a, track_b])
        assert len(res) == 2
        assert res[0]["rx_enabled"] == True
        assert res[1]["rx_enabled"] == False

    @staticmethod
    def test_build_tracks_data_without_onboading_label(track_service):
        org_1 = factories.OrganizationFactory.create()
        track_a = factories.ClientTrackFactory.create(
            track=TrackName.GENERIC,
            organization=org_1,
        )
        res = build_tracks_data(client_tracks=[track_a])
        assert len(res) == 0
