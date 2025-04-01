from __future__ import annotations

import json
from datetime import datetime
from typing import List, Tuple

from sqlalchemy.orm.scoping import ScopedSession

from appointments.models.constants import PRIVACY_CHOICES
from appointments.services.common import obfuscate_appointment_id
from authn.models.user import User
from geography import Country, CountryRepository
from models.verticals_and_specialties import is_cx_vertical_name
from mpractice.error import MissingMemberError, MissingPractitionerError
from mpractice.models.appointment import (
    MPracticeMember,
    MPracticePractitioner,
    ProviderAppointment,
    ProviderAppointmentForList,
    Vertical,
)
from mpractice.models.common import (
    OrderDirection,
    Pagination,
    ProviderAppointmentFilter,
)
from mpractice.models.translated_appointment import (
    MemberProfile,
    Need,
    Organization,
    PractitionerProfile,
    Product,
    Profiles,
    SessionMetaInfo,
    State,
    TranslatedMPracticeMember,
    TranslatedMPracticePractitioner,
    TranslatedProviderAppointment,
    TranslatedProviderAppointmentForList,
)
from mpractice.repository.mpractice_member import MPracticeMemberRepository
from mpractice.repository.mpractice_practitioner import MPracticePractitionerRepository
from mpractice.repository.provider_appointment import ProviderAppointmentRepository
from mpractice.repository.provider_appointment_for_list import (
    ProviderAppointmentForListRepository,
)
from mpractice.repository.transaction import TransactionRepository
from mpractice.service.note import MPracticeNoteService
from mpractice.utils import appointment_utils, rx_utils
from storage.connection import db
from tracks import TrackSelectionService
from utils.log import logger

log = logger(__name__)


class ProviderAppointmentService:
    def __init__(
        self,
        session: ScopedSession | None = None,
        country_repo: CountryRepository | None = None,
        provider_appt_repo: ProviderAppointmentRepository | None = None,
        provider_appt_for_list_repo: ProviderAppointmentForListRepository | None = None,
        member_repo: MPracticeMemberRepository | None = None,
        practitioner_repo: MPracticePractitionerRepository | None = None,
        transaction_repo: TransactionRepository | None = None,
        note_service: MPracticeNoteService | None = None,
        track_selection_service: TrackSelectionService | None = None,
        include_soft_deleted_question_sets: bool | None = False,
    ):
        self.session = session or db.session
        self.country_repo = country_repo or CountryRepository(session=self.session)
        self.provider_appt_repo = provider_appt_repo or ProviderAppointmentRepository(
            session=self.session
        )
        self.provider_appt_for_list_repo = (
            provider_appt_for_list_repo
            or ProviderAppointmentForListRepository(session=self.session)
        )
        self.member_repo = member_repo or MPracticeMemberRepository(
            session=self.session
        )
        self.practitioner_repo = practitioner_repo or MPracticePractitionerRepository(
            session=self.session
        )
        self.transaction_repo = transaction_repo or TransactionRepository(
            session=self.session
        )
        self.note_service = note_service or MPracticeNoteService(
            session=self.session,
            include_soft_deleted_question_sets=include_soft_deleted_question_sets,
        )
        self.track_selection_service = (
            track_selection_service or TrackSelectionService()
        )

    def get_provider_appointment_by_id(
        self, appointment_id: int, user: User
    ) -> TranslatedProviderAppointment | None:
        appointment = self.provider_appt_repo.get_appointment_by_id(
            appointment_id=appointment_id
        )
        if not appointment:
            log.warn(f"Appointment {appointment_id} does not exist")
            return None

        latest_post_session_note = self.provider_appt_repo.get_latest_post_session_note(
            appointment_id=appointment_id
        )

        translated_member = self.get_translated_member(
            member_id=appointment.member_id, appointment_privacy=appointment.privacy
        )
        if not translated_member:
            raise MissingMemberError()

        translated_practitioner = self.get_translated_practitioner(
            practitioner_id=appointment.practitioner_id
        )
        if not translated_practitioner:
            raise MissingPractitionerError()

        return self.translate_provider_appointment(
            user=user,
            appointment=appointment,
            latest_post_session_note=latest_post_session_note,
            translated_member=translated_member,
            translated_practitioner=translated_practitioner,
        )

    def translate_provider_appointment(
        self,
        user: User,
        appointment: ProviderAppointment,
        latest_post_session_note: SessionMetaInfo | None,
        translated_member: TranslatedMPracticeMember,
        translated_practitioner: TranslatedMPracticePractitioner,
    ) -> TranslatedProviderAppointment:
        transaction_info = self.transaction_repo.get_transaction_info_by_appointment_id(
            appointment_id=appointment.id
        )
        structured_internal_note = self.note_service.get_structured_internal_note(
            appointment_id=appointment.id, practitioner_id=translated_practitioner.id
        )
        provider_addenda = self.note_service.get_provider_addenda_and_questionnaire(
            appointment_id=appointment.id, practitioner_id=translated_practitioner.id
        )

        state = appointment_utils.get_state(
            scheduled_start=appointment.scheduled_start,
            scheduled_end=appointment.scheduled_end,
            member_started_at=appointment.member_started_at,
            member_ended_at=appointment.member_ended_at,
            practitioner_started_at=appointment.practitioner_started_at,
            practitioner_ended_at=appointment.practitioner_ended_at,
            cancelled_at=appointment.cancelled_at,
            disputed_at=appointment.disputed_at,
            payment_captured_at=(
                transaction_info.payment_captured_at if transaction_info else None
            ),
            payment_amount=(
                transaction_info.payment_amount if transaction_info else None
            ),
            credit_latest_used_at=(
                transaction_info.credit_latest_used_at if transaction_info else None
            ),
            total_used_credits=(
                transaction_info.total_used_credits if transaction_info else None
            ),
            fees_count=transaction_info.fees_count if transaction_info else None,
            appointment_json=appointment.json,
        )
        need = (
            Need(
                id=appointment.need_id,
                name=appointment.need_name,
                description=appointment.need_description,
            )
            if appointment.need_id
            else None
        )
        product = Product(
            practitioner=translated_practitioner, vertical_id=appointment.vertical_id
        )
        post_session = (
            SessionMetaInfo(created_at=None, draft=None, notes="")
            if latest_post_session_note is None
            else latest_post_session_note
        )

        # rx info
        prescription_info = rx_utils.get_prescription_info(
            member=translated_member, practitioner=translated_practitioner
        )
        rx_enabled = rx_utils.rx_enabled(
            appointment_privacy=appointment.privacy,
            member=translated_member,
            practitioner=translated_practitioner,
        )
        rx_reason = rx_utils.get_rx_reason(
            rx_enabled=rx_enabled,
            member=translated_member,
            practitioner=translated_practitioner,
            prescription_info=prescription_info,
        )
        rx_written_via = rx_utils.get_rx_written_via(appointment.json)

        cancelled_note = None
        member_disconnected_at = None
        practitioner_disconnected_at = None
        if appointment.json:
            try:
                appointment_json = json.loads(appointment.json)
                cancelled_note = appointment_json.get("cancelled_note")
                if appointment_json.get("member_disconnected_at"):
                    member_disconnected_at = datetime.fromisoformat(
                        appointment_json.get("member_disconnected_at")
                    )
                if appointment_json.get("practitioner_disconnected_at"):
                    practitioner_disconnected_at = datetime.fromisoformat(
                        appointment_json.get("practitioner_disconnected_at")
                    )
            except ValueError as e:
                log.error(
                    f"Failed to load value from appointment json due to {e}",
                    appointment_id=appointment.id,
                )

        # only display member email to care advocates
        is_care_advocate = False
        if (
            translated_practitioner.profiles
            and translated_practitioner.profiles.practitioner
            and translated_practitioner.profiles.practitioner.vertical_objects
        ):
            provider_verticals = (
                translated_practitioner.profiles.practitioner.vertical_objects
            )
            is_care_advocate = any(
                is_cx_vertical_name(v.name) for v in provider_verticals
            )
        if not is_care_advocate:
            translated_member.email = None

        return TranslatedProviderAppointment(
            id=obfuscate_appointment_id(appointment.id),
            appointment_id=appointment.id,
            scheduled_start=appointment.scheduled_start,
            scheduled_end=appointment.scheduled_end,
            cancelled_at=appointment.cancelled_at,
            cancellation_policy=appointment.cancellation_policy_name,
            cancelled_note=cancelled_note,
            member_started_at=appointment.member_started_at,
            member_ended_at=appointment.member_ended_at,
            member_disconnected_at=member_disconnected_at,
            practitioner_started_at=appointment.practitioner_started_at,
            practitioner_ended_at=appointment.practitioner_ended_at,
            practitioner_disconnected_at=practitioner_disconnected_at,
            phone_call_at=appointment.phone_call_at,
            privacy=appointment.privacy,
            privilege_type=appointment.privilege_type,
            purpose=appointment.purpose,
            state=state,
            pre_session=SessionMetaInfo(notes=appointment.client_notes),
            post_session=post_session,
            need=need,
            product=product,
            member=translated_member,
            prescription_info=prescription_info
            if appointment.privacy != PRIVACY_CHOICES.anonymous
            else None,
            rx_enabled=rx_enabled,
            rx_reason=rx_reason,
            rx_written_via=rx_written_via,
            structured_internal_note=structured_internal_note,
            provider_addenda=provider_addenda,
        )

    def get_translated_member(
        self, member_id: int, appointment_privacy: str | None
    ) -> TranslatedMPracticeMember | None:
        member: MPracticeMember | None = self.member_repo.get_member_by_id(
            member_id=member_id
        )
        if not member:
            return None

        name = appointment_utils.get_full_name(member.first_name, member.last_name)
        country = self.get_country(country_code=member.country_code)
        member_organization = self.track_selection_service.get_organization_for_user(
            user_id=member.id
        )
        organization = (
            Organization(
                name=member_organization.name,
                education_only=member_organization.education_only,
                rx_enabled=member_organization.rx_enabled,
            )
            if member_organization
            else None
        )
        profiles = Profiles(
            member=MemberProfile(
                care_plan_id=member.care_plan_id,
                subdivision_code=member.subdivision_code,
                state=State(abbreviation=member.state_abbreviation),
                tel_number=member.phone_number,
            )
        )

        is_anonymous = appointment_privacy == PRIVACY_CHOICES.anonymous
        translated_member = TranslatedMPracticeMember(**vars(member))
        translated_member.country = country
        translated_member.profiles = profiles
        if is_anonymous:
            translated_member.email = None
            translated_member.created_at = None
            translated_member.name = None
            translated_member.first_name = None
            translated_member.last_name = None
        else:
            translated_member.name = name
            translated_member.organization = organization
        return translated_member

    def get_translated_practitioner(
        self, practitioner_id: int
    ) -> TranslatedMPracticePractitioner | None:
        practitioner: MPracticePractitioner | None = (
            self.practitioner_repo.get_practitioner_by_id(practitioner_id)
        )
        if not practitioner:
            return None

        subdivision_codes = self.practitioner_repo.get_practitioner_subdivision_codes(
            practitioner_id=practitioner_id
        )
        verticals = self.practitioner_repo.get_practitioner_verticals(practitioner_id)
        certified_subdivision_codes = self.get_certified_values(
            verticals=verticals, values=subdivision_codes
        )
        full_name = appointment_utils.get_full_name(
            practitioner.first_name, practitioner.last_name
        )

        states = self.practitioner_repo.get_practitioner_states(
            practitioner_id=practitioner.id
        )
        can_prescribe = rx_utils.practitioner_enabled_for_prescription(
            practitioner.dosespot
        )
        certified_states = self.get_certified_values(verticals=verticals, values=states)

        return TranslatedMPracticePractitioner(
            id=practitioner.id,
            name=full_name,
            profiles=Profiles(
                practitioner=PractitionerProfile(
                    can_prescribe=can_prescribe,
                    messaging_enabled=practitioner.messaging_enabled,
                    certified_subdivision_codes=certified_subdivision_codes,
                    vertical_objects=verticals,
                )
            ),
            certified_states=[state.upper() for state in certified_states],
            dosespot=practitioner.dosespot,
        )

    @staticmethod
    def get_certified_values(verticals: List[Vertical], values: List[str]) -> List[str]:
        if not verticals:
            return values
        for vertical in verticals:
            if vertical.filter_by_state:
                return values
        return []

    def get_provider_appointments(
        self, args: dict
    ) -> Tuple[List[TranslatedProviderAppointmentForList], Pagination]:
        order_direction = (
            args.get("order_direction")
            if args.get("order_direction")
            else OrderDirection.ASC.value
        )
        limit = args.get("limit") if args.get("limit") else 5
        offset = args.get("offset") if args.get("offset") else 0

        filters = ProviderAppointmentFilter(
            practitioner_id=args.get("practitioner_id"),
            member_id=args.get("member_id"),
            scheduled_start=args.get("scheduled_start"),
            scheduled_end=args.get("scheduled_end"),
            schedule_event_ids=args.get("schedule_event_ids"),
            exclude_statuses=args.get("exclude_statuses"),
        )
        (
            appts,
            total_count,
        ) = self.provider_appt_for_list_repo.get_paginated_appointments_with_total_count(
            filters=filters,
            order_direction=OrderDirection(order_direction),
            limit=limit,
            offset=offset,
        )

        appt_ids = [appt.id for appt in appts]
        appt_id_to_latest_post_session_note = self.provider_appt_for_list_repo.get_appointment_id_to_latest_post_session_note(
            appointment_ids=appt_ids
        )
        translated_appts = [
            self.translate_provider_appointment_for_list(
                appt, appt_id_to_latest_post_session_note.get(appt.id)
            )
            for appt in appts
        ]
        pagination = Pagination(
            order_direction=order_direction,  # type: ignore[arg-type] # Argument "order_direction" to "Pagination" has incompatible type "Union[str, Any, None]"; expected "str"
            limit=limit,  # type: ignore[arg-type] # Argument "limit" to "Pagination" has incompatible type "Union[int, Any, None]"; expected "int"
            offset=offset,  # type: ignore[arg-type] # Argument "offset" to "Pagination" has incompatible type "Union[int, Any, None]"; expected "int"
            total=total_count,
        )
        return translated_appts, pagination

    def translate_provider_appointment_for_list(
        self,
        appointment: ProviderAppointmentForList,
        latest_post_session: SessionMetaInfo | None,
    ) -> TranslatedProviderAppointmentForList:
        member_name = appointment_utils.get_member_name(
            privacy=appointment.privacy,
            member_first_name=appointment.member_first_name,
            member_last_name=appointment.member_last_name,
        )
        repeat_patient = (
            appointment.repeat_patient_appointment_count is not None
            and appointment.repeat_patient_appointment_count > 0
        )
        post_session = (
            SessionMetaInfo(created_at=None, draft=None, notes="")
            if not latest_post_session
            else latest_post_session
        )
        state = appointment_utils.get_state(
            scheduled_start=appointment.scheduled_start,
            scheduled_end=appointment.scheduled_end,
            member_started_at=appointment.member_started_at,
            member_ended_at=appointment.member_ended_at,
            practitioner_started_at=appointment.practitioner_started_at,
            practitioner_ended_at=appointment.practitioner_ended_at,
            cancelled_at=appointment.cancelled_at,
            disputed_at=appointment.disputed_at,
            payment_captured_at=appointment.payment_captured_at,
            payment_amount=appointment.payment_amount,
            credit_latest_used_at=appointment.credit_latest_used_at,
            total_used_credits=appointment.total_used_credits,
            fees_count=appointment.fees_count,
            appointment_json=appointment.json,
        )
        member = TranslatedMPracticeMember(
            id=appointment.member_id,
            name=member_name
            if appointment.privacy != PRIVACY_CHOICES.anonymous
            else None,
            first_name=appointment.member_first_name
            if appointment.privacy != PRIVACY_CHOICES.anonymous
            else None,
            country=self.get_country(appointment.member_country_code),
        )
        return TranslatedProviderAppointmentForList(
            id=obfuscate_appointment_id(appointment.id),
            appointment_id=appointment.id,
            scheduled_start=appointment.scheduled_start,
            scheduled_end=appointment.scheduled_end,
            member=member,
            repeat_patient=repeat_patient,
            state=state,
            privacy=appointment_utils.validate_privacy(appointment.privacy),
            privilege_type=appointment.privilege_type,
            rescheduled_from_previous_appointment_time=appointment.rescheduled_from_previous_appointment_time,
            cancelled_at=appointment.cancelled_at,
            post_session=post_session,
        )

    def get_country(self, country_code: str | None) -> Country | None:
        """
        Return country info if country code is not US.
        This follows the existing logic of UserSchema.get_country_info.
        Note that if country is null, it is defaulted to "US" for display on certain clients.
        """
        if country_code and country_code != "US":
            return self.country_repo.get(country_code=country_code)
        return None
