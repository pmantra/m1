import json
from datetime import datetime, timedelta
from typing import Optional

from appointments.models.constants import APPOINTMENT_STATES
from appointments.repository.v2.cancel_appointment import (
    CancelAppointmentRepository,
    MemberCancellationPolicyRepository,
)
from appointments.services.schedule import (
    update_practitioner_profile_next_availability_with_practitioner_id,
)
from appointments.services.v2.notification import MemberAppointmentNotificationService
from appointments.tasks.appointment_notifications import (
    cancel_member_appointment_confirmation,
    send_member_cancellation_note,
)
from appointments.tasks.appointments import update_member_cancellations
from appointments.utils.appointment_utils import get_member_appointment_state
from appointments.utils.errors import (
    AppointmentAlreadyCancelledException,
    AppointmentCancelledByUserIdNotFoundException,
    AppointmentNotFoundException,
    AppointmentNotInCancellableStateException,
)
from authn.models.user import User
from payments.services.appointment_payments import AppointmentPaymentsService
from storage.connection import db
from utils.log import logger
from utils.service_owner_mapper import service_ns_team_mapper

log = logger(__name__)

CANCELLABLE_STATES = (APPOINTMENT_STATES.scheduled, APPOINTMENT_STATES.overdue)


class CancelAppointmentService:
    def __init__(self) -> None:
        self.session = db.session
        self.cancel_appt_repo = CancelAppointmentRepository(self.session)
        self.cancellation_policy_repo = MemberCancellationPolicyRepository(self.session)
        self.payments_service = AppointmentPaymentsService(self.session)
        self.notification_service = MemberAppointmentNotificationService(self.session)

    def cancel_appointment(
        self,
        user: User,
        appointment_id: int,
        cancelled_note: Optional[str] = None,
        admin_initiated: bool = False,
    ) -> None:
        appointment = self.cancel_appt_repo.get_cancel_appointment_struct_by_id(
            appointment_id=appointment_id
        )

        if appointment is None:
            log.error(
                "Appointment not found",
                appointment_id=appointment_id,
                user_id=user.id,
            )
            raise AppointmentNotFoundException(appointment_id)

        if appointment.cancelled_at is not None:
            log.error(
                "Appointment is already cancelled. Can't cancel it again.",
                appointment_id=appointment_id,
                user_id=user.id,
            )
            raise AppointmentAlreadyCancelledException()

        # "get_member_appointment_state" is used here for both practitioners and members
        # but this is okay as we are only using it to check cancellable states, which
        # should behave the same as "get_state" from mpractice.utils.appointment_utils
        appointment_state = get_member_appointment_state(
            appointment.scheduled_start,
            appointment.scheduled_end,
            appointment.member_started_at,
            appointment.member_ended_at,
            appointment.practitioner_started_at,
            appointment.practitioner_ended_at,
            appointment.cancelled_at,
            appointment.disputed_at,
        )
        if appointment_state not in CANCELLABLE_STATES:
            raise AppointmentNotInCancellableStateException()

        if user.id == appointment.practitioner_id:
            log.info(
                "Starting to cancel appointment for practitioner",
                appointment_id=appointment_id,
                member_id=appointment.member_id,
                admin_initiated=admin_initiated,
            )

            self.payments_service.handle_cancel_appointment_by_practitioner_fees(
                appointment_id=appointment.id
            )
            if not admin_initiated:
                service_ns_tag = "appointment_notifications"
                team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
                send_member_cancellation_note.delay(
                    appointment_id=appointment_id,
                    note=cancelled_note,
                    team_ns=team_ns_tag,
                    service_ns=service_ns_tag,
                )

        elif user.id == appointment.member_id:
            log.info(
                "Starting to cancel appointment for member",
                appointment_id=appointment_id,
                member_id=appointment.member_id,
                admin_initiated=admin_initiated,
            )

            # Update the number of member cancellations.
            # Includes both member initiated and member no-show cancellations.
            service_ns_tag = "appointments"
            team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
            update_member_cancellations.delay(
                appointment_id=appointment_id,
                admin_initiated=admin_initiated,
                service_ns=service_ns_tag,
                team_ns=team_ns_tag,
            )

            self.payments_service.handle_cancel_appointment_by_member_fees(
                appointment_id=appointment_id,
                member_id=appointment.member_id,
                product_id=appointment.product_id,
                product_price=appointment.product_price,
                scheduled_start=appointment.scheduled_start,
                admin_initiated=admin_initiated,
            )
        else:
            log.error(
                "Not canceling appointment for unaffiliated user",
                appointment_id=appointment_id,
                user_id=user.id,
            )

        json_data = {}
        if appointment.json_str:
            try:
                json_data = json.loads(appointment.json_str)
            except json.decoder.JSONDecodeError:
                log.error(
                    "Incorrectly formatted json",
                    appointment_id=appointment_id,
                    json_str=appointment.json_str,
                )
        json_data["cancelled_note"] = cancelled_note
        updated_json_str = json.dumps(json_data)

        # Update the appointment model to set the cancelled_at and cancelled_by_user_id fields
        self.cancel_appt_repo.update_appointment_for_cancel(
            appointment_id=appointment_id,
            user_id=user.id,
            json_str=updated_json_str,
        )
        self.session.commit()
        cancel_member_appointment_confirmation.delay(appointment_id)

        # TODO: revisit this implementation when we support cancel for
        # providers to see if there's a better way to check if
        # update_appointment_for_cancel succeeded.
        # fetch the cancelled_by_user_id again after we updated it earlier.
        cancelled_by_user_id = self.cancel_appt_repo.get_cancelled_by_user_id(
            appointment_id=appointment_id
        )
        if not cancelled_by_user_id:
            log.warning(
                "Appointment could not be cancelled", appointment_id=appointment_id
            )
            raise AppointmentCancelledByUserIdNotFoundException()

        log.info("Cancelled appointment", appointment_id=appointment_id)

        # TODO: move this method into a service class. Currently, this method
        # drastically increased the db query count.
        update_practitioner_profile_next_availability_with_practitioner_id(
            session=self.session,
            practitioner_user_id=appointment.practitioner_id,
            appointment_id=appointment_id,
        )

        appointment_starts_in = self._get_appointment_starts_in(
            scheduled_start=appointment.scheduled_start
        )

        self.notification_service.send_slack_cancellation(
            practitioner_id=appointment.practitioner_id,
            member_id=appointment.member_id,
            appointment_id=appointment_id,
            appointment_starts_in=appointment_starts_in,
            cancelled_by_user_id=cancelled_by_user_id,
        )

    def _get_appointment_starts_in_minutes(self, scheduled_start: datetime, now=None):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        """Add one min so we force to round up since we use an integer"""
        now = now or datetime.utcnow()
        return int(((scheduled_start - now).total_seconds()) / 60) + 1

    def _get_appointment_starts_in(self, scheduled_start: datetime, now=None) -> str:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        starts_in_seconds = (
            self._get_appointment_starts_in_minutes(
                scheduled_start=scheduled_start, now=now
            )
            * 60
        )
        return str(timedelta(seconds=starts_in_seconds))
