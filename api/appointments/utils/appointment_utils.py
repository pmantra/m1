from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from maven import feature_flags
from sqlalchemy.orm import lazyload

from appointments.models.appointment import Appointment
from appointments.models.constants import (
    APPOINTMENT_STATES,
    PRIVACY_CHOICES,
    AppointmentTypes,
)
from appointments.models.v2.member_appointment import MemberAppointmentStruct
from authn.models.user import User
from models.base import db
from models.profiles import MemberProfile, PractitionerProfile
from providers.service.provider import ProviderService
from services.common import PrivilegeType
from utils.flag_groups import GET_MY_PATIENTS_MARSHMALLOW_V3_MIGRATION
from utils.launchdarkly import user_context
from utils.log import logger

log = logger(__name__)


def is_anonymous(privacy: str | None) -> bool:
    return privacy == PRIVACY_CHOICES.anonymous


def get_started_at(
    member_started_at: datetime | None = None,
    practitioner_started_at: datetime | None = None,
) -> datetime | None:
    if member_started_at and practitioner_started_at:
        return max(member_started_at, practitioner_started_at)
    return None


def get_ended_at(
    member_started_at: datetime | None = None,
    practitioner_started_at: datetime | None = None,
    member_ended_at: datetime | None = None,
    practitioner_ended_at: datetime | None = None,
) -> datetime | None:
    started_at = get_started_at(member_started_at, practitioner_started_at)
    if started_at and member_ended_at and practitioner_ended_at:
        return min(member_ended_at, practitioner_ended_at)
    return None


def get_member_appointment_state(
    scheduled_start: datetime,
    scheduled_end: datetime,
    member_started_at: datetime | None,
    member_ended_at: datetime | None,
    practitioner_started_at: datetime | None,
    practitioner_ended_at: datetime | None,
    cancelled_at: datetime | None,
    disputed_at: datetime | None,
) -> str | None:
    """
    Gets state for member appointments without "payment" info, as this will cross a service boundary in triforce
    A new AppointmentState has been created, named "payment_pending_or_resolved"

    Eventually this will be refactored with mpractice/utils/appointment_utils.py
    """
    started_at = get_started_at(
        member_started_at=member_started_at,
        practitioner_started_at=practitioner_started_at,
    )
    ended_at = get_ended_at(
        member_started_at=member_started_at,
        member_ended_at=member_ended_at,
        practitioner_started_at=practitioner_started_at,
        practitioner_ended_at=practitioner_ended_at,
    )
    now = datetime.utcnow()

    if cancelled_at:
        return APPOINTMENT_STATES.cancelled
    elif disputed_at:
        return APPOINTMENT_STATES.disputed
    elif scheduled_start and started_at:
        if ended_at:
            return APPOINTMENT_STATES.payment_pending_or_resolved
        elif scheduled_end > now and not (member_ended_at or practitioner_ended_at):
            return APPOINTMENT_STATES.occurring
        elif scheduled_end and scheduled_end < now and not ended_at:
            return APPOINTMENT_STATES.overflowing
        elif member_ended_at or practitioner_ended_at:
            return APPOINTMENT_STATES.incomplete
    elif scheduled_start:
        if scheduled_start < now:
            return APPOINTMENT_STATES.overdue
        else:
            return APPOINTMENT_STATES.scheduled

    return None


def is_rx_enabled(
    appointment: MemberAppointmentStruct,
    sqla_provider_profile: PractitionerProfile,
    sqla_member_profile: MemberProfile,
) -> bool:
    return all(
        [
            not is_anonymous(appointment.privacy),
            sqla_member_profile.enabled_for_prescription,
            ProviderService().can_prescribe_to_member(
                sqla_provider_profile.user_id,
                sqla_member_profile.prescribable_state,
                # if the practitioner profile is available when calling
                # `can_prescribe_to_member` always include it to avoid
                # downstream implementations from refetching it. The
                # additional fetch is a non-trivial cost and can be as much
                # as 30 additional queries per appointment.
                sqla_provider_profile,
            ),
        ]
    )


def get_appointment_type(appointment: MemberAppointmentStruct) -> AppointmentTypes:
    if appointment.privilege_type == PrivilegeType.ANONYMOUS:
        return AppointmentTypes.ANONYMOUS
    elif appointment.privilege_type == PrivilegeType.EDUCATION_ONLY:
        return AppointmentTypes.EDUCATION_ONLY
    elif appointment.privilege_type == PrivilegeType.INTERNATIONAL:
        if appointment.privacy == PRIVACY_CHOICES.anonymous:
            return AppointmentTypes.ANONYMOUS
        else:
            return AppointmentTypes.EDUCATION_ONLY
    # Default value
    return AppointmentTypes.STANDARD


def get_appointments_by_ids(appointment_ids: List[int]) -> List[Appointment]:
    return (
        db.session.query(Appointment).filter(Appointment.id.in_(appointment_ids)).all()
    )


def check_appointment_by_ids(
    appointment_ids: list[int], nullable_appointment_id: bool
) -> None:
    """
    Checks that the appointment_ids match the nullability constraint and that
    the appointment_ids in the list exist as ids of appointments in the database.
    """
    appointment_ids_to_check = []
    for appointment_id in appointment_ids:
        if appointment_id is None:
            if not nullable_appointment_id:
                raise Exception("The appointment id is null, which is disallowed")
        else:
            appointment_ids_to_check.append(appointment_id)

    existing_appointment_id_tups = (
        db.session.query(Appointment.id)
        .filter(Appointment.id.in_(appointment_ids_to_check))
        .all()
    )
    existing_appointment_ids: list[int] = [
        appt_id_tup[0] for appt_id_tup in existing_appointment_id_tups
    ]

    if len(existing_appointment_ids) != len(appointment_ids_to_check) is None:
        raise Exception(
            f"appointment_ids_to_check: {appointment_ids_to_check} does not match appointment_ids_obtained: {existing_appointment_ids}"
        )


def check_appointment_by_id(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    appointment_id: Optional[int], nullable_appointment_id: bool
):
    if appointment_id is None:
        if not nullable_appointment_id:
            raise Exception("The appointment id is null, which is disallowed")
        return

    # Use lazyload to avoid eager loading for associated data which is not needed in this case
    appointment = (
        db.session.query(Appointment)
        .options(lazyload(Appointment.post_session_notes))
        .options(lazyload(Appointment.provider_addenda))
        .filter_by(id=appointment_id)
        .one_or_none()
    )

    if appointment is None:
        raise Exception(f"Could not find the appointment with id: {appointment_id}")


def upsert_appointment(appointment: Appointment):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    db.session.add(appointment)


def enable_get_my_patients_marshmallow_v3(user: User) -> bool:
    return feature_flags.bool_variation(
        GET_MY_PATIENTS_MARSHMALLOW_V3_MIGRATION,
        user_context(user),
        default=False,
    )


def convert_time_to_message_str(upcoming_appt_time_in_mins: int) -> str:
    """
    Convert incoming int (in minutes) into a readable string response
    i.e. "60 -> 1 hour", "2 -> 2 minutes"

    :param upcoming_appt_time_in_mins:
    :return:
    """

    if upcoming_appt_time_in_mins < 60:
        if upcoming_appt_time_in_mins == 1:
            return f"{upcoming_appt_time_in_mins} minute"
        return f"{upcoming_appt_time_in_mins} minutes"
    else:
        # convert minutes to hours
        hours = upcoming_appt_time_in_mins // 60
        if hours == 1:
            return f"{hours} hour"
        return f"{hours} hours"
