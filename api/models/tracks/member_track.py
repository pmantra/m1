from __future__ import annotations

import enum
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Iterable, Optional, Sequence

from maven import feature_flags
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    and_,
    case,
    event,
    func,
    inspect,
    select,
)
from sqlalchemy.engine import Connection
from sqlalchemy.ext import baked
from sqlalchemy.orm import Mapper, column_property, relationship, validates
from sqlalchemy.sql import exists

from common import stats
from messaging.services.zendesk_client import IdentityType
from models.base import ModelBase, PolymorphicAwareMixin, TimeLoggedModelBase
from models.marketing import Resource, ResourceTrack
from models.verticals_and_specialties import get_vertical_groups_for_track
from storage.connection import db
from utils.log import logger
from utils.primitive_threaded_cached_property import primitive_threaded_cached_property

from .client_track import ClientTrack, TrackModifiers
from .phase import PhaseNamePrefix
from .resources import get_resources_for_track_phase, resources_for_track_query
from .track import (
    PhaseType,
    TrackConfig,
    TrackName,
    TransitionConfig,
    get_track,
    validate_name,
)

if TYPE_CHECKING:
    from appointments.models.needs_and_categories import Need, NeedCategory
    from models.enterprise import (  # noqa: F401
        AssessmentLifecycle,
        Organization,
        OrganizationEmployee,
    )
    from models.verticals_and_specialties import VerticalGroup  # noqa: F401

MEMBER_TRACK_METRICS_COLLECTION_KS = "member_track-metrics-collection-ks"

bakery = baked.bakery()  # type: ignore[call-arg,func-returns-value] # Missing positional argument "initial_fn" in call to "__call__" of "Bakery" #type: ignore[func-returns-value] # Function does not return a value (it only ever returns None)
log = logger(__name__)


class ChangeReason(str, enum.Enum):
    ADMIN_FORCE_TRANSITION = "admin_force_transition"
    ADMIN_TRANSITION = "admin_transition"
    ADMIN_MANUAL_TRACK_SELECTION = "admin_manual_track_selection"
    ADMIN_PROGRAM_TERMINATE = "admin_program_terminate"
    ADMIN_REACTIVATE = "admin_reactivate"
    ADMIN_CANCEL_TRANSITION = "admin_cancel_transition"
    ADMIN_TERMINATE_TRACK = "admin_terminate_track"
    ADMIN_MEMBER_PROFILE_UPDATE = "admin_member_profile_update"
    DATA_ADMIN_INITIATE_TRACK = "data_admin_initiate_track"
    AUTO_JOB_TRANSITION = "auto_job_transition"
    AUTO_JOB_TERMINATE = "auto_job_terminate"
    AUTO_JOB_RENEW_TERMINATE = "auto_job_renew_terminate"
    AUTO_HEALTH_PROFILE_UPDATE = "auto_health_profile_update"
    AUTO_MIGRATE_TO_FERTILITY_JUNE_2024 = "auto_migrate_to_fertility_june_2024"
    ENSURE_JOB_CHECK_STATE = "ensure_job_check_state"
    OPT_OUT_JOB_RENEW = "opt_out_job_renew"
    API_PROGRAM_CANCEL_TRANSITION = "api_program_cancel_transition"
    API_PROGRAM_FINISH_TRANSITION = "api_program_finish_transition"
    API_PROGRAM_TRANSITION = "api_program_transition"
    API_PROGRAM_INITIATE_TRANSITION = "api_program_initiate_transition"
    API_ASSOCIATE_USER_WITH_ORG = "api_associate_user_with_org"
    API_PUT_HEALTH_PROFILE_UPDATE = "api_put_health_profile_update"
    API_PATCH_HEALTH_PROFILE_UPDATE = "api_patch_health_profile_update"
    API_PUT_PREGNANCY_AND_RELATED_CONDITIONS = (
        "api_put_pregnancy_and_related_conditions"
    )
    API_CLAIM_INV = "api_claim_inv"
    API_CLAIM_PARTNER_INV = "api_claim_partner_inv"
    API_CLAIM_WALLET_PARTNER_INVITE = "api_claim_wallet_partner_invite"
    API_USER_DELETE = "api_user_delete"
    API_INITIATE_TRANSITION = "api_initiate_transition"
    API_FINISH_TRANSITION = "api_finish_transition"
    API_CANCEL_TRANSITION = "api_cancel_transition"
    API_RENEW = "api_renew"
    API_SCHEDULED_CANCEL_TERMINATE = "api_scheduled_cancel_terminate"
    MANUAL_UPDATE = "manual_update"

    def __str__(self) -> str:
        return str(self.value)


class MemberTrack(ModelBase, PolymorphicAwareMixin):
    """The base MemberTrack ORM description.

    This class may be used to create and query new member tracks. It should *not* be
    used for any complex business logic.

    Notes:
        Thanks to `PolymorphicAwareMixin`, this class will automatically intercept
        instantiation and provide the correct subclass based upon the provided `name`.

    See Also:
        - `models.base.PolymorphicAwareMixin`
        - `WeeklyMemberTrackMixin`
        - `StaticMemberTrackMixin`
    """

    __tablename__ = "member_track"
    __table_args__ = (Index("ix_member_track_user_track_name", "user_id", "name"),)
    __calculated_columns__ = frozenset(["get_scheduled_end_date"])

    id = Column(Integer, primary_key=True)

    modified_at = Column(
        DateTime,
        default=func.now(),
        onupdate=func.now(),
    )
    created_at = Column(
        DateTime,
        default=func.now(),
    )
    name = Column(String(120), nullable=False, index=True)
    transitioning_to = Column(String(120), nullable=True)
    client_track_id = Column(Integer, ForeignKey("client_track.id"), nullable=False)
    client_track: "ClientTrack" = relationship(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "RelationshipProperty[ClientTrack]", variable has type "ClientTrack")
        "ClientTrack", back_populates="member_tracks", load_on_pending=True
    )
    anchor_date = Column(Date(), default=date.today)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=True)
    user = relationship("User")
    eligibility_member_id = Column(Integer, nullable=True)
    eligibility_verification_id = Column(Integer, nullable=True)
    eligibility_member_2_id = Column(Integer, nullable=True)
    eligibility_member_2_version = Column(Integer, nullable=True)
    eligibility_verification_2_id = Column(Integer, nullable=True)
    sub_population_id = Column(Integer, nullable=True, default=None)
    is_employee = Column(Boolean, default=True)
    auto_transitioned = Column(Boolean, default=False)
    start_date = Column(Date(), default=func.current_date())
    activated_at = Column(DateTime())
    ended_at = Column(DateTime(), nullable=True)
    legacy_program_id = Column(Integer, ForeignKey("care_program.id"), nullable=True)
    legacy_program = relationship("CareProgram")
    legacy_module_id = Column(Integer, ForeignKey("module.id"), nullable=True)
    legacy_module = relationship("Module")
    previous_member_track_id = Column(
        Integer, ForeignKey("member_track.id"), nullable=True
    )
    bucket_id = Column(
        String(36), nullable=False, default=lambda: str(uuid.uuid4()), index=True
    )
    modified_by = Column(String(120), nullable=True, default=None)
    change_reason = Column(
        Enum(ChangeReason, native_enum=False), nullable=True, default=None
    )
    active = column_property(
        case(
            [(and_(ended_at.is_(None), activated_at.isnot(None)), True)],
            else_=False,
        )
    )
    inactive = column_property(
        case(
            [(and_(ended_at.isnot(None), activated_at.isnot(None)), True)],
            else_=False,
        )
    )
    scheduled = column_property(
        case(
            [(and_(ended_at.is_(None), activated_at.is_(None)), True)],
            else_=False,
        )
    )
    closure_reason_id = Column(
        Integer, ForeignKey("track_change_reason.id"), nullable=True
    )
    closure_reason = relationship("TrackChangeReason")
    qualified_for_optout = Column(Boolean, default=None, nullable=True)

    statuses = relationship(
        "MemberTrackStatus",
        uselist=True,
        viewonly=True,
        order_by="MemberTrackStatus.created_at",
    )
    current_status = relationship(
        "MemberTrackStatus",
        primaryjoin=lambda: MemberTrack.current_status_join_expression(),
        uselist=False,
    )

    __mapper_args__ = {"polymorphic_on": name}
    _expire_mutex = threading.Lock()

    @primitive_threaded_cached_property
    def _today(self) -> date:
        return date.today()

    @validates("name")
    def validate_name(self, key, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        validate_name(self, key, name)
        return name

    @validates("transitioning_to")
    def validate_transition(self, key, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        transitions = {str(t.name) for t in self.transitions} | {
            TrackName.GENERIC.value
        }
        if name in transitions or name is None:
            return name
        raise ValueError(
            f"{self.__class__.__name__}.{key}: "
            f"{self} is not configured to transition to {str(name)!r}. "
            f"Valid transitions are: {(*transitions,)}"
        )

    @classmethod
    def current_status_join_expression(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (cls.id == MemberTrackStatus.member_track_id) & (
            MemberTrackStatus.id == cls.current_status_expression()
        )

    @classmethod
    def current_status_expression(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (
            select([MemberTrackStatus.id])
            .where(MemberTrackStatus.member_track_id == cls.id)
            .order_by(MemberTrackStatus.created_at.desc(), MemberTrackStatus.id.desc())
            .limit(1)
            .correlate(cls)  # type: ignore[arg-type] # Argument 1 to "correlate" of "Select" has incompatible type "Type[MemberTrack]"; expected "FromClause"
            .as_scalar()
            .label("current_member_track_status_id")
        )

    def get_scheduled_end_date(self) -> date:
        """
        After the scheduled end date, a user's track will be terminated or
        autotransitioned (depending on auto_transition_to)
        """
        return self.anchor_date + self.length() + self.grace_period()

    def set_scheduled_end_date(self, scheduled_end_date: date) -> None:
        """
        Sets the scheduled end date for the member track, which is intended to only
        be supported for testing
        """
        difference = scheduled_end_date - self.get_scheduled_end_date()
        self.start_date = self.start_date + timedelta(days=difference.days)
        self.set_anchor_date()

    def length(self) -> timedelta:
        if not self.client_track:
            log.error(f"null client track detected for member_track_id={self.id}")
            return self._config.length
        return self.client_track.length

    def grace_period(self) -> timedelta:
        """
        The number of days after track.length that the user should still be allowed
        to access maven care. During this period, the user is in the `end` phase.
        """
        return self._config.grace_period

    # Overwritten in PregnancyMemberTrack
    def get_display_scheduled_end_date(self) -> date:
        return self.get_scheduled_end_date()

    # instance level cache of partner_track. get_track will be called multiple
    # times if the cached value is None. this is a place for future
    # optimization.
    _cached_partner_track: TrackConfig | None = None

    @property
    def partner_track(self) -> TrackConfig | None:
        if self._cached_partner_track:
            return self._cached_partner_track

        if self._config.partner_track:
            self._cached_partner_track = get_track(self._config.partner_track)

        return self._cached_partner_track

    @property
    def partner_track_enabled(self) -> bool:
        if self.partner_track:
            return ClientTrack.exists(self.partner_track.name, self.organization.id)
        return False

    @property
    def initial_phase(self) -> "MemberTrackPhase":
        raise NotImplementedError()

    def phase_at(self, today: date) -> "MemberTrackPhase":
        raise NotImplementedError()

    @property
    def current_phase(self) -> "MemberTrackPhase":
        return self.phase_at(date.today())

    @property
    def final_phase(self) -> Optional["MemberTrackPhase"]:
        raise NotImplementedError()

    @property
    def phase_history(self) -> Sequence["MemberTrackPhase"]:
        raise NotImplementedError()

    # Overwritten in tracks with weekly phases and static tracks
    @property
    def total_phases(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return None

    # instance level caching of vertical_groups
    _cached_vertical_groups: Iterable[VerticalGroup] | None = None

    @property
    def vertical_groups(self) -> Iterable[VerticalGroup]:
        if self._cached_vertical_groups:
            return self._cached_vertical_groups

        self._cached_vertical_groups = get_vertical_groups_for_track(self.name)
        return self._cached_vertical_groups

    # instance level caching of needs
    _cached_needs: Iterable[Need] | None = None

    @property
    def needs(self) -> Iterable[Need]:
        if self._cached_needs:
            return self._cached_needs

        from appointments.models.needs_and_categories import get_needs_for_track

        self._cached_needs = get_needs_for_track(self.name)
        return self._cached_needs

    # instance level caching of need_categories
    _cached_need_categories: Iterable[NeedCategory] | None = None

    @property
    def need_categories(self) -> Iterable[NeedCategory]:
        if self._cached_need_categories:
            return self._cached_need_categories

        from appointments.models.needs_and_categories import (
            get_need_categories_for_track,
        )

        self._cached_need_categories = get_need_categories_for_track(self.name)
        return self._cached_need_categories

    @property
    def organization(self) -> "Organization":
        return self.client_track.organization

    @property
    def is_extended(self) -> bool:
        return self.client_track.is_extended

    def allowed_resources_query(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return Resource.allowed_tracks.any(ResourceTrack.track_name == self.name)

    # instance level caching of allowed_resources
    _cached_allowed_resources: Iterable[Resource] | None = None

    @property
    def allowed_resources(self) -> Iterable[Resource]:
        if self._cached_allowed_resources:
            return self._cached_allowed_resources

        baked = resources_for_track_query()
        query = baked(db.session()).params(track_name=self.name)
        self._cached_allowed_resources = query.all()
        return self._cached_allowed_resources  # type: ignore[return-value] # Incompatible return value type (got "Optional[Iterable[Resource]]", expected "Iterable[Resource]")

    @property
    def intro_message(self) -> Optional[str]:
        return self._config.intro_message

    @property
    def restrict_booking_verticals(self) -> bool:
        return self._config.restrict_booking_verticals

    @property
    def _config(self) -> TrackConfig:
        return get_track(self.name)

    @property
    def display_name(self) -> Optional[str]:
        return self._config.display_name

    # instance level caching of onboarding_assessment_lifecycle
    _cached_onboarding_assessment_lifecycle: AssessmentLifecycle | None = None

    @property
    def onboarding_assessment_lifecycle(self) -> AssessmentLifecycle | None:
        if self._cached_onboarding_assessment_lifecycle:
            return self._cached_onboarding_assessment_lifecycle

        from models.enterprise import AssessmentLifecycle, AssessmentLifecycleTrack

        self._cached_onboarding_assessment_lifecycle = (
            db.session.query(AssessmentLifecycle)
            .join(
                AssessmentLifecycleTrack,
                AssessmentLifecycleTrack.assessment_lifecycle_id
                == AssessmentLifecycle.id,
            )
            .filter(AssessmentLifecycleTrack.track_name == self.name)
            .first()
        )
        return self._cached_onboarding_assessment_lifecycle

    @primitive_threaded_cached_property
    def onboarding_assessment_slug(self) -> str:
        from models.tracks.assessment import AssessmentTrack

        track_relationship = AssessmentTrack.query.filter(
            AssessmentTrack.track_name == self.name
        ).first()
        return (
            track_relationship.assessment_onboarding_slug
            if track_relationship
            else None
        )

    @property
    def transitions(self) -> Sequence[TransitionConfig]:
        return self._config.transitions

    @property
    def auto_transition_to(self) -> Optional[TrackName]:
        return self._config.auto_transition_to

    @property
    def beyond_scheduled_end(self) -> bool:
        return (
            not self.ended_at  # type: ignore[return-value] # Incompatible return value type (got "Union[date, bool]", expected "bool")
            and self.anchor_date
            and self._today > self.get_scheduled_end_date()
        )

    @property
    def is_active_transition(self) -> bool:
        return self.transitioning_to is not None

    @property
    def required_information(self) -> Iterable[str]:
        return self._config.required_information

    @property
    def phase_type(self) -> "PhaseType":
        return self._config.phase_type

    @property
    def image(self) -> str:
        return self._config.image

    @property
    def description(self) -> str:
        return self._config.description

    @property
    def enrollment_requirement_description(self) -> Optional[str]:
        return self._config.enrollment_requirement_description

    @property
    def display_length(self) -> Optional[str]:
        return self._config.display_length

    @property
    def life_stage(self) -> Optional[str]:
        return self._config.life_stage

    @property
    def track_selection_category(self) -> Optional[str]:
        return self._config.track_selection_category

    @property
    def can_be_renewed(self) -> bool:
        return self._config.can_be_renewed

    @property
    def is_deprecated(self) -> bool:
        return self._config.deprecated

    @property
    def dashboard(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """The dashboard system that should be used when this track is selected"""
        # 2024-04: this code is being used by the front-ends
        return "dashboard2020"

    @property
    def track_modifiers(self) -> list[TrackModifiers] | None:
        return self.client_track.track_modifiers_list

    def is_scheduled_for_renewal(self) -> bool:
        return any(
            t.name == self.name and t.previous_member_track_id == self.id
            for t in self.user.scheduled_tracks
        )

    def is_eligible_for_renewal(self) -> bool:
        return self.can_be_renewed and not self.is_scheduled_for_renewal()

    def is_ending_soon(self) -> bool:
        return (self.get_scheduled_end_date() - datetime.utcnow().date()).days <= 30

    def _calculate_anchor_date(self) -> Optional[date]:
        return self.start_date

    def set_anchor_date(self) -> Optional[date]:  # type: ignore[return] # Missing return statement
        current_anchor_date = self.anchor_date
        new_anchor_date = self._calculate_anchor_date()
        if new_anchor_date and new_anchor_date != current_anchor_date:
            self.anchor_date = new_anchor_date
            self.expire_phases()
            return new_anchor_date

    @classmethod
    def retain_data_for_user(cls, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return db.session.query(exists().where(cls.user_id == user.id)).scalar()

    def expire_phases(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        with self._expire_mutex:
            expire_cached_property_keys(self, *self._PHASE_KEYS)
            try:
                # instance level caches must be added to the expiry list explicitly
                self._cached_initial_phase = None
                self._cached_partner_track = None
                self._cached_vertical_groups = None
                self._cached_needs = None
                self._cached_allowed_resources = None
                self._cached_onboarding_assessment_lifecycle = None
                self._cached_final_phase = None
            except Exception as e:
                log.exception(
                    "error expiring phases for member track",
                    exception=e,
                )

    _PHASE_KEYS = (
        current_phase.fget.__name__,  # type: ignore[attr-defined] # "Callable[[MemberTrack], MemberTrackPhase]" has no attribute "fget"
        initial_phase.fget.__name__,  # type: ignore[attr-defined] # "Callable[[MemberTrack], MemberTrackPhase]" has no attribute "fget"
        final_phase.fget.__name__,  # type: ignore[attr-defined] # "Callable[[MemberTrack], Optional[MemberTrackPhase]]" has no attribute "fget"
        phase_history.fget.__name__,  # type: ignore[attr-defined] # "Callable[[MemberTrack], Sequence[MemberTrackPhase]]" has no attribute "fget"
    )


@event.listens_for(MemberTrack, "before_insert", propagate=True)
def before_insert_listener(
    mapper: Mapper, connection: Connection, target: MemberTrack
) -> None:
    if feature_flags.bool_variation(MEMBER_TRACK_METRICS_COLLECTION_KS, default=False):
        return

    stats.increment(
        metric_name="member_track.create.attempt",
        pod_name=stats.PodNames.ENROLLMENTS,
        tags=[
            f"track_name:{target.name}",
            f"org:{target.organization.id}",
        ],
    )


@event.listens_for(MemberTrack, "after_insert", propagate=True)
def after_insert_listener(
    mapper: Mapper, connection: Connection, target: MemberTrack
) -> None:
    if feature_flags.bool_variation(MEMBER_TRACK_METRICS_COLLECTION_KS, default=False):
        return

    try:
        org_id = target.organization.id
        count_active_tracks = MemberTrack.query.filter(
            MemberTrack.user_id == target.user_id, MemberTrack.active.is_(True)
        ).count()
        is_multi_track = count_active_tracks > 1
    except Exception as e:
        log.exception(
            "Error after insert MemberTrack",
            exception=e,
        )
        org_id = None

    stats.increment(
        metric_name="member_track.create.success",
        pod_name=stats.PodNames.ENROLLMENTS,
        tags=[
            f"track_name:{target.name}",
            f"org:{org_id}",
            f"change_reason:{target.change_reason}",
        ],
    )
    log.info(
        "[Member Track] Successfully created MemberTrack",
        user_id=target.user_id,
        track_name=target.name,
        track_id=target.id,
        org_id=org_id,
        change_reason=target.change_reason,
        transitioning_to=target.transitioning_to,
        anchor_date=target.anchor_date,
        is_multi_track=is_multi_track,
    )


@event.listens_for(MemberTrack, "after_update", propagate=True)
def after_update_listener(
    mapper: Mapper, connection: Connection, target: MemberTrack
) -> None:
    if feature_flags.bool_variation(MEMBER_TRACK_METRICS_COLLECTION_KS, default=False):
        return

    try:
        org_id = target.organization.id
        count_active_tracks = MemberTrack.query.filter(
            MemberTrack.user_id == target.user_id, MemberTrack.active.is_(True)
        ).count()
        is_multi_track = count_active_tracks > 1
    except Exception as e:
        log.exception(
            "Error after update MemberTrack",
            exception=e,
        )
        org_id = None
        is_multi_track = None

    stats.increment(
        metric_name="member_track.update.success",
        pod_name=stats.PodNames.ENROLLMENTS,
        tags=[
            f"track_name:{target.name}",
            f"org:{org_id}",
            f"change_reason:{target.change_reason}",
        ],
    )
    log.info(
        "[Member Track] Successfully updated MemberTrack",
        user_id=target.user_id,
        track_name=target.name,
        track_id=target.id,
        org_id=org_id,
        change_reason=target.change_reason,
        transitioning_to=target.transitioning_to,
        anchor_date=target.anchor_date,
        is_multi_track=is_multi_track,
    )


@event.listens_for(MemberTrack, "after_insert", propagate=True)
def zendesk_after_insert_listener(
    mapper: Mapper, connection: Connection, target: MemberTrack
) -> None:
    if target.activated_at is not None:
        update_zendesk_user_on_track_update(mapper, connection, target)


@event.listens_for(MemberTrack, "after_update", propagate=True)
def zendesk_after_update_listener(
    mapper: Mapper, connection: Connection, target: MemberTrack
) -> None:
    activated_history = inspect(target).get_history("activated_at", True)
    ended_at_history = inspect(target).get_history("ended_at", True)
    if activated_history.has_changes() or ended_at_history.has_changes():
        update_zendesk_user_on_track_update(mapper, connection, target)


def update_zendesk_user_on_track_update(
    mapper: Mapper, connection: Connection, target: MemberTrack
) -> None:
    from messaging.services.zendesk import (
        should_update_zendesk_user_profile,
        update_zendesk_user,
    )

    if should_update_zendesk_user_profile():
        log.info(
            "Updating Zendesk Profile for user track change",
            user_id=target.user_id,
            track_name=target.name,
            track_id=target.id,
        )
        # update the profile with the new track information
        update_zendesk_user.delay(
            user_id=target.user_id,
            update_identity=IdentityType.TRACK,
            team_ns="virtual_care",
            caller="update_zendesk_user_on_track_update",
        )


class TrackChangeReason(ModelBase):
    __tablename__ = "track_change_reason"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False, unique=True)
    display_name = Column(String(120), nullable=False, unique=True)
    description = Column(String(255), nullable=True)

    @property
    def display_name_and_description(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.description:
            return f"{self.display_name} ({self.description}) [ID:{self.id}]"
        return f"{self.display_name} [ID:{self.id}]"


def expire_cached_property_keys(instance, *keys):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    ns = vars(instance)
    for k in ns.keys() & {*keys}:
        del ns[k]


# -- Standard "Weekly" Tracks.


class WeeklyMemberTrackMixin:
    """A 'weekly' Member Track initiates a new phase every seven days.

    This mixin implements the necessary logic for tracking the phase history
    of a given user's track.
    """

    # TODO: [Tracks] ch13164
    _WEEK_OFFSET = 0

    def get_phase_name(self: MemberTrack, interval: int) -> str:
        # Handle when a user's configured track content is "over"
        # but they haven't moved off the track itself.
        if interval > self.length() / timedelta(weeks=1):
            return PhaseNamePrefix.END.value
        return f"{PhaseNamePrefix.WEEKLY}-{interval + self._WEEK_OFFSET}"

    def _initial_interval(self: MemberTrack) -> int:
        """
        Returns the week number for the initial phase.

        For most tracks, this will just return 1. For Pregnancy tracks, it will typically
        be a later week, based on how long after the anchor date the user joined Maven.
        For example, a user who joins 12 weeks after the anchor date will be in week-12.
        """

        track_start_date = self.start_date
        return self.week_at(self.anchor_date, track_start_date)

    # instance level cache of initial_phase
    _cached_initial_phase: MemberTrackPhase | None = None

    @property
    def initial_phase(self: MemberTrack) -> MemberTrackPhase:
        if self._cached_initial_phase:
            return self._cached_initial_phase

        started = self.start_date
        ended = started + timedelta(weeks=1)

        # If this track ended during the "initial" phase, return the "final" phase.
        if self.ended_at and self.ended_at.date() <= ended:
            self._cached_initial_phase = self.final_phase
            return self._cached_initial_phase  # type: ignore[return-value] # Incompatible return value type (got "Optional[MemberTrackPhase]", expected "MemberTrackPhase")

        if ended > self._today:
            ended = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "date")

        # This is typically week-1, except for Pregnancy, where users usually join after week-4.
        week = self._initial_interval()
        phase_name = self.get_phase_name(week)

        self._cached_initial_phase = MemberTrackPhase(
            member_track=self,
            name=phase_name,
            display_name=phase_name,  # TODO
            started_at=started,
            ended_at=ended,
        )
        return self._cached_initial_phase

    def phase_at(self: MemberTrack, today: date) -> "MemberTrackPhase":
        """Fetch the correct phase for this track, given a date."""
        # Always send the final phase if this track has ended.
        if self.ended_at:
            return self.final_phase  # type: ignore[return-value] # Incompatible return value type (got "Optional[MemberTrackPhase]", expected "MemberTrackPhase")

        # Small gotcha!
        #   If we create a track, we should report the initial phase on the day it was
        #   started, which should be based upon `start_date`, not `anchor_date`
        if today <= self.start_date:
            return self.initial_phase

        # For weekly calculations, we use `anchor_date` to ensure we account for any
        #   special logic around what actually determines the anchor.
        track_start_date = self.anchor_date
        current_week = self.week_at(track_start_date, today)
        current_start_date = track_start_date + timedelta(days=(7 * (current_week - 1)))
        phase_name = self.get_phase_name(current_week)
        return MemberTrackPhase(
            member_track=self,
            name=phase_name,
            display_name=phase_name,
            started_at=current_start_date,
            ended_at=None,
        )

    def week_at(self: MemberTrack, start: date, today: date) -> int:
        return int((today - start).days / 7) + 1

    # instance level cache of final_phase
    _cached_final_phase: MemberTrackPhase | None = None

    @property
    def final_phase(self: MemberTrack) -> MemberTrackPhase | None:
        if self._cached_final_phase:
            return self._cached_final_phase

        if self.ended_at:
            track_start_date = self.start_date
            end_date = self.ended_at.date()
            phase_interval = timedelta(weeks=1)
            # Tracks may end at a different date than the scheduled end
            # Get the interval count based upon the end date
            initial_interval = self._initial_interval()
            elapsed_intervals = (end_date - track_start_date) / phase_interval
            interval = initial_interval + elapsed_intervals
            # If we ended on the same day we started, use track_start_date
            if interval <= 0:
                start_date = track_start_date
                # Arrays start at 0, but phases start at 1 :')
                interval = 1
            else:
                # The ended_at date is later than the configured end of the track.
                # This can happen if a user idles in the "end" phase
                # without offboarding.
                max_interval = int(self.length().days / 7)
                if interval > max_interval:
                    interval = max_interval
                # Subtracting 1 to get the "start" interval value
                # Use that to calculate the start of the final phase.
                start_date = track_start_date + (
                    phase_interval * (elapsed_intervals - 1)
                )
            phase_name = self.get_phase_name(int(interval))
            self._cached_final_phase = MemberTrackPhase(
                member_track=self,
                name=phase_name,
                display_name=phase_name,
                started_at=start_date,
                ended_at=end_date,
            )
        return self._cached_final_phase

    @property
    def total_phases(self: MemberTrack) -> int:
        return int(self.length().days / 7)


class EggFreezingMemberTrack(WeeklyMemberTrackMixin, MemberTrack):
    __tablename__ = "member_track"
    __mapper_args__ = {"polymorphic_identity": TrackName.EGG_FREEZING}
    __table_args__ = {"extend_existing": True}  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Dict[str, bool]", base class "MemberTrack" defined the type as "Tuple[Index]")


class FertilityMemberTrack(WeeklyMemberTrackMixin, MemberTrack):
    __tablename__ = "member_track"
    __mapper_args__ = {"polymorphic_identity": TrackName.FERTILITY}
    __table_args__ = {"extend_existing": True}  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Dict[str, bool]", base class "MemberTrack" defined the type as "Tuple[Index]")


class GeneralWellnessMemberTrack(WeeklyMemberTrackMixin, MemberTrack):
    __tablename__ = "member_track"
    __mapper_args__ = {"polymorphic_identity": TrackName.GENERAL_WELLNESS}
    __table_args__ = {"extend_existing": True}  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Dict[str, bool]", base class "MemberTrack" defined the type as "Tuple[Index]")


class PartnerFertilityMemberTrack(WeeklyMemberTrackMixin, MemberTrack):
    __tablename__ = "member_track"
    __mapper_args__ = {"polymorphic_identity": TrackName.PARTNER_FERTILITY}
    __table_args__ = {"extend_existing": True}  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Dict[str, bool]", base class "MemberTrack" defined the type as "Tuple[Index]")


class TryingToConceiveMemberTrack(WeeklyMemberTrackMixin, MemberTrack):
    __tablename__ = "member_track"
    __mapper_args__ = {"polymorphic_identity": TrackName.TRYING_TO_CONCEIVE}
    __table_args__ = {"extend_existing": True}  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Dict[str, bool]", base class "MemberTrack" defined the type as "Tuple[Index]")


class AdoptionMemberTrack(WeeklyMemberTrackMixin, MemberTrack):
    __tablename__ = "member_track"
    __mapper_args__ = {"polymorphic_identity": TrackName.ADOPTION}
    __table_args__ = {"extend_existing": True}  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Dict[str, bool]", base class "MemberTrack" defined the type as "Tuple[Index]")


class MenopauseMemberTrack(WeeklyMemberTrackMixin, MemberTrack):
    __tablename__ = "member_track"
    __mapper_args__ = {"polymorphic_identity": TrackName.MENOPAUSE}
    __table_args__ = {"extend_existing": True}  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Dict[str, bool]", base class "MemberTrack" defined the type as "Tuple[Index]")


# -- Custom "Weekly" tracks


class PregnancyMemberTrack(WeeklyMemberTrackMixin, MemberTrack):
    __tablename__ = "member_track"
    __mapper_args__ = {"polymorphic_identity": TrackName.PREGNANCY}
    __table_args__ = {"extend_existing": True}  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Dict[str, bool]", base class "MemberTrack" defined the type as "Tuple[Index]")

    # We define pregnancy duration as 39 weeks, meaning that the beginning of
    # our week-1 phase is exactly 39 weeks before the user's due date.
    # NOTE: this is distinct from config.length, because pregnancy tracks can go
    # on for longer than 39 weeks.
    PREGNANCY_DURATION = timedelta(weeks=39)

    def get_phase_name(self, interval: int) -> str:
        # Ensure the latest phase is capped at week-42, not week-43 or end.
        # Prevents weird bugs if the track isn't auto-transitioned on time.
        max_interval = int(self.length().days / 7)
        if interval > max_interval:
            interval = max_interval
        return f"{PhaseNamePrefix.WEEKLY}-{interval + self._WEEK_OFFSET}"

    def length(self) -> timedelta:
        # Note: Prevent an extension from affecting the length of pregnancy tracks.
        # This is because we always want to autotransition users after _config.length,
        # regardless of what extension admins have added to maternity tracks.
        return self._config.length

    def _calculate_anchor_date(self) -> Optional[date]:  # type: ignore[return] # Missing return statement
        due_date = self.user.health_profile.due_date
        if due_date:
            return due_date - PregnancyMemberTrack.PREGNANCY_DURATION

    def set_scheduled_end_date(self, scheduled_end_date: date) -> None:
        raise NotImplementedError(
            "Pregnancy does not support setting scheduled end date"
        )

    def get_display_scheduled_end_date(self) -> date:
        return self.get_scheduled_end_date() + get_track(TrackName.POSTPARTUM).length


class PartnerPregnancyMemberTrack(PregnancyMemberTrack):
    __tablename__ = "member_track"
    __mapper_args__ = {"polymorphic_identity": TrackName.PARTNER_PREGNANT}
    __table_args__ = {"extend_existing": True}  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Dict[str, bool]", base class "MemberTrack" defined the type as "Tuple[Index]")


class PostpartumMemberTrack(WeeklyMemberTrackMixin, MemberTrack):
    __tablename__ = "member_track"
    __mapper_args__ = {"polymorphic_identity": TrackName.POSTPARTUM}
    __table_args__ = {"extend_existing": True}  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Dict[str, bool]", base class "MemberTrack" defined the type as "Tuple[Index]")

    # TODO: [Tracks] ch13164
    _WEEK_OFFSET = 39

    def _calculate_anchor_date(self) -> Optional[date]:
        return self.user.health_profile.last_child_birthday

    def set_scheduled_end_date(self, scheduled_end_date: date) -> None:
        raise NotImplementedError(
            "Postpartum does not support setting scheduled end date"
        )


class PartnerPostpartumMemberTrack(PostpartumMemberTrack):
    __tablename__ = "member_track"
    __mapper_args__ = {"polymorphic_identity": TrackName.PARTNER_NEWPARENT}
    __table_args__ = {"extend_existing": True}  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Dict[str, bool]", base class "MemberTrack" defined the type as "Tuple[Index]")


# -- "Static" tracks, with only one phase.


class StaticMemberTrackMixin:
    # instance level cache of initial_phase
    _cached_initial_phase: MemberTrackPhase | None = None

    @property
    def initial_phase(self: MemberTrack) -> MemberTrackPhase:
        if self._cached_initial_phase:
            return self._cached_initial_phase

        self._cached_initial_phase = MemberTrackPhase(
            member_track=self,
            name=PhaseNamePrefix.STATIC.value,
            display_name=PhaseNamePrefix.STATIC.value,
            started_at=self.anchor_date,
            ended_at=self.ended_at and self.ended_at.date(),
        )
        return self._cached_initial_phase

    def phase_at(self, _) -> "MemberTrackPhase":  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        return self.initial_phase

    @property
    def final_phase(self: MemberTrack) -> MemberTrackPhase | None:
        # no need to cache this property since self.initial_phase is already cached
        return self.initial_phase if self.ended_at else None

    @property
    def phase_history(self) -> Sequence[MemberTrackPhase]:
        # no need to cache this property since self.initial_phase is already cached
        return [self.initial_phase]

    @property
    def total_phases(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # Added for correctness, not used anywhere yet
        return 1


class BMSMemberTrack(StaticMemberTrackMixin, MemberTrack):
    __tablename__ = "member_track"
    __mapper_args__ = {"polymorphic_identity": TrackName.BREAST_MILK_SHIPPING}
    __table_args__ = {"extend_existing": True}  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Dict[str, bool]", base class "MemberTrack" defined the type as "Tuple[Index]")


class GenericMemberTrack(StaticMemberTrackMixin, MemberTrack):
    __tablename__ = "member_track"
    __mapper_args__ = {"polymorphic_identity": TrackName.GENERIC}
    __table_args__ = {"extend_existing": True}  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Dict[str, bool]", base class "MemberTrack" defined the type as "Tuple[Index]")


class PregnancyOptionsTrack(StaticMemberTrackMixin, MemberTrack):
    __tablename__ = "member_track"
    __mapper_args__ = {"polymorphic_identity": TrackName.PREGNANCY_OPTIONS}
    __table_args__ = {"extend_existing": True}  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Dict[str, bool]", base class "MemberTrack" defined the type as "Tuple[Index]")


class ParentingMemberTrack(WeeklyMemberTrackMixin, MemberTrack):
    __tablename__ = "member_track"
    __mapper_args__ = {"polymorphic_identity": TrackName.PARENTING_AND_PEDIATRICS}
    __table_args__ = {"extend_existing": True}  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Dict[str, bool]", base class "MemberTrack" defined the type as "Tuple[Index]")


class PregnancyLossMemberTrack(WeeklyMemberTrackMixin, MemberTrack):
    __tablename__ = "member_track"
    __mapper_args__ = {"polymorphic_identity": TrackName.PREGNANCYLOSS}
    __table_args__ = {"extend_existing": True}  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Dict[str, bool]", base class "MemberTrack" defined the type as "Tuple[Index]")


class SponsoredMemberTrack(StaticMemberTrackMixin, MemberTrack):
    __tablename__ = "member_track"
    __mapper_args__ = {"polymorphic_identity": TrackName.SPONSORED}
    __table_args__ = {"extend_existing": True}  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Dict[str, bool]", base class "MemberTrack" defined the type as "Tuple[Index]")


class SurrogacyMemberTrack(WeeklyMemberTrackMixin, MemberTrack):
    __tablename__ = "member_track"
    __mapper_args__ = {"polymorphic_identity": TrackName.SURROGACY}
    __table_args__ = {"extend_existing": True}  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Dict[str, bool]", base class "MemberTrack" defined the type as "Tuple[Index]")


@dataclass
class MemberTrackPhase:
    """A 'phase' is a single unit-of-time useful mostly for grouping user content.

    It can also be used to associate user behavior with a certain period within a track.
    """

    __slots__ = ("member_track", "name", "display_name", "started_at", "ended_at")

    member_track: MemberTrack
    name: str
    display_name: str
    started_at: date
    ended_at: date | None

    # instance level cache of allowed_resources
    _cached_allowed_resources: Sequence[Resource] | None = field(
        init=False,
        repr=False,
        default=None,
    )

    @property
    def allowed_resources(self) -> Sequence[Resource]:
        if self._cached_allowed_resources:
            return self._cached_allowed_resources

        self._cached_allowed_resources = get_resources_for_track_phase(
            self.member_track.name, self.name  # type: ignore[arg-type] # Argument 1 to "get_resources_for_track_phase" has incompatible type "str"; expected "TrackName"
        )
        return self._cached_allowed_resources

    @property
    def module_id(self) -> int:
        return self.member_track.legacy_module_id  # type: ignore[return-value] # Incompatible return value type (got "Optional[int]", expected "int")

    @property
    def legacy_program_phase_id(self) -> Optional[int]:
        return None

    def to_table_mapping(self) -> dict:
        """Useful for writing data in bulk for reporting purposes.

        Examples:
            >>> track = MemberTrack.query.get(1)
            >>> history = [p.to_table_mapping() for p in track.phase_history()]
            >>> db.session.bulk_write_mappings(MemberTrackPhaseReporting, history)
        """
        mapping = asdict(self)
        mapping["member_track_id"] = self.member_track.id
        return mapping


class MemberTrackPhaseReporting(TimeLoggedModelBase):
    """An ORM description for historical reporting of a MemberTrack's phase history.

    Notes:
        Should *not* be used in normal application runtime.
    """

    __tablename__ = "member_track_phase"

    id = Column(Integer, primary_key=True)
    member_track_id = Column(Integer, ForeignKey("member_track.id"), nullable=False)
    member_track = relationship("MemberTrack")
    name = Column(String(120), nullable=False)
    started_at = Column(Date, nullable=False)
    ended_at = Column(Date)
    legacy_program_phase_id = Column(
        Integer, ForeignKey("care_program_phase.id"), nullable=True
    )
    legacy_program_phase = relationship("CareProgramPhase")


class MemberTrackStatusName(str, enum.Enum):
    QUALIFIED_FOR_RENEWAL = "qualified_for_renewal"
    SCHEDULED_FOR_RENEWAL = "scheduled_for_renewal"
    RENEWED = "renewed"


class MemberTrackStatus(TimeLoggedModelBase):
    __tablename__ = "member_track_status"

    id = Column(Integer, primary_key=True)
    member_track_id = Column(Integer, ForeignKey("member_track.id"), nullable=False)
    member_track = relationship("MemberTrack")
    status = Column(Enum(MemberTrackStatusName, native_enum=False), nullable=False)

    def __repr__(self) -> str:
        return f"<MemberTrackStatus[{self.id}] {self.status.name}>"  # type: ignore[attr-defined] # "str" has no attribute "name"

    @validates("status")
    def validate_status(self, key, status):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return MemberTrackStatusName(status)
