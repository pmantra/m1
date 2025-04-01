from __future__ import annotations

import dataclasses
import enum
from typing import List, Optional, cast

from flask import make_response, request
from flask_babel import format_date, gettext
from flask_restful import abort
from httpproblem import Problem
from marshmallow import Schema, ValidationError, fields

import eligibility
from authn.models.user import User
from common.health_profile.health_profile_service_client import (
    HealthProfileServiceClient,
)
from common.services.api import AuthenticatedResource
from eligibility import EnterpriseVerificationService
from models.tracks import (
    ChangeReason,
    ClientTrack,
    MemberTrack,
    TrackConfig,
    TrackLifecycleError,
    TrackName,
    cancel_transition,
    finish_transition,
    initiate_transition,
)
from models.tracks.lifecycle import _should_bypass_eligibility, renew, terminate
from models.tracks.track import validate_names
from storage.connection import db
from tracks import repository
from tracks.service import TrackSelectionService
from utils.lock import prevent_concurrent_requests
from utils.log import logger
from views.schemas.common_v3 import CSVStringField

log = logger(__name__)


@dataclasses.dataclass
class Transition:
    __slots__ = ("destination", "description", "track_length")
    destination: str
    description: str
    track_length: Optional[int]


class MemberTrackCTAName(str, enum.Enum):
    CANCEL_RENEWAL = "CANCEL_RENEWAL"
    SCHEDULE_RENEWAL = "SCHEDULE_RENEWAL"


@dataclasses.dataclass
class MemberTrackCTA:
    __slots__ = ("text", "action")
    text: str
    action: MemberTrackCTAName


@dataclasses.dataclass
class ActiveMemberTrack:
    __slots__ = (
        "id",
        "name",
        "display_name",
        "display_length",
        "scheduled_end",
        "current_phase",
        "life_stage",
        "image",
        "description",
        "enrollment_requirement_description",
        "transitions",
        "track_selection_category",
        "length",
        "cta",
        "status_description",
    )
    id: int
    name: str
    display_name: str
    display_length: str
    scheduled_end: str
    current_phase: str
    life_stage: str
    image: str
    description: str
    enrollment_requirement_description: str
    transitions: List[Transition]
    track_selection_category: str
    length: int
    cta: Optional[MemberTrackCTA]
    status_description: Optional[str]


class TransitionSchema(Schema):
    destination = fields.String()
    description = fields.String()
    track_length = fields.Integer(allow_none=True)


class MemberTrackCTASchema(Schema):
    text = fields.String()
    action = fields.Method("get_action")

    def get_action(self, cta: MemberTrackCTA):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return cta.action.name


class ActiveMemberTrackSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    display_name = fields.String()
    display_length = fields.String()
    scheduled_end = fields.String()
    current_phase = fields.String()
    life_stage = fields.String()
    image = fields.String()
    description = fields.String()
    enrollment_requirement_description = fields.String()
    transitions = fields.List(fields.Nested(TransitionSchema))
    track_selection_category = fields.String()
    length = fields.Integer()
    cta = fields.Nested(MemberTrackCTASchema)
    status_description = fields.String()


class AvailableTrackSchema(Schema):
    name = fields.String()
    display_name = fields.String()
    display_length = fields.String()
    image = fields.String()
    description = fields.String()
    enrollment_requirement_description = fields.String()
    life_stage = fields.String()
    track_selection_category = fields.String()
    display_name = fields.String()
    length_in_days = fields.Integer()


class UserTracksSchema(Schema):
    active_tracks = fields.List(fields.Nested(ActiveMemberTrackSchema))
    available_tracks = fields.List(fields.Nested(AvailableTrackSchema))


def get_status_description(track: MemberTrack) -> Optional[str]:  # type: ignore[return] # Missing return statement
    formatted_end_date = format_date(
        date=track.get_display_scheduled_end_date(), format="long"
    )

    if track.is_scheduled_for_renewal():
        return gettext("views_tracks_scheduled_to_renew_on").format(
            date=formatted_end_date
        )

    if track.is_ending_soon() and track.is_eligible_for_renewal():
        return gettext("views_tracks_access_will_end_on").format(
            date=formatted_end_date
        )


def get_member_track_cta(  # type: ignore[return] # Missing return statement
    track: MemberTrack, user_is_known_to_be_eligible: bool
) -> Optional[MemberTrackCTA]:
    if track.is_scheduled_for_renewal():
        return MemberTrackCTA(
            text=gettext("views_tracks_cancel"),
            action=MemberTrackCTAName.CANCEL_RENEWAL,
        )

    if (
        user_is_known_to_be_eligible
        and track.is_ending_soon()
        and track.is_eligible_for_renewal()
    ):
        return MemberTrackCTA(
            text=gettext("views_tracks_renew_program"),
            action=MemberTrackCTAName.SCHEDULE_RENEWAL,
        )


def get_description(track: MemberTrack) -> str:
    return TrackConfig.from_name(TrackName(track.name)).description


class TracksResource(AuthenticatedResource):
    def __init__(self) -> None:
        self.schema = UserTracksSchema()
        self.track_service: TrackSelectionService = TrackSelectionService()
        self.enterprise_verification_service: EnterpriseVerificationService = (
            eligibility.get_verification_service()
        )
        super().__init__()

    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        organization_id = self.track_service.get_organization_id_for_user(
            user_id=self.user.id
        )
        user_is_known_to_be_eligible = (
            self.enterprise_verification_service.is_user_known_to_be_eligible_for_org(
                user_id=self.user.id,
                organization_id=organization_id,
                timeout=2,
            )
        )

        active_tracks = [
            ActiveMemberTrack(
                id=member_track.id,
                name=member_track.name,
                display_name=member_track.display_name,
                display_length=member_track.display_length,
                scheduled_end=member_track.get_display_scheduled_end_date().isoformat(),
                current_phase=member_track.current_phase.name,
                life_stage=member_track.life_stage,
                image=member_track.image,
                description=get_description(member_track),
                enrollment_requirement_description=member_track.enrollment_requirement_description,
                transitions=self._get_transitions(
                    member_track, user_is_known_to_be_eligible
                ),
                track_selection_category=member_track.track_selection_category,
                length=member_track.length().days,
                cta=get_member_track_cta(member_track, user_is_known_to_be_eligible),
                status_description=get_status_description(member_track),
            )
            for member_track in self.user.active_tracks
        ]

        user_available_tracks: List[TrackConfig] = (
            self._get_enrollable_tracks() if user_is_known_to_be_eligible else []
        )

        json = self.schema.dump(
            {
                "active_tracks": active_tracks,
                "available_tracks": user_available_tracks,
            }
        )
        return make_response(json, 200)

    def _get_transitions(
        self, track: MemberTrack, user_is_known_to_be_eligible: bool
    ) -> List[Transition]:
        tracks_repo: repository.TracksRepository = repository.TracksRepository()
        user_id = track.user_id
        org_id: int = track.client_track.organization_id

        constructed_transitions = []
        available_client_tracks = self._get_available_client_tracks()
        all_client_tracks = (
            tracks_repo.get_all_client_tracks(user_id=user_id, organization_id=org_id)
            if user_id
            else []
        )

        for future_track in track.transitions:
            # try to find the client track in the list of tracks the user is eligible for
            future_client_track = next(
                (t for t in available_client_tracks if t.name == future_track.name),
                None,
            )
            # if the user is not eligible for the transition target track and this is an allowlisted transition,
            # find the client track from the list of ALL client tracks with that org
            if not future_client_track:
                future_client_track = next(
                    (
                        t
                        for t in all_client_tracks
                        if t.name == future_track.name
                        and _should_bypass_eligibility(track.name, future_track.name)
                    ),
                    None,
                )
            if not future_client_track:
                continue
            if (
                not _should_bypass_eligibility(track.name, future_track.name)
                and not user_is_known_to_be_eligible
            ):
                continue
            constructed_transitions.append(
                Transition(
                    destination=future_track.name,
                    description=future_track.display_description,
                    track_length=future_client_track.length_in_days,
                )
            )
        return constructed_transitions

    def _get_available_client_tracks(self) -> List[ClientTrack]:
        available_client_tracks: List[ClientTrack] = []
        organization_id = self.track_service.get_organization_id_for_user(
            user_id=self.user.id
        )

        if organization_id is not None:
            available_client_tracks = self.track_service.get_available_tracks_for_org(
                user_id=self.user.id, organization_id=organization_id
            )

        return available_client_tracks

    def _get_enrollable_tracks(self) -> List[TrackConfig]:
        available_tracks: List[TrackConfig] = []
        organization_id = self.track_service.get_organization_id_for_user(
            user_id=self.user.id
        )

        if organization_id is not None:
            available_client_tracks = self.track_service.get_enrollable_tracks_for_org(
                user_id=self.user.id, organization_id=organization_id
            )
            available_tracks = [
                TrackConfig.from_name(t.name) for t in available_client_tracks
            ]
            # Filter by tracks that are enabled for onboarding and sort by onboarding order
            available_tracks = [
                t for t in available_tracks if t.onboarding.order is not None
            ]
            available_tracks = sorted(
                available_tracks, key=lambda t: cast(int, t.onboarding.order)
            )

        return available_tracks


def get_user_active_track(user: User, track_id: int) -> MemberTrack:
    """
    Find the user's track with the given ID. Raises HTTProblem if not found in user's
    active_tracks.
    """
    # TODO: maybe use query(Track).get(track_id) and validate .user_id and .active?
    #  I'm not doing that now to avoid repeating logic here and user.active_tracks
    track = next((track for track in user.active_tracks if track.id == track_id), None)
    if not track:
        raise Problem(404, detail=f"Track with ID = {track_id} not found")
    return track


class StartTransitionInputSchema(Schema):
    destination = fields.String(required=True)


class TracksStartTransitionResource(AuthenticatedResource):
    schema = StartTransitionInputSchema()

    def post(self, track_id: int) -> dict:
        args = self.schema.load(request.json if request.is_json else {})
        destination_name = args["destination"]
        track = get_user_active_track(self.user, track_id)
        if track.name == "fertility" and destination_name == "pregnancy":
            try:
                hps_client = HealthProfileServiceClient(self.user)
                hps_client.post_fertility_status_history("successful_pregnancy")
            except Exception as e:
                log.exception(
                    "Exception updating user's fertility status to successful_pregnancy",
                    error=e,
                )

        try:
            destination = TrackName(destination_name)
        except ValueError:
            raise Problem(400, detail=f"No track with name = {destination_name} found")

        try:
            initiate_transition(
                track=track,
                target=destination,
                change_reason=ChangeReason.API_INITIATE_TRANSITION,
            )
        except TrackLifecycleError as e:
            log.exception("Exception trying to start a transition", error=e)
            if len(e.args) > 1:
                raise Problem(400, detail=str(e.args[0]), message=str(e.args[1]))
            else:
                raise Problem(500, detail=str(e))
        db.session.commit()
        return {"success": True}


class FinishTransitionSchema(Schema):
    success = fields.Boolean()
    track_id = fields.Integer()


class TracksFinishTransitionResource(AuthenticatedResource):
    schema = FinishTransitionSchema()

    @prevent_concurrent_requests(lambda self, track_id: f"transition:{self.user.id}")
    def post(self, track_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            track = get_user_active_track(self.user, track_id)
            new_track = finish_transition(
                track=track, change_reason=ChangeReason.API_FINISH_TRANSITION
            )
            db.session.commit()
        except TrackLifecycleError as e:
            log.warn("Exception trying to finish a transition", error=e)
            raise Problem(500, detail=str(e))
        return self.schema.dump({"success": True, "track_id": new_track.id})


class TracksCancelTransitionResource(AuthenticatedResource):
    def post(self, track_id: int) -> dict:
        track = get_user_active_track(self.user, track_id)
        try:
            cancel_transition(
                track=track, change_reason=ChangeReason.API_CANCEL_TRANSITION
            )
        except TrackLifecycleError as e:
            log.warn("Exception trying to cancel a transition", error=e)
            raise Problem(400, detail=str(e))
        db.session.commit()
        return {"success": True}


class TrackRenewalSchema(Schema):
    success = fields.Boolean()
    track_id = fields.Integer()
    scheduled_end_date = fields.Date()


class TracksRenewalResource(AuthenticatedResource):
    schema = TrackRenewalSchema()

    @prevent_concurrent_requests(lambda self, track_id: f"renewal:{self.user.id}")
    def post(self, track_id: int) -> tuple[dict, int]:
        track = get_user_active_track(self.user, track_id)
        try:
            new_track = renew(track=track, change_reason=ChangeReason.API_RENEW)
        except TrackLifecycleError as e:
            log.warn("Exception trying to renew a track", error=e)
            raise Problem(400, detail=str(e))

        db.session.commit()

        return (
            self.schema.dump(
                {
                    "success": True,
                    "track_id": new_track.id,
                    "scheduled_end_date": new_track.get_scheduled_end_date(),
                }
            ),
            201,
        )


class ScheduledTrackCancellationResource(AuthenticatedResource):
    @prevent_concurrent_requests(
        lambda self, track_id: f"scheduled_track_cancellation:{self.user.id}"
    )
    def delete(self, track_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        track = get_user_active_track(self.user, track_id)
        try:
            scheduled_tracks = self.user.scheduled_tracks
            scheduled_track = next(
                (
                    st
                    for st in scheduled_tracks
                    if st.previous_member_track_id == track.id
                ),
                None,
            )

            if scheduled_track:
                terminate(
                    track=scheduled_track,
                    change_reason=ChangeReason.API_SCHEDULED_CANCEL_TERMINATE,
                )
            else:
                log.warn(
                    "Could not find scheduled track associated with given track",
                    track_id=track_id,
                )
                raise Problem(
                    404,
                    detail=f"Could not find scheduled track associated with given track (<Track ID:{track_id}>",
                )

        except TrackLifecycleError as e:
            log.warn("Exception trying to terminate a scheduled track", error=e)
            raise Problem(400, detail=str(e))

        db.session.commit()

        return None, 204


class TracksIntroAppointmentEligibilityArgsSchema(Schema):
    tracks = CSVStringField(required=True, validate=validate_names)


class TracksIntroAppointmentEligibilityResponseSchema(Schema):
    eligible_for_intro_appointment = fields.Boolean()


class TracksIntroAppointmentEligibilityResource(AuthenticatedResource):
    def __init__(self) -> None:
        self.track_service: TrackSelectionService = TrackSelectionService()
        self.request_schema = TracksIntroAppointmentEligibilityArgsSchema()
        self.response_schema = TracksIntroAppointmentEligibilityResponseSchema()
        super().__init__()

    def get(self) -> TracksIntroAppointmentEligibilityResponseSchema:
        try:
            args = self.request_schema.load(request.args)
        except ValidationError as e:
            log.warn(
                "Exception validating TracksIntroAppointmentEligibilityResource args",
                exception=e.messages,
            )
            abort(400, message=e.messages)

        log.info(
            "Starting get request for TracksIntroAppointmentEligibilityResource",
            tracks=args["tracks"],
        )

        try:
            any_eligible = self.track_service.any_eligible_for_intro_appointment(
                track_names=args["tracks"]
            )

            log.info(
                "Successfully computed if any track is eligible for intro appointment",
                tracks=args["tracks"],
                any_eligible=any_eligible,
            )
            return self.response_schema.dump(
                {"eligible_for_intro_appointment": any_eligible}
            )

        except Exception as e:
            log.warning(
                "Exception computing if any track is eligible for intro appointment",
                exception=e.messages,  # type: ignore[attr-defined] # "Exception" has no attribute "messages"
            )
            return (  # type: ignore[return-value] # Incompatible return value type (got "Tuple[Dict[str, str], int]", expected "TracksIntroAppointmentEligibilityResponseSchema")
                {
                    "error": f"Exception checking if tracks eligible for intro appointment. {str(e.messages)}"  # type: ignore[attr-defined] # "Exception" has no attribute "messages"
                },
                500,
            )
