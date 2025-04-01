import datetime

from flask import request
from flask_restful import abort
from maven import feature_flags

from appointments.models.schedule_event import ScheduleEvent
from appointments.resources.constants import PractitionerScheduleResource
from appointments.schemas.events import EventSchema
from appointments.schemas.events_v3 import (
    EventSchemaV3,
    EventsGetSchemaV3,
    EventsSchemaV3,
)
from appointments.services.schedule import (
    detect_schedule_conflict,
    get_overlapping_maintenance_windows,
)
from appointments.utils.availability_notifications import (
    update_next_availability_and_alert_about_availability,
)
from authz.services.permission import add_schedule_event
from providers.service.provider import ProviderService
from storage.connection import db
from utils import launchdarkly
from utils.log import logger

log = logger(__name__)


class ScheduleEventsResource(PractitionerScheduleResource):
    @property
    def launchdarkly_context(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return launchdarkly.marshmallow_context(self.user.esp_id, self.user.email)

    def get(self, practitioner_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        schema = EventsGetSchemaV3()
        args = schema.load(request.args)  # type: ignore[attr-defined] # "object" has no attribute "load"
        schedule = self.user.schedule
        starts_at = args.get("starts_at") or datetime.datetime.utcnow()
        ends_at = args.get("ends_at") or starts_at + datetime.timedelta(days=7)
        product_id = args.get("product_id")

        events = schedule.existing_events(starts_at, ends_at, args["recurring"])
        events = events.order_by(
            getattr(ScheduleEvent.starts_at, args["order_direction"])()
        )

        maintenance_windows = get_overlapping_maintenance_windows(starts_at, ends_at)
        scheduling_constraints = ProviderService().get_scheduling_constraints(
            practitioner_id, product_id
        )

        meta_info = {
            "user_id": practitioner_id,
            "starts_at": starts_at,
            "ends_at": ends_at,
        }
        pagination = {"total": events.count()}

        output_schema = EventsSchemaV3()
        result = {
            "data": events.all(),
            "meta": meta_info,
            "pagination": pagination,
            "maintenance_windows": maintenance_windows,
            "provider_scheduling_constraints": scheduling_constraints,
        }

        return output_schema.dump(result)  # type: ignore[attr-defined] # "object" has no attribute "dump"

    @add_schedule_event.require()
    def post(self, practitioner_id: int) -> tuple[dict, int]:
        self._check_practitioner(practitioner_id)
        experiment_enabled = feature_flags.bool_variation(
            "experiment-marshmallow-schedule-events-upgrade",
            self.launchdarkly_context,
            default=False,
        )
        schema = (
            EventSchema(exclude=("id",))
            if not experiment_enabled
            else EventSchemaV3(exclude=("id",))
        )
        request_json = request.json if request.is_json else None
        args = (
            schema.load(request_json).data  # type: ignore[attr-defined] # "object" has no attribute "load"
            if not experiment_enabled
            else schema.load(request_json)  # type: ignore[attr-defined] # "object" has no attribute "load"
        )
        schedule = self.user.schedule

        if schedule is None:
            abort(403, message="Need a schedule to add an event!")

        # will abort if necessary
        detect_schedule_conflict(
            schedule, args["starts_at"], args["ends_at"], request=request
        )

        new = ScheduleEvent(
            schedule=schedule,
            starts_at=args["starts_at"],
            ends_at=args["ends_at"],
            state=args["state"],
        )
        db.session.add(new)
        db.session.commit()
        self.audit("schedule_events_create", request_args=request_json)

        update_next_availability_and_alert_about_availability(
            practitioner_profile=self.user.practitioner_profile,
            user_full_name=self.user.full_name,
            starts_at=args["starts_at"],
            ends_at=args["ends_at"],
        )

        schema = EventSchema() if not experiment_enabled else EventSchemaV3()
        return (
            schema.dump(new).data if not experiment_enabled else schema.dump(new),  # type: ignore[attr-defined] # "object" has no attribute "dump"
            201,
        )
