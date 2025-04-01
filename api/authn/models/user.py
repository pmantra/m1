from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, Iterable, Optional, Set
from warnings import warn

import ddtrace
import pycountry
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    FetchedValue,
    ForeignKey,
    Integer,
    String,
    and_,
    case,
    event,
    inspect,
    select,
)
from sqlalchemy.engine.base import Connection
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapper, joinedload, relationship, validates

import geography
from authz.models.roles import ROLES
from common import stats
from geography.repository import CountryRepository
from health.data_models.member_risk_flag import MemberRiskFlag
from health.data_models.risk_flag import RiskFlag
from health.models.health_profile import HealthProfile
from messaging.services.zendesk_client import IdentityType
from models import base
from models.base import db
from models.products import Product
from utils.data import PHONE_NUMBER_LENGTH
from utils.log import logger
from utils.log_model_usage import log_model_usage
from utils.primitive_threaded_cached_property import primitive_threaded_cached_property
from wallet.models.member_benefit import MemberBenefit

# These will cause a circular imports at run-time but are valid for static type-checking
if TYPE_CHECKING:
    from models.enterprise import Organization
    from models.profiles import (
        Agreement,
        MemberProfile,
        OrganizationAgreement,
        PractitionerProfile,
    )

log = logger(__name__)

LIFE_STAGES = [
    {
        "id": 1,
        "weight": 1,
        "image": "life-stage-1",
        "name": "pregnant",
        "subtitle": "",
        "title": "I'm Pregnant",
    },
    {
        "id": 2,
        "weight": 2,
        "image": "life-stage-2",
        "name": "new-mom",
        "subtitle": "With a baby under 24 months",
        "title": "I'm A New Mom",
    },
]

# NOTE: both are deprecated
REDIS_API_KEYS_HOST = "redis"
REDIS_SESSIONS_HOST = "redis"


class MFAState(enum.Enum):
    DISABLED = "disabled"
    # MFA should be on for this user, but the user needs to complete verification.
    PENDING_VERIFICATION = "pending_verification"
    # MFA has fully set up (enabled and verified).
    ENABLED = "enabled"


class User(base.ModelBase):
    __tablename__ = "user"
    __restricted_columns__ = frozenset(["api_key", "password", "otp_secret"])

    id = Column(Integer, primary_key=True)
    esp_id = Column(
        String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4())
    )
    first_name = Column(String(40))
    middle_name = Column(String(40))
    last_name = Column(String(40))
    username = Column(String(100), unique=True)

    active = Column(Boolean, nullable=False, default=True)
    email_confirmed = Column(Boolean, nullable=False, default=False)

    email = Column(String(120), unique=True, nullable=False)
    password = Column(String(120), nullable=False)
    api_key = Column(String(80), unique=True, default=lambda: str(uuid.uuid4()))

    created_at = Column(DateTime, server_default=FetchedValue())
    modified_at = Column(
        DateTime, server_default=FetchedValue(), server_onupdate=FetchedValue()
    )

    image_id = Column(Integer, ForeignKey("image.id"))
    image = relationship("Image")

    zendesk_user_id = Column(BigInteger, unique=True)

    schedule = relationship("Schedule", back_populates="user", uselist=False)

    member_benefit = relationship(MemberBenefit, back_populates="member", uselist=False)

    health_profile = relationship(
        HealthProfile,
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    timezone = Column(String(128), nullable=False, default="UTC")

    otp_secret = Column(String(16), nullable=True)
    care_team = association_proxy("practitioner_associations", "practitioner_profile")

    # MFA settings
    mfa_state = Column(Enum(MFAState), default=MFAState.DISABLED, nullable=False)
    sms_phone_number = Column(String(PHONE_NUMBER_LENGTH))
    authy_id = Column(Integer(), nullable=True, doc="The Twilio Authy user ID")

    practitioner_profile = relationship(
        "PractitionerProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="joined",
    )
    member_profile = relationship(
        "MemberProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="joined",
    )
    roles = relationship(
        "Role", secondary="role_profile", back_populates="users", lazy="joined"
    )

    install_attribution = relationship(
        "UserInstallAttribution", backref="user", uselist=False
    )
    current_program = relationship(
        "CareProgram",
        primaryjoin=lambda: User.current_program_join_expression(),
        uselist=False,
    )
    member_tracks = relationship(
        "MemberTrack", back_populates="user", cascade="all, delete-orphan"
    )

    # BEGIN DEPRECATED CODE
    current_member_track = relationship(
        "MemberTrack",
        primaryjoin=lambda: User.current_track_join_expression(),
        uselist=False,
    )
    """DEPRECATED: members can have multiple tracks. Use user.active_tracks instead"""
    # END DEPRECATED CODE

    active_tracks = relationship(
        "MemberTrack",
        uselist=True,
        viewonly=True,
        primaryjoin=lambda: User.active_tracks_join_expression(),
        order_by="MemberTrack.created_at",
    )
    active_client_track = relationship(
        "ClientTrack",
        uselist=False,
        viewonly=True,
        secondary="member_track",
        primaryjoin=lambda: User.active_tracks_join_expression(),
        secondaryjoin="MemberTrack.client_track_id == ClientTrack.id",
        order_by="MemberTrack.created_at.desc()",
    )
    inactive_tracks = relationship(
        "MemberTrack",
        uselist=True,
        viewonly=True,
        primaryjoin=lambda: User.inactive_tracks_join_expression(),
        order_by="MemberTrack.ended_at.desc()",
    )
    scheduled_tracks = relationship(
        "MemberTrack",
        uselist=True,
        viewonly=True,
        primaryjoin=lambda: User.scheduled_tracks_join_expression(),
    )

    onboarding_state = relationship(
        "UserOnboardingState", back_populates="user", uselist=False
    )

    webinars = association_proxy(
        "webinar_association",
        "webinar",
        creator=lambda x: User.user_webinar_expression(x),
    )

    organization_employee = relationship(
        "OrganizationEmployee",
        secondary="user_organization_employee",
        secondaryjoin=lambda: User.organization_employee_join_expression(),
        order_by="UserOrganizationEmployee.id.desc()",
        uselist=False,
    )

    user_organization_employees = relationship(
        "UserOrganizationEmployee", back_populates="user", cascade="all, delete-orphan"
    )

    _profiles_map = None

    def __repr__(self) -> str:
        return f"<User[{self.id}] {'active' if self.active else 'inactive'}>"

    __str__ = __repr__

    @property
    def is_employee_with_maven_benefit(self) -> bool:
        """Currently the known way to determine whether this user is the actual employee
        who is receiving the Maven Wallet benefit from the user's employer.

        Returns:
            bool: Whether this user is the employee directly recieving the benefit
        """
        return bool(self.active_tracks) and any(
            track.is_employee for track in self.active_tracks
        )

    @property
    def full_name(self) -> str:
        return f"{self.first_name or ''} {self.last_name or ''}".strip()

    @validates("image_id")
    def validate_image_id(self, key, image_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        log.debug("Setting image for user.", image_id=image_id, user_id=self.id)
        return image_id

    @property
    def country_code(self) -> str | None:
        return self.profile and self.profile.country_code

    @property
    def country(self) -> geography.repository.Country | None:
        return CountryRepository(session=db.session).get(country_code=self.country_code)  # type: ignore[arg-type] # Argument "country_code" to "get" of "CountryRepository" has incompatible type "Optional[str]"; expected "str"

    @property
    def normalized_country_abbr(self) -> str:
        """
        null country value indicates a US user (probably because they were created
        before countries were added and never backfilled)
        """
        if self.profile and self.profile.country_code:
            return self.profile.country_code

        return "US"

    @property
    def profiles_map(self) -> dict[str, MemberProfile | PractitionerProfile]:
        if self._profiles_map is None:
            profiles_data = {}
            member = self.member_profile
            if member:
                profiles_data[member.role.name] = member
            practitioner = self.practitioner_profile
            if practitioner:
                profiles_data[practitioner.role.name] = practitioner

            self._profiles_map = profiles_data  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Dict[Any, MemberProfile]", variable has type "None")

        return self._profiles_map  # type: ignore[return-value] # Incompatible return value type (got "None", expected "Dict[str, Union[MemberProfile, PractitionerProfile]]")

    @property
    def user_types(self) -> Set[str]:
        types = {r.name for r in self.roles}
        if self.practitioner_profile:
            types.add(self.practitioner_profile.role.name)
        if self.member_profile:
            types.add(self.member_profile.role.name)
        return types

    @property
    def profile(self) -> PractitionerProfile | MemberProfile | None:
        return self.practitioner_profile or self.member_profile

    @primitive_threaded_cached_property
    def date_of_birth(self) -> str | None:
        """
        Returns the date of birth (YYYY-MM-DD) if it is stored in the
        member's profile. Returns None otherwise.
        """
        return (
            self.health_profile
            and (  # type: ignore[return-value] # Incompatible return value type (got "Union[HealthProfile, date, Any]", expected "Optional[str]")
                self.health_profile.date_of_birth
                or self.health_profile.json.get("birthday", None)
            )
        )

    @property
    def role_name(self) -> str | None:
        if self.practitioner_profile:
            return self.practitioner_profile.role.name
        if self.member_profile:
            return self.member_profile.role.name

        log.warning("No ROLE for user.", user_id=self.id)
        return None  # explicitly returns

    @property
    def identities(self) -> list[str]:
        _identities = []
        if self.is_practitioner:
            _identities.append(ROLES.practitioner)
            if self.is_care_coordinator:
                _identities.append(ROLES.care_coordinator)
        else:
            _identities.append(ROLES.member)

        return _identities

    @classmethod
    def current_track_expression(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        from models.tracks.member_track import MemberTrack, TrackName  # noqa: F811

        return (
            select([MemberTrack.id])
            .where((MemberTrack.user_id == cls.id) & (MemberTrack.active.is_(True)))
            .limit(1)
            # BEGIN DIRTY HACK
            # While we phase out usages of `current_member_track`, it's helpful to have
            # it return a consistent track. To that end, this will ALWAYS return the
            # non-P&P track if there is one.
            .order_by(
                case(
                    {TrackName.PARENTING_AND_PEDIATRICS.value: 1},
                    value=MemberTrack.name,
                    else_=0,
                ),
                MemberTrack.created_at,
            )
            # END DIRTY HACK
            .correlate(cls)  # type: ignore[arg-type] # Argument 1 to "correlate" of "Select" has incompatible type "Type[User]"; expected "FromClause"
            .as_scalar()
            .label("current_track_id")
        )

    @classmethod
    def current_track_join_expression(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        from models.tracks.member_track import MemberTrack  # noqa: F811

        return (cls.id == MemberTrack.user_id) & (
            MemberTrack.id == cls.current_track_expression()
        )

    @classmethod
    def current_program_expression(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        from models.programs import CareProgram  # noqa: F811

        return (
            select([CareProgram.id])
            .where((CareProgram.user_id == cls.id) & (CareProgram.ended_at == None))
            .limit(1)
            .correlate(cls)  # type: ignore[arg-type] # Argument 1 to "correlate" of "Select" has incompatible type "Type[User]"; expected "FromClause"
            .as_scalar()
            .label("current_program_id")
        )

    @classmethod
    def current_program_join_expression(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        from models.programs import CareProgram  # noqa: F811

        return (cls.id == CareProgram.user_id) & (
            CareProgram.id == cls.current_program_expression()
        )

    @classmethod
    def active_tracks_join_expression(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        from models.tracks.member_track import MemberTrack  # noqa: F811

        return (cls.id == MemberTrack.user_id) & MemberTrack.active

    @classmethod
    def inactive_tracks_join_expression(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        from models.tracks.member_track import MemberTrack  # noqa: F811

        return (cls.id == MemberTrack.user_id) & MemberTrack.inactive

    @classmethod
    def scheduled_tracks_join_expression(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        from models.tracks.member_track import MemberTrack  # noqa: F811

        return (cls.id == MemberTrack.user_id) & MemberTrack.scheduled

    @property
    def default_product(self) -> Product | None:
        active_products = [p for p in self.products if p.is_active]
        if not active_products:
            return None
        Product.sort_products_by_price(active_products)
        return active_products[0]

    @classmethod
    def organization_employee_join_expression(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        from models.enterprise import OrganizationEmployee, UserOrganizationEmployee

        return and_(
            User.id == UserOrganizationEmployee.user_id,
            OrganizationEmployee.id
            == UserOrganizationEmployee.organization_employee_id,
            UserOrganizationEmployee.ended_at.is_(None),
        )

    @property
    @ddtrace.tracer.wrap()
    def is_enterprise(self) -> bool:
        warn(
            "#engineering This method is deprecated",
            DeprecationWarning,
            stacklevel=2,
        )
        # TODO: [multitrack] Use self.active_tracks
        # Avoid circular import
        from eligibility.utils import verification_utils  # noqa: F811

        has_oe = self.organization_employee is not None
        has_member_track = self.current_member_track is not None
        old_val = has_oe and has_member_track
        new_val = has_member_track

        if not verification_utils.is_oe_deprecated_for_user_enterprise():
            return old_val

        if new_val != old_val:
            stats.increment(
                metric_name="mono.oe_deprecation.user.is_enterprise.mismatch",
                pod_name=stats.PodNames.ELIGIBILITY,
                tags=[
                    f"user_id:{self.id}",
                    f"has_oe:{has_oe}",
                    f"has_member_track:{has_member_track}",
                ],
            )
            log.info(
                "user is_enterprise mis-match",
                user_id=self.id,
                old_val=old_val,
                new_val=new_val,
                organization_employee_id=(
                    self.organization_employee.id if self.organization_employee else -1
                ),
            )

        if verification_utils.is_oe_deprecated_for_user_enterprise():
            return new_val
        return old_val

    @hybrid_property
    def is_practitioner(self) -> bool:
        return self.practitioner_profile is not None

    @is_practitioner.expression  # type: ignore[no-redef] # Name "is_practitioner" already defined on line 526
    def is_practitioner(cls) -> bool:
        from models.profiles import PractitionerProfile

        return PractitionerProfile.user_id == cls.id

    @hybrid_property
    def is_member(self) -> bool:
        return self.member_profile is not None and not self.is_practitioner

    @is_member.expression  # type: ignore[no-redef] # Name "is_member" already defined on line 536
    def is_member(cls) -> bool:
        from models.profiles import MemberProfile

        return MemberProfile.user_id == cls.id and not cls.is_practitioner

    @property
    def is_care_coordinator(self) -> bool:
        return self.is_practitioner and self.practitioner_profile.is_cx

    @property
    def organization(self) -> Optional["Organization"]:
        from eligibility.utils import verification_utils

        warn(
            "organization is deprecated. Use organization_v2 instead.",
            DeprecationWarning,
        )

        # Measure time for entire comparison operation
        with stats.timed(
            metric_name="mono.oe_deprecation.organization.duration",
            pod_name=stats.PodNames.ELIGIBILITY,
            tags=[
                f"compare_enabled:{verification_utils.is_organization_compare_enabled()}"
            ],
        ):
            org_v1 = (
                self.organization_employee.organization
                if self.organization_employee
                else None
            )

            # Skip comparison if FF is disabled
            if not verification_utils.is_organization_compare_enabled():
                return org_v1

            org_v2 = self.organization_v2

            if org_v1 != org_v2:
                suffix = "no_org_v2" if org_v2 is None else "no_org_v1"
                stats.increment(
                    metric_name=f"mono.oe_deprecation.user.organization.mismatch.{suffix}",
                    pod_name=stats.PodNames.ELIGIBILITY,
                    tags=[f"user_id:{self.id}"],
                )

                log.info(
                    "user organization mis-match",
                    user_id=self.id,
                    org_v1_id=org_v1.id if org_v1 else -1,
                    org_v2_id=org_v2.id if org_v2 else -1,
                    organization_employee_id=self.organization_employee.id
                    if self.organization_employee
                    else -1,
                )

            # Check feature flag to determine which value to return
            if verification_utils.is_organization_deprecation_enabled():
                return org_v2
            return org_v1

    @property
    def organization_v2(self) -> Optional["Organization"]:
        # Avoiding circular import
        from tracks import service as tracks_svc

        track_svc = tracks_svc.TrackSelectionService()
        organization = track_svc.get_organization_for_user(user_id=self.id)
        return organization

    @property
    def care_team_with_type(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        from models.profiles import MemberPractitionerAssociation

        if not self.is_member:
            return []
        return MemberPractitionerAssociation.care_team_for_user(self.id)

    @property
    def care_coordinators(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        from models.profiles import CareTeamTypes

        coordinators = []
        if self.care_team:
            coordinators = [
                ct[0]
                for ct in self.care_team_with_type
                if ct[1] == CareTeamTypes.CARE_COORDINATOR.value
            ]
        return coordinators

    @property
    def avatar_url(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.image_id:
            return self.image.asset_url(height=500, width=500)

    def capabilities(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Use sparingly - it's expensive!!
        """
        capabilities = []

        for role in self.roles:
            capabilities.extend(role.capabilities)
        if self.practitioner_profile:
            capabilities.extend(self.practitioner_profile.role.capabilities)
        if self.member_profile:
            capabilities.extend(self.member_profile.role.capabilities)

        return capabilities

    def is_anonymous(self) -> bool:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return not bool(self.id and self.email)

    def is_authenticated(self) -> bool:
        return self.active and bool(self.id)

    def is_active(self) -> bool:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.active

    def get_id(self) -> str:
        return str(self.id)

    def rotate_api_key(self) -> None:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        log.info("Revoking api key from redis.", user_id=self.id)
        if self.api_key is None:
            log.error("Encountered null API key for a user.", user_id=self.id)
            return

        log.info("Recording new api key on user record.", user_id=self.id)
        self.api_key = str(uuid.uuid4())
        db.session.add(self)
        db.session.commit()

    @property
    def api_key_ttl(self) -> int:
        if self.is_practitioner:
            return 60 * 60 * 72  # 72 hours
        elif self.is_enterprise:
            try:
                org = self.organization
                # Get the session ttl off the org setting
                return org.session_ttl * 60  # type: ignore[union-attr] # Item "None" of "Optional[Organization]" has no attribute "session_ttl"
            except Exception as e:
                log.error(
                    "Error finding organization.session_ttl", err=e, user_id=self.id
                )
                return 60 * 10  # 10 minutes
        else:
            return 60 * 60 * 24 * 7  # 7 days for marketplace

    @property
    def api_key_with_ttl(self) -> str:
        return f"ttl-{self.api_key_ttl}:{self.api_key}"

    @property
    def test_group(self) -> str:
        """
        This property is deprecated.
        Incentives are now configured using the following models:
        - Incentive
        - IncentiveOrganization
        - IncentiveFulfillment
        """
        return None  # type: ignore[return-value] # Incompatible return value type (got "None", expected "str")

    def add_practitioner_to_care_team(self, practitioner_id, _type):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Add a practitioner to user's (self) care team
        :param practitioner_id: practitioner's user id
        :param _type: CareTeamTypes ENUM type
        """
        from models.profiles import MemberPractitionerAssociation

        log.info(
            "Current care team",
            practitioner_associations=self.practitioner_associations,
        )
        existing = [
            (ps.user_id, ps.practitioner_id, ps.type)
            for ps in self.practitioner_associations
        ]
        if (self.id, practitioner_id, _type) in existing:
            log.debug(
                "Practitioner[%s] is already in Member[%s]'s care team via %s",
                practitioner_id,
                self.id,
                _type,
            )
            return
        mpa = MemberPractitionerAssociation(
            user_id=self.id, practitioner_id=practitioner_id, type=_type
        )
        self.practitioner_associations.append(mpa)
        db.session.add(self)
        log.info(
            "Adding Practitioner to Member's care team",
            practitioner_id=practitioner_id,
            user_id=self.id,
        )
        return mpa

    def add_care_team_via_appointment(self, appointment) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation
        from models.profiles import CareTeamTypes

        self.add_practitioner_to_care_team(
            appointment.practitioner.id, CareTeamTypes.APPOINTMENT
        )

    def add_track_onboarding_care_team_member(self, practitioner_id, member_track=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        from models.profiles import CareTeamTypes

        # Type is QUIZ because these used to be assigned after onboarding assessment completion
        # TODO: Change to be something more tracky
        mpa = self.add_practitioner_to_care_team(practitioner_id, CareTeamTypes.QUIZ)
        if member_track and mpa:
            mpa.member_track_id = member_track.id

    def replace_care_team_via_quiz(self, practitioners):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        from models.profiles import CareTeamTypes, MemberPractitionerAssociation

        existing_practitioners = MemberPractitionerAssociation.query.filter_by(
            user_id=self.id, type=CareTeamTypes.QUIZ.value
        )
        existing_practitioners.delete(synchronize_session="fetch")
        log.info(
            "Deleting rows in MemberPractitionerAssociation",
            user_id=self.id,
        )
        for practitioner in practitioners:
            self.add_track_onboarding_care_team_member(practitioner.id)

    def add_care_team_via_care_coordination(self, practitioner_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        from models.profiles import CareTeamTypes

        self.add_practitioner_to_care_team(
            practitioner_id, CareTeamTypes.CARE_COORDINATOR
        )

    # Used only to link to CA dashboard (pink page) from member profile admin page
    def last_care_advocate_appointment(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.is_member:
            return next(
                (
                    a
                    for a in sorted(
                        self.schedule.appointments, reverse=True, key=lambda a: a.id
                    )
                    if a.practitioner.is_care_coordinator
                ),
                None,
            )

    def current_risk_flags(self) -> Iterable[RiskFlag]:
        member_risks = self.get_member_risks(True, False)
        return [obj.risk_flag for obj in member_risks]

    def get_member_risks(
        self, active_only: bool = False, track_relevant_only: bool = False
    ) -> Iterable[MemberRiskFlag]:
        from health.services.member_risk_service import MemberRiskService

        service = MemberRiskService(self.id)
        return service.get_member_risks(active_only, track_relevant_only)

    # instance cache for fetched pending_organization_agreements
    _cached_pending_organization_agreements: list[Agreement] | None = None

    def get_pending_organization_agreements(
        self, organization_ids: Set[int]
    ) -> list[Agreement]:
        """
        Get a list of pending agreements for the User with given organizations.
        An agreement is pending if we do not have a corresponding AgreementAcceptance.
        Only includes agreements that are tied to the User's specific organization.
        @return: list of Agreements that have yet to be agreed to that are specific to this User related Organization(s)
        """
        if self._cached_pending_organization_agreements is not None:
            return self._cached_pending_organization_agreements

        if not organization_ids:
            return []

        pending_agreements: list[Agreement] = self._all_pending_agreements
        pending_org_agreements: list[OrganizationAgreement] = []
        for agreement in pending_agreements:
            org_agreements: list[
                OrganizationAgreement
            ] = agreement.organization_agreements

            agreement_org_ids = {oa.organization_id for oa in org_agreements}

            if bool(organization_ids.intersection(agreement_org_ids)):
                pending_org_agreements.append(agreement)

        self._cached_pending_organization_agreements = pending_org_agreements
        return self._cached_pending_organization_agreements

    # instance cache for fetched pending_user_agreements
    _cached_pending_user_agreements: list[Agreement] | None = None

    @property
    def pending_user_agreements(self) -> list[Agreement]:
        """
        Get a list of pending agreements for the User.
        An agreement is pending if we do not have a corresponding AgreementAcceptance.
        Only includes agreements that are not tied to a specific organization.
        @return: list of Agreements that have yet to be agreed to that are specific to an Organization
        """
        # use the previously fetched list if it exists
        if self._cached_pending_user_agreements is not None:
            return self._cached_pending_user_agreements

        pending_agreements = [
            agreement
            for agreement in self._all_pending_agreements
            if not agreement.organization_agreements
        ]
        self._cached_pending_user_agreements = pending_agreements
        return self._cached_pending_user_agreements

    # instance cache for fetched _all_pending_agreements
    _cached_all_pending_agreements: list[Agreement] | None = None

    @property
    def _all_pending_agreements(self) -> list[Agreement]:
        """
        Retrieve all pending agreements for the user

        An agreement is pending if there is a newer version of the agreement
        in the language that was most recently agreed to. If there is a newer
        version, return the most recent English version*.

        *We are returning the English version upon request from Legal
        """
        # use the previously fetched list if it exists
        if self._cached_all_pending_agreements is not None:
            return self._cached_all_pending_agreements

        from models.profiles import Agreement, AgreementAcceptance, Language

        all_agreement_types_for_user = Agreement.get_agreements(self)

        if not all_agreement_types_for_user:
            self._cached_all_pending_agreements = []
            return self._cached_all_pending_agreements

        # Eagerly load language and organization_agreements to avoid N+1 queries
        all_agreements = (
            Agreement.query.options(
                joinedload(Agreement.language),
                joinedload(Agreement.organization_agreements),
            )
            .filter(Agreement.name.in_(all_agreement_types_for_user))
            .all()
        )
        all_agreement_acceptances = AgreementAcceptance.query.filter(
            AgreementAcceptance.user_id == self.id
        ).all()

        all_recorded_agreements_ids = [
            a.agreement_id for a in all_agreement_acceptances
        ]
        all_recorded_agreements = [
            a for a in all_agreements if a.id in all_recorded_agreements_ids
        ]
        pending_agreements: list[Agreement] = []
        for agreement_name in all_agreement_types_for_user:
            all_versions = [a for a in all_agreements if a.name == agreement_name]
            eng_versions = [
                a
                for a in all_versions
                if a.language is None or a.language.name == Language.ENGLISH
            ]

            if len(eng_versions) == 0:
                continue

            latest_eng_version = sorted(
                eng_versions, key=lambda a: a.version, reverse=True
            )[0]

            all_recorded_versions = [
                a for a in all_recorded_agreements if a.name == agreement_name
            ]

            # if no acceptances, include the latest English version of this agreement
            if len(all_recorded_versions) == 0:
                pending_agreements.append(latest_eng_version)
                continue

            latest_recorded_version = sorted(
                all_recorded_versions, key=lambda a: a.version, reverse=True
            )[0]

            if (
                latest_recorded_version.language is None
                or latest_recorded_version.language.name == Language.ENGLISH
            ):
                latest_version_of_latest_recorded_version_language = latest_eng_version
            else:
                lang_versions = [
                    a
                    for a in all_versions
                    if a.language is not None
                    and a.language.name == latest_recorded_version.language.name
                ]
                latest_version_of_latest_recorded_version_language = sorted(
                    lang_versions, key=lambda a: a.version, reverse=True
                )[0]

            # if there is a more recent version in the language of the most recently accepted version,
            # return the latest English version of this agreement
            if (
                latest_version_of_latest_recorded_version_language.version
                > latest_recorded_version.version
            ):
                pending_agreements.append(latest_eng_version)

            # else, this agreement is not pending
        self._cached_all_pending_agreements = pending_agreements
        return self._cached_all_pending_agreements

    @classmethod
    def user_webinar_expression(cls, x):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        from models.zoom import UserWebinar

        return UserWebinar(webinar=x)

    @property
    def subdivision(self) -> Optional[pycountry.Subdivision]:
        if self.subdivision_code:
            return pycountry.subdivisions.get(code=self.subdivision_code)
        return  # type: ignore[return-value] # Return value expected


# Some models excluded because they are producing too many custom events,
# and we are already tracking these for migration elsewhere
_USER_MODEL_EXCLUSIONS = frozenset(
    [
        "/api/messaging/models/messaging.py",
        "/api/appointments/models/appointment.py",
        "/api/appointments/resources/booking.py",
        "/api/common/services/api.py",
        "/api/models/profiles.py",
        "/api/views/profiles.py",
    ]
)

_USER_MODEL_DEPRECATION = (
    "The user model has been deprecated. Use Profile models instead."
)


@event.listens_for(User, "after_update")
def update_zendesk_user_on_attrs_update(
    mapper: Mapper,
    connection: Connection,
    target: User,
) -> None:
    # avoid circular import
    from messaging.services.zendesk import (
        should_update_zendesk_user_profile,
        update_zendesk_user,
    )

    # determine whether any of the User's attributes that we propagate to zd was updated
    email_updated = inspect(target).get_history("email", True).has_changes()
    first_name_updated = inspect(target).get_history("first_name", True).has_changes()
    last_name_updated = inspect(target).get_history("last_name", True).has_changes()
    full_name_updated = first_name_updated or last_name_updated

    # determine whether changes have been detected and the user is a member
    user_attrs_updated = email_updated or full_name_updated
    if (
        user_attrs_updated and target.is_member
    ) and should_update_zendesk_user_profile():
        log.info(
            "Updating Zendesk Profile for user due to an updated attribute",
            user_id=target.id,
            email_updated=email_updated,
            full_name_updated=full_name_updated,
        )

        # update the profile with the new email
        update_zendesk_user.delay(
            user_id=target.id,
            update_identity=IdentityType.EMAIL
            if email_updated
            else IdentityType.NAME
            if full_name_updated
            else "",
            team_ns="virtual_care",
            caller="update_zendesk_user_on_attrs_update",
        )


@event.listens_for(User, "init")
def receive_init(target, args, kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log_model_usage(
        "User",
        exclude_files=_USER_MODEL_EXCLUSIONS,  # type: ignore[arg-type] # Argument "exclude_files" to "log_model_usage" has incompatible type "FrozenSet[str]"; expected "Optional[Set[str]]"
        pod_name=stats.PodNames.CORE_SERVICES,
        deprecation_warning=_USER_MODEL_DEPRECATION,
    )


@event.listens_for(User, "load")
def receive_load(target, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log_model_usage(
        "User",
        exclude_files=_USER_MODEL_EXCLUSIONS,  # type: ignore[arg-type] # Argument "exclude_files" to "log_model_usage" has incompatible type "FrozenSet[str]"; expected "Optional[Set[str]]"
        pod_name=stats.PodNames.CORE_SERVICES,
        deprecation_warning=_USER_MODEL_DEPRECATION,
    )


# Temporary solution for updating the profiles with changes to the User
# Once we remove the reliance on the User fields, these will be removed
@event.listens_for(User.first_name, "set")
def update_profiles_first_name(target: User, value, old_value, initiator):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    _update_profiles(target, "first_name", value)


@event.listens_for(User.last_name, "set")
def update_profiles_last_name(target: User, value, old_value, initiator):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    _update_profiles(target, "last_name", value)


@event.listens_for(User.middle_name, "set")
def update_profiles_middle_name(target: User, value, old_value, initiator):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    _update_profiles(target, "middle_name", value)


@event.listens_for(User.zendesk_user_id, "set")
def update_profiles_zendesk_user_id(target: User, value, old_value, initiator):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    _update_profiles(target, "zendesk_user_id", value)


@event.listens_for(User.esp_id, "set")
def update_profiles_esp_id(target: User, value, old_value, initiator):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    _update_profiles(target, "esp_id", value)


def _update_profiles(target: User, attribute: str, value):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    if target.member_profile:
        setattr(target.member_profile, attribute, value)
    if target.practitioner_profile:
        setattr(target.practitioner_profile, attribute, value)
