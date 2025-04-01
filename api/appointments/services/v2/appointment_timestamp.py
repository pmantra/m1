import json
from datetime import datetime
from typing import Optional

from appointments.models.constants import APPOINTMENT_STATES
from appointments.repository.v2.appointment_video_timestamp import (
    AppointmentVideoTimestampRepository,
)
from appointments.services.common import get_platform
from appointments.services.v2.member_appointment import RECONNECTING_STATES, log
from appointments.tasks.appointments import appointment_completion
from appointments.utils.appointment_utils import get_member_appointment_state
from appointments.utils.errors import AppointmentNotFoundException
from storage.connection import db
from utils.service_owner_mapper import service_ns_team_mapper


class AppointmentTimestampService:
    def add_video_timestamp(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        user_id: int,
        appointment_id: int,
        started_at: Optional[datetime] = None,
        ended_at: Optional[datetime] = None,
        disconnected_at: Optional[datetime] = None,
        phone_call_at: Optional[datetime] = None,
        user_agent: Optional[str] = None,
    ):
        repository = AppointmentVideoTimestampRepository(session=db.session)
        appointment = repository.get_appointment_video_timestamp(appointment_id)
        if not appointment:
            log.error(
                "Appointment not found", user_id=user_id, appointment_id=appointment_id
            )
            raise AppointmentNotFoundException(appointment_id)

        if phone_call_at:
            # This field is not segmented into provider vs member fields, so
            # we just set it here
            appointment.phone_call_at = phone_call_at

        platform_info = {}

        # Check permissions
        user_is_member = user_id == appointment.member_id
        user_is_provider = user_id == appointment.provider_id
        log.info(
            "Adding video timestamp",
            user_id=user_id,
            appointment_id=appointment_id,
            started_at=started_at,
            ended_at=ended_at,
            disconnected_at=disconnected_at,
            phone_call_at=phone_call_at,
            is_provider=user_is_provider,
        )
        if not user_is_member and not user_is_provider:
            log.error(
                "User is not associated with the appointment",
                user_id=user_id,
                appointment_id=appointment_id,
            )
            raise AppointmentNotFoundException(appointment_id)
        elif user_is_member:
            if started_at and not appointment.member_started_at:
                appointment.member_started_at = started_at

            if ended_at and not appointment.member_ended_at:
                appointment.member_ended_at = ended_at

            platform_info = {
                "member_started": get_platform(user_agent),
                "member_started_raw": user_agent,
            }

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
            if disconnected_at and state in RECONNECTING_STATES:
                # Adapted from appointments/resources/appointment.py lines 465-467:
                # use member_disconnected_at value as the member_started_at value if the member_started_at value hasn't been set
                if not appointment.member_started_at:
                    appointment.member_started_at = disconnected_at

                disconnect_times: list[str] = appointment.json_data.setdefault(
                    "member_disconnect_times", []
                )
                disconnect_times.append(disconnected_at.isoformat())

            # in the case that we have an ended_at time and not a started_at time, default
            # started_at to utcnow
            if appointment.member_ended_at and not appointment.member_started_at:
                log.warning(
                    "Receiving appointment member_ended_at without member_started_at. Setting member_started_at to utcnow.",
                    user_id=user_id,
                    appointment_id=appointment_id,
                    member_started_at=appointment.member_started_at,
                    member_ended_at=appointment.member_ended_at,
                )
                appointment.member_started_at = datetime.utcnow()
        elif user_is_provider:
            if started_at and not appointment.practitioner_started_at:
                appointment.practitioner_started_at = started_at

            if ended_at and not appointment.practitioner_ended_at:
                appointment.practitioner_ended_at = ended_at

            platform_info = {
                "practitioner_started": get_platform(user_agent),
                "practitioner_started_raw": user_agent,
            }

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
            if disconnected_at and state in RECONNECTING_STATES:
                # Adapted from appointments/resources/appointment.py lines 465-467:
                # use practitioner_disconnected_at value as the practitioner_started_at value if the
                # practitioner_started_at value hasn't been set
                if not appointment.practitioner_started_at:
                    appointment.practitioner_started_at = disconnected_at

                provider_disconnect_times: list[str] = appointment.json_data.setdefault(
                    "practitioner_disconnect_times", []
                )
                provider_disconnect_times.append(disconnected_at.isoformat())

            # in the case that we have an ended_at time and not a started_at time, default
            # started_at to utcnow
            if (
                appointment.practitioner_ended_at
                and not appointment.practitioner_started_at
            ):
                log.warning(
                    "Receiving appointment practitioner_ended_at without practitioner_started_at. Setting practitioner_started_at to utcnow.",
                    user_id=user_id,
                    appointment_id=appointment_id,
                    practitioner_started_at=appointment.practitioner_started_at,
                    practitioner_ended_at=appointment.practitioner_ended_at,
                )
                appointment.practitioner_started_at = datetime.utcnow()
        # Save fields to the DB
        platforms = appointment.json_data.get("platforms", {})
        platforms.update(platform_info)
        appointment.json_data["platforms"] = platforms
        json_str = json.dumps(appointment.json_data)
        repository.set_appointment_video_timestamp(
            appointment_id,
            appointment.member_started_at,
            appointment.member_ended_at,
            appointment.practitioner_started_at,
            appointment.practitioner_ended_at,
            appointment.phone_call_at,
            json_str,
        )
        db.session.commit()

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
        if state == APPOINTMENT_STATES.payment_pending_or_resolved:
            service_ns_tag = "appointments"
            team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
            appointment_completion.delay(
                appointment.id,
                user_id=user_id,
                service_ns=service_ns_tag,
                team_ns=team_ns_tag,
            )

        return appointment_id
