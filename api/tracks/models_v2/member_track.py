from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from models.tracks.client_track import TrackModifiers
from models.tracks.track import TrackName, get_track
from tracks.repository_v2.member_track import (
    ActiveMemberTrackData,
    BaseMemberTrackData,
    InactiveMemberTrackData,
    ScheduledMemberTrackData,
)


# Copied from tracks/resources/member_tracks.py, but no ORM helpers
@dataclass
class Organization:
    id: int
    name: str
    vertical_group_version: str
    bms_enabled: bool
    rx_enabled: bool
    education_only: bool
    display_name: str
    benefits_url: str


# Copied from tracks/resources/member_tracks.py, but no ORM helpers
@dataclass
class MemberTrackBase:
    id: int
    name: str
    display_name: Optional[str]
    scheduled_end: str


class PhaseNamePrefix(str, enum.Enum):
    WEEKLY: str = "week"
    STATIC: str = "static"
    END: str = "end"


def calculate_scheduled_end(member_track: BaseMemberTrackData) -> date:
    config = get_track(member_track.name)
    if member_track.name in [TrackName.PREGNANCY, TrackName.PARTNER_PREGNANT]:
        return (
            member_track.anchor_date
            + config.length
            + config.grace_period
            + get_track(TrackName.POSTPARTUM).length
        )
    else:
        length = (
            timedelta(days=member_track.length_in_days)
            if member_track.length_in_days
            else config.length
        )
        return member_track.anchor_date + length + config.grace_period


# Copied from tracks/resources/member_tracks.py, but no ORM helpers
@dataclass
class ActiveMemberTrack(MemberTrackBase):
    current_phase: str
    organization: Organization
    dashboard: str
    track_modifiers: list[TrackModifiers] | None = None

    @staticmethod
    def from_member_track_data(
        member_track: ActiveMemberTrackData,
    ) -> "ActiveMemberTrack":
        config = get_track(member_track.name)

        if member_track.name in {
            TrackName.BREAST_MILK_SHIPPING,
            TrackName.GENERIC,
            TrackName.PREGNANCY_OPTIONS,
            TrackName.SPONSORED,
        }:
            cur_phase_name = PhaseNamePrefix.STATIC.value

        else:
            track_start_date = member_track.anchor_date
            today = date.today()
            interval = int((today - track_start_date).days / 7) + 1
            if member_track.name in (
                TrackName.POSTPARTUM,
                TrackName.PARTNER_NEWPARENT,
            ):
                cur_phase_name = f"{PhaseNamePrefix.WEEKLY}-{interval + 39}"
            elif member_track.name in (TrackName.PREGNANCY, TrackName.PARTNER_PREGNANT):
                max_interval = int(config.length.days / 7)
                if interval > max_interval:
                    interval = max_interval
                cur_phase_name = f"{PhaseNamePrefix.WEEKLY}-{interval}"
            elif interval > config.length / timedelta(weeks=1):
                cur_phase_name = PhaseNamePrefix.END.value
            else:
                cur_phase_name = f"{PhaseNamePrefix.WEEKLY}-{interval}"

        org = Organization(
            id=member_track.org_id,
            name=member_track.org_name,
            vertical_group_version=member_track.org_vertical_group_version,
            bms_enabled=bool(member_track.org_bms_enabled),
            rx_enabled=bool(member_track.org_rx_enabled),
            education_only=bool(member_track.org_education_only),
            display_name=member_track.org_display_name,
            benefits_url=member_track.org_benefits_url,
        )
        return ActiveMemberTrack(
            id=member_track.id,
            name=TrackName(member_track.name),
            display_name=config.display_name,
            scheduled_end=calculate_scheduled_end(member_track).isoformat(),
            current_phase=cur_phase_name,
            organization=org,
            dashboard="dashboard2020",
            track_modifiers=member_track.track_modifiers,
        )


# Copied from tracks/resources/member_tracks.py, but no ORM helpers
@dataclass
class InactiveMemberTrack(MemberTrackBase):
    ended_at: str

    @staticmethod
    def from_member_track_data(
        member_track: InactiveMemberTrackData,
    ) -> "InactiveMemberTrack":
        config = get_track(member_track.name)
        display_name = config.display_name
        return InactiveMemberTrack(
            id=member_track.id,
            name=member_track.name,
            display_name=str(display_name),
            scheduled_end=calculate_scheduled_end(member_track).isoformat(),
            ended_at=member_track.ended_at.isoformat(),
        )


# Copied from tracks/resources/member_tracks.py, but no ORM helpers
@dataclass
class ScheduledMemberTrack(MemberTrackBase):
    start_date: str

    @staticmethod
    def from_member_track_data(
        member_track: ScheduledMemberTrackData,
    ) -> "ScheduledMemberTrack":
        config = get_track(member_track.name)
        display_name = config.display_name
        return ScheduledMemberTrack(
            id=member_track.id,
            name=member_track.name,
            display_name=str(display_name),
            scheduled_end=calculate_scheduled_end(member_track).isoformat(),
            start_date=member_track.start_date.isoformat(),
        )
