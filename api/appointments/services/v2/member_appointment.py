from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy.orm import joinedload
from sqlalchemy.orm.exc import NoResultFound

from appointments.models.constants import APPOINTMENT_STATES
from appointments.models.needs_and_categories import Need, NeedAppointment
from appointments.models.schedule import Schedule
from appointments.models.v2.member_appointment import MemberAppointmentStruct
from appointments.models.v2.member_appointments import MemberAppointmentsListElement
from appointments.repository.v2.member_appointment import MemberAppointmentRepository
from appointments.repository.v2.member_appointments import (
    MemberAppointmentsListRepository,
)
from appointments.schemas.appointments import (
    CANCELLATION_SURVEY_QUESTIONNAIRE_OID,
    MEMBER_RATING_OIDS,
)
from appointments.schemas.v2.member_appointment import (
    MemberAppointmentByIdServiceResponse,
    MemberAppointmentServiceResponseCertifiedState,
    MemberAppointmentServiceResponseNeed,
    MemberAppointmentServiceResponseProvider,
    MemberAppointmentServiceResponseVertical,
)
from appointments.schemas.v2.member_appointments import (
    MemberAppointmentsListServiceResponseElement,
)
from appointments.utils.appointment_utils import (
    get_appointment_type,
    get_member_appointment_state,
    is_rx_enabled,
)
from appointments.utils.errors import (
    AppointmentNotFoundException,
    MemberNotFoundException,
    ProviderNotFoundException,
)
from authn.models.user import User
from clinical_documentation.services.member_questionnaire_service import (
    MemberQuestionnairesService,
)
from glidepath import glidepath
from models.products import Product
from models.profiles import CareTeamTypes, MemberProfile, PractitionerProfile
from mpractice.models.common import Pagination
from providers.service.provider import ProviderService
from storage.connection import db
from tracks.utils.common import get_active_member_track_modifiers
from utils.log import logger

log = logger(__name__)

__all__ = ["MemberAppointmentService"]

RECONNECTING_STATES = (
    APPOINTMENT_STATES.scheduled,
    APPOINTMENT_STATES.overdue,
    APPOINTMENT_STATES.occurring,
    APPOINTMENT_STATES.overflowing,
)


class MemberAppointmentService:
    def get_member_appointment_by_id(
        self, user: User, appointment_id: int, skip_check_permissions: bool = False
    ) -> MemberAppointmentByIdServiceResponse:
        """
        Gets a user's appointment by id

        The appointment "service boundary" is crossed in the following methods
        (these boundaries will need to be refactored into external calls
        when moving to triforce):
            - _get_member_appointment_by_id_external_dependencies()

        :param user: the member or practitioner accessing the appointment
        :param appointment_id: deobfuscated appointment_id
        """
        member_appointment_repository = MemberAppointmentRepository(session=db.session)
        appointment = member_appointment_repository.get_by_id(appointment_id)
        if not appointment:
            log.error(
                "Appointment not found", user_id=user.id, appointment_id=appointment_id
            )
            raise AppointmentNotFoundException(appointment_id)

        (
            sqla_member_profile,
            provider,
            rx_enabled,
            need,
        ) = self._get_member_appointment_by_id_external_dependencies(appointment)

        product_ids = [appointment.product_id]
        vertical_specific_oids_by_product_id: dict[
            int, list[str]
        ] = MemberQuestionnairesService().get_vertical_specific_member_rating_questionnaire_oids_by_product_id(
            [product_ids], user
        )

        # Check permissions
        user_is_member = user.id == sqla_member_profile.user_id
        if not skip_check_permissions and not user_is_member:
            log.error(
                "User is not an associated member",
                user_id=user.id,
                appointment_id=appointment_id,
            )
            raise AppointmentNotFoundException(appointment_id)

        state = get_member_appointment_state(
            appointment.scheduled_start,
            appointment.scheduled_end,
            appointment.member_started_at,
            appointment.member_ended_at,
            appointment.practitioner_started_at,
            appointment.practitioner_ended_at,
            appointment.cancelled_at,
            appointment.disputed_at,
        )
        return MemberAppointmentByIdServiceResponse(
            id=appointment_id,
            state=state,  # type: ignore[arg-type] # Argument "state" to "MemberAppointmentByIdServiceResponse" has incompatible type "Optional[str]"; expected "str"
            product_id=appointment.product_id,
            pre_session_notes=appointment.client_notes,
            cancelled_at=appointment.cancelled_at,
            scheduled_start=appointment.scheduled_start,
            scheduled_end=appointment.scheduled_end,
            privacy=appointment.privacy,
            appointment_type=get_appointment_type(appointment).value,
            rx_enabled=rx_enabled,
            video_practitioner_token=None,
            video_member_token=None,
            video_session_id=None,
            member_tel_number=sqla_member_profile.phone_number,  # type: ignore[arg-type] # Argument "member_tel_number" to "MemberAppointmentByIdServiceResponse" has incompatible type "Optional[str]"; expected "str"
            member_state=sqla_member_profile.state,
            survey_types=self._get_survey_types(
                state == APPOINTMENT_STATES.cancelled,
                appointment.product_id,
                vertical_specific_oids_by_product_id,
            ),
            provider=provider,
            member_started_at=appointment.member_started_at,
            member_ended_at=appointment.member_ended_at,
            practitioner_started_at=appointment.practitioner_started_at,
            practitioner_ended_at=appointment.practitioner_ended_at,
            member_disconnected_at=appointment.member_disconnected_at,  # type: ignore[arg-type] # Argument "member_disconnected_at" to "MemberAppointmentByIdServiceResponse" has incompatible type "Optional[datetime]"; expected "datetime"
            practitioner_disconnected_at=appointment.practitioner_disconnected_at,  # type: ignore[arg-type] # Argument "practitioner_disconnected_at" to "MemberAppointmentByIdServiceResponse" has incompatible type "Optional[datetime]"; expected "datetime"
            phone_call_at=appointment.phone_call_at,
            need=need,
        )

    def _get_member_appointment_by_id_external_dependencies(
        self,
        appointment: MemberAppointmentStruct,
    ) -> Tuple[
        MemberProfile,
        MemberAppointmentServiceResponseProvider,
        bool,
        MemberAppointmentServiceResponseNeed,
    ]:
        """
        Gets dependencies from outside of "appointment" boundaries
        """
        try:
            sqla_product: Product = (
                db.session.query(Product)
                .filter(Product.id == appointment.product_id)
                .options(
                    joinedload(Product.practitioner)
                    .joinedload("practitioner_profile")
                    .selectinload("certified_states"),
                    joinedload(Product.practitioner)
                    .joinedload("practitioner_profile")
                    .joinedload("verticals"),
                    joinedload(Product.practitioner)
                    .joinedload("practitioner_profile")
                    .joinedload("certified_states"),
                )
                .one()
            )
            sqla_provider: User = sqla_product.practitioner
            sqla_provider_profile: PractitionerProfile = (
                sqla_provider.practitioner_profile
            )
        except NoResultFound:
            log.error(
                "Could not find related provider",
                product_id=appointment.product_id,
            )
            raise ProviderNotFoundException

        try:
            sqla_member_schedule: Schedule = (
                db.session.query(Schedule)
                .filter(Schedule.id == appointment.member_schedule_id)
                .one()
            )
            sqla_member_profile: MemberProfile = (
                sqla_member_schedule.user.member_profile
            )
        except NoResultFound:
            log.error(
                "Could not find related member",
                member_schedule_id=appointment.member_schedule_id,
            )
            raise MemberNotFoundException

        active_tracks = sqla_member_profile.active_tracks
        member_track_modifiers = get_active_member_track_modifiers(active_tracks)

        client_track_ids = [track.client_track_id for track in active_tracks]

        sqla_provider_verticals = sqla_provider_profile.verticals
        verticals = []
        with glidepath.respond():
            for vertical in sqla_provider_verticals:
                # None of the properties accessed are relations
                # therefore there should be no sql calls made here
                verticals.append(
                    MemberAppointmentServiceResponseVertical(
                        id=vertical.id,
                        name=vertical.name,
                        slug=vertical.slug,
                        description=vertical.description,
                        can_prescribe=vertical.can_prescribe,
                        filter_by_state=vertical.filter_by_state,
                    )
                )

            certified_states = []
            for certified_state in sqla_provider_profile.certified_states:
                certified_states.append(
                    MemberAppointmentServiceResponseCertifiedState(
                        id=certified_state.id,
                        name=certified_state.name,
                        abbreviation=certified_state.abbreviation,
                    )
                )

        # Get care team types for member and filter for this appointment's provider
        member_care_team_with_type: list[Tuple[User, CareTeamTypes]] = [
            x
            for x in sqla_member_profile.user.care_team_with_type
            if x[0].id == sqla_provider.id
        ]
        if member_care_team_with_type:
            care_team_type = member_care_team_with_type.pop()[1]
        else:
            care_team_type = None

        can_prescribe = ProviderService().provider_can_prescribe_in_state(
            sqla_provider_profile,
            sqla_member_profile.prescribable_state,
        )

        provider = MemberAppointmentServiceResponseProvider(
            id=sqla_provider_profile.user_id,
            avatar_url=sqla_provider.avatar_url,
            name=sqla_provider_profile.full_name,
            first_name=sqla_provider_profile.first_name,  # type: ignore[arg-type] # Argument "first_name" to "MemberAppointmentServiceResponseProvider" has incompatible type "Optional[str]"; expected "str"
            care_team_type=care_team_type,  # type: ignore[arg-type] # Argument "care_team_type" to "MemberAppointmentServiceResponseProvider" has incompatible type "Optional[CareTeamTypes]"; expected "CareTeamTypes"
            verticals=verticals,
            certified_states=certified_states,
            can_prescribe=can_prescribe,
            messaging_enabled=sqla_provider_profile.messaging_enabled,
            is_care_advocate=sqla_provider_profile.is_cx,
            can_member_interact=ProviderService().provider_can_member_interact(
                provider=sqla_provider_profile,
                modifiers=member_track_modifiers,
                client_track_ids=client_track_ids,
            ),
        )

        rx_enabled = is_rx_enabled(
            appointment, sqla_provider_profile, sqla_member_profile
        )

        sqla_need = (
            db.session.query(Need)
            .join(NeedAppointment)
            .filter(NeedAppointment.appointment_id == appointment.id)
            .one_or_none()
        )
        need = (
            MemberAppointmentServiceResponseNeed(
                id=sqla_need.id,
                name=sqla_need.name,
            )
            if sqla_need
            else None
        )
        return (sqla_member_profile, provider, rx_enabled, need)  # type: ignore[return-value] # Incompatible return value type (got "Tuple[MemberProfile, MemberAppointmentServiceResponseProvider, bool, Optional[MemberAppointmentServiceResponseNeed]]", expected "Tuple[MemberProfile, MemberAppointmentServiceResponseProvider, bool, MemberAppointmentServiceResponseNeed]")

    def list_member_appointments(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self,
        user,
        member_id: int,
        scheduled_start: datetime,
        scheduled_end: datetime,
        limit: int = 10,
        offset: int = 0,
        order_direction: str = "desc",
    ) -> Tuple[list[MemberAppointmentsListServiceResponseElement], Pagination]:
        """
        Gets a user's appointments

        :param member_id: the id of the member to get appointments for
        :param scheduled_start: start of the range to look for appointments
        :param scheduled_end: end of the range to look for appointments
        :param limit: pagination limit
        :param offset: pagination offset
        :param order_direction: sort by appointment's start time. Defaults to descending
        """
        member_appointment_repository = MemberAppointmentsListRepository(
            session=db.session
        )
        appointments: list[
            MemberAppointmentsListElement
        ] = member_appointment_repository.list_member_appointments(
            member_id,
            scheduled_start,
            scheduled_end,
            limit=limit,
            offset=offset,
            order_direction=order_direction,
        )

        count = member_appointment_repository.count_member_appointments(
            member_id, scheduled_start, scheduled_end
        )

        log.info(
            "Appointments found for member",
            member_id=member_id,
            len_appointments=len(appointments),
        )

        (
            provider_by_product_id,
            needs_by_appt_id,
        ) = self._list_member_appointments_external_dependencies(
            member_id,
            appointments,
        )

        # TODO: determine if we need the flag here
        # Some verticals have a specific member rating survey instead of the standard one
        # Get a map of them here. This is an external dependency.
        product_ids = [a.product_id for a in appointments]
        vertical_specific_oids_by_product_id: dict[
            int, list[str]
        ] = MemberQuestionnairesService().get_vertical_specific_member_rating_questionnaire_oids_by_product_id(
            product_ids, user
        )

        appointments_response = []
        for appointment in appointments:
            state = get_member_appointment_state(
                appointment.scheduled_start,
                appointment.scheduled_end,
                appointment.member_started_at,
                appointment.member_ended_at,
                appointment.practitioner_started_at,
                appointment.practitioner_ended_at,
                appointment.cancelled_at,
                appointment.disputed_at,
            )

            need = needs_by_appt_id.get(appointment.id)
            appointments_response.append(
                MemberAppointmentsListServiceResponseElement(
                    id=appointment.id,
                    state=state,
                    product_id=appointment.product_id,
                    provider=provider_by_product_id[appointment.product_id],
                    pre_session_notes=appointment.client_notes,
                    cancelled_at=appointment.cancelled_at,
                    scheduled_start=appointment.scheduled_start,
                    scheduled_end=appointment.scheduled_end,
                    privacy=appointment.privacy,
                    appointment_type=get_appointment_type(appointment).value,  # type: ignore[arg-type] # Argument 1 to "get_appointment_type" has incompatible type "MemberAppointmentsListElement"; expected "MemberAppointmentStruct"
                    member_started_at=appointment.member_started_at,
                    member_ended_at=appointment.member_ended_at,
                    practitioner_started_at=appointment.practitioner_started_at,
                    practitioner_ended_at=appointment.practitioner_ended_at,
                    member_disconnected_at=appointment.member_disconnected_at,  # type: ignore[arg-type] # Argument "member_disconnected_at" to "MemberAppointmentsListServiceResponseElement" has incompatible type "Optional[datetime]"; expected "datetime"
                    practitioner_disconnected_at=appointment.practitioner_disconnected_at,  # type: ignore[arg-type] # Argument "practitioner_disconnected_at" to "MemberAppointmentsListServiceResponseElement" has incompatible type "Optional[datetime]"; expected "datetime"
                    phone_call_at=appointment.phone_call_at,
                    survey_types=self._get_survey_types(
                        state == APPOINTMENT_STATES.cancelled,
                        appointment.product_id,
                        vertical_specific_oids_by_product_id,
                    ),
                    need=need,  # type: ignore[arg-type] # Argument "need" to "MemberAppointmentsListServiceResponseElement" has incompatible type "Optional[MemberAppointmentServiceResponseNeed]"; expected "MemberAppointmentServiceResponseNeed"
                )
            )

        pagination = Pagination(
            order_direction=order_direction,
            limit=limit,
            offset=offset,
            total=count,
        )
        return (appointments_response, pagination)

    def _get_survey_types(
        self,
        is_cancelled: bool,
        product_id: int,
        member_rating_oids_by_product_id: dict[int, list[str]],
    ) -> list[str]:
        survey_types = []
        if is_cancelled:
            survey_types.append(CANCELLATION_SURVEY_QUESTIONNAIRE_OID)

        # We want to add a member rating survey. Use a vertical-specific one
        # if one exists, otherwise use the generic ones.
        if product_id in member_rating_oids_by_product_id:
            survey_types.extend(member_rating_oids_by_product_id[product_id])
        else:
            survey_types.extend(MEMBER_RATING_OIDS)
        return survey_types

    def _list_member_appointments_external_dependencies(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self, member_id, appointments
    ) -> Tuple[
        dict[int, MemberAppointmentServiceResponseProvider],
        dict[int, MemberAppointmentServiceResponseNeed],
    ]:
        """
        Gets products and needs from outside of "appointments" service boundaries
        """
        appointment_ids = [a.id for a in appointments]
        product_ids = [a.product_id for a in appointments]
        sqla_products: list[Product] = (
            db.session.query(Product)
            .filter(Product.id.in_(product_ids))
            .options(
                joinedload(Product.practitioner)
                .joinedload("practitioner_profile")
                .selectinload("certified_states"),
                joinedload(Product.practitioner)
                .joinedload("practitioner_profile")
                .joinedload("verticals"),
                joinedload(Product.practitioner)
                .joinedload("practitioner_profile")
                .joinedload("certified_states"),
            )
            .all()
        )

        sqla_member_profile: MemberProfile = (
            db.session.query(MemberProfile)
            .filter(MemberProfile.user_id == member_id)
            .one()
        )
        member_care_team_with_types = sqla_member_profile.care_team_with_type

        active_tracks = sqla_member_profile.active_tracks
        member_track_modifiers = get_active_member_track_modifiers(
            sqla_member_profile.active_tracks
        )

        client_track_ids = [track.client_track_id for track in active_tracks]

        with glidepath.respond():
            provider_by_product_id = {}
            for product in sqla_products:
                sqla_practitioner: User = product.practitioner
                sqla_verticals = product.practitioner.practitioner_profile.verticals

                # Create a list of vertical response objects for each vertical associated
                # with the product
                verticals = [
                    MemberAppointmentServiceResponseVertical(
                        id=vertical.id,
                        name=vertical.name,
                        slug=vertical.slug,
                        description=vertical.description,
                        can_prescribe=vertical.can_prescribe,
                        filter_by_state=vertical.filter_by_state,
                    )
                    for vertical in sqla_verticals
                ]

                certified_states: list[
                    MemberAppointmentServiceResponseCertifiedState
                ] = [
                    MemberAppointmentServiceResponseCertifiedState(
                        id=certified_state.id,
                        name=certified_state.name,
                        abbreviation=certified_state.abbreviation,
                    )
                    for certified_state in sqla_practitioner.profile.certified_states  # type: ignore[union-attr] # Item "None" of "Union[PractitionerProfile, MemberProfile, None]" has no attribute "certified_states"
                ]

                # Get care team types for member and filter for this appointment's provider
                member_care_team_with_type: list[Tuple[User, CareTeamTypes]] = [
                    x
                    for x in member_care_team_with_types
                    if x[0].id == sqla_practitioner.id
                ]
                if member_care_team_with_type:
                    care_team_type = member_care_team_with_type.pop()[1]
                else:
                    care_team_type = None

                provider_by_product_id[
                    product.id
                ] = MemberAppointmentServiceResponseProvider(
                    id=sqla_practitioner.id,
                    avatar_url=sqla_practitioner.avatar_url,
                    verticals=verticals,
                    certified_states=certified_states,
                    name=sqla_practitioner.full_name,
                    first_name=sqla_practitioner.first_name,  # type: ignore[arg-type] # Argument "first_name" to "MemberAppointmentServiceResponseProvider" has incompatible type "Optional[str]"; expected "str"
                    can_prescribe=ProviderService().enabled_for_prescribing(
                        sqla_practitioner.id,
                        sqla_practitioner.practitioner_profile,
                    ),
                    care_team_type=care_team_type,  # type: ignore[arg-type] # Argument "care_team_type" to "MemberAppointmentServiceResponseProvider" has incompatible type "Optional[CareTeamTypes]"; expected "CareTeamTypes"
                    messaging_enabled=sqla_practitioner.practitioner_profile.messaging_enabled,
                    is_care_advocate=sqla_practitioner.practitioner_profile.is_cx,
                    can_member_interact=ProviderService().provider_can_member_interact(
                        provider=sqla_practitioner.practitioner_profile,
                        modifiers=member_track_modifiers,
                        client_track_ids=client_track_ids,
                    ),
                )

        sqla_needs = (
            db.session.query(NeedAppointment.appointment_id, Need.id, Need.name)
            .join(Need)
            .filter(NeedAppointment.appointment_id.in_(appointment_ids))
            .all()
        )
        needs_by_appt_id = {
            x[0]: MemberAppointmentServiceResponseNeed(id=x[1], name=x[2])
            for x in sqla_needs
        }

        return provider_by_product_id, needs_by_appt_id

    def get_current_or_next_appointment_for_member(
        self, user: User
    ) -> Optional[MemberAppointmentStruct]:
        member_appointment_repository = MemberAppointmentRepository(session=db.session)
        appointment = member_appointment_repository.get_current_or_next(user.id)
        return appointment
