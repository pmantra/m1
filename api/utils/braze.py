from __future__ import annotations

import datetime
import enum
from collections import Collection  # type: ignore
from dataclasses import dataclass
from enum import Enum, unique
from functools import wraps
from inspect import signature
from typing import Any, Callable, List, Optional
from warnings import warn

import requests
import yaml
from babel import Locale
from sqlalchemy.orm import joinedload

from appointments.models.appointment import Appointment
from appointments.models.constants import APPOINTMENT_STATES
from appointments.models.schedule import Schedule
from assessments.utils.assessment_exporter import (
    AssessmentExporter,
    AssessmentExportTopic,
)
from authn.models.user import User
from braze import client, format_dt
from braze.client import constants
from direct_payment.clinic.models.user import FertilityClinicUserProfile
from direct_payment.clinic.repository.clinic_location import (
    FertilityClinicLocationRepository,
)
from direct_payment.clinic.repository.user import FertilityClinicUserRepository
from geography.repository import CountryRepository, SubdivisionRepository
from health.services.health_profile_service import HealthProfileService
from messaging.models.messaging import Message
from models.enterprise import Invite, InviteType, OnboardingState, Organization
from models.products import Product, Purposes
from models.profiles import PractitionerProfile
from models.tracks import MemberTrack, TrackName
from models.tracks.client_track import TrackModifiers
from models.verticals_and_specialties import is_cx_vertical_name
from storage.connection import db
from utils.cache import redis_client
from utils.log import logger
from utils.rotatable_token import BRAZE_CONNECTED_EVENT_TOKEN
from wallet.models.wallet_user_invite import WalletUserInvite

log = logger(__name__)

LAST_ORGANIZATION_OFFERS_PNP = "last_organization_offers_pnp"

_BRAZE_USER_ATTR_FIELDS = frozenset(
    (
        "email",
        "first_name",
        "last_name",
        "Registration date",
        "user_flags",
        "fertility_treatment_status",
        "country",
        "state",
        "Organization",
        "Intro appointment status",
        "Intro appointment completed at",
        "current_track",
        "track_started",
        "extended_track",
        "current_phase",
        "current_phase_pnp",  # for pnp track, should only refer to this new field instead of current_phase
        "phase_started",
        "phase_auto_transitioned",
        "Care coordinator first name",
        "Care coordinator last name",
        "Care coordinator id",
        "Care coordinator photo url",
        "install_source",
        "last_track",
        "last_track_ended_date",
        "braze_pause_message_1",
        "braze_pause_message_2",
        "braze_pause_message_3",
        "braze_pause_message_4",
        "braze_pause_message_5",
        "braze_pause_message_6",
        "braze_pause_message_7",
        "braze_pause_message_8",
        "braze_pause_message_9",
        "braze_pause_message_10",
        "next_scheduled_provider_appointment_date",
        "most_recent_completed_provider_appointment_date",
        "member_last_messaged_with_CA_date",
        "CA_last_messaged_with_member_date",
        "assessment_status",
        "ca_appointments_completed_count",
        "non_ca_appointments_completed_count",
        "birth_planning_appointment_scheduled",
        "is_practitioner",
        "verticals",
        "first_time_mom",
        "track_length_in_days",
        "email_click_tracking_disabled",
        "pnp_available",
        "pregnancy_available",
        "pnp_track_started",
        LAST_ORGANIZATION_OFFERS_PNP,
        "is_doula_only",
    )
)

REQUEST_TIMEOUT = 15
UNSUBSCRIBES_ENDPOINT_LIMIT = 500


class SupportedMethods(str, enum.Enum):
    GET = "GET"
    POST = "POST"


@dataclass(frozen=True)
class BrazePractitioner:
    __slots__ = (
        "email",
        "first_name",
        "last_name",
        "phone_number",
        "external_id",
        "certified_states",
        "email_click_tracking_disabled",
    )
    email: str
    first_name: str
    last_name: str
    phone_number: str
    external_id: str
    certified_states: List[str]
    email_click_tracking_disabled: bool


@dataclass(frozen=True)
class BrazeFertilityClinicUser:
    # we want to try to not send and build the attributes that have nothing attached
    """
    A few attributes are optional because of the workflow.

    Users are created first, and upon registration a fertility clinic user profile is later created.
    """
    email: str
    external_id: str
    first_name: str
    last_name: str
    user_role: Optional[str] = None
    phone_number: Optional[str] = None
    clinic_location_country: Optional[List[str]] = None
    clinic_location_name: Optional[List[str]] = None
    clinic_location_state: Optional[List[str]] = None
    clinic_name: Optional[List[str]] = None


def track_user(
    user: User, email: str | None = None, email_subscribe: bool | None = None
) -> None:
    if fertility_clinic_user(user.id):
        braze_app = "fertility clinic"
        assert (
            constants.BRAZE_FERTILITY_CLINIC_PORTAL_API_KEY is not None
        ), "BRAZE_FERTILITY_CLINIC_PORTAL_API_KEY must not be None"
        braze_client = client.BrazeClient(
            api_key=constants.BRAZE_FERTILITY_CLINIC_PORTAL_API_KEY
        )
        braze_user_attributes = braze_fertility_clinic_user_attributes(user)
    else:
        braze_app = "default"
        braze_client = client.BrazeClient()
        braze_user_attributes = build_user_attrs(user, email, email_subscribe)

    braze_client.track_user(user_attributes=braze_user_attributes)
    log.info(f"Tracking {user} on Braze in the {braze_app} app")


def track_email_from_invite(
    invite: Invite,
    track: str,
    alternate_verification: str | None = None,
) -> None:
    log.info("Tracking email from invite", invite=invite, track=track)
    attrs = {
        "email": invite.email,
        "first_name": invite.name,
        "invite_id": invite.id,
        "invite_time": format_dt(invite.created_at),
        "account_claimed": invite.claimed,
        "invite_from_track": track,
    }
    if alternate_verification is not None:
        attrs["invite_alternate_verification"] = alternate_verification

    braze_client = client.BrazeClient()
    braze_user_attributes = client.BrazeUserAttributes(
        external_id=invite.id,
        attributes=attrs,
    )
    braze_client.track_user(user_attributes=braze_user_attributes)


def track_fileless_email_from_invite(invite: Invite) -> None:
    attrs = {
        "email": invite.email,
        "first_name": invite.name,
        "invite_id": invite.id,
        "invite_time": format_dt(invite.created_at),
        "account_claimed": invite.claimed,
        "is_employee": invite.type == InviteType.FILELESS_EMPLOYEE,
        "type": "FILELESS",
    }

    braze_client = client.BrazeClient()
    braze_user_attributes = client.BrazeUserAttributes(
        external_id=invite.id,
        attributes=attrs,
    )
    braze_client.track_user(user_attributes=braze_user_attributes)


def track_user_locale(user: User, locale_str: str) -> None:
    language = Locale.parse(locale_str, "-").language
    attrs = {
        "language": language,
    }
    braze_client = client.BrazeClient()
    braze_user_attributes = client.BrazeUserAttributes(
        external_id=user.esp_id,
        attributes=attrs,
    )
    braze_client.track_user(user_attributes=braze_user_attributes)


def fileless_invite_requested(invite: Invite) -> None:
    braze_client = client.BrazeClient()
    braze_event = client.BrazeEvent(
        external_id=invite.id,
        name="fileless_eligibility_email",
    )
    braze_client.track_user(events=[braze_event])


def request_and_track_fileless_invite(invite: Invite) -> None:
    attrs = {
        "email": invite.email,
        "first_name": invite.name,
        "invite_id": invite.id,
        "invite_time": format_dt(invite.created_at),
        "account_claimed": invite.claimed,
        "is_employee": invite.type == InviteType.FILELESS_EMPLOYEE,
        "type": "FILELESS",
    }
    braze_client = client.BrazeClient()
    braze_user_attributes = client.BrazeUserAttributes(
        external_id=invite.id,
        attributes=attrs,
    )
    braze_event = client.BrazeEvent(
        external_id=invite.id,
        name="fileless_eligibility_email",
    )
    braze_client.track_user(
        user_attributes=braze_user_attributes,
        events=[braze_event],
    )


def braze_practitioner_attributes(user: User) -> client.BrazeUserAttributes:
    return client.BrazeUserAttributes(
        external_id=user.esp_id,
        attributes=dict(
            first_name=user.first_name,
            last_name=user.last_name,
            certified_states=_get_certified_states(user),
            phone_number=user.practitioner_profile.phone_number,
            email=user.email,
            email_click_tracking_disabled=False,
        ),
    )


def sync_practitioners(
    users: List[User],
) -> None:
    if not isinstance(users, Collection):
        users = list(users)

    if not constants.BRAZE_MPRACTICE_API_KEY:
        log.warning(
            "No Braze mPractice API Key is configured for this environment."
            " Defaulting to `BRAZE_API_KEY`"
        )
    assert (
        constants.BRAZE_MPRACTICE_API_KEY is not None
    ), "BRAZE_MPRACTICE_API_KEY must not be None"
    braze_client = client.BrazeClient(api_key=constants.BRAZE_MPRACTICE_API_KEY)
    braze_client.track_users(
        user_attributes=[braze_practitioner_attributes(u) for u in users]
    )


def delete_practitioners(
    users: List[User], external_id_attribute: str = "esp_id"
) -> None:
    external_ids = [getattr(u, external_id_attribute) for u in users]
    if not constants.BRAZE_MPRACTICE_API_KEY:
        raise EnvironmentError(
            "To run the `delete-practitioners` command,"
            " you must specify an environment variable for `BRAZE_MPRACTICE_API_KEY`"
        )
    braze_client = client.BrazeClient(api_key=constants.BRAZE_MPRACTICE_API_KEY)
    braze_client.delete_users(external_ids=external_ids)


def bulk_track_users(users: list[User]) -> None:
    braze_client = client.BrazeClient()
    braze_user_attributes = [build_user_attrs(u) for u in users]
    braze_client.track_users(user_attributes=braze_user_attributes)


def braze_fertility_clinic_user_attributes(user: User) -> client.BrazeUserAttributes:
    fertility_clinic_user_profile = _get_fertility_clinic_profile(user.id)
    user_clinics = fertility_clinic_user_profile.clinics  # type: ignore[union-attr] # Item "None" of "Optional[FertilityClinicUserProfile]" has no attribute "clinics"
    fertility_clinic_location_data = _fertility_clinic_location_data(
        [c.id for c in user_clinics]
    )

    fc_user_attrs = dict(
        clinic_location_country=fertility_clinic_location_data.get("country"),
        clinic_location_name=fertility_clinic_location_data.get("name"),
        clinic_location_state=fertility_clinic_location_data.get("state"),
        clinic_name=[c.name for c in user_clinics],
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone_number=user.sms_phone_number,
        user_role=fertility_clinic_user_profile.role
        if fertility_clinic_user_profile is not None
        else None,
    )
    attrs = {k: v for k, v in fc_user_attrs.items() if k is not None}

    return client.BrazeUserAttributes(external_id=user.esp_id, attributes=attrs)


def build_user_attrs(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    user: User, email: Optional[str] = None, email_subscribe=None
) -> client.BrazeUserAttributes:
    if fertility_clinic_user(user.id):
        return braze_fertility_clinic_user_attributes(user)

    country_repo = CountryRepository()
    if user.country_code is not None:
        country = country_repo.get(country_code=user.country_code)
    else:
        country = None

    user_attrs = {
        "email": email if email else user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "Registration date": format_dt(user.created_at),
        "user_flags": [f.name for f in user.current_risk_flags()],
        "country": country and country.alpha_2,
        "state": (
            user.member_profile.state.abbreviation
            if user.member_profile and user.member_profile.state
            else None
        ),
        "install_source": (
            user.install_attribution.json.get("media_source")
            if user.install_attribution and user.install_attribution.json
            else None
        ),
        "is_practitioner": user.is_practitioner,
        "verticals": (
            [
                {"display_name": vertical.display_name, "id": vertical.id}
                for vertical in user.practitioner_profile.verticals
            ]
            if user.is_practitioner is True
            else None
        ),
        "email_click_tracking_disabled": False,
    }

    if email_subscribe:
        user_attrs["email_subscribe"] = email_subscribe

    if user.active_tracks:
        _populate_enterprise_attrs(user_attrs, user)

    _populate_last_track_attrs(user_attrs, user)  # only after tracks end
    _populate_last_org_attrs(user_attrs, user)  # only after tracks start
    _populate_bulk_messaging_attrs(user_attrs, user)  # after member profile is updated
    _populate_appointment_attrs(user_attrs, user)
    _populate_message_attrs(user_attrs, user)

    attrs = {
        k: user_attrs[k] if k in user_attrs else None for k in _BRAZE_USER_ATTR_FIELDS
    }

    return client.BrazeUserAttributes(external_id=user.esp_id, attributes=attrs)


def terminate_track(user: User) -> None:
    # clear out track related attributes when terminating the track
    attrs = {
        "Organization": None,
        "pnp_available": None,
        "pregnancy_available": None,
        "Intro appointment status": None,
        "Intro appointment completed at": None,
        "assessment_status": None,
        "fertility_treatment_status": None,
        "Care coordinator first name": None,
        "Care coordinator last name": None,
        "Care coordinator id": None,
        "current_track": None,
        "current_phase": None,
        "current_phase_pnp": None,
        "track_started": None,
        "pnp_track_started": None,
        "phase_started": None,
        "phase_auto_transitioned": None,
        "extended_track": None,
        "first_time_mom": None,
        "track_length_in_days": None,
    }
    # try to fill them in again if the user is enrolled in another active track
    if user.active_tracks:
        _populate_enterprise_attrs(attrs, user)

    _populate_last_track_attrs(attrs, user)
    _populate_last_org_attrs(attrs, user)

    if attrs:
        braze_client = client.BrazeClient()
        braze_user_attributes = client.BrazeUserAttributes(
            external_id=user.esp_id,
            attributes=attrs,
        )
        braze_client.track_user(user_attributes=braze_user_attributes)


def activate_track(user: User) -> None:
    attrs = {}
    _populate_enterprise_attrs(attrs, user)

    attrs = {k: v for k, v in attrs.items() if v is not None}
    if attrs:
        braze_client = client.BrazeClient()
        braze_user_attributes = client.BrazeUserAttributes(
            external_id=user.esp_id,
            attributes=attrs,
        )
        braze_client.track_user(user_attributes=braze_user_attributes)


def _get_firsttime_status(user: User) -> bool | None:
    is_first_time_mom = user.health_profile.first_time_mom
    if is_first_time_mom is not None:
        return is_first_time_mom

    # TODO: remove old AssessmentExporter logic once exclusively using new assessment
    exporter = AssessmentExporter.for_user_assessments(user)
    answers = exporter.most_recent_answers_for(
        user, AssessmentExportTopic.ANALYTICS, ("first_pregnancy",)
    )
    if answers["first_pregnancy"] is not None:
        return answers["first_pregnancy"].exported_answer

    # If we don't find an answer, return None so this attribute is omitted on braze. We shouldn't
    # go from having an answer to not, so we should never be removing this attribute from a braze user.
    return None


def _get_certified_states(user: User) -> List[str]:
    return [state.abbreviation for state in user.practitioner_profile.certified_states]


def fertility_clinic_user(user_id: int) -> bool:
    return True if _get_fertility_clinic_profile(user_id) else False


def _get_fertility_clinic_profile(user_id: int) -> FertilityClinicUserProfile | None:
    fertility_clinic_user_repository = FertilityClinicUserRepository()
    return fertility_clinic_user_repository.get_by_user_id(user_id=user_id)


def _fertility_clinic_location_data(clinic_ids: list[int]) -> dict:
    """
    Create lists of all clinic location metadata and remove duplicate state and country codes
    """
    fertility_clinic_location_repo = FertilityClinicLocationRepository()
    country_repo = CountryRepository()
    state_repo = SubdivisionRepository()
    fertility_clinic_location_data = {}

    for clinic_id in clinic_ids:
        locations = fertility_clinic_location_repo.get_by_clinic_id(
            fertility_clinic_id=clinic_id
        )

        for location in locations:
            if location.country_code:
                country = country_repo.get(
                    country_code=location.country_code
                ).alpha_2  # type: ignore[union-attr] # Item "None" of "Optional[Country]" has no attribute "alpha_2"

                if fertility_clinic_location_data.get("country"):
                    fertility_clinic_location_data["country"].add(country)
                else:
                    fertility_clinic_location_data["country"] = {country}

            if fertility_clinic_location_data.get("name"):
                fertility_clinic_location_data["name"].append(location.name)  # type: ignore[attr-defined] # "Set[Union[str, Any]]" has no attribute "append"
            else:
                fertility_clinic_location_data["name"] = [location.name]  # type: ignore[assignment] # Incompatible types in assignment (expression has type "List[Any]", target has type "Set[Union[str, Any]]")

            state = None
            if location.subdivision_code:
                state_obj = state_repo.get(subdivision_code=location.subdivision_code)
                if state_obj is not None:
                    state = state_obj.abbreviation

            if fertility_clinic_location_data.get("state"):
                fertility_clinic_location_data["state"].add(state)
            else:
                fertility_clinic_location_data["state"] = {state}

    if fertility_clinic_location_data.get("country"):
        fertility_clinic_location_data["country"] = list(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "List[Union[str, Any]]", target has type "Set[Union[str, Any]]")
            fertility_clinic_location_data["country"]
        )

    if fertility_clinic_location_data.get("state"):
        fertility_clinic_location_data["state"] = list(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "List[Union[str, Any]]", target has type "Set[Union[str, Any]]")
            fertility_clinic_location_data["state"]
        )

    return fertility_clinic_location_data


def _populate_last_track_attrs(user_attrs: dict, user: User) -> None:
    if len(user.inactive_tracks) > 0:
        last_track = user.inactive_tracks[0]
        user_attrs.update(
            last_track=last_track.name,
            last_track_ended_date=format_dt(last_track.final_phase.ended_at),
        )


def _populate_last_org_attrs(user_attrs: dict, user: User) -> None:
    from tracks.service import TrackSelectionService

    tracks_service = TrackSelectionService()
    org_id = tracks_service.get_organization_id_for_user(user_id=user.id)

    if org_id:
        org = db.session.query(Organization).get(org_id)
        user_attrs[LAST_ORGANIZATION_OFFERS_PNP] = any(
            t.name == TrackName.PARENTING_AND_PEDIATRICS for t in org.allowed_tracks
        )


def _populate_bulk_messaging_attrs(user_attrs: dict, user: User) -> None:
    if not user.member_profile:
        return

    for n in range(10):
        key = f"braze_pause_message_{n + 1}"
        if key in user.member_profile.json:
            if user.member_profile.json[key] == "yes":
                user_attrs[key] = "yes"
            else:
                user_attrs[key] = "no"


def update_bulk_messaging_attrs(
    user: User,
) -> None:
    if not user.member_profile:
        return

    attrs = {}
    for n in range(10):
        key = f"braze_pause_message_{n + 1}"
        if key in user.member_profile.json:
            if user.member_profile.json[key] == "yes":
                attrs[key] = "yes"
            else:
                attrs[key] = "no"

    if attrs:
        braze_client = client.BrazeClient()
        braze_user_attributes = client.BrazeUserAttributes(
            external_id=user.esp_id,
            attributes=attrs,
        )
        braze_client.track_user(user_attributes=braze_user_attributes)


def _populate_track_attrs(user_attrs: dict, user: User) -> None:
    from tracks.utils.common import (  # avoid circular import
        get_active_member_track_modifiers,
    )

    if user.active_tracks:
        organization = user.active_tracks[0].organization
        user_attrs["Organization"] = organization.name
        user_attrs["pnp_available"], user_attrs["pregnancy_available"] = False, False
        for t in organization.allowed_tracks:
            if t.name == TrackName.PARENTING_AND_PEDIATRICS:
                user_attrs["pnp_available"] = True
            elif t.name == TrackName.PREGNANCY:
                user_attrs["pregnancy_available"] = True

    # [multitrack] for current multiple track scenario (only pnp + one other track)
    # added current_phase_pnp to represent pnp track phase
    # existing current_track + current_phase for all tracks except pnp
    current_track = user.current_member_track
    current_phase = current_track and current_track.current_phase
    if current_track and current_phase:
        pnp_track_started = None
        if pnp_track := next(
            (
                t
                for t in user.active_tracks
                if t.name == TrackName.PARENTING_AND_PEDIATRICS
            ),
            None,
        ):
            pnp_track_started = format_dt(pnp_track.created_at)

        user_attrs.update(
            current_track=current_track.name,
            track_started=format_dt(current_track.created_at),
            pnp_track_started=pnp_track_started,
            phase_started=format_dt(current_phase.started_at),
            phase_auto_transitioned=current_track.auto_transitioned,
            extended_track=current_track.is_extended,
            first_time_mom=_get_firsttime_status(user),
            track_length_in_days=current_track.length().days,
            is_doula_only=TrackModifiers.DOULA_ONLY
            in get_active_member_track_modifiers(user.active_tracks),
        )

        if current_track.name == TrackName.PARENTING_AND_PEDIATRICS:
            user_attrs["current_phase_pnp"] = current_phase.name
        else:
            user_attrs["current_phase"] = current_phase.name
            user_attrs["current_phase_pnp"] = (
                pnp_track.current_phase.name if pnp_track else None
            )


def _populate_enterprise_attrs(user_attrs: dict, user: User) -> None:
    hp_service = HealthProfileService(user)

    user_attrs["assessment_status"] = _user_assessment_status(user)
    user_attrs[
        "fertility_treatment_status"
    ] = hp_service.get_fertility_treatment_status()
    _populate_care_coordinator_attrs(user_attrs, user)

    _populate_track_attrs(user_attrs, user)


def update_current_track_phase(track: MemberTrack) -> requests.Response:
    current_phase = track.current_phase
    if track.name == TrackName.PARENTING_AND_PEDIATRICS:
        attrs = dict(
            external_id=track.user.esp_id,
            current_phase_pnp=current_phase.name,
            phase_started=format_dt(current_phase.started_at),
        )
    else:
        attrs = dict(
            external_id=track.user.esp_id,
            current_phase=current_phase.name,
            phase_started=format_dt(current_phase.started_at),
        )

    attrs = {k: v for k, v in attrs.items() if v is not None}
    braze_client = client.BrazeClient()
    braze_user_attributes = client.BrazeUserAttributes(
        external_id=track.user.esp_id,
        attributes=attrs,
    )
    return braze_client.track_user(user_attributes=braze_user_attributes)


def update_health_profile(user: User) -> None:
    profile = user.health_profile
    hp_service = HealthProfileService(user)
    attrs = dict(
        fertility_treatment_status=hp_service.get_fertility_treatment_status(),
        first_time_mom=_get_firsttime_status(profile.user),
    )
    attrs = {k: v for k, v in attrs.items() if v is not None}
    if attrs:
        braze_client = client.BrazeClient()
        braze_user_attributes = client.BrazeUserAttributes(
            external_id=profile.user.esp_id,
            attributes=attrs,
        )
        braze_client.track_user(user_attributes=braze_user_attributes)


def _populate_message_attrs(user_attrs: dict, user: User) -> None:
    last_member_message_to_ca = Message.last_member_message_to_ca(user)
    user_attrs[
        "member_last_messaged_with_CA_date"
    ] = last_member_message_to_ca and format_dt(last_member_message_to_ca.created_at)
    last_ca_message_to_member = Message.last_ca_message_to_member(user)

    user_attrs[
        "CA_last_messaged_with_member_date"
    ] = last_ca_message_to_member and format_dt(last_ca_message_to_member.created_at)


def update_message_attrs(user: User) -> None:
    attrs = {}
    _populate_message_attrs(attrs, user)

    attrs = {k: v for k, v in attrs.items() if v is not None}
    if attrs:
        braze_client = client.BrazeClient()
        braze_user_attributes = client.BrazeUserAttributes(
            external_id=user.esp_id,
            attributes=attrs,
        )
        braze_client.track_user(user_attributes=braze_user_attributes)


def _populate_appointment_attrs(user_attrs: dict, user: User) -> None:
    ca_appointments_completed_count = 0
    non_ca_appointments_completed_count = 0
    most_recent_provider_appointment = None
    next_scheduled_provider_appointment = None
    birth_planning_appointment_scheduled = False
    intro_appointment_status = "no booking"
    intro_appointment_completed_at = None

    now = datetime.datetime.utcnow()
    appointments = (
        db.session.query(Appointment)
        .options(joinedload(Appointment.product).joinedload(Product.vertical))
        .join(Schedule)
        .filter(Schedule.user_id == user.id)
        .order_by(Appointment.scheduled_start.asc())
        .all()
    )
    for appt in appointments:
        is_completed = appt.is_completed()
        is_ca = is_cx_vertical_name(appt.product.vertical.name)

        if is_completed:
            if is_ca:
                ca_appointments_completed_count += 1
            else:
                non_ca_appointments_completed_count += 1

        if not is_ca:
            if is_completed:
                most_recent_provider_appointment = appt
            elif (
                next_scheduled_provider_appointment is None
                and appt.scheduled_start > now
                and appt.cancelled_at is None
            ):
                next_scheduled_provider_appointment = appt

        if appt.purpose == Purposes.BIRTH_PLANNING.value:
            pregnancy_track = next(
                (
                    t
                    for t in user.active_tracks
                    if t.name == TrackName.PREGNANCY
                    or t.name == TrackName.PARTNER_PREGNANT
                ),
                None,
            )
            if (
                pregnancy_track
                and pregnancy_track.created_at < appt.scheduled_start
                and appt.cancelled_at is None
            ):
                birth_planning_appointment_scheduled = True

        # As soon as we find an intro appt with status payment_resolved,
        # we will set intro_appointment_status to completed.
        # After that, no need to continue checking for other appointments.
        if appt.is_intro and intro_appointment_status != "completed":
            if appt.state == APPOINTMENT_STATES.payment_resolved:
                intro_appointment_status = "completed"
                intro_appointment_completed_at = appt.scheduled_end
            elif appt.state == APPOINTMENT_STATES.scheduled:
                intro_appointment_status = "scheduled"
            elif appt.state == APPOINTMENT_STATES.cancelled:
                intro_appointment_status = "missed"
            else:
                intro_appointment_status = "other"

    user_attrs[
        "most_recent_completed_provider_appointment_date"
    ] = most_recent_provider_appointment and format_dt(
        most_recent_provider_appointment.scheduled_start.date()
    )
    user_attrs[
        "next_scheduled_provider_appointment_date"
    ] = next_scheduled_provider_appointment and format_dt(
        next_scheduled_provider_appointment.scheduled_start.date()
    )
    user_attrs["ca_appointments_completed_count"] = ca_appointments_completed_count
    user_attrs[
        "non_ca_appointments_completed_count"
    ] = non_ca_appointments_completed_count
    user_attrs[
        "birth_planning_appointment_scheduled"
    ] = birth_planning_appointment_scheduled

    user_attrs["Intro appointment status"] = intro_appointment_status
    user_attrs["Intro appointment completed at"] = intro_appointment_completed_at


def update_appointment_attrs(user: User) -> None:
    attrs = {}
    _populate_appointment_attrs(attrs, user)
    log.info("Updating appointment attributes in braze", user_id=user.id)

    braze_client = client.BrazeClient()
    braze_user_attributes = client.BrazeUserAttributes(
        external_id=user.esp_id,
        attributes=attrs,
    )
    braze_client.track_user(user_attributes=braze_user_attributes)


def _populate_care_coordinator_attrs(user_attrs: dict, user: User) -> None:
    care_coordinator = _user_care_coordinator(user)
    if care_coordinator:
        user_attrs["Care coordinator first name"] = care_coordinator.first_name
        user_attrs["Care coordinator last name"] = care_coordinator.last_name
        user_attrs["Care coordinator id"] = care_coordinator.id


def update_care_advocate_attrs(
    user: User,
) -> None:
    attrs = {}
    _populate_care_coordinator_attrs(attrs, user)
    log.info("Updating care coordinator attributes in braze", user_id=user.id)
    braze_client = client.BrazeClient()
    braze_user_attributes = client.BrazeUserAttributes(
        external_id=user.esp_id,
        attributes=attrs,
    )
    braze_client.track_user(user_attributes=braze_user_attributes)


def _user_care_coordinator(user: User) -> PractitionerProfile:
    if user.care_coordinators:
        return user.care_coordinators[0]
    # DD log monitor: https://app.datadoghq.com/monitors/137849398
    log.warning(
        "Calling default_care_coordinator from utils/braze.py. We should never get to this place, all members should have CA",
        user_id=user.id,
    )
    # TODO: This is not the appropiate place for setting a default CA. Todo in KICK-1661
    from care_advocates.models.assignable_advocates import AssignableAdvocate

    return AssignableAdvocate.default_care_coordinator()


def _user_assessment_status(user: User) -> list[str]:
    assessments = user.assessments
    return [
        f"{assessment.type.value}:{assessment.status}"
        for assessment in assessments
        if assessment.type
    ]


def track_user_webinars(user: User, webinar_topic: str) -> None:
    attrs = {"webinars_attended": {"add": [webinar_topic]}}
    braze_client = client.BrazeClient()
    braze_user_attributes = client.BrazeUserAttributes(
        external_id=user.esp_id,
        attributes=attrs,
    )
    braze_client.track_user(user_attributes=braze_user_attributes)


def send_event(
    user: User,
    event_name: str,
    event_data: Optional[dict] = None,
    user_attributes: Optional[dict] = None,
) -> dict:
    warn(
        """This function is deprecated.
        Try:
            braze_client = BrazeClient()
            braze_client.track_user()
        """,
        DeprecationWarning,
        stacklevel=2,
    )
    return send_event_by_ids(
        user_id=user.id,
        user_esp_id=user.esp_id,
        event_name=event_name,
        event_data=event_data,
        user_attributes=user_attributes,
    )


def track_email_from_wallet_user_invite(
    wallet_user_invite: WalletUserInvite, name: str, invitation_link: str
) -> None:
    """Creates a Braze profile and sends an invitation."""
    # Maybe these map to user Attributes
    attrs = {
        "email": wallet_user_invite.email,
        "first_name": "Partner",
        "invite_id": str(wallet_user_invite.id),
        "invite_time": format_dt(wallet_user_invite.created_at),
    }

    braze_client = client.BrazeClient()
    braze_user_attributes = client.BrazeUserAttributes(
        # This external_id should not matter and is only needed
        # to create the profile for sending the invitation.
        external_id=str(wallet_user_invite.id),
        attributes=attrs,
    )
    braze_event = client.BrazeEvent(
        external_id=str(wallet_user_invite.id),
        name="share_a_wallet_partner_invited",
        properties=dict(
            invitation_link=invitation_link,
            sender_first_name=name,
            recipient_email=wallet_user_invite.email,
        ),
    )
    braze_client.track_user(
        user_attributes=braze_user_attributes,
        events=[braze_event],
    )

    log.info(
        "Share a Wallet - Sent Braze event to send invitation.",
        invitation_id=str(wallet_user_invite.id),
        sender_user_id=str(wallet_user_invite.created_by_user_id),
    )


def appointment_rescheduled_member(
    appointment: Appointment,
) -> None:
    """
    Sends an email via Braze to the member to inform them about a rescheduled appointment
    :param appointment:
    :return:
    """
    # Grab the organization this user is associated with - avoid circular import
    from tracks import service as tracks_svc
    from utils.braze_events import _gcal_link, _ical_link

    track_svc = tracks_svc.TrackSelectionService()
    member_id = appointment.member.id
    practitioner_id = appointment and appointment.practitioner_id
    organization = track_svc.get_organization_for_user(user_id=member_id)
    log.info(
        "Sending member braze notification about appointment rescheduled",
        user_id=member_id,
        appointment_id=appointment.id,
        practitioner_id=practitioner_id,
    )

    try:
        braze_client = client.BrazeClient()
        event_properties = {
            "appointment_id": appointment.api_id,
            "practitioner_id": (
                appointment.practitioner.id if appointment.practitioner else None
            ),
            "practitioner_name": (
                appointment.practitioner.full_name if appointment.practitioner else None
            ),
            "practitioner_image": (
                appointment.practitioner.avatar_url
                if appointment.practitioner
                else None
            ),
            "practitioner_type": (
                ", ".join(
                    v.name
                    for v in appointment.practitioner.practitioner_profile.verticals
                )
                if appointment.practitioner
                else None
            ),
            "scheduled_start_time": format_dt(appointment.scheduled_start),
            "booked_at": format_dt(appointment.created_at),
            "has_pre_session_note": bool(appointment.client_notes),
            "health_binder_fields_completed": all(
                (
                    appointment.member.health_profile.height,
                    appointment.member.health_profile.weight,
                )
            ),
            "user_country": (
                appointment.member.country and appointment.member.country.name
            ),
            "user_organization": (organization and organization.name),
            "appointment_purpose": appointment.purpose,
            "anonymous_appointment": appointment.is_anonymous,
            "prescription_available": (
                appointment.rx_enabled
                and appointment.practitioner.practitioner_profile.dosespot != {}
                if appointment.practitioner
                else None
            ),
            "gcal_link": _gcal_link(appointment),
            "ical_link": _ical_link(appointment),
        }

        braze_event = client.BrazeEvent(
            external_id=appointment.member.esp_id,
            name="appointment_rescheduled_member",
            properties=event_properties,
        )
        braze_client.track_user(events=[braze_event])
    except Exception as e:
        log.error(
            "Error when attempting to send rescheduled appointment email to member",
            member_id=member_id,
            practioner_id=practitioner_id,
            appointment_id=appointment.id,
            exception=e,
        )


def send_event_by_ids(
    user_id: int,
    user_esp_id: str,
    event_name: str,
    event_data: Optional[dict] = None,
    user_attributes: Optional[dict] = None,
) -> dict:
    warn(
        """This function is deprecated.
        Try:
            braze_client = BrazeClient()
            braze_client.track_user()
        """,
        DeprecationWarning,
        stacklevel=2,
    )
    braze_event = client.BrazeEvent(
        external_id=user_esp_id,
        name=event_name,
        properties=event_data,
    )
    braze_user_attributes = None
    if user_attributes is not None:
        braze_user_attributes = client.BrazeUserAttributes(
            external_id=user_esp_id,
            attributes=user_attributes,
        )

    if fertility_clinic_user(user_id):
        braze_app = "fertility clinic"
        assert (
            constants.BRAZE_FERTILITY_CLINIC_PORTAL_API_KEY is not None
        ), "BRAZE_FERTILITY_CLINIC_PORTAL_API_KEY must not be None"
        braze_client = client.BrazeClient(
            api_key=constants.BRAZE_FERTILITY_CLINIC_PORTAL_API_KEY,
        )
    else:
        braze_app = "default"
        braze_client = client.BrazeClient()

    resp = braze_client.track_user(
        user_attributes=braze_user_attributes,
        events=[braze_event],
    )

    success = "true" if resp and resp.ok else "false"
    log.info(
        f"Sending Braze Event Request in {braze_app} app",
        user_id=user_id,
        esp_id=user_esp_id,
        braze_event_name=event_name,
        braze_event_properties=event_data and ",".join(event_data.keys()),
        braze_user_attributes=user_attributes and ",".join(user_attributes.keys()),
    )

    return {"success": success, "response": resp}


@dataclass(frozen=True)
class BrazeUser:
    __slots__ = ("external_id",)
    external_id: str


@dataclass(frozen=True)
class BrazeUserOnboardingState(BrazeUser):
    __slots__ = ("onboarding_state",)
    onboarding_state: OnboardingState


@dataclass(frozen=True)
class BrazeEligibleThroughOrganization(BrazeUser):
    __slots__ = ("last_eligible_through_organization",)
    last_eligible_through_organization: str


@dataclass(frozen=True)
class BrazeUserIncentives(BrazeUser):
    __slots__ = ("incentive_id_ca_intro", "incentive_id_offboarding")
    incentive_id_ca_intro: int
    incentive_id_offboarding: int


@dataclass(frozen=True)
class BrazeUserOffboardingIncentives(BrazeUser):
    __slots__ = "incentive_id_offboarding"
    incentive_id_offboarding: int | None


def send_onboarding_state(external_id: str, onboarding_state: OnboardingState) -> None:
    braze_client = client.BrazeClient()
    braze_client.track_user(
        user_attributes=client.BrazeUserAttributes(
            external_id=external_id, attributes={"onboarding_state": onboarding_state}
        )
    )


def send_onboarding_states(
    user_onboarding_states: List[BrazeUserOnboardingState],
) -> None:
    braze_client = client.BrazeClient()
    braze_client.track_users(
        user_attributes=[
            client.BrazeUserAttributes(
                external_id=uos.external_id,
                attributes={"onboarding_state": uos.onboarding_state},
            )
            for uos in user_onboarding_states
        ]
    )


def send_last_eligible_through_organization(
    external_id: str, organization_name: str
) -> None:
    braze_client = client.BrazeClient()
    braze_client.track_user(
        user_attributes=client.BrazeUserAttributes(
            external_id=external_id,
            attributes={"last_eligible_through_organization": organization_name},
        )
    )


def send_last_eligible_through_organizations(
    last_eligible_through_organizations: List[BrazeEligibleThroughOrganization],
) -> None:
    braze_client = client.BrazeClient()
    braze_client.track_users(
        user_attributes=[
            client.BrazeUserAttributes(
                external_id=leto.external_id,
                attributes={
                    "last_eligible_through_organization": leto.last_eligible_through_organization
                },
            )
            for leto in last_eligible_through_organizations
        ]
    )


def send_incentive(
    external_id: str, incentive_id_ca_intro: int, incentive_id_offboarding: int
) -> None:
    braze_client = client.BrazeClient()
    braze_client.track_user(
        user_attributes=client.BrazeUserAttributes(
            external_id=external_id,
            attributes={
                "incentive_id_ca_intro": incentive_id_ca_intro,
                "incentive_id_offboarding": incentive_id_offboarding,
            },
        )
    )


def send_incentives(
    user_incentives: List[BrazeUserIncentives],
) -> None:
    braze_client = client.BrazeClient()
    braze_client.track_users(
        user_attributes=[
            client.BrazeUserAttributes(
                external_id=user_incentive.external_id,
                attributes={
                    "incentive_id_ca_intro": user_incentive.incentive_id_ca_intro,
                    "incentive_id_offboarding": user_incentive.incentive_id_offboarding,
                },
            )
            for user_incentive in user_incentives
        ]
    )


def send_incentives_offboarding(
    user_incentives: List[BrazeUserOffboardingIncentives],
) -> None:
    braze_client = client.BrazeClient()
    braze_client.track_users(
        user_attributes=[
            client.BrazeUserAttributes(
                external_id=user_incentive.external_id,
                attributes={
                    "incentive_id_offboarding": user_incentive.incentive_id_offboarding,
                },
            )
            for user_incentive in user_incentives
        ]
    )


def send_incentives_allowed(
    external_id: str, welcome_box_allowed: bool, gift_card_allowed: bool
) -> None:
    log.info("Updating incentives allows in braze", external_id=external_id)
    braze_client = client.BrazeClient()
    braze_client.track_user(
        user_attributes=client.BrazeUserAttributes(
            external_id=external_id,
            attributes={
                "welcome_box_allowed": welcome_box_allowed,
                "gift_card_allowed": gift_card_allowed,
            },
        )
    )


def send_user_wallet_attributes(
    external_id: str,
    wallet_qualification_datetime: datetime.datetime | None = None,
    wallet_added_payment_method_datetime: datetime.datetime | None = None,
    wallet_added_health_insurance_datetime: datetime.datetime | None = None,
) -> None:
    log.info(
        "Updating wallet attributes for user in braze",
        external_id=external_id,
        wallet_qualification_datetime=wallet_qualification_datetime,
        wallet_added_payment_method_datetime=wallet_added_payment_method_datetime,
        wallet_added_health_insurance_datetime=wallet_added_health_insurance_datetime,
    )
    braze_client = client.BrazeClient()
    attributes_raw = {
        "wallet_qualification_datetime": wallet_qualification_datetime,
        "wallet_added_payment_method_datetime": wallet_added_payment_method_datetime,
        "wallet_added_health_insurance_datetime": wallet_added_health_insurance_datetime,
    }
    attributes = {k: v for k, v in attributes_raw.items() if v is not None}
    braze_client.track_user(
        user_attributes=client.BrazeUserAttributes(
            external_id=external_id,
            attributes=attributes,
        )
    )


def is_whitelisted_braze_ip(ip_address: str) -> bool:
    if not ip_address or not isinstance(ip_address, str):
        return False

    key = "braze_whitelist_ips"
    client = redis_client(skip_on_fatal_exceptions=True, default_tags=["caller:braze"])
    if not client.smembers(key):
        try:
            with open("/api/braze/braze_whitelisted_ips.yml") as stream:
                yaml_data = yaml.safe_load(stream)
        except Exception as e:
            # If we cannot load whitelisted IPs, log the error and skip this check
            log.error("Could not load Braze whitelisted IPs", exception=e)
            return True

        braze_ips = yaml_data["braze"]["whitelist-ips"]
        client.sadd(key, *braze_ips)
        return ip_address in braze_ips
    return client.sismember(key, ip_address)


_TOKEN_KEY = "connected_event_token"
_EVENT_KEY = "e"
_USER_ID_KEY = "u"
_CONNECTED_EVENT_REGISTRY = {}


@unique
class ConnectedEvent(Enum):
    """ConnectedEvent overcomes event property limitations by deferring event properties to a connected content call.
    Property limitations being that the custom event properties of string type cannot exceed 255 characters.

    Connected events make use of JWTs (JSON Web Tokens) to grant Braze the temporary ability to call a handler function
    with particular subject arguments. For the event to be dispatched correctly, a couple of rules should be followed:

    1. The ConnectedEvent instance names (e.g. password_reset), should match the event name as expected in Braze.
    2. The value associated with a particular ConnectedEvent instance should not change as it would corrupt live tokens.
    """

    password_reset = 1
    new_user_registration = 2
    existing_fertility_user_password_reset = 3

    def __call__(self, exp: int = 600, compatibility_mode: bool = False) -> Callable:
        """The wrapping function encodes the arguments it receives as a token that is sent with the Braze event. Later
        when the connected content call is made, the decorated function is dispatched to generate event properties.

        Args:
            exp: In seconds, the duration for which the issued token will be valid.
            compatibility_mode: When True, the event properties are included alongside the token so that
                                Braze templates can be progressively updated while testing the new mechanism.

        Example:
            @ConnectedEvent.password_reset()
            def send_password_reset(user):
                return {
                    "password_reset_url": f"..."
                }
        """

        def decorator(func: Callable) -> Callable:

            assert (
                self not in _CONNECTED_EVENT_REGISTRY
            ), "Only one handler may be registered per event."
            _CONNECTED_EVENT_REGISTRY[self] = func

            handler_signature = signature(func)

            assert (
                next(iter(handler_signature.parameters.keys())) == "user"
            ), "ConnectedEvent handlers must accept user as their first argument."

            @wraps(func)
            def send_event_with_token(user: User, *args: Any, **kwargs: dict) -> None:
                if compatibility_mode:
                    log.debug(
                        "Sending event properties alongside token.",
                        event_name=self.name,
                    )
                    event_properties = func(user, *args, **kwargs)
                    assert (
                        _TOKEN_KEY not in event_properties
                    ), f"{_TOKEN_KEY} is a reserved event property representing the connected event properties token."
                else:
                    event_properties = {}

                token_properties = handler_signature.bind(
                    user, *args, **kwargs
                ).arguments
                token_properties.pop("user")
                assert (
                    _EVENT_KEY not in token_properties
                ), f"{_EVENT_KEY} is a reserved key representing the event name."
                assert (
                    _USER_ID_KEY not in token_properties
                ), f"{_USER_ID_KEY} is a reserved key representing the user id."
                token_properties[_EVENT_KEY] = self.value
                token_properties[_USER_ID_KEY] = user.esp_id
                connected_event_token = client.RawBrazeString(
                    BRAZE_CONNECTED_EVENT_TOKEN.encode(token_properties, exp=exp)
                )
                event_properties[_TOKEN_KEY] = connected_event_token

                send_event(user, self.name, event_properties)

            return send_event_with_token

        return decorator

    @classmethod
    def event_properties_from_token(cls, token):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        token_properties = BRAZE_CONNECTED_EVENT_TOKEN.decode(token)
        if token_properties is None:
            return (
                {
                    "error": "Cannot retrieve connected event properties with expired or invalid token."
                },
                401,
            )

        event = cls(token_properties.pop(_EVENT_KEY))
        esp_id = token_properties.pop(_USER_ID_KEY)
        user = User.query.filter_by(esp_id=esp_id).one()

        log.info(
            "Generating connected event properties.",
            event_name=event.name,
            user_id=user.id,
        )
        func = _CONNECTED_EVENT_REGISTRY[event]
        try:
            return client.recursive_html_escape(func(user, **token_properties)), 200
        except Exception as e:
            log.error(
                "Could not generate connected event properties.",
                exception=e,
                event_name=event.name,
                user_id=user.id,
            )
            return (
                {
                    "error": "Encountered error while generating connected event properties."
                },
                500,
            )
