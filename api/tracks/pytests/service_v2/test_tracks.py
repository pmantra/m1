import datetime

# from unittest import mock, patch
from unittest.mock import patch

from models.tracks.track import TrackName
from tracks.models_v2.member_track import (
    ActiveMemberTrack,
    InactiveMemberTrack,
    Organization,
)
from tracks.repository_v2.member_track import (
    ActiveMemberTrackData,
    EnrolledMemberTrackData,
    InactiveMemberTrackData,
    MemberTrackRepository,
)
from tracks.service_v2.tracks import TrackService


def test_get_active_tracks():
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    length = 294 + 168
    scheduled_end = yesterday + datetime.timedelta(days=length)
    track_data = [
        ActiveMemberTrackData(
            id=1,
            name=TrackName.PREGNANCY,
            anchor_date=yesterday,
            start_date=yesterday,
            activated_at=datetime.datetime.utcnow() - datetime.timedelta(days=1),
            length_in_days=length,
            org_id=1,
            org_name="org_name",
            org_vertical_group_version="1.0",
            org_bms_enabled=True,
            org_rx_enabled=True,
            org_education_only=True,
            org_display_name="org_name",
            track_modifiers=[],
            org_benefits_url="testurl.com",
        ),
    ]
    expected_tracks = [
        ActiveMemberTrack(
            id=1,
            name=TrackName.PREGNANCY,
            display_name="Pregnancy",
            scheduled_end=scheduled_end.isoformat(),
            current_phase="week-1",
            organization=Organization(
                id=1,
                name="org_name",
                vertical_group_version="1.0",
                bms_enabled=True,
                rx_enabled=True,
                education_only=True,
                display_name="org_name",
                benefits_url="testurl.com",
            ),
            dashboard="dashboard2020",
            track_modifiers=[],
        )
    ]
    with patch.object(
        MemberTrackRepository, "get_active_member_tracks", return_value=track_data
    ):
        assert TrackService().get_active_tracks(user_id=123) == expected_tracks


def test_get_inactive_tracks():
    track_datas = [
        InactiveMemberTrackData(
            id=1,
            name=TrackName.PREGNANCY,
            anchor_date=datetime.datetime(2020, 1, 1),
            ended_at=datetime.datetime(2021, 1, 1),
            activated_at=datetime.datetime(2020, 6, 1),
            length_in_days=264,
        ),
    ]
    expected_tracks = [
        InactiveMemberTrack(
            id=1,
            name=TrackName.PREGNANCY,
            display_name="Pregnancy",
            scheduled_end="2021-04-07T00:00:00",
            ended_at="2021-01-01T00:00:00",
        )
    ]
    with patch.object(
        MemberTrackRepository, "get_inactive_member_tracks", return_value=track_datas
    ):
        assert TrackService().get_inactive_tracks(user_id=1) == expected_tracks


def test_get_organization_id_for_user():
    user_id = 123
    org_id = 192
    track_data = [
        EnrolledMemberTrackData(
            id=108,
            name="pregnancy",
            anchor_date=datetime.date(2024, 10, 29),
            length_in_days=365,
            activated_at=datetime.datetime(2024, 10, 29, 5, 58, 57),
            start_date=datetime.date(2024, 10, 29),
            org_id=org_id,
            org_name="Jacobs and Sons",
            org_display_name="org_name",
            is_active=True,
        )
    ]

    # Mocking the repository method
    with patch.object(
        MemberTrackRepository, "get_all_enrolled_tracks", return_value=track_data
    ):
        assert TrackService().get_organization_id_for_user(user_id) == org_id


class TestTrackService:
    def test_get_organization_id_for_user(self, factories):
        user = factories.DefaultUserFactory.create()
        org = factories.OrganizationFactory.create()

        # Test getting inactive track
        factories.MemberTrackFactory.create(
            user=user,
            ended_at=datetime.datetime(2023, 1, 1),
            client_track=factories.ClientTrackFactory(
                organization=org,
            ),
        )
        assert TrackService().get_organization_id_for_user(user.id) == org.id

        # Test getting active track
        another_org = factories.OrganizationFactory.create()

        factories.MemberTrackFactory.create(
            user=user,
            client_track=factories.ClientTrackFactory(
                organization=another_org,
            ),
        )
        assert TrackService().get_organization_id_for_user(user.id) == another_org.id
