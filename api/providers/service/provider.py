from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Dict, List, Optional

import dateutil.tz
import ddtrace
from maven import feature_flags
from pytz import timezone
from sqlalchemy import and_, case, func, not_, or_
from sqlalchemy.orm import contains_eager, joinedload
from sqlalchemy.orm.query import Query

from appointments.models.appointment import Appointment
from appointments.models.needs_and_categories import (
    Need,
    NeedRestrictedVertical,
    NeedVertical,
    need_specialty,
)
from appointments.models.payments import Credit
from appointments.models.schedule import Schedule
from appointments.models.schedule_event import ScheduleEvent
from authn.models.user import User
from authz.models.roles import ROLES, Role
from common import stats
from l10n.db_strings.translate import TranslateDBFields
from models.base import db
from models.common import PrivilegeType
from models.products import Product
from models.profiles import (
    CareTeamTypes,
    Language,
    MemberPractitionerAssociation,
    PractitionerProfile,
    State,
    practitioner_languages,
    practitioner_specialties,
    practitioner_states,
    practitioner_verticals,
)
from models.tracks import TrackName
from models.tracks.client_track import TrackModifiers
from models.verticals_and_specialties import (
    CX_FERTILITY_CARE_COACHING_SLUG,
    CX_PREGNANCY_CARE_COACHING_SLUG,
    DOULA_ONLY_VERTICALS,
    Specialty,
    Vertical,
    is_cx_vertical_name,
)
from payments.models.practitioner_contract import ContractType, PractitionerContract
from provider_matching.models.in_state_matching import VerticalInStateMatchState
from providers.domain.model import Provider
from providers.repository import provider as repository
from providers.repository.v2.provider import ProviderRepositoryV2
from providers.schemas.provider_languages import ProviderLanguagesServiceResponse
from utils.log import logger

__all__ = ("ProviderService",)

log = logger(__name__)

UTILIZATION_BUFFER_IN_DAYS = 7
UTILIZATION_BRACKETS = [0, 25, 50, 75, 100]

PROVIDER_FIXED_COST_PRIORITIZATION = [
    (
        PractitionerContract.contract_type == ContractType.W2.name,
        1,
    ),
    (
        PractitionerContract.contract_type == ContractType.FIXED_HOURLY.name,
        1,
    ),
    (
        PractitionerContract.contract_type == ContractType.FIXED_HOURLY_OVERNIGHT.name,
        1,
    ),
    (
        PractitionerContract.contract_type == ContractType.HYBRID_2_0.name,
        2,
    ),
    (
        PractitionerContract.contract_type == ContractType.HYBRID_1_0.name,
        2,
    ),
    (
        PractitionerContract.contract_type == ContractType.BY_APPOINTMENT.name,
        3,
    ),
    (
        PractitionerContract.contract_type
        == ContractType.NON_STANDARD_BY_APPOINTMENT.name,
        3,
    ),
]

ASYNC_CARE_ALLOWED_STATES = [
    "AL",
    "CA",
    "CT",
    "FL",
    "IL",
    "IA",
    "ME",
    "MI",
    "NE",
    "NV",
    "NC",
    "ND",
    "OH",
    "PA",
    "SD",
    "WI",
    "WY",
]


@dataclass
class ProductSchedulingConstraintsStruct:
    # like ProviderSchedulingConstraintsStruct, but potentially with
    # product-specific prep buffer
    prep_buffer: int
    booking_buffer: int
    max_capacity: int
    daily_intro_capacity: int


class ProviderService:
    def __init__(self) -> None:
        self.providers = repository.ProviderRepository()

    def provider_can_prescribe(self, provider: Provider | None) -> bool:
        """
        Is the Provider in a Vertical that can_prescribe and has dosespot info?
        :returns true if a provider exists and can prescribe
        """
        return (
            provider is not None
            and any(v.can_prescribe for v in provider.verticals)
            and provider.dosespot != {}
        )

    @ddtrace.tracer.wrap()
    def can_prescribe(
        self,
        provider_id: int,
        # optionally pass provider if it has already been fetched
        provider: Provider | None = None,
    ) -> bool:
        """
        Returns true if provider belongs to any vertical that is can_prescribe=true
        """
        if not provider:
            provider = self.providers.get_by_user_id(provider_id)

        return self.provider_can_prescribe(provider)

    @ddtrace.tracer.wrap()
    def can_prescribe_to_member(
        self,
        provider_id: int,
        member_state_abbreviation: Optional[str],
        # optionally pass provider if it has already been fetched
        provider: Provider | None = None,
    ) -> bool:
        """
        Can a provider prescribe to a member?
        :param provider_id: Id of the Provider who would be writing the prescription
        :param member_state_abbreviation State where the member can receive a prescription
        :return True if the provider is able to write prescriptions for the member
        """
        if not provider:
            provider = self.providers.get_by_user_id(provider_id)

        return self.provider_can_prescribe_in_state(provider, member_state_abbreviation)

    @ddtrace.tracer.wrap()
    def provider_can_prescribe_in_state(
        self,
        provider: Provider,
        state_abbreviation: Optional[str],
    ) -> bool:
        """
        Can a provider prescribe in the state provided?
        :param provider_id: Id of the Provider who would be writing the prescription
        :param state_abbreviation State where the member can receive a prescription
        :return True if the provider is able to write prescriptions for the state provided
        """
        return self.provider_can_prescribe(provider) and state_abbreviation in [
            s.abbreviation for s in provider.certified_states
        ]

    @ddtrace.tracer.wrap()
    def enabled_for_prescribing(
        self,
        provider_id: int,
        # optionally pass provider if it has already been fetched
        provider: Provider | None = None,
    ) -> bool:
        """
        Returns true if the provider with the provided id is enabled for prescribing
        """
        if not provider:
            provider = self.providers.get_by_user_id(provider_id)

        return self.provider_enabled_for_prescribing(provider)

    @ddtrace.tracer.wrap()
    def provider_enabled_for_prescribing(self, provider: Provider) -> bool:
        """
        Returns true if the provider is enabled for prescribing
        """
        if not provider:
            return False

        return all(
            [
                provider.dosespot.get("clinic_key"),
                provider.dosespot.get("clinic_id"),
                provider.dosespot.get("user_id"),
            ]
        )

    @ddtrace.tracer.wrap()
    def get_full_names_for_providers(self, provider_ids: list[int]) -> Dict[int, str]:
        providers = self.providers.get_by_user_ids(provider_ids)
        full_names_by_ids = {
            provider.user_id: provider.full_name for provider in providers
        }

        return full_names_by_ids

    @ddtrace.tracer.wrap()
    def is_medical_provider(
        self,
        provider_id: int,
        # optionally pass provider if it has already been fetched
        provider: User | None = None,
    ) -> bool:
        """
        Returns true if any of the provider's verticals has filter_by_state=True
        provider may be optionally passed if it has already been fetched
        """
        if not provider:
            provider = self.providers.get_by_user_id(provider_id)

        if not provider:
            return False

        return any(v.filter_by_state for v in provider.verticals)

    @ddtrace.tracer.wrap()
    def in_certified_states(
        self,
        provider_id: int,
        state: State,
        # optionally pass provider if it has already been fetched
        provider: User | None = None,
    ) -> bool:
        """
        Returns true if the state is a state the provider is certified for
        """
        if not provider:
            provider = self.providers.get_by_user_id(provider_id)

        if not provider:
            return False

        return state in provider.certified_states

    @ddtrace.tracer.wrap()
    def get_latest_appointments_by_provider_id(
        self, current_user_id: int, provider_ids: List[int]
    ) -> Dict:
        # TODO: we should create a separate AppointmentService and move this over
        # For each provider we are returning, get the date of their
        # most recent completed appointment (if any) with this user.
        now = datetime.datetime.utcnow()
        latest_appointments = (
            Appointment.query.with_entities(
                Product.user_id, func.max(Appointment.member_ended_at)
            )
            .join(Appointment.product, Appointment.member_schedule)
            .filter(
                Schedule.user_id == current_user_id,
                Product.user_id.in_(provider_ids),
                Appointment.scheduled_start < now,
                Appointment.member_ended_at != None,
                Appointment.practitioner_ended_at != None,
                Appointment.cancelled_at == None,
            )
            .group_by(Product.user_id)
            .all()
        )

        return {t[0]: t[1] for t in latest_appointments}

    @ddtrace.tracer.wrap()
    def provider_contract_can_accept_availability_requests(
        self, provider: Provider
    ) -> bool:
        if not provider:
            return False

        request_availability_contract_types = [
            ContractType.BY_APPOINTMENT,
            ContractType.NON_STANDARD_BY_APPOINTMENT,
            ContractType.HYBRID_1_0,
            ContractType.HYBRID_2_0,
        ]
        has_availability_contract_type = (
            db.session.query(PractitionerContract)
            .filter(
                PractitionerContract.practitioner_id == provider.user_id,
                PractitionerContract.contract_type.in_(
                    request_availability_contract_types
                ),
                PractitionerContract.active == True,
            )
            .first()
        )
        if not has_availability_contract_type:
            return False
        return True

    @ddtrace.tracer.wrap()
    def list_available_practitioners_query(
        self,
        user: User,
        practitioner_ids: List[int],
        can_prescribe: bool = False,
        provider_steerage_sort: bool = False,
    ) -> List[PractitionerProfile]:
        """
        Takes a member, possible practitioner ids and can_prescribe and
        queries for available practitioner profile models
        """
        users = (
            PractitionerProfile.query.filter(
                PractitionerProfile.active.is_(True),
                PractitionerProfile.next_availability != None,
            )
            .join(
                PractitionerProfile.user,
                User.products,
                PractitionerProfile.verticals,
            )
            .filter(
                Product.is_active.is_(True),
                PractitionerProfile.user_id.in_(practitioner_ids),
            )
            .options(
                contains_eager(PractitionerProfile.user).options(
                    contains_eager(User.products), joinedload(User.schedule)
                ),
                contains_eager(PractitionerProfile.verticals),
            )
        )

        if can_prescribe:
            users = users.filter(
                Vertical.can_prescribe.is_(True), Provider.dosespot != {}
            )

        or_stmts = [
            Vertical.filter_by_state.is_(False),
            PractitionerProfile.anonymous_allowed.is_(True),
        ]
        if user.member_profile.state:
            users = users.outerjoin(
                practitioner_states,
                and_(
                    practitioner_states.c.user_id == PractitionerProfile.user_id,
                    practitioner_states.c.state_id == user.member_profile.state.id,
                ),
            )
            or_stmts.append(
                practitioner_states.c.state_id == user.member_profile.state.id
            )

        if user.is_enterprise:
            or_stmts.append((PractitionerProfile.ent_national.is_(True)))
            users = users.filter(PractitionerProfile.show_in_enterprise.is_(True))
        else:
            users = users.filter(PractitionerProfile.show_in_marketplace.is_(True))
        users = users.filter(or_(*or_stmts))

        if not provider_steerage_sort:
            users = self.sort_by_contract_and_next_availability(users)

        return users.all()

    @ddtrace.tracer.wrap()
    def _base_query(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Create the initial query for the provider search
        :param current_user: The user requesting the search. Usually the user logged in client side
        :param previous_provider_override: Determines whether to override in-state matching and allow previously
            seen providers to be surfaced in search
        :return Initial query logic to be extended later
        """
        base_query = (
            db.session.query(User)
            .join(Provider)
            .join(Role)
            .join(practitioner_verticals)
            .join(Vertical)
            .distinct(Provider.user_id)
            .filter(
                Role.name == ROLES.practitioner,
                Provider.active.is_(True),
                Vertical.deleted_at == None,
            )
        )

        base_query = base_query.options(
            joinedload(User.image),
            joinedload(User.practitioner_profile),
        )

        return base_query

    @staticmethod
    def _apply_state_matching(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        query,
        current_user: User,
        allow_anonymous_appointments: bool,
        allow_previous_providers_to_ignore_state_match: bool,
    ):
        if current_user.member_profile.is_international:
            # For international members, we need to exclude just one specific case:
            # US-based providers in filter_by_state=True Verticals who do not accept
            # anonymous appointments. This is because all non-US member, US-provider
            # matches will be anonymous appointments.

            # So we accept the converse, all providers who
            # are any of: outside the US, in a filter_by_state=False Vertical, or
            # accept anonymous appointments.
            query = query.filter(
                or_(
                    ((Provider.country_code != "US") & (Provider.country_code != None)),
                    Vertical.filter_by_state.is_(False),
                    Provider.anonymous_allowed.is_(True),
                )
            )
            return query

        # For US-based members, they may not match providers outside the US.
        # For now, we are assuming that null country-code means "inside US".
        query = query.filter(
            or_(Provider.country_code == "US", Provider.country_code == None)
        )

        # We apply two levels of state-matching filtering.
        # At the Vertical level, filter_by_state == True means that from a regulatory perspective,
        # providers must be licensed within that state in order to practice. However, in order to
        # accommodate sparse markets, we also allow providers from outside that state to match
        # as "anonymous appointments" (meaning the provider doesn't see the user's details).
        user_state_id = current_user.member_profile.state_id

        or_stmts = [
            Vertical.filter_by_state.is_(False),
        ]

        if current_user.member_profile and current_user.member_profile.state:
            # For US-residents, we are looking for providers in-state...
            or_stmts.append(
                practitioner_states.c.state_id == current_user.member_profile.state.id
            )
            if allow_anonymous_appointments:
                # or US-based providers who take anonymous appts.
                or_stmts.append(Provider.anonymous_allowed.is_(True))
        else:
            # For members without states set, we can only match them with anonymous appts
            # This should be a very rare case.
            stats.increment(
                metric_name="api.providersearch.current_member_state_unset",
                pod_name=stats.PodNames.CARE_DISCOVERY,
            )
            or_stmts.append(
                (
                    Vertical.filter_by_state.is_(True)
                    & Provider.anonymous_allowed.is_(True)
                )
            )

        if current_user.is_enterprise:
            or_stmts.append((Provider.ent_national.is_(True)))

        query = query.filter(or_(*or_stmts))

        # For some states and verticals, we have a dense-enough supply of providers
        # that we will be stricter about matching. In these (state, vertical) pairs,
        # we don't allow anonymous appointments. This is conceptually simple but the code
        # to implement this is complex because a provider supplies multiple verticals.
        # These pairs are stored in the VerticalInStateMatchState table.
        in_state_matching_vertical_ids_for_state = [
            visms.vertical_id
            for visms in VerticalInStateMatchState.query.filter_by(
                state_id=user_state_id
            ).with_entities(VerticalInStateMatchState.vertical_id)
        ]

        # Also, to make things even more complicated, we sometimes allow
        # providers who have previously matched our user to override even
        # this stricter matching setting.
        user_care_team = []
        if allow_previous_providers_to_ignore_state_match:
            user_care_team = (
                MemberPractitionerAssociation.query.filter_by(
                    user_id=current_user.id,
                    type=CareTeamTypes.APPOINTMENT,
                ).with_entities(MemberPractitionerAssociation.practitioner_id)
            ).all()

        care_team_practitioner_ids = [
            care_team.practitioner_id for care_team in user_care_team
        ]

        query = query.outerjoin(practitioner_states).filter(
            # To accommodate in-state matching, we'll require either one of the following:
            # (1) The Provider is in the user's state
            # (2) The Provider has previously met with the user prior to in-state matching being enabled
            # (3) The Provider isn't in the user's state but is configured for a vertical
            #     for which we don't do in-state matching
            (practitioner_states.columns["state_id"] == user_state_id)
            | (practitioner_states.columns["user_id"].in_(care_team_practitioner_ids))
            | ~(
                practitioner_verticals.columns["vertical_id"].in_(
                    in_state_matching_vertical_ids_for_state
                )
            ),
        )
        return query

    @staticmethod
    def _apply_needs_filtering(query, needs, need_ids, need_slugs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # A need is a collection of specialties and verticals.
        # A provider matches a need if that provider matches at least one vertical
        # AND at least one specialty within that need.
        # For example, "Your child's development" is a need with verticals
        # "Pediatrician", "Pediatric OT", "Developmental psychologist",
        # with specialties "Pediatric developmental delays", "Fine motor skills",
        # "Gross motor skills". A provider may have any of these vertical and any of
        # these specialties in order to match.

        # A need may have 0 specialties listed, and in that case a provider
        # does not need to match on specialty to match that need.

        # NeedRestrictedVerticals (called SpecialityRestrictedVerticals in admin)
        # are Verticals that have a more specific set of specialties linked to them
        # individually. For example, we might have a NRV with vertical "Speech Therapist"
        # and specialty "Pediatric behavioral concerns".
        # That means a Speech Therapist must have that specialty (and not
        # "Pediatric developmental delays" specialty from above) in order to match this need.

        # Sample needs spreadsheet:
        # https://docs.google.com/spreadsheets/d/12oBaMUbPF9iBBE2LyVgtgYftBUBMheZLiJUlMdPALmA/edit#gid=1394485364
        needs = needs or []
        need_ids = need_ids or []
        need_slugs = need_slugs or []
        query = (
            query.join(
                practitioner_specialties,
                practitioner_verticals.c.user_id == practitioner_specialties.c.user_id,
            )
            .join(
                Specialty,
                Specialty.id == practitioner_specialties.c.specialty_id,
            )
            .join(
                NeedVertical,
                NeedVertical.vertical_id == practitioner_verticals.c.vertical_id,
            )
            .join(
                Need,
                Need.id == NeedVertical.need_id,
            )
            .outerjoin(
                NeedRestrictedVertical,
                NeedVertical.id == NeedRestrictedVertical.need_vertical_id,
            )
            .outerjoin(need_specialty, need_specialty.c.need_id == Need.id)
            .filter(
                or_(
                    Need.name.in_(needs),
                    Need.id.in_(need_ids),
                    Need.slug.in_(need_slugs),
                ),
                or_(
                    # If there is no NRV and no specialty, a vertical match is enough.
                    # (Verticals were matched above).
                    and_(
                        NeedRestrictedVertical.need_vertical_id.is_(None),
                        need_specialty.c.specialty_id == None,
                    ),
                    # If there is no NRV but the need has a specialty, the specialty must
                    # match.
                    and_(
                        NeedRestrictedVertical.need_vertical_id.is_(None),
                        Specialty != None,
                        need_specialty.c.specialty_id == Specialty.id,
                    ),
                    # If there is a NRV, the specialty must match the one on the NRV.
                    and_(
                        NeedRestrictedVertical.need_vertical_id != None,
                        NeedRestrictedVertical.specialty_id == Specialty.id,
                    ),
                ),
            )
        )
        return query

    @staticmethod
    def _apply_messageable_states_filter(providers: List[User], current_user: User):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # We allow a provider to do async care if either:
        # 1 they practice in a vertical that does not filter by state, OR
        # (2 the user is in a state that generally allows async care AND
        #  3 they are certified to practice in the user's state.)

        # We already checked conditions 1 and 3 in _apply_state_matching,
        # so in this function we need to apply the additional filter of 2 for
        # providers that don't meet condition 1.
        if not current_user.member_profile.state:
            return []

        state = current_user.member_profile.state.abbreviation
        user_state_allows_async_care = state in ASYNC_CARE_ALLOWED_STATES

        providers_to_return = [
            p
            for p in providers
            if not p.practitioner_profile.verticals[0].filter_by_state
            or user_state_allows_async_care
        ]
        return providers_to_return

    @staticmethod
    def _apply_track_modifiers_filtering(
        query: Query, member_track_modifiers: List[TrackModifiers]
    ) -> Query:
        if TrackModifiers.DOULA_ONLY in member_track_modifiers:
            filtered_verticals = set(DOULA_ONLY_VERTICALS)
            filtered_verticals.remove(
                "care advocate"
            )  # we don't want to include care advocates in search results
            return query.filter(func.lower(Vertical.name).in_(filtered_verticals))

        # default to just return the query; we currently don't have any other track modifiers to evaluate
        return query

    @ddtrace.tracer.wrap()
    def get_contract_priorities(self, provider_user_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        today = datetime.datetime.today()
        return (
            db.session.query(
                PractitionerContract.practitioner_id,
                case(
                    PROVIDER_FIXED_COST_PRIORITIZATION,
                    else_=99,
                ).label("contract_priority"),
            )
            .filter(
                PractitionerContract.practitioner_id.in_(provider_user_ids),
                PractitionerContract.start_date <= today,
                or_(
                    PractitionerContract.end_date > today,
                    PractitionerContract.end_date.is_(None),
                ),
            )
            .all()
        )

    @ddtrace.tracer.wrap()
    def sort_by_contract_and_next_availability(self, provider_users_query):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        today = datetime.datetime.today()
        provider_users_query = provider_users_query.outerjoin(
            PractitionerContract,
            and_(
                User.id == PractitionerContract.practitioner_id,
                PractitionerContract.start_date <= today,
                or_(
                    PractitionerContract.end_date > today,
                    PractitionerContract.end_date.is_(None),
                ),
            ),
        ).order_by(
            case(
                PROVIDER_FIXED_COST_PRIORITIZATION,
                else_=99,
            )
        )
        provider_users_query = provider_users_query.order_by(Provider.next_availability)
        return provider_users_query

    @ddtrace.tracer.wrap()
    @db.from_app_replica
    def search(  # type: ignore[no-untyped-def] # Function is missing a return type annotation # noqa: C901 (benedict) -- this is indeed too complex, but I'm punting on it
        self,
        current_user: User,
        user_ids: List | None = None,
        bypass_availability: bool | None = None,
        name_query: str | None = None,
        exclude_CA_names: bool | None = None,
        verticals: List[str] | None = None,
        vertical_ids: List[int] | None = None,
        specialties: List[str] | None = None,
        specialty_ids: List[int] | None = None,
        needs: List[str] | None = None,
        need_ids: List[int] | None = None,
        need_slugs: List[str] | None = None,
        language_ids: List[int] | None = None,
        can_prescribe: bool | None = None,
        product_minutes: int | None = None,
        only_free: bool | None = None,
        available_in_next_hours: int | None = None,
        availability_scope_in_days: int | None = None,
        order_by: str | None = None,
        order_direction: str = "asc",
        limit: int | None = None,
        offset: int | None = None,
        include_count: bool | None = True,
        member_track_modifiers: List[TrackModifiers] | None = None,
        in_state_match: bool | None = None,
    ):
        """
        Search for Providers given the parameters
        :param member_track_modifiers:
        :param include_count if False, return -1 instead of the count, to reduce the queries
        :return Providers matching the criteria and the number of providers
        """

        users = self._base_query()
        users = self._apply_state_matching(
            users,
            current_user,
            allow_anonymous_appointments=True,
            allow_previous_providers_to_ignore_state_match=bool(user_ids),
        )

        if user_ids:
            users = users.filter(Provider.user_id.in_(user_ids))
        else:
            users = users.filter(Provider.default_cancellation_policy_id.isnot(None))
            if not bypass_availability:
                users = users.filter(
                    or_(
                        (Provider.next_availability >= datetime.datetime.utcnow()),
                        (Provider.show_when_unavailable.is_(True)),
                    )
                )

        if current_user.is_enterprise:
            users = users.filter(Provider.show_in_enterprise.is_(True))
        else:
            users = users.filter(Provider.show_in_marketplace.is_(True))

        if name_query:
            if exclude_CA_names:
                users = users.filter(not_(is_cx_vertical_name(Vertical.name)))
            name_query = "".join(name_query.split())
            name_query_string = f"%{name_query}%"
            users = users.filter(
                or_(
                    User.first_name.like(name_query_string),
                    User.last_name.like(name_query_string),
                    User.first_name.concat(User.last_name).like(name_query_string),
                    User.last_name.concat(User.first_name).like(name_query_string),
                )
            )

        if verticals is not None:
            users = users.filter(Vertical.name.in_(verticals))
        if vertical_ids is not None:
            users = users.filter(Vertical.id.in_(vertical_ids))
        if specialties is not None:
            users = (
                users.join(practitioner_specialties)
                .join(Specialty)
                .filter(Specialty.name.in_(specialties))
            )
        if specialty_ids is not None:
            users = (
                users.join(practitioner_specialties)
                .join(Specialty)
                .filter(Specialty.id.in_(specialty_ids))
            )
        if needs is not None or need_ids is not None or need_slugs is not None:
            users = self._apply_needs_filtering(users, needs, need_ids, need_slugs)
        if language_ids is not None:
            users = (
                users.join(practitioner_languages)
                .join(Language)
                .filter(Language.id.in_(language_ids))
            )

        if can_prescribe:
            users = users.filter(
                Vertical.can_prescribe.is_(True), Provider.dosespot != {}
            )
            log.warning("Provider search called with deprecated param 'can_prescribe'")

        if product_minutes not in (0, None):
            log.warning(
                "Provider search called with deprecated param 'product_minutes'"
            )
            users = (
                users.join(User, aliased=True)
                .join(Product)
                .filter(
                    Product.is_active.is_(True),
                    Product.minutes == product_minutes,
                )
            )
        if only_free:
            log.warning("Provider search called with deprecated param 'only_free'")
            current_credit = Credit.available_amount_for_user(current_user)
            users = (
                users.join(User, aliased=True)
                .join(Product)
                .filter(Product.is_active.is_(True), Product.price <= current_credit)
            )

        if available_in_next_hours not in (0, None):
            assert available_in_next_hours is not None  # mypy
            available_until = datetime.datetime.utcnow() + datetime.timedelta(
                hours=available_in_next_hours
            )
            users = users.filter(
                and_(
                    (Provider.next_availability >= datetime.datetime.utcnow()),
                    (Provider.next_availability < available_until),
                )
            )

        # Check for an availability scope, with the default being 0 meaning no limit
        if availability_scope_in_days and availability_scope_in_days > 0:
            # Set the limit 1 day beyond the limit using the user's time zone
            available_until = datetime.datetime.now(
                tz=timezone(current_user.timezone)
            ) + datetime.timedelta(days=availability_scope_in_days + 1)

            # Clear the time so that it is midnight (still in user's time zone)
            # and then convert to UTC
            available_until = available_until.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            ).astimezone(dateutil.tz.UTC)

            # Filter for anyone w/ availability before the scope limit or anyone that
            # has no availabilities but with show_when_unavailable is True
            users = users.filter(
                or_(
                    (Provider.next_availability < available_until),
                    and_(
                        Provider.show_when_unavailable.is_(True),
                        Provider.next_availability.is_(None),
                    ),
                )
            )

        if in_state_match:
            log.info(
                "Provider search is filtered by in_state_match",
                user_id=current_user.id,
                member_prescribable_state=current_user.member_profile.prescribable_state,
            )
            users = users.filter(
                Provider.verticals.any(can_prescribe=True),
                Provider.dosespot.isnot(None),
                Provider.certified_states.any(
                    abbreviation=current_user.member_profile.prescribable_state
                ),
            )

        # evaluate whether member has track_modifiers to limit the query response
        if member_track_modifiers:
            users = self._apply_track_modifiers_filtering(users, member_track_modifiers)

        if order_by == "next_availability":
            users = users.order_by(
                case([(Provider.next_availability.is_(None), 1)], else_=0),
                getattr(Provider.next_availability, order_direction)(),
            )
        elif order_by == "first_name":
            users = users.order_by(
                getattr(User.first_name, order_direction)(),
            )
        else:
            users = self.sort_by_contract_and_next_availability(users)

        if limit:
            if offset:
                users = users.offset(offset).limit(limit)
            else:
                users = users.limit(limit)

        users = (
            users.options(
                joinedload(User.practitioner_profile).selectinload(
                    PractitionerProfile.languages
                )
            )
            .options(
                joinedload(User.practitioner_profile).selectinload(
                    PractitionerProfile.verticals
                )
            )
            .options(
                joinedload(User.practitioner_profile).selectinload(
                    PractitionerProfile.certified_states
                )
            )
        )
        user_results = users.all()
        # if at all possible, we want to avoid calling users.count() because that fires
        # off another query which is almost as expensive as the total query
        count = -1
        if include_count:
            if limit:
                # in this case we have no choice since we're truncating the results
                count = users.count()
            else:
                count = len(user_results)

        return user_results, count

    def search_messageable(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        current_user: User,
        vertical_ids: List[int] | None = None,
        specialty_ids: List[int] | None = None,
        need_ids: List[int] | None = None,
        language_ids: List[int] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        member_track_modifiers: List[TrackModifiers] | None = None,
    ):
        # This search differs from the main search in a few key ways:
        # - We filter for providers, needs, and verticals that have messaging enabled / promoted
        # - We don't allow anonymous appointments
        # - We search by availability regardless of appointments, because we think
        #   that providers can quickly respond to messages even if they are booked
        users = self._base_query()

        # There is a subtlety here: if we expand needs into verticals, those
        # individual verticals must still have the promote_messaging flag turned on.
        users = users.filter(
            PractitionerProfile.messaging_enabled == True,
            Vertical.promote_messaging == True,
        )

        # Filter for needs that have this flag enabled
        if need_ids:
            need_ids = [
                r[0]
                for r in db.session.query(Need)
                .filter(Need.id.in_(need_ids), Need.promote_messaging == True)
                .with_entities(Need.id)
            ]

        users = self._apply_state_matching(
            users,
            current_user,
            allow_anonymous_appointments=False,
            allow_previous_providers_to_ignore_state_match=False,
        )
        if vertical_ids is not None:
            users = users.filter(Vertical.id.in_(vertical_ids))
        if specialty_ids is not None:
            users = (
                users.join(practitioner_specialties)
                .join(Specialty)
                .filter(Specialty.id.in_(specialty_ids))
            )
        if need_ids is not None:
            users = self._apply_needs_filtering(
                users, needs=[], need_ids=need_ids, need_slugs=[]
            )
        if language_ids is not None:
            users = (
                users.join(practitioner_languages)
                .join(Language)
                .filter(Language.id.in_(language_ids))
            )
        users = self._apply_track_modifiers_filtering(
            query=users, member_track_modifiers=member_track_modifiers or []
        )

        # We look for providers who have availability blocks in the next 72 hours
        # (regardless of whether they have appointments scheduled during those times
        # because we assume they can still find time to send messages.)
        users = (
            users.join(Schedule, Schedule.user_id == User.id)
            .join(ScheduleEvent, ScheduleEvent.schedule_id == Schedule.id)
            .filter(
                ScheduleEvent.ends_at >= datetime.datetime.now(),
                ScheduleEvent.starts_at
                < (datetime.datetime.now() + datetime.timedelta(hours=72)),
            )
            .group_by(User.id)
            .with_entities(User.id, func.min(ScheduleEvent.starts_at))
        )

        # Unfortunately at this point we have to make another query for the User
        # objects. The previous query returned a Tuple instead of ORM objects
        # because we included the func.min(starts_at) in the previous query and I couldn't
        # find another way to convert the returned tuples into a User object. We need
        # various fields off of it like avatar_url and verticals which are hard to recreate,
        # so just refetch them from the db here (it should be a small list anyways).
        user_ids = [u.id for u in users]
        users = (
            self._base_query()
            .filter(User.id.in_(user_ids))
            .options(
                joinedload(User.practitioner_profile).selectinload(
                    PractitionerProfile.languages
                )
            )
        )

        users = self._apply_messageable_states_filter(users, current_user)
        offset = offset or 0
        end = limit + offset if limit else None
        return users[offset:end]

    @ddtrace.tracer.wrap()
    @db.from_app_replica
    def search_for_search_api(
        self,
        current_user: User,
        user_ids: List[int],
        order_by: str | None = None,
        order_direction: str = "asc",
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[User]:
        """
        Search for a list of Providers by id.

        This method has been adapted from the above method "search", and is meant to be
        used after the search api (elasticsearch) returns a list of matches.

        All of the filters on the "Provider" table, such as the next_availability and
        show_when_unavailable filters, can most likely be moved to the elasticsearch
        query in the future.

        :return Providers matching the criteria
        """
        users = self._base_query()
        users = self._apply_state_matching(
            users,
            current_user,
            allow_anonymous_appointments=True,
            allow_previous_providers_to_ignore_state_match=bool(user_ids),
        )

        users = users.filter(Provider.user_id.in_(user_ids))
        users = users.filter(Provider.default_cancellation_policy_id.isnot(None))

        # Filter by availability
        users = users.filter(
            or_(
                (Provider.next_availability >= datetime.datetime.utcnow()),
                (Provider.show_when_unavailable.is_(True)),
            )
        )

        if current_user.is_enterprise:
            users = users.filter(Provider.show_in_enterprise.is_(True))
        else:
            users = users.filter(Provider.show_in_marketplace.is_(True))

        # Exclude CA names
        users = users.filter(not_(is_cx_vertical_name(Vertical.name)))

        # Order by first name
        users = users.order_by(
            getattr(User.first_name, order_direction)(),
        )

        if limit:
            if offset:
                users = users.offset(offset).limit(limit)
            else:
                users = users.limit(limit)

        users = (
            users.options(
                joinedload(User.practitioner_profile).selectinload(
                    PractitionerProfile.languages
                )
            )
            .options(
                joinedload(User.practitioner_profile).selectinload(
                    PractitionerProfile.verticals
                )
            )
            .options(
                joinedload(User.practitioner_profile).selectinload(
                    PractitionerProfile.certified_states
                )
            )
        )

        return list(users.all())

    @staticmethod
    def get_provider_languages(
        provider_ids: list[int], l10n_flag: bool
    ) -> list[ProviderLanguagesServiceResponse]:
        """
        Returns a set of language names and ids from a list of provider ids
        """
        languages = (
            db.session.query(Language.id, Language.name, Language.slug)
            .join(practitioner_languages)
            .filter(practitioner_languages.c.user_id.in_(provider_ids))
            .distinct()
            .all()
        )

        if l10n_flag:
            tbdf = TranslateDBFields()
            return [
                ProviderLanguagesServiceResponse(
                    id=l[0], name=tbdf.get_translated_language(l[2], "name", l[1])
                )
                for l in languages
            ]
        else:
            return [
                ProviderLanguagesServiceResponse(id=l[0], name=l[1]) for l in languages
            ]

    @staticmethod
    @ddtrace.tracer.wrap()
    def provider_can_member_interact(
        provider: Provider,
        modifiers: list[TrackModifiers],
        client_track_ids: list[int],
    ) -> bool:
        """
        Can a member interact with a provider?
        :param client_track_ids:
        :param provider: provider
        :param modifiers: list of modifiers from all the member's tracks
        :return True if the member is allowed to interact with the provider
        """

        # If no modifiers are provided, allow interaction by default
        if not modifiers:
            return True

        # Return True as long as any of the user's client_track_ids allows access to the provider's vertical(s)
        return any(
            vertical.has_access_with_track_modifiers(
                track_modifiers=modifiers, client_track_id=client_track_id
            )
            for vertical in provider.verticals
            for client_track_id in client_track_ids
        )

    @staticmethod
    @ddtrace.tracer.wrap()
    def get_scheduling_constraints(
        provider_id: int, product_id: int
    ) -> ProductSchedulingConstraintsStruct:
        constraints = ProviderRepositoryV2(db.session).get_scheduling_constraints(
            provider_id
        )
        product_prep_buffer = None
        if product_id:
            product_prep_buffer = (
                db.session.query(Product.prep_buffer)
                .filter(Product.id == product_id)
                .scalar()
            )
        return ProductSchedulingConstraintsStruct(
            prep_buffer=product_prep_buffer or constraints.default_prep_buffer,
            booking_buffer=constraints.booking_buffer,
            max_capacity=constraints.max_capacity,
            daily_intro_capacity=constraints.daily_intro_capacity,
        )

    @staticmethod
    @ddtrace.tracer.wrap()
    def is_member_matched_to_coach_for_active_track(
        member: User,
    ) -> bool:
        # This property call could be replaced by a call to a service method in the future
        # if it's eventually factored out to one.
        tracks = member.active_tracks

        for track in tracks:
            if track.name == TrackName.FERTILITY:
                if ProviderRepositoryV2(
                    db.session
                ).is_member_matched_to_coach_with_specialty(
                    member.id, CX_FERTILITY_CARE_COACHING_SLUG
                ):
                    return True
            elif track.name == TrackName.PREGNANCY:
                if ProviderRepositoryV2(
                    db.session
                ).is_member_matched_to_coach_with_specialty(
                    member.id, CX_PREGNANCY_CARE_COACHING_SLUG
                ):
                    return True
            # other tracks have no coaching specialties for now
        return False

    @staticmethod
    def get_provider_appointment_type_for_member(
        provider_vertical_filter_by_state: bool,
        is_instate_match: bool,
        provider_is_international: bool,
        member_is_international: bool,
        member_org_coaching_only: bool,
        privacy: str = "basic",
    ) -> str:
        privilege_type = ProviderService.get_provider_privilege_type_for_member(
            provider_vertical_filter_by_state,
            is_instate_match,
            provider_is_international,
            member_is_international,
            member_org_coaching_only,
        )
        return Appointment.get_appointment_type_from_privilege_type(
            privilege_type, privacy
        ).value

    @staticmethod
    def get_provider_privilege_type_for_member(
        provider_vertical_filter_by_state: bool,
        is_instate_match: bool,
        provider_is_international: bool,
        member_is_international: bool,
        member_org_coaching_only: bool,
    ) -> str:
        enable_fix_ff = feature_flags.bool_variation("disco-5342-fix", default=False)
        if not enable_fix_ff:
            # NB: Prior to 2024/11/14 we were relying on the clients to compute
            # "appointment type" based on these factors. We are starting to
            # shift this logic over to the backend. We are also eliminating the
            # "anonymous" appointment type as part of this migration.
            # This function returns the "most privileged" type of appointment
            # that this provider can provider for this member.
            if member_is_international or provider_is_international:
                # NB: this is flipped in priority with the state-code check
                # in the PRD https://docs.google.com/document/d/1FsO317-HRkXmpmqEu20e5nRMA88h2TJ64OvsNC4PZOw/edit?tab=t.0
                # but the effect should be the same since all intl provider
                # appointments are international type.
                # Putting this check higher insulates us from possible weirdness of
                # intl state codes.
                return PrivilegeType.INTERNATIONAL.value
            elif not provider_vertical_filter_by_state:
                # Implicit is that as of 2024/11/14, only US-based
                # verticals will sometimes have filter_by_state == False,
                # all intl verticals are filter_by_state == True
                return PrivilegeType.STANDARD.value
            elif not is_instate_match:
                return PrivilegeType.EDUCATION_ONLY.value
            elif member_org_coaching_only:
                return PrivilegeType.EDUCATION_ONLY.value
            else:
                return PrivilegeType.STANDARD.value
        else:
            if not provider_vertical_filter_by_state:
                return PrivilegeType.STANDARD.value
            elif member_is_international or provider_is_international:
                return PrivilegeType.INTERNATIONAL.value
            elif not is_instate_match:
                return PrivilegeType.EDUCATION_ONLY.value
            elif member_org_coaching_only:
                return PrivilegeType.EDUCATION_ONLY.value
            else:
                return PrivilegeType.STANDARD.value
