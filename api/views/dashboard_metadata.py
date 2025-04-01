from __future__ import annotations

import dataclasses
import datetime
import enum
import functools
from typing import FrozenSet, Iterable, List, Mapping, Optional, Tuple

import ddtrace
import tenacity
from flask import abort, request
from httpproblem import Problem
from marshmallow import Schema, fields
from maven import feature_flags
from sqlalchemy import bindparam, case, func
from sqlalchemy.ext import baked
from sqlalchemy.orm import joinedload

import eligibility
import tracks
from appointments.models.v2.member_appointment import MemberAppointmentStruct
from appointments.services.common import obfuscate_appointment_id
from appointments.services.v2.member_appointment import MemberAppointmentService
from appointments.utils.booking import (
    AvailabilityCalculator,
    AvailabilityTools,
    PotentialAppointment,
)
from authn.models.user import User
from care_advocates.models.assignable_advocates import AssignableAdvocate
from common.health_data_collection.user_assessment_status_api import (
    get_user_assessment_by_user_id_and_slug,
)
from common.services.api import AuthenticatedResource
from health.services.care_coaching_eligibility_service import (
    CareCoachingEligibilityService,
)
from health.services.health_profile_service import HealthProfileService
from learn.services import article_thumbnail_service
from models.enterprise import Assessment, NeedsAssessment, OnboardingState, Organization
from models.marketing import (
    Resource,
    ResourceContentTypes,
    ResourceTrack,
    ResourceTrackPhase,
    resource_organizations,
)
from models.products import Product
from models.profiles import (
    CareTeamTypes,
    MemberPractitionerAssociation,
    PractitionerProfile,
)
from models.tracks import MemberTrack, TrackConfig, TrackName
from models.tracks.client_track import TrackModifiers
from models.tracks.phase import UnrecognizedPhaseName, ensure_new_phase_name
from preferences.utils.member_communications import get_member_communications_preference
from providers.service.provider import ProviderService
from storage.connection import db
from tracks.service.tracks import TrackSelectionService
from utils.launchdarkly import user_context
from utils.log import logger
from views.tracks import AvailableTrackSchema, get_user_active_track
from wallet.models.constants import WalletState
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.repository.reimbursement_wallet import ReimbursementWalletRepository
from wallet.utils.eligible_wallets import get_eligible_wallet_org_settings

log = logger(__name__)

ModuleRangeT = Tuple[datetime.datetime, datetime.datetime]

ELIGIBILITY_TIMEOUT_SECONDS = 1.5


@dataclasses.dataclass
class DashboardModule:
    """Where this user is in their maternity - pregnant, postpartum, etc."""

    __slots__ = ("id", "name", "next_module_name", "start_date", "end_date")

    id: int
    name: str
    next_module_name: str
    start_date: str
    end_date: str


@dataclasses.dataclass
class DashboardAssessment:
    """A scheduled assessment for the user."""

    id: int
    slug: str
    title: str
    version: int
    completed: bool
    url: str = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        self.url = f"/onboarding/onboarding-assessment/{self.id}/{self.slug}/take/1"


@dataclasses.dataclass
class DashboardProgram:
    """The overarching enrollment for a given user."""

    name: str
    display_name: str
    selected_phase: str
    current_phase: str
    transitioning_to: Optional[TrackName]
    auto_transitioned: bool
    length_in_days: int
    anchor_date: str
    scheduled_end_date: str
    eligible_for_renewal: bool
    qualified_for_optout: bool
    track_modifiers: List[TrackModifiers]
    total_phases: Optional[int] = None


@dataclasses.dataclass
class AdditionalTrack:
    """Minimal information for a user's additional track."""

    __slots__ = ("name", "display_name", "scheduled_end_date")

    name: str
    display_name: str
    scheduled_end_date: str


@dataclasses.dataclass
class DashboardOrg:
    """The company associated to the user."""

    id: int
    name: str
    icon: str
    bms_enabled: bool = False


@dataclasses.dataclass
class DashboardAppointment:
    """An upcoming appointment with a practitioner."""

    __slots__ = ("id", "start", "end")

    id: int
    start: str
    end: str


@dataclasses.dataclass
class DashboardPractitionerAvailability:
    """A single availability slot for a particular product"""

    __slots__ = ("scheduled_start", "scheduled_end", "product_id")

    scheduled_start: str
    scheduled_end: str
    product_id: int


@dataclasses.dataclass
class DashboardPractitioner:
    """A care provider."""

    id: int
    name: str
    image: str
    vertical: str
    is_prescriber: bool = False
    verticals: Iterable[str] = dataclasses.field(default_factory=list)
    availabilities: Iterable[DashboardPractitionerAvailability] = dataclasses.field(
        default_factory=list
    )


@dataclasses.dataclass
class DashboardScheduledCare:
    """Upcoming care for a given user."""

    practitioner: DashboardPractitioner
    appointment: Optional[DashboardAppointment] = None


class DashboardUserWalletStatus(str, enum.Enum):
    INELIGIBLE = "ineligible"
    ELIGIBLE = "eligible"
    ENROLLED = "enrolled"


@dataclasses.dataclass
class DashboardUserHealthProfile:
    due_date: Optional[str] = None
    fertility_treatment_status: Optional[str] = None


@dataclasses.dataclass
class DashboardUser:
    """The associated metadata for a given user."""

    id: int
    organization: Optional[DashboardOrg]
    advocate: DashboardPractitioner
    has_had_intro_appointment: bool
    wallet_status: Optional[DashboardUserWalletStatus]
    first_name: str
    has_available_tracks: bool
    health_profile: DashboardUserHealthProfile
    subscribed_to_promotional_email: bool
    is_eligible_for_care_coaching: bool
    is_matched_to_care_coach: bool
    is_known_to_be_eligible: Optional[bool] = False
    scheduled_care: Optional[DashboardScheduledCare] = None
    has_care_plan: bool = False
    country: Optional[str] = None
    current_risk_flags: List[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class DashboardLibraryResource:
    """A simplified representation of a resource."""

    id: int
    title: str
    group: str
    url: str
    icon: Optional[str] = None
    tagline: Optional[str] = None


@dataclasses.dataclass
class DashboardLibraryResources:
    """The shape of the response for fetching dashboard resources."""

    __slots__ = ("maven", "org")

    maven: Iterable[DashboardLibraryResource]
    org: Iterable[DashboardLibraryResource]


@dataclasses.dataclass
class DashboardMetadata:
    """The metadata required to render a dashboard for a user."""

    __slots__ = ("user", "program", "additional_tracks", "resources")

    user: DashboardUser
    program: DashboardProgram
    additional_tracks: List[AdditionalTrack]
    resources: DashboardLibraryResources


bakery = baked.bakery()  # type: ignore[call-arg,func-returns-value] # Missing positional argument "initial_fn" in call to "__call__" of "Bakery" #type: ignore[func-returns-value] # Function does not return a value (it only ever returns None) #type: ignore[func-returns-value] # Function does not return a value (it only ever returns None)


@ddtrace.tracer.wrap()
def get_practitioner_availabilities(
    user: User,
    practitioner_profile: PractitionerProfile,
    vertical_name: Optional[str] = None,
) -> Iterable[DashboardPractitionerAvailability]:
    product = AvailabilityTools.get_product_for_practitioner(
        profile=practitioner_profile, vertical_name=vertical_name
    )
    if not product:
        return []
    calculator = AvailabilityCalculator(practitioner_profile, product)
    start_time = AvailabilityTools.pad_and_round_availability_start_time(
        datetime.datetime.utcnow(),
        practitioner_profile.booking_buffer,
        practitioner_profile.rounding_minutes,
    )
    end_time = start_time + datetime.timedelta(days=2)
    slots = calculator.get_availability(
        start_time=start_time,
        end_time=end_time,
        member=user,
        limit=3,  # TODO: customizable limits?
    )

    def build_availability_slot(potential_appointment: PotentialAppointment):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return DashboardPractitionerAvailability(
            scheduled_start=potential_appointment.scheduled_start.isoformat(),
            scheduled_end=potential_appointment.scheduled_end.isoformat(),
            product_id=product.id,
        )

    return [build_availability_slot(slot) for slot in slots]


@ddtrace.tracer.wrap()
def get_practitioner(
    user: User, vertical_name: Optional[str], specialty_name: Optional[str]
) -> Optional[DashboardPractitioner]:
    kwargs = {"current_user": user, "order_by": "next_availability", "limit": 1}
    if vertical_name:
        kwargs["verticals"] = [vertical_name]
    if specialty_name:
        kwargs["specialties"] = [specialty_name]

    practitioners, count = ProviderService().search(**kwargs)
    if not practitioners:
        return None
    practitioner = practitioners[0]
    verticals = practitioner.practitioner_profile.verticals
    is_prescriber = ProviderService().enabled_for_prescribing(practitioner.id)
    vertical_names = [vertical.marketing_name for vertical in verticals]
    display_vertical = (
        next((v.marketing_name for v in verticals if v.name == vertical_name), None)
        or vertical_names[0]
    )
    availabilities = get_practitioner_availabilities(
        user=user,
        practitioner_profile=practitioner.practitioner_profile,
        vertical_name=vertical_name,
    )
    return DashboardPractitioner(
        id=practitioner.id,
        name=practitioner.full_name,
        image=practitioner.avatar_url,
        is_prescriber=is_prescriber,
        vertical=display_vertical,
        verticals=vertical_names,
        availabilities=availabilities,
    )


@ddtrace.tracer.wrap()
def get_care_advocate(user: User) -> DashboardPractitioner:
    """Get a user's care advocate and convert it to the API schema."""
    query: baked.BakedQuery = bakery(
        lambda session: session.query(User)
        .join(
            MemberPractitionerAssociation,
            MemberPractitionerAssociation.practitioner_id == User.id,
        )
        .filter(MemberPractitionerAssociation.type == CareTeamTypes.CARE_COORDINATOR)
        .filter(MemberPractitionerAssociation.user_id == bindparam("user_id"))
        # Load in everything that might be needed for get_practitioner_availabilities
        .options(
            joinedload(User.practitioner_profile).options(
                joinedload(PractitionerProfile.verticals),
                joinedload(PractitionerProfile.user),
            ),
            joinedload(User.image),
            joinedload(User.products),
            joinedload(User.schedule),
        )
    )
    cc: User = query(db.session()).params(user_id=user.id).first()
    log.info("Querying rows in MemberPractitionerAssociation", user_id=user.id)
    if not cc:
        cc = AssignableAdvocate.default_care_coordinator()
    care_advocate = DashboardPractitioner(
        id=cc.id,
        name=cc.full_name,
        image=cc.avatar_url,
        is_prescriber=ProviderService().enabled_for_prescribing(cc.id),
        vertical=cc.profile.verticals[0].marketing_name,  # type: ignore[union-attr,index] # Item "None" of "Union[PractitionerProfile, MemberProfile, None]" has no attribute "verticals" #type: ignore[index] # Value of type "Union[Any, RelationshipProperty[Any]]" is not indexable #type: ignore[index] # Value of type "Union[Any, RelationshipProperty[Any]]" is not indexable
        verticals=[v.marketing_name for v in cc.profile.verticals],  # type: ignore[union-attr] # Item "None" of "Union[PractitionerProfile, MemberProfile, None]" has no attribute "verticals" #type: ignore[union-attr] # Item "RelationshipProperty[Any]" of "Union[Any, RelationshipProperty[Any]]" has no attribute "__iter__" (not iterable)
        availabilities=get_practitioner_availabilities(user, cc.profile),
    )
    return care_advocate


AssessmentScalarT = Tuple[int, str, str, str, bool]


@ddtrace.tracer.wrap()
def locate_assessment(user_id: int, type: str) -> Optional[AssessmentScalarT]:
    """Query for the targeted assessment for the given user."""
    # Make the query.
    query: baked.BakedQuery = bakery(
        lambda session: session.query(
            Assessment.id,
            Assessment.slug,
            Assessment.title,
            Assessment.version,
            # In case there are multiple NeedsAssessments, return true if ANY are true
            func.max(
                case(
                    [(NeedsAssessment.completed == None, False)],
                    else_=NeedsAssessment.completed,
                )
            ),
        )
        .outerjoin(
            NeedsAssessment,
            (NeedsAssessment.assessment_id == Assessment.id)
            & (NeedsAssessment.user_id == bindparam("user_id")),
        )
        .filter(
            Assessment.slug == bindparam("type_outer"),
            Assessment.version
            == (
                session.query(func.max(Assessment.version)).filter_by(
                    slug=bindparam("type_inner")
                )
            ),
        )
        .group_by(Assessment.id)
    )
    return (
        query(db.session())
        .params(user_id=user_id, type_outer=type, type_inner=type)
        .one_or_none()
    )


@ddtrace.tracer.wrap()
def locate_maven_library(track_name: str, phase_name: str) -> Iterable[Resource]:
    """Get all the eligible Maven resources for the given phase."""
    query: baked.BakedQuery = bakery(
        lambda session: session.query(Resource)
        .join(
            ResourceTrackPhase,
            (Resource.id == ResourceTrackPhase.resource_id)
            & (ResourceTrackPhase.track_name == bindparam("track_name"))
            & (ResourceTrackPhase.phase_name == bindparam("phase_name")),
        )
        .filter(Resource.content_type != ResourceContentTypes.on_demand_class.name)
        .filter(Resource.published_at <= func.now())
        .order_by(Resource.published_at.desc())
    )
    resources = (
        query(db.session()).params(phase_name=phase_name, track_name=track_name).all()
    )
    thumbnail_service = article_thumbnail_service.ArticleThumbnailService()
    return thumbnail_service.get_thumbnails_for_resources(resources)  # type: ignore[return-value] # Incompatible return value type (got "List[ResourceWithThumbnail]", expected "Iterable[Resource]")


@ddtrace.tracer.wrap()
def locate_org_library(org_id: int, track_name: str) -> Iterable[Resource]:
    """Get all the eligible Organization Resources for this user."""
    query: baked.BakedQuery = bakery(
        lambda session: session.query(Resource)
        .join(
            resource_organizations,
            (Resource.id == resource_organizations.c.resource_id)
            & (resource_organizations.c.organization_id == bindparam("org_id")),
        )
        .join(
            ResourceTrack,
            (Resource.id == ResourceTrack.resource_id)
            & (ResourceTrack.track_name == bindparam("track_name")),
        )
        .filter(Resource.content_type != ResourceContentTypes.on_demand_class.name)
        .filter(Resource.published_at <= func.now())
        .order_by(Resource.published_at.desc())
    )

    return query(db.session()).params(org_id=org_id, track_name=track_name).all()


@ddtrace.tracer.wrap()
def get_library_resources(
    user: User, track_name: str, phase_name: str, org: Optional[DashboardOrg]
) -> DashboardLibraryResources:
    """Fetch all Maven and Organization resources for a given user."""
    return DashboardLibraryResources(
        maven=[
            DashboardLibraryResource(
                id=r.id,
                title=r.title,
                group=r.content_type,
                url=r.content_url,
                icon=r.image and r.image.asset_url(),
                tagline=trim_chars_ish(r.subhead) if r.subhead else None,
            )
            for r in locate_maven_library(track_name, phase_name)
        ],
        org=(
            [
                DashboardLibraryResource(
                    id=r.id, title=r.title, group=r.content_type, url=r.custom_url
                )
                for r in locate_org_library(org.id, track_name)
            ]
            if org
            else []
        ),
    )


def get_risk_flags(user: User) -> List[str]:
    risk_flags = user.current_risk_flags()
    return [risk_flag.name for risk_flag in risk_flags]


def _get_product(product_id: int) -> Product:
    product = (
        db.session.query(Product)
        .filter(Product.id == product_id)
        .options(
            joinedload(Product.practitioner)
            .joinedload("practitioner_profile")
            .joinedload("verticals"),
        )
        .one_or_none()
    )
    return product


@ddtrace.tracer.wrap()
def get_scheduled_care(user: User) -> Optional[DashboardScheduledCare]:
    """Locate the next available appointment and who it's with, if any."""
    # Get the currently scheduled appointments for a user.
    appointment: Optional[
        MemberAppointmentStruct
    ] = MemberAppointmentService().get_current_or_next_appointment_for_member(user)
    if appointment is None:
        return None

    # Create the appointment with the data we need.
    apt = DashboardAppointment(
        id=obfuscate_appointment_id(appointment.id),
        start=appointment.scheduled_start.isoformat(),
        end=appointment.scheduled_end.isoformat(),
    )
    # Get the practitioner data for this appointment.
    vertical_localization_flag = feature_flags.bool_variation(
        "release-disco-be-localization",
        user_context(user),
        default=False,
    )
    product = _get_product(appointment.product_id)
    if product is None:
        return None
    prac_orm = product.practitioner

    prac_role: Optional[PractitionerProfile] = (
        prac_orm.practitioner_profile if prac_orm else None
    )
    prac = DashboardPractitioner(
        id=prac_orm.id,
        name=prac_orm.full_name,
        image=prac_orm.avatar_url,
        is_prescriber=ProviderService().enabled_for_prescribing(prac_orm.id),
        vertical=product
        and product.vertical.get_marketing_name(
            should_localize=vertical_localization_flag
        ),
        verticals=[
            v.get_marketing_name(should_localize=vertical_localization_flag)
            for v in prac_role.verticals
        ]
        if prac_role
        else [],
    )

    # Get the scheduled care for this user.
    return DashboardScheduledCare(practitioner=prac, appointment=apt)


@tenacity.retry(
    stop=tenacity.stop_after_attempt(2),
    reraise=False,
    retry=tenacity.retry_if_result(lambda r: r is None),
)
def get_organization_id_for_user(user_id: int) -> Optional[int]:
    return TrackSelectionService().get_organization_id_for_user(user_id=user_id)


@ddtrace.tracer.wrap()
def get_org(user: User) -> Optional[DashboardOrg]:
    """Try to fetch an organization for this user."""
    try:
        org_id = get_organization_id_for_user(user.id)
    except tenacity.RetryError:
        log.warn("No organization id found for user", user_id=user.id)
        return None

    org: Organization = db.session.query(Organization).get(org_id)

    if org:
        return DashboardOrg(
            id=org.id,
            name=org.marketing_name,  # type: ignore[arg-type] # Argument "name" to "DashboardOrg" has incompatible type "ColumnProperty"; expected "str"
            icon=org.icon,  # type: ignore[arg-type] # Argument "icon" to "DashboardOrg" has incompatible type "Optional[str]"; expected "str"
            bms_enabled=org.bms_enabled,
        )
    else:
        log.warn("No organization found for user", user_id=user.id, org_id=org_id)
        return None


@ddtrace.tracer.wrap()
def locate_member_track_and_phase(
    user: User, track_id: int, phase_name: str = None  # type: ignore[assignment] # Incompatible default for argument "phase_name" (default has type "None", argument has type "str")
) -> Tuple[MemberTrack, str]:
    """Try to fetch the member track and selected phase for this user."""
    track = get_user_active_track(user, track_id)
    selected_phase_name = phase_name or track.current_phase.name
    return track, selected_phase_name


@ddtrace.tracer.wrap()
def get_dashboard_program(track: MemberTrack, phase_name: str) -> DashboardProgram:
    """Translate the data into a DashboardProgram."""

    return DashboardProgram(
        name=track.name,
        display_name=track.display_name,  # type: ignore[arg-type] # Argument "display_name" to "DashboardProgram" has incompatible type "Optional[str]"; expected "str"
        selected_phase=ensure_new_phase_name(phase_name, track.name),
        current_phase=track.current_phase.name,
        total_phases=track.total_phases,
        anchor_date=track.anchor_date.isoformat(),
        length_in_days=track.length().days,
        transitioning_to=track.transitioning_to,  # type: ignore[arg-type] # Argument "transitioning_to" to "DashboardProgram" has incompatible type "Optional[str]"; expected "Optional[TrackName]"
        auto_transitioned=track.auto_transitioned,
        scheduled_end_date=track.get_scheduled_end_date().isoformat(),
        eligible_for_renewal=track.is_eligible_for_renewal(),
        track_modifiers=track.client_track.track_modifiers_list,
        qualified_for_optout=bool(track.qualified_for_optout),
    )


def get_additional_track(track: MemberTrack) -> AdditionalTrack:
    return AdditionalTrack(
        name=track.name,
        display_name=track.display_name,  # type: ignore[arg-type] # Argument "display_name" to "AdditionalTrack" has incompatible type "Optional[str]"; expected "str"
        scheduled_end_date=track.get_scheduled_end_date().isoformat(),
    )


# A mostly arbitrary array of words that kinda feel weird to stop a phrase on.
STOP_WORDS = frozenset(
    {"for", "to", "and", "as", "at", "by", "in", "a", "the", "of", "if", "but"}
)


@functools.lru_cache(maxsize=1000)
def trim_chars_ish(
    string: str,
    *,
    chars: int = 80,
    tail: str = "...",
    marker: str = ".",
    sep: str = " ",
    __stop: FrozenSet[str] = STOP_WORDS,
) -> str:
    """Extract about the character count, but don't cut off words.

    Add a tail ('...') if we cut off before the defined marker ('.').

    Args:
        string
            The text to trim down.

    Keyword Args:
        chars
            The maximum number of characters.
        tail
            The characters to add to the end if the string doesn't end with ``marker``.
        marker
            The character to check for at the end of a string.
        sep
            The word separator to use.
    """
    if len(string) < chars:
        return string
    # Cut it down to size
    cleaned = string[: chars + 1]
    # Get the final word.
    if not cleaned[-1].isspace():
        cleaned = cleaned.rsplit(maxsplit=1)[0]
    # Convert all whitespace to a simple space, extract the final word.
    cleaning = sep.join(cleaned.split()).rsplit(sep, maxsplit=1)
    cleaned, final = cleaning if len(cleaning) == 2 else (cleaned, "")
    # If the final word is a "stop word", drop it.
    if final not in __stop:
        cleaned = f"{cleaned}{sep}{final}"
    # Add a tail if we must.
    if not cleaned.endswith(marker):
        cleaned = f"{cleaned}{sep}{tail}"
    return cleaned


@ddtrace.tracer.wrap()
def get_wallet_status(user: User, org_id: int) -> DashboardUserWalletStatus:
    # If user has a wallet, we don't need to check organization status
    all_wallet_states = ReimbursementWalletRepository().get_wallet_states_for_user(
        user.id
    )
    if WalletState.QUALIFIED.value in all_wallet_states:
        return DashboardUserWalletStatus.ENROLLED

    if WalletState.PENDING.value in all_wallet_states:
        return DashboardUserWalletStatus.ELIGIBLE

    # as of review on 2023-06-15:
    # the get_eligible_wallet_org_settings filters out any existing wallets
    # so DISQUALIFIED OR EXPIRED wallets will count as ineligible
    # this was approved by product
    org_settings: List[
        ReimbursementOrganizationSettings
    ] = get_eligible_wallet_org_settings(user.id, organization_id=org_id)
    if org_settings:
        return DashboardUserWalletStatus.ELIGIBLE
    return DashboardUserWalletStatus.INELIGIBLE


@ddtrace.tracer.wrap()
def get_dashboard_user(user: User, org: Optional[DashboardOrg]) -> DashboardUser:
    care_advocate = get_care_advocate(user)
    scheduled_care = get_scheduled_care(user)
    risk_flags = get_risk_flags(user)
    has_had_intro_appointment = AvailabilityTools.has_had_ca_intro_appointment(user)
    wallet_status = get_wallet_status(user, org.id) if org else None
    track_service = tracks.TrackSelectionService()
    enrollable_tracks: List[TrackConfig] = (
        track_service.get_enrollable_tracks_for_org(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "List[ClientTrack]", variable has type "List[TrackConfig]")
            user_id=user.id, organization_id=org.id
        )
        if org
        else []
    )

    eligibility_service = eligibility.get_verification_service()
    is_known_to_be_eligible = eligibility_service.is_user_known_to_be_eligible_for_org(
        user_id=user.id,
        organization_id=org.id if org else None,
        timeout=ELIGIBILITY_TIMEOUT_SECONDS,
    )
    hp_service = HealthProfileService(user)
    fertility_treatment_status = hp_service.get_fertility_treatment_status()
    is_matched_to_care_coach = (
        ProviderService().is_member_matched_to_coach_for_active_track(user)
    )
    return DashboardUser(
        id=user.id,
        organization=org,
        advocate=care_advocate,
        scheduled_care=scheduled_care,
        has_had_intro_appointment=has_had_intro_appointment,
        wallet_status=wallet_status,
        first_name=user.first_name,  # type: ignore[arg-type] # Argument "first_name" to "DashboardUser" has incompatible type "Optional[str]"; expected "str"
        has_available_tracks=(len(enrollable_tracks) > 0),
        is_eligible_for_care_coaching=is_matched_to_care_coach
        and CareCoachingEligibilityService().is_user_eligible_for_care_coaching(
            user=user, fertility_treatment_status=fertility_treatment_status
        ),
        is_matched_to_care_coach=is_matched_to_care_coach,
        health_profile=DashboardUserHealthProfile(
            due_date=user.health_profile
            and user.health_profile.due_date
            and user.health_profile.due_date.isoformat(),
            fertility_treatment_status=fertility_treatment_status,
        ),
        has_care_plan=user.member_profile.has_care_plan,
        subscribed_to_promotional_email=get_member_communications_preference(user.id),
        country=user.member_profile.country_code,
        is_known_to_be_eligible=is_known_to_be_eligible,
        current_risk_flags=risk_flags,
    )


@ddtrace.tracer.wrap()
def get_dashboard_metadata(
    user: User, track_id: int, phase_name: str = None  # type: ignore[assignment] # Incompatible default for argument "phase_name" (default has type "None", argument has type "str")
) -> DashboardMetadata:
    member_track, phase_name = locate_member_track_and_phase(user, track_id, phase_name)
    program = get_dashboard_program(member_track, phase_name)
    organization: Optional[DashboardOrg] = get_org(user)
    resources = get_library_resources(
        user=user,
        track_name=member_track.name,
        phase_name=phase_name,
        org=organization,
    )
    return DashboardMetadata(
        user=get_dashboard_user(user, organization),
        program=program,
        additional_tracks=[
            get_additional_track(t) for t in user.active_tracks if t.id != track_id
        ],
        resources=resources,
    )


@dataclasses.dataclass
class DashboardMetadataQuery:
    __slots__ = ("phase",)
    phase: str


@ddtrace.tracer.wrap()
# TODO: [Tracks] Update optimization once we move over to MemberTrack ORM
def locate_user(user_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """Preload all of the relations we're going to access more than once."""
    query: baked.BakedQuery = bakery(
        lambda session: session.query(User)
        .filter(User.id == bindparam("user_id"))
        .options(
            # TODO: use User.active_tracks instead of current_member_track
            joinedload(User.current_member_track),
            joinedload(User.member_profile),
            joinedload(User.health_profile),
            joinedload(User.schedule),
            joinedload(User.reimbursement_wallets),
        )
    )
    return query(db.session()).params(user_id=user_id).one()


class DashboardMetadataRequestSchema(Schema):
    """
    Schema used for requests to the DashboardMetadataResource GET endpoint.
    """

    phase = fields.String(default=None)


class DashboardMetadataResource(AuthenticatedResource):
    def parse_request(self) -> DashboardMetadataQuery:
        if self.user is None:
            return abort(404)

        schema = DashboardMetadataRequestSchema()
        args = schema.load(request.args)
        return DashboardMetadataQuery(phase=args.get("phase", None))

    def handle(self, query: DashboardMetadataQuery):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        raise NotImplementedError()

    def get(self, track_id) -> Mapping[str, Iterable[Mapping[str, Optional[str]]]]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        """Retrieve the dashboard metadata for the authenticated user.

        Optionally supply a specific phase name

        E.g.:
            GET /v1/dashboard-metadata/track/1
            GET /v1/dashboard-metadata/track/1?phase=week-17
        """
        query = self.parse_request()
        log.info(
            "Getting metadata for user.",
            user_id=self.user.id,
            track_id=track_id,
            query=dataclasses.asdict(query),
        )

        user_id = self.user.id
        member_track = (
            db.session.query(MemberTrack)
            .filter(MemberTrack.id == track_id, MemberTrack.user_id == user_id)
            .first()
        )
        if member_track is None:
            raise Problem(
                404,
                detail=f"User with ID = {user_id} has no track with ID = {track_id}",
            )

        try:
            metadata = get_dashboard_metadata(self.user, track_id, query.phase)
        except UnrecognizedPhaseName as e:
            raise Problem(400, detail=str(e))
        return dataclasses.asdict(metadata)


class DashboardMetadataPractitionerRequestSchema(Schema):
    """
    Schema used for requests to the DashboardMetadataPractitionerResource GET endpoint.
    """

    vertical = fields.String()
    specialty = fields.String()


class DashboardMetadataPractitionerResource(AuthenticatedResource):
    """
    An internal endpoint specifically for fetching the next available
    practitioner in a particular vertical. Used by the "Care" block.
    """

    def get(self) -> Optional[dict]:
        schema = DashboardMetadataPractitionerRequestSchema()
        args = schema.load(request.args)
        vertical_name = args.get("vertical", None)
        specialty_name = args.get("specialty", None)
        practitioner = get_practitioner(self.user, vertical_name, specialty_name)
        return dataclasses.asdict(practitioner) if practitioner else None


class DashboardMetadataAssessmentRequestSchema(Schema):
    """
    Schema used for requests to the DashboardMetadataAssessmentResource GET endpoint.
    """

    type = fields.String(required=True)


class DashboardMetadataAssessmentResource(AuthenticatedResource):
    """
    Fetch the latest assessment of a certain type, and whether its been completed by the
    current user.
    """

    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        schema = DashboardMetadataAssessmentRequestSchema()
        # werkzeug enforces "Content-Type" header in latest versions
        # this is to overcome the issue
        if len(request.args) > 0:
            args = schema.load(request.args)
        else:
            args = schema.load(request.get_json(force=True) or {})
        slug = args.get("type", "")
        assessment = get_user_assessment_by_user_id_and_slug(self.user.id, slug)

        if assessment:
            return dataclasses.asdict(assessment)
        else:
            return None


@dataclasses.dataclass
class MarketplaceDashboardMetadata:
    """The metadata required to render a dashboard for a marketplace user."""

    __slots__ = (
        "first_name",
        "onboarding_state",
        "has_recently_ended_track",
        "subscribed_to_promotional_email",
    )

    first_name: str
    onboarding_state: Optional[OnboardingState]
    has_recently_ended_track: bool
    subscribed_to_promotional_email: bool


class MarketplaceDashboardMetadataResource(AuthenticatedResource):
    """
    Fetches data needed to render a dashboard for a marketplace user.
    """

    def get(self) -> dict:
        marketplace_metadata = MarketplaceDashboardMetadata(
            first_name=self.user.first_name,
            onboarding_state=self.user.onboarding_state
            and self.user.onboarding_state.state,
            has_recently_ended_track=bool(
                self.user.member_profile
                and self.user.member_profile.has_recently_ended_track
            ),
            subscribed_to_promotional_email=get_member_communications_preference(
                self.user.id
            ),
        )
        return dataclasses.asdict(marketplace_metadata)


class ExpiredTrackSchema(AvailableTrackSchema):
    ended_at = fields.DateTime()


class ExpiredTrackCareAdvocateSchema(Schema):
    id = fields.Integer()
    first_name = fields.String()


class ExpiredTrackDashboardMetadataSchema(Schema):
    is_known_to_be_eligible = fields.Boolean(required=True)
    available_tracks = fields.List(fields.Nested(AvailableTrackSchema))
    expired_track = fields.Nested(ExpiredTrackSchema)
    advocate = fields.Nested(ExpiredTrackCareAdvocateSchema)
    first_name = fields.String()


class ExpiredTrackDashboardMetadataResource(AuthenticatedResource):
    """
    Retrieve the expired track dashboard metadata for the authenticated user.
    """

    def __init__(self) -> None:
        super().__init__()
        self.schema = ExpiredTrackDashboardMetadataSchema()
        self.track_service = tracks.TrackSelectionService()

    def get(self, track_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        log.info(
            "Getting expired track metadata for user.",
            user_id=self.user.id,
            track_id=track_id,
        )

        if track_id not in {mt.id for mt in self.user.member_tracks}:
            raise Problem(
                404,
                detail=f"User with ID = {self.user.id} has no track with ID = {track_id}",
            )

        track = next(
            (track for track in self.user.inactive_tracks if track.id == track_id), None
        )

        if track is None:
            raise Problem(400, detail=f"Track with ID = {track_id} has not expired")

        org = get_org(self.user)
        ordered_recommended_tracks = (
            self.track_service.get_ordered_recommended_tracks(
                user_id=self.user.id, organization_id=org.id, previous_track=track.name
            )
            if org is not None
            else []
        )

        eligibility_service = eligibility.get_verification_service()
        is_known_to_be_eligible = (
            eligibility_service.is_user_known_to_be_eligible_for_org(
                user_id=self.user.id,
                organization_id=org.id if org else None,
                timeout=ELIGIBILITY_TIMEOUT_SECONDS,
            )
        )

        return self.schema.dump(
            {
                "is_known_to_be_eligible": is_known_to_be_eligible,
                "available_tracks": ordered_recommended_tracks,
                "expired_track": track,
                "advocate": (
                    self.user.care_coordinators[0]
                    if len(self.user.care_coordinators) > 0
                    else None
                ),
                "first_name": self.user.first_name,
            }
        )
