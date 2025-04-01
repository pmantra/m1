import datetime

from flask import request
from flask_restful import abort
from maven import feature_flags

from appointments.models.constants import APPOINTMENT_STATES
from appointments.models.reschedule_history import RescheduleHistory
from appointments.models.schedule_event import ScheduleEvent
from appointments.schemas.appointments_v3 import (
    AppointmentRescheduleSchemaV3,
    AppointmentSchemaV3,
)
from appointments.services.common import get_cleaned_appointment
from appointments.services.schedule import update_practitioner_profile_next_availability
from appointments.tasks.appointments import appointment_post_reschedule_async_tasks
from appointments.utils.flask_redis_ext import APPOINTMENT_REDIS, invalidate_cache
from common import stats
from common.services.api import AuthenticatedResource
from storage.connection import db
from utils.flag_groups import CARE_DELIVERY_RELEASE
from utils.log import logger
from utils.marshmallow_experiment import marshmallow_experiment_enabled
from utils.service_owner_mapper import service_ns_team_mapper

log = logger(__name__)


class RescheduleAppointmentResource(AuthenticatedResource):
    def redis_cache_key(self, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return f"appointment_details:{self.user.id}:{kwargs.get('appointment_id')}"

    def redis_tags(self, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return [
            f"appointment_data:{kwargs.get('appointment_id')}",
            f"user_appointments:{self.user.id}",
        ]

    def experiment_enabled(self, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return marshmallow_experiment_enabled(
            "experiment-enable-appointments-redis-cache",
            self.user.esp_id,
            self.user.email,
            default=False,
        )

    @invalidate_cache(redis_name=APPOINTMENT_REDIS, namespace="appointment_detail")
    def patch(self, appointment_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        request_json = request.json if request.is_json else None
        patch_request = AppointmentRescheduleSchemaV3().load(
            request_json or request.form
        )
        if patch_request.get("product_id"):
            log.info("Got product_id in reschedule endpoint, ignoring")
        appointment = get_cleaned_appointment(
            appointment_id=appointment_id, user=self.user
        )
        if appointment is None:
            stats.increment(
                metric_name="api.appointments.resources.reschedule_appointment.reschedule_appointment",
                tags=["variant:error_appointment_not_found"],
                pod_name=stats.PodNames.VIRTUAL_CARE,
            )
            abort(404, message="Appointment not found")

            # MyPy doesn't recognize that code after "abort()" is unreachable
            # for now, this unreachable line is stopping errors
            raise AttributeError
        else:
            if len(appointment) == 0:
                stats.increment(
                    metric_name="api.appointments.resources.reschedule_appointment.reschedule_appointment",
                    tags=["variant:error_cannot_view_the_appointment"],
                    pod_name=stats.PodNames.VIRTUAL_CARE,
                )
                abort(403, message="Cannot view that appointment!")

            appointment = appointment[0]

        product = appointment.product
        scheduled_start = patch_request["scheduled_start"]
        scheduled_end = scheduled_start + datetime.timedelta(
            minutes=float(product.minutes or 0)
        )

        if feature_flags.bool_variation(
            CARE_DELIVERY_RELEASE.ENABLE_RESCHEDULE_APPOINTMENT_WITHIN_2_HOURS,
            feature_flags.Context.create(
                CARE_DELIVERY_RELEASE.ENABLE_RESCHEDULE_APPOINTMENT_WITHIN_2_HOURS
            ),
            default=False,
        ):
            if appointment.state != APPOINTMENT_STATES.scheduled:  # type: ignore[union-attr] # Item "None" of "Optional[Appointment]" has no attribute "state"
                stats.increment(
                    metric_name="api.appointments.resources.reschedule_appointment.reschedule_appointment",
                    tags=["variant:error_cannot_reschedule_state_not_scheduled"],
                    pod_name=stats.PodNames.CARE_DISCOVERY,
                )
                abort(
                    400,
                    message="Can't reschedule an appointment that is not in the SCHEDULED state.",
                )

            reschedulable_until = (
                appointment.scheduled_start  # type: ignore[union-attr] # Item "None" of "Optional[Appointment]" has no attribute "scheduled_start"
                - datetime.timedelta(hours=2)
            )
            if (
                not self.user.is_enterprise
                and datetime.datetime.utcnow() > reschedulable_until
            ):
                stats.increment(
                    metric_name="api.appointments.resources.reschedule_appointment.reschedule_appointment",
                    tags=["variant:error_cannot_reschedule_marketplace_within_2_hours"],
                    pod_name=stats.PodNames.CARE_DISCOVERY,
                )
                abort(
                    403,
                    message="Marketplace members can't reschedule an appointment within 2 hours of scheduled start.",
                )
        else:
            if appointment.scheduled_start < datetime.datetime.utcnow():  # type: ignore[union-attr] # Item "None" of "Optional[Appointment]" has no attribute "scheduled_start"
                stats.increment(
                    metric_name="api.appointments.resources.reschedule_appointment.reschedule_appointment",
                    tags=["variant:error_cannot_reschedule_after_start_time"],
                    pod_name=stats.PodNames.CARE_DISCOVERY,
                )
                abort(
                    400, message="Can't reschedule after the appointment's start time."
                )

        update_schedule_event_id = feature_flags.bool_variation(
            "enable-update-reschedule-appointment-schedule-event-id",
            default=False,
        )
        if update_schedule_event_id:
            try:
                event = ScheduleEvent.get_schedule_event_from_timestamp(
                    product.practitioner.schedule,
                    scheduled_start,
                )
            except Exception as error:
                abort(400, message=str(error))

        log.info(
            "Member rescheduling appointment to a new start time.",
            user_id=self.user.id,
            practitioner_id=product.practitioner.id,
            scheduled_start=str(scheduled_start),
            scheduled_end=str(scheduled_end),
            appointment_id=appointment.id,  # type: ignore[union-attr] # Item "None" of "Optional[Appointment]" has no attribute "id"
        )

        # Create a new record in the reschedule history table
        reschedule_history = RescheduleHistory(
            appointment_id=appointment.id,  # type: ignore[union-attr] # Item "None" of "Optional[Appointment]" has no attribute "id"
            scheduled_start=appointment.scheduled_start,  # type: ignore[union-attr] # Item "None" of "Optional[Appointment]" has no attribute "scheduled_start"
            scheduled_end=appointment.scheduled_end,  # type: ignore[union-attr] # Item "None" of "Optional[Appointment]" has no attribute "scheduled_end"
            created_at=datetime.datetime.utcnow(),
        )
        db.session.add(reschedule_history)
        log.info(
            "Reschedule event is appended to the reschedule history table.",
            user_id=self.user.id,
            practitioner_id=product.practitioner.id,
            scheduled_start=str(appointment.scheduled_start),  # type: ignore[union-attr] # Item "None" of "Optional[Appointment]" has no attribute "scheduled_start"
            scheduled_end=str(appointment.scheduled_end),  # type: ignore[union-attr] # Item "None" of "Optional[Appointment]" has no attribute "scheduled_end"
            appointment_id=appointment.id,  # type: ignore[union-attr] # Item "None" of "Optional[Appointment]" has no attribute "id"
        )

        # Update the appointment's scheduled_start and scheduled_end to be the new
        # time, and the schedule_event to be for the new schedule_event
        appointment.scheduled_start = scheduled_start  # type: ignore[union-attr] # Item "None" of "Optional[Appointment]" has no attribute "scheduled_start"
        appointment.scheduled_end = scheduled_end  # type: ignore[union-attr] # Item "None" of "Optional[Appointment]" has no attribute "scheduled_end"
        if update_schedule_event_id:
            appointment.schedule_event = event
        db.session.add(appointment)
        db.session.commit()
        log.info(
            "Appointment scheduled time is updated.",
            user_id=self.user.id,
            practitioner_id=product.practitioner.id,
            new_scheduled_start=str(appointment.scheduled_start),  # type: ignore[union-attr] # Item "None" of "Optional[Appointment]" has no attribute "scheduled_start"
            new_scheduled_end=str(appointment.scheduled_end),  # type: ignore[union-attr] # Item "None" of "Optional[Appointment]" has no attribute "scheduled_end"
            appointment_id=appointment.id,  # type: ignore[union-attr] # Item "None" of "Optional[Appointment]" has no attribute "id"
        )
        service_ns_tag = "appointments"
        team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
        appointment_post_reschedule_async_tasks.delay(appointment.id, team_ns=team_ns_tag, service_ns=service_ns_tag)  # type: ignore[union-attr] # Item "None" of "Optional[Appointment]" has no attribute "id"

        update_practitioner_profile_next_availability(
            product.practitioner.practitioner_profile
        )

        stats.increment(
            metric_name="api.appointments.resources.reschedule_appointment.reschedule_appointment",
            tags=["variant:reschedule_appointment_success"],
            pod_name=stats.PodNames.VIRTUAL_CARE,
        )

        appointment_schema = AppointmentSchemaV3()
        appointment_schema.context["user"] = self.user
        return appointment_schema.dump(appointment)
