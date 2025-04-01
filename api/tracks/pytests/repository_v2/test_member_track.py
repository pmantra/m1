import datetime
from time import sleep

from models.tracks import TrackName
from models.tracks.client_track import TrackModifiers
from tracks.repository_v2.member_track import (
    EnrolledMemberTrackData,
    MemberTrackRepository,
)


class TestMemberTrackRepository:
    def test_get_active_member_tracks(self, db, factories, client_track):
        session = db.session
        client_track = factories.ClientTrackFactory.create(
            track_modifiers="doula_only", track=TrackName.PREGNANCY
        )
        # first active track for a user
        first_active_track = factories.MemberTrackFactory.create(
            name="pregnancy", client_track=client_track
        )
        sleep(1)
        client_track = factories.ClientTrackFactory.create(track_modifiers="")
        # second active track for the same user
        second_active_track = factories.MemberTrackFactory.create(
            name="parenting_and_pediatrics",
            user=first_active_track.user,
            client_track=client_track,
        )
        result = MemberTrackRepository(session).get_active_member_tracks(
            first_active_track.user_id
        )

        assert len(result) == 2
        assert result[0].id == first_active_track.id
        assert result[0].track_modifiers == [TrackModifiers.DOULA_ONLY]
        assert result[1].id == second_active_track.id
        assert result[1].track_modifiers == []

    def test_get_inactive_member_tracks(self, db, factories):
        session = db.session
        # active track for target user
        inactive_track = factories.MemberTrackFactory.create(
            ended_at=datetime.datetime(2020, 1, 1)
        )
        # active track for same user
        factories.MemberTrackFactory.create(user=inactive_track.user)
        # inactive track for different user
        factories.MemberTrackFactory.create(ended_at=datetime.datetime(2020, 1, 1))

        result = MemberTrackRepository(session).get_inactive_member_tracks(
            inactive_track.user_id
        )

        assert len(result) == 1
        assert result[0].id == inactive_track.id

    def test_get_scheduled_member_tracks(self, db, default_user, factories):
        session = db.session
        scheduled_track = factories.MemberTrackFactory.create(
            user=default_user,
            start_date=datetime.date.today() + datetime.timedelta(weeks=2),
            activated_at=None,
            ended_at=None,
        )

        result = MemberTrackRepository(session).get_scheduled_member_tracks(
            default_user.id
        )

        assert len(result) == 1
        assert result[0].id == scheduled_track.id

    def test_get_all_enrolled_tracks(self, db, factories):
        session = db.session
        active_track = factories.MemberTrackFactory.create(
            created_at=datetime.datetime(2023, 10, 1)
        )
        inactive_track = factories.MemberTrackFactory.create(
            created_at=datetime.datetime(2023, 10, 2),
            user=active_track.user,
            ended_at=datetime.datetime(2024, 1, 1),
        )
        active_track_2 = factories.MemberTrackFactory.create(
            created_at=datetime.datetime(2023, 10, 3), user=active_track.user
        )

        # Test getting active tracks
        active_results = MemberTrackRepository(session).get_all_enrolled_tracks(
            active_track.user_id, active_only=True
        )
        assert len(active_results) == 2
        assert isinstance(active_results[0], EnrolledMemberTrackData)
        assert active_results[0].id == active_track.id

        # Test getting all tracks
        all_results = MemberTrackRepository(session).get_all_enrolled_tracks(
            active_track.user_id, active_only=False
        )
        assert len(all_results) == 3
        assert isinstance(all_results[2], EnrolledMemberTrackData)
        assert isinstance(all_results[1], EnrolledMemberTrackData)
        assert isinstance(all_results[0], EnrolledMemberTrackData)
        assert all_results[0].id == active_track.id
        assert all_results[1].id == inactive_track.id
        assert all_results[2].id == active_track_2.id
