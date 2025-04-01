import datetime
from time import sleep

from models.tracks import TrackName
from pytests.factories import OrganizationFactory
from tracks.repository_v2.client_track import ClientTrackRepository


class TestClientTrackRepository:
    def test_get_available_member_tracks_with_eligibility(
        self, db, factories, client_track
    ):
        session = db.session
        org1 = OrganizationFactory.create()
        client_track = factories.ClientTrackFactory.create(
            track=TrackName.PREGNANCY,
            organization=org1,
            launch_date=datetime.datetime(2024, 10, 2),
            active=True,
        )
        # first active track for a user
        member_track = factories.MemberTrackFactory.create(
            name="pregnancy",
            client_track=client_track,
        )
        sleep(1)
        client_track_2 = factories.ClientTrackFactory.create(
            track=TrackName.PARENTING_AND_PEDIATRICS,
            organization=org1,
            launch_date=datetime.datetime(2023, 11, 2),
            active=True,
        )
        # second active track for the another user
        member_track_2 = factories.MemberTrackFactory.create(
            name="parenting_and_pediatrics",
            client_track=client_track_2,
        )

        client_track_ids = [client_track.id, client_track_2.id]

        result = ClientTrackRepository(session).get_all_available_tracks(
            member_track.user_id, client_track_ids, [org1.id]
        )
        assert len(result) == 1
        assert result[0].id == client_track_2.id
        assert result[0].name == TrackName.PARENTING_AND_PEDIATRICS
        assert result[0].active

        result = ClientTrackRepository(session).get_all_available_tracks(
            member_track_2.user_id, client_track_ids, [org1.id]
        )
        assert len(result) == 1
        assert result[0].id == client_track.id
        assert result[0].name == TrackName.PREGNANCY
        assert result[0].active
