import datetime

from flask import request
from flask_restful import abort

from appointments.models.appointment import Appointment
from appointments.models.schedule_event import ScheduleEvent
from appointments.resources.constants import PractitionerScheduleResource
from appointments.schemas.events import EventSchema
from appointments.services.schedule import (
    detect_schedule_conflict,
    update_practitioner_profile_next_availability,
)
from models.actions import ACTIONS, audit
from models.products import Product
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class ScheduleEventResource(PractitionerScheduleResource):
    def get(self, practitioner_id, event_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._check_practitioner(practitioner_id)
        event = ScheduleEvent.query.get_or_404(event_id)
        schema = EventSchema()
        return schema.dump(event).data

    def put(self, practitioner_id, event_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._check_practitioner(practitioner_id)
        event = ScheduleEvent.query.get_or_404(event_id)

        schema = EventSchema(exclude=("id", "state"))
        request_json = request.json if request.is_json else None
        args = schema.load(request_json).data

        # will abort if necessary
        detect_schedule_conflict(
            self.user.schedule,
            args["starts_at"],
            args["ends_at"],
            event.id,
            request=request,
        )

        avail_ranges_to_delete = []
        avail_ranges_to_create = []

        existing_appointments = self._existing_appointments(
            practitioner_id, event.starts_at, event.ends_at
        )
        if existing_appointments:
            log.info(
                f"We have conflicting events: [{event.id}, {event.starts_at} - {event.ends_at}] to "
                f"edit to [{args['starts_at']} - {args['ends_at']}]."
            )

            # you can expand the window in either or both directions safely
            # at this point since schedule conflicts are eliminated already
            if args["ends_at"] > event.ends_at:
                avail_ranges_to_create.append((event.ends_at, args["ends_at"]))
                event.ends_at = args["ends_at"]
            if args["starts_at"] < event.starts_at:
                avail_ranges_to_create.append((args["starts_at"], event.starts_at))
                event.starts_at = args["starts_at"]

            # contracting the window is where we can have conflicts with the
            # existing appointments
            if args["starts_at"] > event.starts_at:
                # we want to contract the window
                _in_order = sorted(
                    existing_appointments, key=lambda x: x.scheduled_start
                )
                if args["starts_at"] <= _in_order[0].scheduled_start:
                    # we are contracting by a safe amount
                    event.starts_at = args["starts_at"]
                else:
                    abort(400, message="Conflict with an appointment!")

            if args["ends_at"] < event.ends_at:
                # we want to contract the window
                _in_order = sorted(existing_appointments, key=lambda x: x.scheduled_end)
                if args["ends_at"] >= _in_order[-1].scheduled_end:
                    # we are contracting by a safe amount
                    avail_ranges_to_delete.append(
                        (_in_order[-1].scheduled_end, event.ends_at)
                    )
                    avail_ranges_to_create.append(
                        (_in_order[-1].scheduled_end, args["ends_at"])
                    )
                    event.ends_at = args["ends_at"]
                else:
                    abort(400, message="Conflict with an appointment!")

        else:
            log.info("No conflicting appts - allowing edit of %s to %s", event, args)
            event.starts_at = args["starts_at"]
            event.ends_at = args["ends_at"]

        res_schema = EventSchema()
        db.session.add(event)
        db.session.commit()
        update_practitioner_profile_next_availability(self.user.practitioner_profile)
        return res_schema.dump(event).data

    def delete(self, practitioner_id, event_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._check_practitioner(practitioner_id)
        event = ScheduleEvent.query.get_or_404(event_id)

        # Check for existing appointments using the Appointment table
        existing_appointments = self._existing_appointments(
            practitioner_id, event.starts_at, event.ends_at
        )

        if not existing_appointments:
            log.info("Now setting unavail %s", event)

            db.session.delete(event)
            db.session.commit()

            audit(
                ACTIONS.availability_removed,
                self.user.id,
                type="non-recurring",
                event_start=str(event.starts_at),
                event_end=str(event.ends_at),
            )
            update_practitioner_profile_next_availability(
                self.user.practitioner_profile
            )
            return "", 204
        else:
            log.debug("Not deleting %s - existing booking!", event)
            abort(400, message="Cannot delete when you are booked!")

    def _existing_appointments(self, practitioner_id, starts_at, ends_at):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """return incomplete appts during a time window"""

        existing_appointments = (
            db.session.query(Appointment)
            .join(Product)
            .filter(
                Product.user_id == practitioner_id,
                Appointment.scheduled_start >= starts_at,
                Appointment.scheduled_start < ends_at,
                Appointment.cancelled_at == None,
            )
            .all()
        )

        if existing_appointments:
            existing_appointments = [
                a
                for a in existing_appointments
                if ((a.scheduled_end > datetime.datetime.utcnow()) and not a.ended_at)
            ]

        return existing_appointments or []
