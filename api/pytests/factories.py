import datetime
import json
import random
import time
from typing import Dict, Iterable, Optional

import factory
from factory.alchemy import SQLAlchemyModelFactory
from faker import Faker
from faker.proxy import UniqueProxy
from sqlalchemy import desc, inspect

from appointments.models.appointment import Appointment
from appointments.models.appointment_meta_data import AppointmentMetaData
from appointments.models.availability_notification_request import (
    AvailabilityNotificationRequest,
)
from appointments.models.cancellation_policy import CancellationPolicy
from appointments.models.constants import (
    PRIVACY_CHOICES,
    AppointmentMetaDataTypes,
    AppointmentTypes,
    ScheduleFrequencies,
    ScheduleStates,
)
from appointments.models.member_appointment import MemberAppointmentAck
from appointments.models.needs_and_categories import (
    Need,
    NeedAppointment,
    NeedCategory,
    NeedCategoryTrack,
    NeedRestrictedVertical,
    NeedTrack,
    NeedVertical,
)
from appointments.models.payments import (
    Credit,
    FeeAccountingEntry,
    FeeAccountingEntryTypes,
    Invoice,
)
from appointments.models.practitioner_appointment import PractitionerAppointmentAck
from appointments.models.reschedule_history import RescheduleHistory
from appointments.models.schedule import Schedule
from appointments.models.schedule_event import ScheduleEvent
from appointments.models.schedule_recurring_block import (
    ScheduleRecurringBlock,
    ScheduleRecurringBlockWeekdayIndex,
)
from appointments.models.v2.member_appointment_video_timestamp import (
    AppointmentVideoTimestampStruct,
)
from appointments.models.v2.member_appointments import MemberAppointmentsListElement
from appointments.schemas.appointments import PrivacyType
from appointments.schemas.v2.member_appointment import (
    MemberAppointmentServiceResponseCertifiedState,
    MemberAppointmentServiceResponseNeed,
    MemberAppointmentServiceResponseProvider,
    MemberAppointmentServiceResponseVertical,
)
from assessments.utils.assessment_exporter import AssessmentExportTopic
from authn.domain.model import UserAuth
from authn.models.email_domain_denylist import EmailDomainDenylist
from authn.models.user import User
from authz.models.rbac import AllowedList
from authz.models.roles import ROLES, Capability, Role
from care_advocates.models.assignable_advocates import AssignableAdvocate
from care_advocates.models.transitions import (
    CareAdvocateMemberTransitionLog,
    CareAdvocateMemberTransitionSender,
    CareAdvocateMemberTransitionTemplate,
)
from clinical_documentation.models.mpractice_template import MPracticeTemplate
from common.models.scheduled_maintenance import ScheduledMaintenance
from conftest import BaseMeta
from geography.models.country_metadata import CountryMetadata
from health.data_models.member_risk_flag import MemberRiskFlag
from health.data_models.risk_flag import RiskFlag, RiskFlagSeverity
from health.models.health_profile import HealthProfile
from health.models.risk_enums import RiskFlagName
from incentives.models.incentive import (
    Incentive,
    IncentiveAction,
    IncentiveDesignAsset,
    IncentiveOrganization,
    IncentiveOrganizationCountry,
    IncentiveType,
)
from incentives.models.incentive_fulfillment import (
    IncentiveFulfillment,
    IncentiveStatus,
)
from l10n.db_strings.slug_backfill import BackfillL10nSlugs
from messaging.models.messaging import (
    Channel,
    ChannelUsers,
    Message,
    MessageCredit,
    MessageUsers,
)
from models.enterprise import (
    Assessment,
    AssessmentLifecycle,
    AssessmentLifecycleTrack,
    ExternalIDPNames,
    Invite,
    NeedsAssessment,
    NeedsAssessmentTypes,
    Organization,
    OrganizationEligibilityField,
    OrganizationEmailDomain,
    OrganizationEmployee,
    OrganizationExternalID,
    PartnerInvite,
    UserAsset,
    UserAssetState,
    UserOnboardingState,
    UserOrganizationEmployee,
)
from models.gdpr import GDPRDeletionBackup, GDPRUserRequest
from models.images import Image
from models.marketing import (
    PopularTopic,
    Resource,
    ResourceConnectedContentTrackPhase,
    ResourceTrack,
    ResourceTrackPhase,
    ResourceTypes,
    Tag,
    URLRedirect,
    URLRedirectPath,
)
from models.products import Product
from models.profiles import (
    Address,
    Agreement,
    AgreementAcceptance,
    AgreementNames,
    CareTeamTypes,
    Category,
    CategoryVersion,
    Certification,
    Language,
    MemberPractitionerAssociation,
    MemberProfile,
    OrganizationAgreement,
    PractitionerProfile,
    PractitionerSubdivision,
    RoleProfile,
    State,
)
from models.programs import (
    CareProgramPhase,
    Enrollment,
    Module,
    Phase,
    PhaseLogic,
    ProgramLengthLogic,
)
from models.questionnaires import (
    GENDER_MULTISELECT_QUESTION_OID,
    Answer,
    ProviderAddendum,
    ProviderAddendumAnswer,
    Question,
    Questionnaire,
    QuestionSet,
    QuestionTypes,
    RecordedAnswer,
    RecordedAnswerSet,
)
from models.referrals import ReferralCode, ReferralCodeCategory, ReferralCodeSubCategory
from models.tracks import TrackName
from models.tracks.assessment import AssessmentTrack
from models.tracks.client_track import ClientTrack
from models.tracks.member_track import (
    MemberTrack,
    MemberTrackPhaseReporting,
    MemberTrackStatus,
    TrackChangeReason,
)
from models.verticals_and_specialties import (
    CX_VERTICAL_NAME,
    Specialty,
    SpecialtyKeyword,
    Vertical,
    VerticalAccessByTrack,
    VerticalGroup,
    VerticalGroupTrack,
    VerticalGroupVersion,
)
from models.virtual_events import (
    VirtualEvent,
    VirtualEventCategory,
    VirtualEventCategoryTrack,
    VirtualEventUserRegistration,
)
from models.zoom import UserWebinar, Webinar
from provider_matching.models.in_state_matching import VerticalInStateMatchState
from provider_matching.models.practitioner_track_vgc import PractitionerTrackVGC
from storage.connection import db
from user_locale.models.user_locale_preference import UserLocalePreference
from wallet.models.constants import WalletUserStatus, WalletUserType
from wallet.models.member_benefit import MemberBenefit
from wallet.models.organization_employee_dependent import OrganizationEmployeeDependent
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers

seed = int(time.time() * 1000000)
fake = Faker(random_seed=seed)


def postiveint(integer: int):
    return integer + 1


# This is a custom solution to the fact that Faker does not have an option to return unique values
# Reference: https://github.com/FactoryBoy/factory_boy/issues/305#issuecomment-986154884
class UniqueFaker(factory.Faker):
    def evaluate(self, instance, step, extra):
        locale = extra.pop("locale")
        subfaker: factory.Faker = self._get_faker(locale)
        unique_proxy: UniqueProxy = subfaker.unique
        return unique_proxy.format(self.provider, **extra)


class HealthProfileFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = HealthProfile

    due_date = factory.LazyFunction(
        lambda: datetime.date.today() + datetime.timedelta(weeks=25)
    )

    class Params:
        has_birthday = factory.Trait(
            birthday=datetime.date.today() - datetime.timedelta(weeks=1043)
        )

    @factory.post_generation
    def last_child_birthday(profile: HealthProfile, create, birthday, **kwargs):
        if not birthday:
            birthday = datetime.date.today() - datetime.timedelta(weeks=40)
        profile.add_a_child(birthday)


class CountryMetadataFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = CountryMetadata

    country_code = "US"
    summary = factory.Faker("text")
    ext_info_link = factory.Faker("url")


class DefaultUserFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = User
        sqlalchemy_get_or_create = ("id", "username")

    id = None
    username = UniqueFaker("user_name")
    email = factory.Sequence(lambda n: f"email+{n}@google.com")
    password = factory.Faker("password")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    health_profile = factory.RelatedFactory(
        HealthProfileFactory, factory_related_name="user"
    )

    @factory.post_generation
    def email_prefix(user: User, create, prefix, **kwargs):
        if prefix:
            number = random.randint(0, 999999)
            user.email = f"test+{prefix}.{number}@mavenclinic.com"


class EmailDomainDenylistFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = EmailDomainDenylist

    domain = factory.Sequence(lambda n: f"google{n}.com")


class GDPRUserRequestFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = GDPRUserRequest
        sqlalchemy_get_or_create = ("id", "user_id", "user_email")

    id = None
    user_id = UniqueFaker("user_id")
    user_email = factory.Sequence(lambda n: f"email+{n}@google.com")
    status = "PENDING"
    source = "ADMIN"


class GDPRDeletionBackupFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = GDPRDeletionBackup

    data = "{}"


class RoleFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Role
        sqlalchemy_get_or_create = ("name",)

    name = ROLES.member

    @factory.post_generation
    def capabilities(self: Role, create, capabilities):
        if create and capabilities:
            for c in capabilities:
                self.capabilities.append(c)


class RoleProfileFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = RoleProfile

    role = factory.SubFactory(RoleFactory)
    user = factory.SubFactory(DefaultUserFactory)


class ScheduledMaintenanceFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ScheduledMaintenance


class CapabilityFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Capability


class MemberProfileFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = MemberProfile

    role = factory.SubFactory(RoleFactory)
    state_id = factory.SelfAttribute("state.id", None)
    user_id = factory.SelfAttribute("user.id", None)

    @factory.post_generation
    def care_team(member: MemberProfile, create, care_team):
        if create and care_team:
            for cc in care_team:
                member.add_practitioner_to_care_team(
                    cc.id, CareTeamTypes.CARE_COORDINATOR
                )


class MemberProfileCarePlanFactory(MemberProfileFactory):
    class Meta(BaseMeta):
        model = MemberProfile

    care_plan_id = random.randint(1, 1000)
    has_care_plan = True


class AddressFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Address

    street_address = factory.Faker("street_address")
    city = factory.Faker("city")
    zip_code = factory.Faker("numerify", text="######")
    state = "NY"
    country = "US"


class StateFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = State
        sqlalchemy_get_or_create = (
            "name",
            "abbreviation",
        )

    name = "New York"
    abbreviation = "NY"


class MemberFactory(DefaultUserFactory):
    member_profile = factory.RelatedFactory(
        MemberProfileFactory, factory_related_name="user"
    )


class ScheduleFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Schedule

    user = factory.SubFactory(DefaultUserFactory)
    name = factory.SelfAttribute("user.first_name")


class ScheduleEventFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ScheduleEvent

    state = ScheduleStates.available


class ScheduleRecurringBlockFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ScheduleRecurringBlock

    starts_at = datetime.datetime.utcnow()
    ends_at = factory.LazyAttribute(
        lambda i: datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    )
    frequency = ScheduleFrequencies.WEEKLY
    until = factory.LazyAttribute(
        lambda i: datetime.datetime.utcnow() + datetime.timedelta(weeks=1)
    )
    latest_date_events_created = None
    schedule = factory.SubFactory(ScheduleFactory)


class ScheduleRecurringBlockWeekdayIndexFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ScheduleRecurringBlockWeekdayIndex

    week_days_index = 1
    schedule_recurring_block = factory.SubFactory(ScheduleRecurringBlockFactory)


class OrganizationEligibilityFieldFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = OrganizationEligibilityField


class OrganizationFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Organization
        sqlalchemy_get_or_create = ("name",)

    name = factory.Faker("company")
    created_at = factory.Faker("date_time")
    modified_at = factory.Faker("date_time")
    activated_at = factory.Faker("date_time")

    @factory.post_generation
    def allowed_tracks(
        org: Organization, create, track_names: Optional[Iterable[TrackName]], **kwargs
    ):
        """Create ClientTrack associations using only names, and default lengths

        Examples:
            >>> org: Organization = OrganizationFactory.create(allowed_tracks=[*TrackName])
        """
        if create and track_names:
            for name in track_names:
                ClientTrackFactory.create(organization=org, track=name)

    @factory.post_generation
    def client_tracks(
        org: Organization, create, client_tracks: Optional[Iterable[Dict]], **kwargs
    ):
        """Create ClientTrack associations

        Examples:
            >>> org: Organization = OrganizationFactory.create(client_tracks=[
            >>>     { "name": "pregnancy", "length_in_days": 240 },
            >>>     { "name": "postpartum", "length_in_days": 348 },
            >>> ])
        """
        if create and client_tracks:
            for kwargs in client_tracks:
                ClientTrackFactory.create(organization=org, **kwargs)


class OrganizationExternalIDFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = OrganizationExternalID

    idp = ExternalIDPNames.OKTA.value
    external_id = factory.Sequence(lambda n: f"external-id-{n}")
    identity_provider_id = None
    organization = factory.SubFactory(OrganizationFactory)


class OrganizationEmailDomainFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = OrganizationEmailDomain

    domain = factory.Faker("domain_name")
    organization = factory.SubFactory(OrganizationFactory)


class OrganizationEmployeeFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = OrganizationEmployee

    email = factory.Faker("email")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    unique_corp_id = factory.Faker("swift11")
    dependent_id = factory.Faker("swift11")
    organization = factory.SubFactory(OrganizationFactory)
    date_of_birth = factory.Faker("date_of_birth", minimum_age=20)
    eligibility_member_id = factory.Sequence(postiveint)
    json = factory.SubFactory(factory.DictFactory)
    deleted_at = None
    retention_start_date = None
    work_state = None
    eligibility_member_2_id = None
    eligibility_member_2_version = None


class OrganizationEmployeeDependentFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = OrganizationEmployeeDependent

    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    middle_name = factory.Faker("first_name")


class WeeklyModuleFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Module
        sqlalchemy_get_or_create = ("name",)

    name = factory.Faker("random_element", elements=[*TrackName])
    phase_logic = PhaseLogic.WEEKLY
    program_length_logic = ProgramLengthLogic.DURATION
    duration = 1
    days_in_transition = 1


class WeeklyPhaseFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Phase
        sqlalchemy_get_or_create = ("name", "module")

    name = "week-1"
    module = factory.SubFactory(WeeklyModuleFactory)
    is_entry = True
    is_transitional = False


class StaticModuleFactory(WeeklyModuleFactory):
    phase_logic = PhaseLogic.STATIC


class StaticPhaseFactory(WeeklyPhaseFactory):
    is_transitional = False
    name = "static"


class EnrollmentFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Enrollment

    organization = factory.SubFactory(OrganizationFactory)


class CareProgramPhaseFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = CareProgramPhase
        sqlalchemy_get_or_create = ("phase",)

    phase = factory.SubFactory(WeeklyPhaseFactory)
    started_at = factory.LazyAttribute(
        lambda i: datetime.date.today() - datetime.timedelta(weeks=1)
    )


class ClientTrackFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ClientTrack
        sqlalchemy_get_or_create = ("track", "organization")

    track = factory.Faker("random_element", elements=[*TrackName])
    organization = factory.SubFactory(OrganizationFactory)
    length_in_days = 365


class MemberTrackPhaseFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = MemberTrackPhaseReporting

    name = "fake_name"


class MemberTrackStatusFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = MemberTrackStatus


class MemberTrackFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = MemberTrack

    name = TrackName.PREGNANCY.value
    user = factory.SubFactory(DefaultUserFactory)
    client_track = factory.SubFactory(
        ClientTrackFactory,
        organization=factory.SubFactory(OrganizationFactory),
        track=factory.SelfAttribute("..name"),
    )
    activated_at = datetime.datetime.utcnow()

    @factory.post_generation
    def user_organization_employee(self: MemberTrack, create, extracted, **kwargs):
        """
        Generate a UserOrganizationEmployee instance using the MemberTrack's
        User and OrganizationEmployee.
        """
        try:
            org = self.user.organization_v2
        except Exception:
            org = None

        if create and org:
            if (
                org != self.client_track.organization
                and len(self.user.active_tracks) == 1
            ):
                self.client_track = ClientTrackFactory.create(
                    organization=org,
                    track=self.name,
                )

        if create:
            uoe = UserOrganizationEmployee.query.filter_by(
                user=self.user,
            ).first()
            if not uoe:
                if org:
                    UserOrganizationEmployeeFactory.create(
                        user=self.user,
                        organization_employee=OrganizationEmployeeFactory.create(
                            organization=org
                        ),
                    )
                else:
                    UserOrganizationEmployeeFactory.create(
                        user=self.user,
                    )

    @factory.post_generation
    def current_phase(track: MemberTrack, create, extracted, **kwargs):
        """Set the current phase for a MemberTrack at creation.

        Examples:
            >>> track: MemberTrack = MemberTrackFactory.create(
            ...     name=TrackName.PREGNANCY, current_phase="week-15"
            ... )
        """
        # Ignore this unless it's a weekly phase name, in which case we use it to build
        # the track's start date
        if extracted and extracted.startswith("week-"):
            week = int(extracted.split("-")[1]) - track._WEEK_OFFSET
            today = datetime.date.today()
            track.anchor_date = today - datetime.timedelta(weeks=week - 1)

    @factory.post_generation
    def legacy_care_program(track: MemberTrack, create, extracted, **kwargs):
        """Finalize the creation of legacy programs data.

        TODO: [Tracks] Phase 3 - drop this :)
        """
        # If created, also create a corresponding legacy care program
        if create and track.legacy_program:
            last_week = datetime.datetime.now() - datetime.timedelta(days=6)
            cpp: CareProgramPhase = CareProgramPhaseFactory.create(
                program=track.legacy_program,
                started_at=last_week,
                ended_at=None,
                phase__name=track.current_phase.name,
                phase__module__name=track.name,
            )
            track.legacy_module = cpp.module
            # Note: we have to do this because tests can assume that these fields
            # haven't been cached.
            for n in ("initial_phase", "final_phase", "current_phase"):
                track.__dict__.pop(n, None)


class UserAssetFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = UserAsset

    state = UserAssetState.COMPLETE
    file_name = "img.png"
    content_type = "image/png"
    content_length = 1000


class MemberBenefitFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = MemberBenefit

    benefit_id = factory.Faker("pystr_format", string_format="M#########")


class EnterpriseUserFactory(DefaultUserFactory):
    class Meta(BaseMeta):
        model = User

    tracks = factory.RelatedFactoryList(
        MemberTrackFactory,
        "user",
        size=1,
    )
    member_profile = factory.RelatedFactory(MemberProfileFactory, "user")
    member_benefit = factory.RelatedFactory(MemberBenefitFactory, "member")

    @factory.post_generation
    def enabled_tracks(
        user: User, create, enabled_tracks: Optional[Iterable[TrackName]], **kwargs
    ):
        """Set additional tracks as enabled for the user's organization.

        Examples:
            >>> user: User = EnterpriseUserFactory.create(enabled_tracks=[*TrackName])
        """
        if create and enabled_tracks:
            org = user.organization_v2
            for name in enabled_tracks:
                org.allowed_modules.append(WeeklyModuleFactory.create(name=name))
            existing = {t.name for t in user.member_tracks}
            for name in {*enabled_tracks} - existing:
                ClientTrackFactory.create(
                    organization=org, track=name, length_in_days=777
                )

    @factory.post_generation
    def care_team(user: User, create, care_team):
        if create and care_team:
            for cc in care_team:
                user.add_practitioner_to_care_team(
                    cc.id, CareTeamTypes.CARE_COORDINATOR
                )
        elif create:
            cc = PractitionerUserFactory.create()
            v = VerticalFactory.create_cx_vertical()
            cc.practitioner_profile.verticals = [v]
            user.add_practitioner_to_care_team(cc.id, CareTeamTypes.CARE_COORDINATOR)


class EnterpriseUserNoTracksFactory(DefaultUserFactory):
    class Meta(BaseMeta):
        model = User

    member_profile = factory.RelatedFactory(MemberProfileFactory, "user")

    @factory.post_generation
    def care_team(user: User, create, care_team):
        if create and care_team:
            for cc in care_team:
                user.add_practitioner_to_care_team(
                    cc.id, CareTeamTypes.CARE_COORDINATOR
                )
        elif create:
            cc = PractitionerUserFactory.create()
            v = VerticalFactory.create_cx_vertical()
            cc.practitioner_profile.verticals = [v]
            user.add_practitioner_to_care_team(cc.id, CareTeamTypes.CARE_COORDINATOR)


class UserOrganizationEmployeeFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = UserOrganizationEmployee

    user = factory.SubFactory(EnterpriseUserFactory)

    organization_employee = factory.SubFactory(OrganizationEmployeeFactory)


class CreditFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Credit

    amount = 999


class CancellationPolicyFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = CancellationPolicy
        sqlalchemy_get_or_create = ("name",)

    name = fake.pystr(min_chars=5, max_chars=15)
    refund_0_hours = 0
    refund_2_hours = 0
    refund_6_hours = 0
    refund_12_hours = 0
    refund_24_hours = 50
    refund_48_hours = 50


class CertificationFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Certification

    name = "certification_1"


class PractitionerProfileFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = PractitionerProfile

    class Params:
        force_create_verticals = False

    show_in_enterprise = True
    show_in_marketplace = True
    active = True
    show_when_unavailable = True
    anonymous_allowed = True
    messaging_enabled = True
    state = factory.SubFactory(StateFactory)
    state_id = factory.SelfAttribute("state.id", None)
    default_cancellation_policy = factory.SubFactory(CancellationPolicyFactory)
    default_cancellation_policy_id = factory.SelfAttribute(
        "default_cancellation_policy.id", None
    )
    booking_buffer = 10
    country_code = None

    role = factory.SubFactory(RoleFactory, name=ROLES.practitioner)

    @factory.post_generation
    def next_availability(
        self: PractitionerProfile,
        create,
        next_availability: Optional[datetime.datetime],
    ):
        if create and next_availability:
            self.next_availability = next_availability

    @factory.post_generation
    def verticals(self: PractitionerProfile, create, verticals, **kwargs):
        if create and verticals == []:
            self.verticals = []
        elif create and verticals:
            for v in verticals:
                self.verticals.append(v)
        elif create:
            verticals = Vertical.query.all()
            if verticals:
                self.verticals.append(random.choice(verticals))
            else:
                self.verticals.append(VerticalFactory.create(**kwargs))

    @factory.post_generation
    def specialties(self: PractitionerProfile, create, specialties, **kwargs):
        if create and specialties == []:
            return
        elif create and specialties:
            for s in specialties:
                self.specialties.append(s)
        elif create:
            specialties = Specialty.query.all()
            if specialties:
                self.specialties.append(random.choice(specialties))
            else:
                self.specialties.append(SpecialtyFactory.create(**kwargs))

    @factory.post_generation
    def certified_states(self: PractitionerProfile, create, states, **kwargs):
        if create and states:
            for s in states:
                self.certified_states.append(s)
        elif create:
            certified_states = State.query.all()
            if certified_states:
                self.certified_states.append(random.choice(certified_states))
            else:
                self.certified_states.append(
                    StateFactory.create(name="New York", abbreviation="NY", **kwargs)
                )


class PractitionerUserFactory(DefaultUserFactory):
    practitioner_profile = factory.RelatedFactory(
        PractitionerProfileFactory, factory_related_name="user"
    )
    schedule = factory.RelatedFactory(ScheduleFactory, factory_related_name="user")
    timezone = "America/New_York"

    @factory.post_generation
    def products(self: User, create, products, **kwargs):
        if create and products:
            for p in products:
                p.user_id = self.id
            self.products = products  # Seems like its necessary to make this relationship explicit. Otherwise PracProfile.products was not referencing the newly added products for some reason.
        elif create:
            if not self.products:
                kwargs["practitioner"] = self
                self.products.append(ProductFactory.create(**kwargs))


class TagFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Tag
        sqlalchemy_get_or_create = ("name",)

    name = factory.Faker("word")
    display_name = factory.LazyAttribute(lambda tag: tag.name.capitalize())


class PopularTopicFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = PopularTopic

    topic = factory.Faker("catch_phrase")
    sort_order = factory.Sequence(lambda n: n)


class ResourceFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Resource

    resource_type = ResourceTypes.ENTERPRISE
    content_type = factory.Faker(
        "random_element", elements=["article", "ask_a_practitioner", "real_talk"]
    )
    connected_content_type = factory.Faker("bs")
    published_at = factory.Faker("date_time")
    body = factory.Faker("paragraph")
    title = factory.Faker("catch_phrase")
    subhead = factory.Faker("text")
    slug = factory.Faker("slug")
    json = "{}"
    webflow_url = factory.Faker("url")

    @factory.post_generation
    def tags(self: Resource, create, tags, **kwargs):
        if create and tags:
            for tag in tags:
                self.tags.append(tag)

    @factory.post_generation
    def phases(self: Resource, create, phases, **kwargs):
        """
        Usage: phases=[("pregnancy", "week-5"), ("postpartum", "week-1")]

        Note: this is NOT compatible with old-style Phase objects, so should only be
        used with code that expects resource <=> phase relationships to exist in the
        resource_track_phases table
        """
        if create and phases:
            inserts = [
                dict(resource_id=self.id, track_name=track, phase_name=phase)
                for (track, phase) in phases
            ]
            inspect(self).session.bulk_insert_mappings(ResourceTrackPhase, inserts)

    @factory.post_generation
    def connected_content_phases(self: Resource, create, phases, **kwargs):
        """
        Usage: phases=[("pregnancy", "week-5"), ("postpartum", "week-1")]

        Note: this is NOT compatible with old-style Phase objects, so should only be
        used with code that expects resource <=> phase relationships to exist in the
        resource_track_phases table
        """
        if create and phases:
            inserts = [
                dict(resource_id=self.id, track_name=track, phase_name=phase)
                for (track, phase) in phases
            ]
            inspect(self).session.bulk_insert_mappings(
                ResourceConnectedContentTrackPhase, inserts
            )

    @factory.post_generation
    def tracks(self: Resource, create, tracks, **kwargs):
        """
        Usage: tracks=["pregnancy", "postpartum"]
        """
        if create and tracks:
            inserts = [dict(resource_id=self.id, track_name=track) for track in tracks]
            inspect(self).session.bulk_insert_mappings(ResourceTrack, inserts)


class ImageFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Image

    filetype = "image"


class AssessmentFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Assessment

    quiz_body = {"questions": []}

    @classmethod
    def format_question(
        cls,
        id: int,
        widget: dict,
        question_name: str,
        body: str = "String?",
        required: bool = False,
        export_logic: str = "RAW",
    ):
        """Helper method for adding questions to Assessment Exports"""
        return {
            "id": id,
            "body": body,
            "widget": widget,
            "required": required,
            "export": {
                AssessmentExportTopic.ANALYTICS.value: {
                    "question_name": question_name,
                    "export_logic": export_logic,
                }
            },
        }


class NeedsAssessmentFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = NeedsAssessment

    user = factory.SubFactory(DefaultUserFactory)
    completed = False
    json = {"meta": {"completed": False}, "answers": []}

    @classmethod
    def create_with_assessment_type(cls, needs_assessment_type, **kwargs):
        # Note that this automatically gets the most recent version of the assessment
        # If you want an older version, please specify the assessment template manually
        assessment = (
            db.session.query(Assessment)
            .join(AssessmentLifecycle)
            .filter(AssessmentLifecycle.type == needs_assessment_type)
            .order_by(desc(Assessment.version))
            .first()
        )
        return cls.create(
            assessment_template=assessment,
            **kwargs,
        )


class VerticalGroupVersionFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = VerticalGroupVersion
        sqlalchemy_get_or_create = ("name",)

    name = "v2"


class VerticalGroupFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = VerticalGroup

    name = "test"

    @factory.post_generation
    def versions(self: VerticalGroupVersion, create, versions, **kwargs):
        if create and versions:
            for s in versions:
                self.versions.append(s)
        elif create:
            self.versions.append(VerticalGroupVersionFactory.create(**kwargs))


class VerticalGroupTrackFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = VerticalGroupTrack

    track_name = TrackName.BREAST_MILK_SHIPPING
    vertical_group = factory.SubFactory(VerticalGroupFactory)
    vertical_group_id = factory.SelfAttribute("vertical_group.id")


class VerticalFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Vertical
        sqlalchemy_get_or_create = ("name",)

    name = "OB-GYN"
    pluralized_display_name = "OB-GYNs"
    description = "ob-gyn"
    long_description = "This is an ob-gyn long description"
    filter_by_state = True
    can_prescribe = True
    products = [{"minutes": 10, "price": 20}, {"minutes": 15, "price": 30}]
    region = ""

    @classmethod
    def create_cx_vertical(cls):
        return cls.create(
            name=CX_VERTICAL_NAME,
            pluralized_display_name=CX_VERTICAL_NAME + "s",
            filter_by_state=False,
            can_prescribe=False,
            products=[{"minutes": 10, "price": 18}, {"minutes": 15, "price": 25}],
        )

    @factory.post_generation
    def set_slug(self, create, extracted, **kwargs):
        if not self.slug:  # Only set slug if not already provided
            self.slug = BackfillL10nSlugs().convert_name_to_slug(self.name)


class VerticalFactoryNoSlug(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Vertical
        sqlalchemy_get_or_create = ("name",)

    pluralized_display_name = "OB-GYNs"
    description = "ob-gyn"
    long_description = "This is an ob-gyn long description"


class ProductFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Product

    minutes = factory.Sequence(lambda n: n + 1)
    practitioner = factory.SubFactory(PractitionerUserFactory)
    is_active = True
    vertical = factory.SubFactory(VerticalFactory)
    price = factory.Sequence(lambda n: n + 1)


class MemberPractitionerAssociationFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = MemberPractitionerAssociation
        sqlalchemy_get_or_create = ("type", "user_id", "practitioner_id")

    type = CareTeamTypes.APPOINTMENT
    user_id = factory.SelfAttribute("user.id", None)
    practitioner_id = factory.SelfAttribute("practitioner_profile.id", None)


class AppointmentFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Appointment

    class Params:
        is_enterprise_factory = factory.Trait(
            member_schedule=factory.SubFactory(
                ScheduleFactory, user=factory.SubFactory(EnterpriseUserFactory)
            )
        )
        is_enterprise_with_track_factory = factory.Trait(
            member_schedule=factory.SubFactory(
                ScheduleFactory,
                user=factory.SubFactory(
                    EnterpriseUserFactory, enabled_tracks=["general_wellness"]
                ),
            )
        )

    cancellation_policy = factory.SubFactory(CancellationPolicyFactory)
    product = factory.SubFactory(ProductFactory)
    scheduled_start = factory.Faker(
        "date_time_this_month", before_now=True, after_now=False
    )
    scheduled_end = factory.LazyAttribute(
        lambda o: o.scheduled_start + datetime.timedelta(minutes=o.product.minutes)
    )
    purpose = ""

    member_schedule = factory.SubFactory(
        ScheduleFactory, user=factory.SubFactory(MemberFactory)
    )
    member_schedule_id = factory.SelfAttribute("member_schedule.id")

    @factory.post_generation
    def member_practitioner_association(
        self: MemberPractitionerAssociation, create, extracted, **kwargs
    ):
        if create:
            MemberPractitionerAssociationFactory.create(
                user=self.member_schedule.user,
                practitioner_id=self.product.practitioner.id,
            )

    @classmethod
    def create_with_practitioner(
        cls,
        practitioner,
        scheduled_start=None,
        scheduled_end=None,
        purpose=None,
        member_schedule=None,
        privacy=None,
        cancelled_by_user_id=None,
        member_ended_at=None,
        practitioner_ended_at=None,
        # cancellation_policy=None,
    ):
        scheduled_start = scheduled_start or datetime.datetime.now()

        if practitioner.practitioner_profile.verticals:
            product = Product.query.filter_by(user_id=practitioner.id).first()
            if not product:
                product = ProductFactory.create(
                    practitioner=practitioner,
                    vertical=random.choice(practitioner.practitioner_profile.verticals),
                )
        else:
            verticals = Vertical.query.all()
            if verticals:
                vertical_with_product = next(v for v in verticals if v.products)
                if vertical_with_product:
                    # This append will create products associated with the practitioner
                    practitioner.practitioner_profile.verticals.append(
                        vertical_with_product
                    )
                    product = random.choice(practitioner.products)
                else:
                    product = ProductFactory.create(
                        practitioner=practitioner, vertical=random.choice(verticals)
                    )
        return cls.create(
            member_schedule=member_schedule or cls.member_schedule,
            purpose=purpose,
            product=product,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            privacy=privacy,
            cancelled_by_user_id=cancelled_by_user_id,
            member_ended_at=member_ended_at,
            practitioner_ended_at=practitioner_ended_at,
            cancelled_at=None,
            # cancellation_policy=cancellation_policy,
        )

    @classmethod
    def create_with_state_payment_pending(cls):
        return cls.create(
            scheduled_start=datetime.datetime.now() - datetime.timedelta(minutes=1),
            member_started_at=datetime.datetime.now(),
            member_ended_at=datetime.datetime.now() + datetime.timedelta(minutes=2),
            practitioner_started_at=datetime.datetime.now(),
            practitioner_ended_at=datetime.datetime.now()
            + datetime.timedelta(minutes=2),
            scheduled_end=datetime.datetime.now() + datetime.timedelta(minutes=20),
        )

    @classmethod
    def create_with_state_incomplete(cls):
        return cls.create(
            scheduled_start=datetime.datetime.now() - datetime.timedelta(minutes=1),
            member_started_at=datetime.datetime.now(),
            member_ended_at=datetime.datetime.now() + datetime.timedelta(minutes=2),
            practitioner_started_at=datetime.datetime.now(),
            scheduled_end=datetime.datetime.now() + datetime.timedelta(minutes=20),
        )

    @classmethod
    def create_with_completeable_state(cls):
        return cls.create(
            scheduled_start=datetime.datetime.now() - datetime.timedelta(minutes=1),
            member_started_at=datetime.datetime.now(),
            practitioner_started_at=datetime.datetime.now(),
            scheduled_end=datetime.datetime.now() + datetime.timedelta(minutes=20),
        )

    @classmethod
    def create_with_cancellable_state(cls):
        return cls.create(
            scheduled_start=datetime.datetime.now() + datetime.timedelta(days=2)
        )

    @classmethod
    def create_anonymous(cls):
        return cls.create(privacy=PRIVACY_CHOICES.anonymous)

    @factory.post_generation
    def need(self: MemberPractitionerAssociation, create, need, **kwargs):
        if create and need:
            NeedAppointmentFactory.create(
                need_id=need.id,
                appointment_id=self.id,
            )


class RescheduleHistoryFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = RescheduleHistory

    id = factory.Sequence(postiveint)
    scheduled_start = factory.Faker("date_time")
    scheduled_end = factory.LazyAttribute(
        lambda o: o.scheduled_start + datetime.timedelta(minutes=15)
    )
    appointment_id = 123
    created_at = factory.Faker("date_time")


class AppointmentMetaDataFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = AppointmentMetaData

    type = AppointmentMetaDataTypes.PRACTITIONER_NOTE
    appointment = factory.SubFactory(AppointmentFactory)


class PractitionerAppointmentAckFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = PractitionerAppointmentAck

    phone_number = "+12125555555"
    id = factory.Sequence(postiveint)


class AssignableAdvocateFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = AssignableAdvocate

    marketplace_allowed = False
    vacation_started_at = None
    vacation_ended_at = None
    max_capacity = 6
    daily_intro_capacity = 4

    @classmethod
    def create_with_practitioner(cls, practitioner: User):
        v = Vertical.query.filter(Vertical.name == CX_VERTICAL_NAME).one_or_none()
        if not v:
            v = VerticalFactory.create_cx_vertical()

        practitioner.practitioner_profile.verticals.append(v)

        return cls.create(
            practitioner=practitioner.practitioner_profile,
            practitioner_id=practitioner.id,
        )


class EmptyQuestionnaireFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Questionnaire

    sort_order = factory.Sequence(lambda n: n)
    title_text = "health binder!"
    description_text = "a binder (?) of one's health"
    oid = factory.LazyAttribute(lambda x: fake.text(max_nb_chars=100))


class QuestionnaireFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Questionnaire

    sort_order = factory.Sequence(lambda n: n)
    oid = factory.LazyAttribute(lambda x: fake.text(max_nb_chars=100))
    title_text = "health binder!"
    description_text = "a binder (?) of one's health"

    @factory.post_generation
    def question_sets(self: Questionnaire, create, question_sets):
        if create:
            self.question_sets.append(
                QuestionSetFactory.create(questionnaire_id=self.id)
            )

    @factory.post_generation
    def verticals(self: Questionnaire, create, verticals):
        if create and verticals:
            for v in verticals:
                self.verticals.append(v)


class QuestionSetFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = QuestionSet

    sort_order = factory.Sequence(lambda n: n)
    oid = factory.LazyAttribute(lambda x: fake.text(max_nb_chars=100))

    @factory.post_generation
    def questions(self: QuestionSet, create, _):
        if create:
            self.questions.append(
                QuestionFactory.create(
                    question_set_id=self.id, type=QuestionTypes.RADIO
                )
            )
            self.questions.append(
                QuestionFactory.create(
                    question_set_id=self.id, type=QuestionTypes.CHECKBOX
                )
            )
            self.questions.append(
                QuestionFactory.create(question_set_id=self.id, type=QuestionTypes.TEXT)
            )
            self.questions.append(
                QuestionFactory.create(question_set_id=self.id, type=QuestionTypes.STAR)
            )
            self.questions.append(
                QuestionFactory.create(question_set_id=self.id, type=QuestionTypes.DATE)
            )
            self.questions.append(
                QuestionFactory.create(
                    question_set_id=self.id, type=QuestionTypes.MULTISELECT
                )
            )
            self.questions.append(
                QuestionFactory.create(
                    question_set_id=self.id, type=QuestionTypes.SINGLE_SELECT
                )
            )


class EmptyQuestionSetFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = QuestionSet

    sort_order = factory.Sequence(lambda n: n)
    oid = factory.LazyAttribute(lambda x: fake.text(max_nb_chars=100))


class EmptyQuestionFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Question

    sort_order = factory.Sequence(lambda n: n)
    label = "What is this question asking?"
    required = False
    type = QuestionTypes.RADIO
    oid = factory.LazyAttribute(lambda x: fake.text(max_nb_chars=100))


class QuestionFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Question

    sort_order = factory.Sequence(lambda n: n)
    label = "What is this question asking?"
    required = False
    type = QuestionTypes.RADIO
    oid = factory.LazyAttribute(lambda x: fake.text(max_nb_chars=100))

    @factory.post_generation
    def answers(self: Question, create, _):
        if create:
            if self.type in [
                QuestionTypes.RADIO,
                QuestionTypes.CHECKBOX,
                QuestionTypes.STAR,
                QuestionTypes.MULTISELECT,
                QuestionTypes.SINGLE_SELECT,
            ]:
                self.answers.append(
                    AnswerFactory.create(question_id=self.id, text="1", sort_order=1)
                )
                self.answers.append(
                    AnswerFactory.create(question_id=self.id, text="2", sort_order=2)
                )
                self.answers.append(
                    AnswerFactory.create(question_id=self.id, text="3", sort_order=3)
                )
            if self.oid == GENDER_MULTISELECT_QUESTION_OID:
                self.answers.append(
                    AnswerFactory.create(question_id=self.id, text="other", oid="other")
                )

    @factory.post_generation
    def non_db_answer_options_json(self: Question, create, _):
        if create:
            if self.type == QuestionTypes.CONDITION:
                self.non_db_answer_options_json = {
                    "options": ["infertility", "endometriosis"]
                }
            elif self.type == QuestionTypes.ALLERGY_INTOLERANCE:
                self.non_db_answer_options_json = {
                    "medicine_options": ["penicillin", "amoxicillin"],
                    "food_other_options": ["milk", "wheat"],
                }


class AnswerFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Answer

    sort_order = factory.Sequence(lambda n: n)
    text = "answer text"
    oid = factory.LazyAttribute(lambda x: fake.text(max_nb_chars=100))


class RecordedAnswerSetFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = RecordedAnswerSet

    submitted_at = factory.Faker("date_time_between", start_date="-7d")


class RecordedAnswerFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = RecordedAnswer


class MPracticeTemplateFactory(factory.Factory):
    class Meta:
        model = MPracticeTemplate

    id = factory.Faker("random_int", min=1)
    owner_id = factory.Faker("random_int", min=1)
    is_global = False
    title = factory.Faker("word")
    text = factory.Faker("word")
    sort_order = 0
    created_at = factory.Faker("date_time")
    modified_at = factory.Faker("date_time")


class ProviderAddendumFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ProviderAddendum

    appointment = factory.SubFactory(AppointmentFactory)
    questionnaire = factory.SubFactory(QuestionnaireFactory)
    submitted_at = factory.Faker("date_time_between", start_date="-7d")


class ProviderAddendumAnswerFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ProviderAddendumAnswer

    provider_addendum = factory.SubFactory(ProviderAddendumFactory)
    question = factory.SubFactory(QuestionFactory)
    text = "test text"
    date = factory.Faker("date_time_between", start_date="-7d")


class SpecialtyFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Specialty

    name = "Back to work coaching"

    @factory.post_generation
    def specialty_keywords(self: Specialty, create, keywords, **kwargs):
        if create and keywords:
            for k in keywords:
                self.specialty_keywords.append(k)
        elif create:
            keywords = SpecialtyKeyword.query.all()
            if keywords:
                self.specialty_keywords.append(random.choice(keywords))
            else:
                self.specialty_keywords.append(SpecialtyKeywordFactory.create(**kwargs))

    @factory.post_generation
    def set_slug(self, create, extracted, **kwargs):
        if not self.slug:  # Only set slug if not already provided
            self.slug = BackfillL10nSlugs().convert_name_to_slug(self.name)


class SpecialtyKeywordFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = SpecialtyKeyword

    name = "coach"


class UserOnboardingStateFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = UserOnboardingState


class InviteFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Invite


class PartnerInviteFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = PartnerInvite


class MessageFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Message


class MessageCreditFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = MessageCredit


class MessageUsersFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = MessageUsers


class ChannelFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Channel


class ChannelUsersFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ChannelUsers


class VirtualEventCategoryFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = VirtualEventCategory

    name = factory.Sequence(lambda n: f"whatever-10{n}")


class VirtualEventCategoryTrackFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = VirtualEventCategoryTrack


class VirtualEventFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = VirtualEvent

    title = "Adopt a dog"
    registration_form_url = "https://www.petfinder.com/dogs/"
    description = "Dogs are great pets."
    scheduled_start = factory.LazyFunction(
        lambda: datetime.datetime.now() + datetime.timedelta(days=6)
    )
    scheduled_end = factory.LazyFunction(
        lambda: datetime.datetime.now() + datetime.timedelta(days=6)
    )
    host_name = "Clifford the Big Red Dog"
    host_specialty = "Being a good boy"
    description_body = "A dog’s nose print is unique, much like a person’s fingerprint."
    what_youll_learn_body = (
        "Dogs have about 1,700 taste buds. We humans have between 2,000–10,000."
    )
    virtual_event_category = factory.SubFactory(VirtualEventCategoryFactory)


class VirtualEventUserRegistrationFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = VirtualEventUserRegistration


class AssessmentLifecycleFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = AssessmentLifecycle

    name = factory.Faker("random_element", elements=[*NeedsAssessmentTypes])
    type = factory.SelfAttribute("name")


class AssessmentLifecycleTrackFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = AssessmentLifecycleTrack

    track_name = factory.Faker("random_element", elements=[*TrackName])
    assessment_lifecycle = factory.SubFactory(
        AssessmentLifecycleFactory, name=factory.SelfAttribute("..track_name")
    )

    @factory.post_generation
    def assessment_versions(
        assessment_lc_track: AssessmentLifecycleTrack,
        create,
        assessment_versions: Optional[Iterable[int]],
        **kwargs,
    ):
        """Create assessments with provided version numbers"""
        if create:
            for version in assessment_versions:
                AssessmentFactory.create(
                    lifecycle=assessment_lc_track.assessment_lifecycle, version=version
                )


class AssessmentTrackFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = AssessmentTrack

    assessment_onboarding_slug = factory.Faker("word")
    track_name = factory.Faker("random_element", elements=[*TrackName])


class DefaultWebinarFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Webinar

    id = None
    uuid = factory.Faker("word")
    host_id = factory.Faker("word")
    topic = factory.Faker("word")
    timezone = factory.Faker("word")
    created_at = factory.Faker("date_time")
    start_time = factory.Faker("date_time")


class DefaultUserWebinarFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = UserWebinar

    user_id = factory.Faker("integer")
    webinar_id = factory.Faker("integer")
    registrant_id = factory.Faker("word")


class InvoiceFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Invoice

    recipient_id = str(factory.Faker("integer"))
    transfer_id = str(factory.Faker("integer"))
    started_at = factory.Faker("date_time")
    transfer_id = None
    started_at = None
    failed_at = None
    completed_at = None


class FeeAccountingEntryFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = FeeAccountingEntry

    amount = 100
    type = FeeAccountingEntryTypes.ONE_OFF


class LanguageFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Language

    name = Language.ENGLISH

    @factory.post_generation
    def set_slug(self, create, extracted, **kwargs):
        if not self.slug:  # Only set slug if not already provided
            self.slug = BackfillL10nSlugs().convert_name_to_slug(self.name)


class AgreementFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Agreement

    version = 1
    name = AgreementNames.PRIVACY_POLICY
    html = factory.Faker("word")


class AgreementAcceptanceFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = AgreementAcceptance

    agreement = factory.SubFactory(AgreementFactory)


class OrganizationAgreementFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = OrganizationAgreement

    agreement = factory.SubFactory(AgreementFactory)
    organization = factory.SubFactory(OrganizationFactory)


class PractitionerTrackVGCFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = PractitionerTrackVGC


class URLRedirectPathFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = URLRedirectPath

    path = factory.Faker("word")


class URLRedirectFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = URLRedirect

    path = factory.Faker("word")


class TrackChangeReasonFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = TrackChangeReason

    id = factory.Sequence(postiveint)
    name = factory.Faker("word")
    display_name = factory.Faker("word")
    description = factory.Faker("word")


class VerticalInStateMatchStateFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = VerticalInStateMatchState

    vertical_id = factory.Sequence(postiveint)
    state_id = factory.Sequence(postiveint)


class AvailabilityNotificationRequestFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = AvailabilityNotificationRequest

    member_id = factory.SelfAttribute("member.id")
    practitioner_id = factory.SelfAttribute("practitioner.id")


class CareAdvocateMemberTransitionLogFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = CareAdvocateMemberTransitionLog

    id = factory.Sequence(postiveint)
    created_at = factory.LazyAttribute(
        lambda i: datetime.datetime.now() - datetime.timedelta(days=1)
    )
    date_scheduled = factory.LazyAttribute(lambda i: datetime.datetime.now())
    uploaded_filename = factory.Faker("word")
    uploaded_content = json.dumps(
        [
            {
                "member_id": 1,
                "old_cx_id": 2,
                "new_cx_id": 3,
                "messaging": "SHORT_GOODBYE;SOFT_INTRO",
            },
            {
                "member_id": 4,
                "old_cx_id": 5,
                "new_cx_id": 6,
                "messaging": "LONG_GOODBYE",
            },
        ]
    )


class CareAdvocateMemberTransitionTemplateFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = CareAdvocateMemberTransitionTemplate

    id = factory.Sequence(postiveint)
    message_description = factory.Faker("word")
    message_body = factory.Faker("word")
    sender = CareAdvocateMemberTransitionSender.OLD_CX


class NeedCategoryFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = NeedCategory

    id = factory.Sequence(postiveint)
    # These are taken from l10n.db_strings.store.DBStringStore but converted into names
    name = factory.Iterator(
        [
            "Lifestyle & Nutrition",
            "Emotional Health",
            "Fertility Tests & Treatment",
            "Trying to Conceive",
            "General Health",
        ]
    )
    image_id = factory.Faker("word")

    @factory.post_generation
    def set_slug(self, create, extracted, **kwargs):
        if not self.slug:  # Only set slug if not already provided
            self.slug = BackfillL10nSlugs().convert_name_to_slug(self.name)


class NeedCategoryTrackFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = NeedCategoryTrack


class NeedFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Need

    id = factory.Sequence(postiveint)
    name = factory.Iterator(
        [
            "Treatment options and steps",
            "Emotional support",
            "Nutrition",
            "Preparing for treatment",
        ]
    )
    # slug = factory.Faker("slug")
    description = factory.Faker("word")
    verticals = factory.RelatedFactory

    @factory.post_generation
    def set_slug(self, create, extracted, **kwargs):
        if not self.slug:  # Only set slug if not already provided
            name_value = self.name
            self.slug = BackfillL10nSlugs().convert_name_to_slug(name_value)

    @factory.post_generation
    def verticals(self: Need, create, verticals, **kwargs):  # noqa F811
        if create and verticals:
            self.verticals.extend(verticals)
        elif create:
            self.verticals.append(VerticalFactory.create(**kwargs))

    @factory.post_generation
    def specialties(self: Need, create, specialties, **kwargs):
        if create and specialties:
            self.specialties.extend(specialties)


class NeedAppointmentFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = NeedAppointment


class NeedTrackFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = NeedTrack


class NeedVerticalFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = NeedVertical

    id = factory.Sequence(postiveint)


class NeedRestrictedVerticalFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = NeedRestrictedVertical


class ReimbursementOrganizationSettingsFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementOrganizationSettings


class ReimbursementWalletFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementWallet


class ReimbursementWalletUsersFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementWalletUsers

    status = WalletUserStatus.ACTIVE
    type = WalletUserType.EMPLOYEE


class MemberAppointmentAckFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = MemberAppointmentAck

    user = factory.SelfAttribute("appointment.member")
    user_id = factory.SelfAttribute("user.id", None)
    appointment = factory.SubFactory(AppointmentFactory)
    appointment_id = factory.SelfAttribute("appointment.id")


class IncentiveFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Incentive

    id = factory.Sequence(postiveint)
    type = IncentiveType.GIFT_CARD
    name = factory.Faker("word")
    amount = 10
    vendor = "Maven"
    design_asset = IncentiveDesignAsset.GENERIC_GIFT_CARD
    active = True


class IncentiveOrganizationFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = IncentiveOrganization

    id = factory.Sequence(postiveint)
    incentive = factory.SubFactory(IncentiveFactory)
    incentive_id = factory.SelfAttribute("incentive.id")
    organization = factory.SubFactory(OrganizationFactory)
    organization_id = factory.SelfAttribute("organization.id")
    action = factory.Faker("random_element", elements=[*IncentiveAction])
    track_name = factory.Faker(
        "random_element", elements=[t.value for t in [*TrackName]]
    )
    active = True


class IncentiveOrganizationCountryFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = IncentiveOrganizationCountry

    incentive_organization = factory.SubFactory(IncentiveOrganizationFactory)
    country_code = "US"


class IncentiveFulfillmentFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = IncentiveFulfillment

    status = factory.Faker(
        "random_element", elements=[t.value for t in [*IncentiveStatus]]
    )


class AllowedListFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = AllowedList


class SubdivisionCodeFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = PractitionerSubdivision

    subdivision_code = "US-NY"


# appointments/utils/appointment_utils.py get_member_appointment_state()
# will resolve to pending_or_resolved with default factory
class MemberAppointmentVideoTimestampStructFactory(factory.Factory):
    class Meta:
        model = AppointmentVideoTimestampStruct

    id = factory.Faker("random_int", min=1)
    member_started_at = factory.Faker("date_time")
    member_ended_at = factory.Faker("date_time")
    scheduled_start = factory.Faker("date_time")
    scheduled_end = factory.Faker("date_time")
    member_id = factory.Faker("random_int", min=1)
    provider_id = factory.Faker("random_int", min=1)
    json_str = '{"member_disconnected_at": null, "practitioner_disconnected_at": null}'
    practitioner_started_at = factory.Faker("date_time")
    practitioner_ended_at = factory.Faker("date_time")
    phone_call_at = factory.Faker("date_time")
    cancelled_at = None
    disputed_at = None


class MemberAppointmentsListElementFactory(factory.Factory):
    class Meta:
        model = MemberAppointmentsListElement

    id = factory.Faker("random_int", min=1)
    product_id = factory.Faker("random_int", min=1)
    client_notes = factory.Faker("text")
    cancelled_at = None
    disputed_at = None
    json_str = '{"member_disconnected_at": null, "practitioner_disconnected_at": null}'
    member_started_at = factory.Faker("date_time")
    member_ended_at = factory.Faker("date_time")
    scheduled_start = factory.Faker("date_time")
    scheduled_end = factory.Faker("date_time")
    privacy = PrivacyType.BASIC
    privilege_type = AppointmentTypes.STANDARD
    practitioner_started_at = factory.Faker("date_time")
    practitioner_ended_at = factory.Faker("date_time")
    phone_call_at = factory.Faker("date_time")


class MemberAppointmentServiceResponseVerticalFactory(factory.Factory):
    class Meta:
        model = MemberAppointmentServiceResponseVertical

    id = factory.Faker("random_int", min=1)
    name = factory.Faker("word")
    slug = factory.SelfAttribute("name")
    description = factory.Faker("word")
    can_prescribe = True
    filter_by_state = True


class MemberAppointmentServiceResponseCertifiedStateFactory(factory.Factory):
    class Meta:
        model = MemberAppointmentServiceResponseCertifiedState

    id = factory.Faker("random_int", min=1)
    name = factory.Faker("word")
    abbreviation = factory.Faker("state_abbr")


class MemberAppointmentServiceResponseProviderFactory(factory.Factory):
    class Meta:
        model = MemberAppointmentServiceResponseProvider

    id = factory.Faker("random_int", min=1)
    avatar_url = factory.Faker("url")
    verticals = factory.List(
        [factory.SubFactory(MemberAppointmentServiceResponseVerticalFactory)]
    )
    # vertical is set by dataclass __post_init__
    certified_states = factory.List(
        [factory.SubFactory(MemberAppointmentServiceResponseCertifiedStateFactory)]
    )
    name = factory.Faker("name")
    first_name = factory.Faker("first_name")
    can_prescribe = True
    care_team_type = CareTeamTypes.CARE_COORDINATOR
    messaging_enabled = True
    is_care_advocate = False
    can_member_interact = True


class MemberAppointmentServiceResponseNeedFactory(factory.Factory):
    class Meta:
        model = MemberAppointmentServiceResponseNeed

    id = factory.Faker("random_int", min=1)
    name = factory.Faker("word")


class UserAuthFactory(factory.Factory):
    class Meta:
        model = UserAuth

    id = None
    user_id = factory.Sequence(lambda n: n + 1)
    refresh_token = factory.Faker("swift11")
    external_id = factory.Faker("swift11")


class ForumCategoryVersionFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = CategoryVersion

    id = factory.Sequence(postiveint)
    name = factory.Faker("word")


class ForumsCategoryFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Category

    id = factory.Sequence(postiveint)

    @factory.post_generation
    def versions(self: Category, create, versions, **kwargs):
        if versions:
            for version in versions:
                self.versions.append(version)


class UserLocalePreferenceFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = UserLocalePreference

    id = factory.Sequence(postiveint)
    user_id = UniqueFaker("user_id")
    locale = "en"


class VerticalAccessByTrackFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = VerticalAccessByTrack

    client_track_id = factory.Sequence(postiveint)
    vertical_id = factory.Sequence(postiveint)


class RiskFlagFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = RiskFlag

    id = factory.Sequence(postiveint)
    severity = RiskFlagSeverity.HIGH_RISK.value
    name = RiskFlagName.AUTOIMMUNE_DISEASE.value


class MemberRiskFlagFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = MemberRiskFlag

    id = factory.Sequence(postiveint)
    user_id = UniqueFaker("user_id")
    risk_flag = factory.SubFactory(RiskFlagFactory)


class ReferralCodeCategoryFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReferralCodeCategory

    name = factory.Faker("word")


class ReferralCodeSubCategoryFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReferralCodeSubCategory

    name = factory.SelfAttribute("category.name")
    category = factory.SubFactory(ReferralCodeCategoryFactory)


class ReferralCodeFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReferralCode

    user = factory.SubFactory(EnterpriseUserFactory)
    category_name = factory.SelfAttribute("subcategory.name")
    subcategory_name = factory.SelfAttribute("subcategory.name")
    subcategory = factory.SubFactory(ReferralCodeSubCategoryFactory)
