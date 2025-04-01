from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Union

import ddtrace
from httpproblem import Problem
from maven.feature_flags import bool_variation

from common import stats
from common.services.api import AuthenticatedResource
from models.tracks import MemberTrack
from models.tracks.client_track import TrackModifiers
from tracks.models_v2.member_track import ActiveMemberTrack as ActiveMemberTrackV2
from tracks.models_v2.member_track import InactiveMemberTrack as InactiveMemberTrackV2
from tracks.models_v2.member_track import ScheduledMemberTrack as ScheduledMemberTrackV2
from tracks.service_v2.tracks import TrackService
from utils.log import logger

log = logger(__name__)


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


@dataclass
class MemberTrackBase:
    id: int
    name: str
    display_name: str
    scheduled_end: str

    @staticmethod
    def from_member_track(member_track: MemberTrack) -> "MemberTrackBase":
        return MemberTrackBase(
            id=member_track.id,
            name=member_track.name,
            display_name=member_track.display_name,  # type: ignore[arg-type] # Argument "display_name" to "MemberTrackBase" has incompatible type "Optional[str]"; expected "str"
            scheduled_end=member_track.get_display_scheduled_end_date().isoformat(),
        )


@dataclass
class ActiveMemberTrack(MemberTrackBase):
    current_phase: str
    organization: Organization
    dashboard: str
    track_modifiers: list[TrackModifiers] | None = None

    @staticmethod
    def from_member_track(member_track: MemberTrack) -> "ActiveMemberTrack":
        return ActiveMemberTrack(
            id=member_track.id,
            name=member_track.name,
            display_name=member_track.display_name,  # type: ignore[arg-type] # Argument "display_name" to "ActiveMemberTrack" has incompatible type "Optional[str]"; expected "str"
            scheduled_end=member_track.get_display_scheduled_end_date().isoformat(),
            current_phase=member_track.current_phase.name,
            organization=get_organization(member_track),
            dashboard=member_track.dashboard,
            track_modifiers=member_track.track_modifiers,
        )


@dataclass
class InactiveMemberTrack(MemberTrackBase):
    ended_at: str

    @staticmethod
    def from_member_track(member_track: MemberTrack) -> "InactiveMemberTrack":
        return InactiveMemberTrack(
            id=member_track.id,
            name=member_track.name,
            display_name=member_track.display_name,  # type: ignore[arg-type] # Argument "display_name" to "InactiveMemberTrack" has incompatible type "Optional[str]"; expected "str"
            scheduled_end=member_track.get_display_scheduled_end_date().isoformat(),
            ended_at=member_track.ended_at.isoformat(),  # type: ignore[union-attr] # Item "None" of "Optional[datetime]" has no attribute "isoformat"
        )


@dataclass
class ScheduledMemberTrack(MemberTrackBase):
    start_date: str

    @staticmethod
    def from_member_track(member_track: MemberTrack) -> "ScheduledMemberTrack":
        return ScheduledMemberTrack(
            id=member_track.id,
            name=member_track.name,
            display_name=member_track.display_name,  # type: ignore[arg-type] # Argument "display_name" to "ScheduledMemberTrack" has incompatible type "Optional[str]"; expected "str"
            scheduled_end=member_track.get_display_scheduled_end_date().isoformat(),
            start_date=member_track.start_date.isoformat(),
        )


@dataclass
class ActiveMemberTrackResponse:
    active_tracks: Union[List[ActiveMemberTrack], List[ActiveMemberTrackV2]]


@dataclass
class InactiveMemberTrackResponse:
    inactive_tracks: Union[List[InactiveMemberTrack], List[InactiveMemberTrackV2]]


@dataclass
class ScheduledMemberTrackResponse:
    scheduled_tracks: Union[List[ScheduledMemberTrack], List[ScheduledMemberTrackV2]]


@dataclass
class TrackOnboardingAssessmentResponse:
    onboarding_assessment_id: Optional[int]
    onboarding_assessment_slug: Optional[str]


def get_organization(member_track: MemberTrack) -> Organization:
    organization = member_track.client_track.organization

    return Organization(
        id=organization.id,
        name=organization.name,
        vertical_group_version=organization.vertical_group_version,
        bms_enabled=organization.bms_enabled,
        rx_enabled=organization.rx_enabled,
        education_only=organization.education_only,
        display_name=organization.display_name,
        benefits_url=organization.benefits_url,
    )


class ActiveTracksResource(AuthenticatedResource):
    @ddtrace.tracer.wrap()
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        active_tracks = [
            ActiveMemberTrack.from_member_track(member_track)
            for member_track in self.user.active_tracks
        ]

        track_service_v2: bool = bool_variation(
            "track-service-v2-activeTracksResource",
            default=False,
        )
        v1_response = asdict(ActiveMemberTrackResponse(active_tracks=active_tracks))

        if not track_service_v2:
            return v1_response

        track_service = TrackService()
        active_tracks_v2 = track_service.get_active_tracks(self.user.id)
        v2_response = asdict(ActiveMemberTrackResponse(active_tracks=active_tracks_v2))

        responses_match = v1_response == v2_response
        if responses_match:
            stats.increment(
                metric_name="mono.tracks.3lp.active_tracks_resource",
                pod_name=stats.PodNames.ENROLLMENTS,
                tags=["match:true"],
            )
            log.info(
                "[Track Service 3LP] ActiveTracksResource responses match",
                user_id=self.user.id,
            )
        else:
            stats.increment(
                metric_name="mono.tracks.3lp.active_tracks_resource",
                pod_name=stats.PodNames.ENROLLMENTS,
                tags=["match:false"],
            )
            log.info(
                "[Track Service 3LP] ActiveTracksResource responses DO NOT MATCH",
                user_id=self.user.id,
                v1_response=v1_response,
                v2_response=v2_response,
            )
        return v1_response


class InactiveTracksResource(AuthenticatedResource):
    @ddtrace.tracer.wrap()
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        inactive_tracks = [
            InactiveMemberTrack.from_member_track(member_track)
            for member_track in self.user.inactive_tracks
        ]

        track_service_v2: bool = bool_variation(
            "track-service-v2-InactiveTracksResource",
            default=False,
        )
        v1_response = asdict(
            InactiveMemberTrackResponse(inactive_tracks=inactive_tracks)
        )

        if not track_service_v2:
            return v1_response

        track_service = TrackService()
        inactive_tracks_v2 = track_service.get_inactive_tracks(self.user.id)
        v2_response = asdict(
            InactiveMemberTrackResponse(inactive_tracks=inactive_tracks_v2)
        )

        responses_match = v1_response == v2_response
        if responses_match:
            stats.increment(
                metric_name="mono.tracks.3lp.inactive_tracks_resource",
                pod_name=stats.PodNames.ENROLLMENTS,
                tags=["match:true"],
            )
            log.info(
                "[Track Service 3LP] InactiveTracksResource responses match",
                user_id=self.user.id,
            )
        else:
            stats.increment(
                metric_name="mono.tracks.3lp.inactive_tracks_resource",
                pod_name=stats.PodNames.ENROLLMENTS,
                tags=["match:false"],
            )
            log.info(
                "[Track Service 3LP] InactiveTracksResource responses DO NOT MATCH",
                user_id=self.user.id,
            )
        return v1_response


class ScheduledTracksResource(AuthenticatedResource):
    @ddtrace.tracer.wrap()
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        scheduled_tracks = [
            ScheduledMemberTrack.from_member_track(member_track)
            for member_track in self.user.scheduled_tracks
        ]

        track_service_v2: bool = bool_variation(
            "track-service-v-2-scheduled-tracks-resource",
            default=False,
        )
        v1_response = asdict(
            ScheduledMemberTrackResponse(scheduled_tracks=scheduled_tracks)
        )

        if not track_service_v2:
            return v1_response

        track_service = TrackService()
        scheduled_tracks_v2 = track_service.get_scheduled_tracks(self.user.id)
        v2_response = asdict(
            ScheduledMemberTrackResponse(scheduled_tracks=scheduled_tracks_v2)
        )

        responses_match = v1_response == v2_response
        if responses_match:
            stats.increment(
                metric_name="mono.tracks.3lp.scheduled_tracks_resource",
                pod_name=stats.PodNames.ENROLLMENTS,
                tags=["match:true"],
            )
            log.info(
                "[Track Service 3LP] ScheduledTracksResource responses match",
                user_id=self.user.id,
            )
        else:
            stats.increment(
                metric_name="mono.tracks.3lp.scheduled_tracks_resource",
                pod_name=stats.PodNames.ENROLLMENTS,
                tags=["match:false"],
            )
            log.info(
                "[Track Service 3LP] ScheduledTracksResource responses DO NOT MATCH",
                user_id=self.user.id,
                v1_response=v1_response,
                v2_response=v2_response,
            )
        return v1_response


class TracksOnboardingAssessmentResource(AuthenticatedResource):
    @ddtrace.tracer.wrap()
    def get(self, track_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        track = next(
            (track for track in self.user.active_tracks if track.id == track_id), None
        )

        if not track:
            raise Problem(
                404,
                detail=f"User with ID = {self.user.id} has no active track with ID = {track_id}",
            )

        lifecycle = track.onboarding_assessment_lifecycle

        return asdict(
            TrackOnboardingAssessmentResponse(
                onboarding_assessment_id=lifecycle
                and lifecycle.latest_assessment
                and lifecycle.latest_assessment.id,
                onboarding_assessment_slug=track.onboarding_assessment_slug,
            )
        )


class TrackResource(AuthenticatedResource):
    def get(self, track_id: int) -> Dict[str, Any]:
        member_track = next(
            (
                member_track
                for member_track in self.user.member_tracks
                if member_track.id == track_id
            ),
            None,
        )

        if not member_track:
            raise Problem(
                404,
                detail=f"User with ID {self.user.id} has no track with ID {track_id}.",
            )

        if member_track.active:
            response = ActiveMemberTrack.from_member_track(member_track)
        elif member_track.inactive:
            response = InactiveMemberTrack.from_member_track(member_track)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "InactiveMemberTrack", variable has type "ActiveMemberTrack")
        elif member_track.scheduled:
            response = ScheduledMemberTrack.from_member_track(member_track)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "ScheduledMemberTrack", variable has type "ActiveMemberTrack")
        else:
            raise Problem(500)

        return asdict(response)
