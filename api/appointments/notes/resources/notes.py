from time import sleep

import ddtrace
from flask import request
from flask_restful import abort
from sqlalchemy import exc

from appointments.notes.schemas.notes import (
    AppointmentNotesSchema,
    AppointmentNotesSchemaV3,
)
from appointments.notes.services.notes import (
    add_provider_addendum,
    add_provider_addendum_v2,
    update_internal_note,
    update_internal_note_v2,
    update_post_session_send_appointment_note_message,
    update_post_session_send_appointment_note_message_v2,
)
from appointments.services.common import (
    deobfuscate_appointment_id,
    get_cleaned_appointment,
)
from appointments.utils.flask_redis_ext import APPOINTMENT_REDIS, invalidate_cache
from appointments.utils.notes import is_save_notes_without_appointment_table
from common import stats
from common.services.api import AuthenticatedResource
from storage.connection import db
from utils.exceptions import DraftUpdateAttemptException, UserInputValidationError
from utils.log import logger
from utils.marshmallow_experiment import marshmallow_experiment_enabled

RETRY_DELAY = 5

log = logger(__name__)


class AppointmentNotesResource(AuthenticatedResource):
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

    @ddtrace.tracer.wrap()
    @invalidate_cache(redis_name=APPOINTMENT_REDIS, namespace="appointment_detail")
    def post(self, appointment_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # launch darkly flag
        experiment_enabled = marshmallow_experiment_enabled(
            "experiment-marshmallow-appointment-notes-resource",
            self.user.esp_id if self.user else None,
            self.user.email if self.user else None,
            default=False,
        )

        schema = (
            AppointmentNotesSchemaV3()
            if experiment_enabled
            else AppointmentNotesSchema()
        )
        schema.context["user"] = self.user  # type: ignore[attr-defined]

        request_json = request.json if request.is_json else None
        args = (
            schema.load(request_json)  # type: ignore[attr-defined]
            if experiment_enabled
            else schema.load(request_json).data  # type: ignore[attr-defined]
        )
        if not (
            args.get("post_session")
            or args.get("structured_internal_note")
            or args.get("provider_addenda")
        ):
            abort(
                400,
                message="Invalid request body. Must include post_session, structured_internal_note, or provider_addenda",
            )

        appointment = get_cleaned_appointment(appointment_id, self.user)

        if appointment is None:
            abort(404, message="Appointment not found")
        else:
            if len(appointment) == 0:
                abort(403, message="Cannot view that appointment!")

            appointment = appointment[0]
            if appointment and appointment.practitioner_id != self.user.id:
                abort(
                    403,
                    message="Permission denied: you are not the appointment practitioner.",
                )

        # TODO: Remove code and feature flag
        enable_save_notes_without_appointment_table = (
            is_save_notes_without_appointment_table(self.user)
        )
        log.info(
            f"'enable_save_notes_without_appointment_table' is {enable_save_notes_without_appointment_table}."
        )

        if enable_save_notes_without_appointment_table:
            try:
                appointment_id = deobfuscate_appointment_id(appointment_id)
                if args.get("post_session"):
                    update_post_session_send_appointment_note_message_v2(
                        args, appointment_id
                    )

                if args.get("structured_internal_note"):
                    update_internal_note_v2(args, self.user, appointment_id)

                if args.get("provider_addenda"):
                    add_provider_addendum_v2(args, self.user, appointment_id)

                return {}, 201
            except exc.SQLAlchemyError as e:
                abort(503, message=str(e))
            except UserInputValidationError as e:
                abort(422, message=str(e))
            except DraftUpdateAttemptException as e:
                abort(409, message=str(e))
            except Exception as e:
                log.error(f"Unexpected error: {e}")
                abort(500, message=str(e))

        if args.get("post_session"):
            update_post_session_send_appointment_note_message(
                args, self.user, appointment
            )

        if args.get("structured_internal_note"):
            self.timer("notes_time")
            update_internal_note(args, self.user, appointment)

        if args.get("provider_addenda"):
            add_provider_addendum(args, self.user, appointment)

        draft = args.get("post_session", {}).get("draft", False) or args.get(
            "structured_internal_note", {}
        ).get("recorded_answer_set", {}).get("draft", False)
        retries = 0

        while retries <= 1:
            if retries > 0:
                stats.increment(
                    metric_name="api.appointments.notes.resources.notes",
                    pod_name=stats.PodNames.MPRACTICE_CORE,
                    tags=["retry_status:retried"],
                )
            try:
                db.session.add(appointment)
                db.session.commit()
                self.timer("commit_time")
                stats.increment(
                    metric_name="api.appointments.notes.resources.notes.update_notes",
                    pod_name=stats.PodNames.MPRACTICE_CORE,
                    tags=[f"draft:{draft}"],
                )
                break
            except Exception as e:
                retries += 1
                log.info(
                    "Retrying Appointment Note update request",
                    appointment_id=appointment.id,  # type: ignore[union-attr] # Item "None" of "Optional[Appointment]" has no attribute "id"
                    error=e,
                )
                sleep(RETRY_DELAY)

        return schema.dump(appointment)  # type: ignore[attr-defined]
