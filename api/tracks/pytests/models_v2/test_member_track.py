import datetime

from models.tracks.track import TrackName
from tracks.models_v2.member_track import (
    ActiveMemberTrack,
    InactiveMemberTrack,
    Organization,
    ScheduledMemberTrack,
)
from tracks.repository_v2.member_track import (
    ActiveMemberTrackData,
    InactiveMemberTrackData,
    ScheduledMemberTrackData,
)


def test_active_member_track():
    anchor_dates = {
        "yesterday": (datetime.date.today() - datetime.timedelta(days=1), "week-1"),
        "one_week_ago": (datetime.date.today() - datetime.timedelta(weeks=1), "week-2"),
        "tomorrow": (datetime.date.today() + datetime.timedelta(days=1), "week-1"),
    }
    tracks = [
        {
            "name": TrackName.PREGNANCY,
            "length": 294 + 168,
            "grace_period": 0,
            "display_name": "Pregnancy",
        },
        {
            "name": TrackName.PARENTING_AND_PEDIATRICS,
            "length": 364,
            "grace_period": 14,
            "display_name": "Parenting & Pediatrics",
        },
    ]

    for anchor_key, (anchor_date, expected_phase) in anchor_dates.items():
        for track_info in tracks:
            length = track_info["length"]
            grace_period = track_info["grace_period"]
            scheduled_end = anchor_date + datetime.timedelta(days=length + grace_period)

            track_data = ActiveMemberTrackData(
                id=1,
                name=track_info["name"],
                anchor_date=anchor_date,
                start_date=anchor_date,
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
            )
            track = ActiveMemberTrack.from_member_track_data(track_data)

            expected_track = ActiveMemberTrack(
                id=1,
                name=track_info["name"],
                display_name=track_info["display_name"],
                scheduled_end=scheduled_end.isoformat(),
                current_phase=expected_phase,  # The expected current phase based on the anchor date
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

            assert (
                track == expected_track
            ), f"Failed for track {track_info['name']} with anchor date: {anchor_key}"


def test_inactive_member_track_pregancy():
    track_data = InactiveMemberTrackData(
        id=123,
        name=TrackName.PREGNANCY,
        anchor_date=datetime.datetime(2024, 1, 1),
        ended_at=datetime.datetime(2024, 9, 1, 12, 31, 7),
        activated_at=datetime.datetime(2024, 2, 2, 1, 42, 17),
        length_in_days=294,
    )
    track = InactiveMemberTrack.from_member_track_data(track_data)
    expected_track = InactiveMemberTrack(
        id=123,
        name=TrackName.PREGNANCY,
        display_name="Pregnancy",
        scheduled_end="2025-04-07T00:00:00",
        ended_at="2024-09-01T12:31:07",
    )

    assert track == expected_track


def test_null_track_length():
    track_data = InactiveMemberTrackData(
        id=123,
        name=TrackName.POSTPARTUM,
        anchor_date=datetime.datetime(2024, 1, 1),
        ended_at=datetime.datetime(2024, 9, 1, 12, 31, 7),
        activated_at=datetime.datetime(2024, 2, 2, 1, 42, 17),
        length_in_days=None,
    )
    track = InactiveMemberTrack.from_member_track_data(track_data)
    expected_track = InactiveMemberTrack(
        id=123,
        name=TrackName.POSTPARTUM,
        display_name="Postpartum",
        scheduled_end="2024-07-01T00:00:00",
        ended_at="2024-09-01T12:31:07",
    )

    assert track == expected_track


def test_inactive_member_track_menopause():
    track_data = InactiveMemberTrackData(
        id=123,
        name=TrackName.MENOPAUSE,
        anchor_date=datetime.datetime(2024, 1, 1),
        ended_at=datetime.datetime(2024, 9, 1, 12, 31, 7),
        activated_at=datetime.datetime(2024, 2, 2, 1, 42, 17),
        length_in_days=294,
    )
    track = InactiveMemberTrack.from_member_track_data(track_data)
    expected_track = InactiveMemberTrack(
        id=123,
        name=TrackName.MENOPAUSE,
        display_name="Menopause & Midlife Health",
        scheduled_end="2024-10-21T00:00:00",
        ended_at="2024-09-01T12:31:07",
    )

    assert track == expected_track


def test_scheduled_member_track():
    track_data = ScheduledMemberTrackData(
        id=123,
        name=TrackName.PREGNANCY,
        anchor_date=datetime.date.today(),
        length_in_days=294,
        start_date=datetime.date.today() + datetime.timedelta(weeks=2),
    )
    track = ScheduledMemberTrack.from_member_track_data(track_data)
    expected_track = ScheduledMemberTrack(
        id=123,
        name=TrackName.PREGNANCY,
        display_name="Pregnancy",
        scheduled_end=(
            datetime.date.today() + datetime.timedelta(days=462)
        ).isoformat(),
        start_date=(datetime.date.today() + datetime.timedelta(weeks=2)).isoformat(),
    )
    assert track == expected_track
