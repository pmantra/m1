import datetime

import ddtrace
from dateutil.relativedelta import relativedelta
from flask import request
from flask_restful import abort
from marshmallow import ValidationError

from appointments.resources.constants import PractitionerScheduleResource
from appointments.schemas.recurring_blocks import (
    ScheduleRecurringBlockGetRequestArgsSchema,
    ScheduleRecurringBlockGetSchema,
    ScheduleRecurringBlockPostRequestArgsSchema,
)
from appointments.services.recurring_schedule import (
    RecurringScheduleAvailabilityService,
)
from appointments.tasks.availability import create_recurring_availability
from authz.services.permission import add_schedule_event
from utils.log import logger

log = logger(__name__)
RECURRING_AVAILABILITY_START_END_TIME_MAX_DIFFERENCE_IN_HOURS = 8
RECURRING_AVAILABILITY_START_UNTIL_TIME_MAX_DIFFERENCE_IN_MONTHS = 3
RECURRING_AVAILABILITY_NOW_UNTIL_TIME_MAX_DIFFERENCE_IN_MONTHS = 6


class ScheduleRecurringBlocksResource(PractitionerScheduleResource):
    def get(self, practitioner_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._check_practitioner(practitioner_id)

        schema = ScheduleRecurringBlockGetRequestArgsSchema()
        args = schema.load(request.args)

        if not args.get("starts_at"):
            args["starts_at"] = datetime.datetime.utcnow()
        if not args.get("until"):
            args["until"] = datetime.datetime.utcnow() + datetime.timedelta(days=7)

        recurring_schedule_availability_service = RecurringScheduleAvailabilityService()
        recurring_blocks = recurring_schedule_availability_service.get_schedule_recurring_block_by_user_and_date_range(
            user_id=self.user.id, starts_at=args["starts_at"], until=args["until"]
        )

        meta_info = {
            "user_id": self.user.id,
            "starts_at": args["starts_at"],
            "until": args["until"],
        }
        pagination = {"total": len(recurring_blocks)}

        schema = ScheduleRecurringBlockGetSchema()  # type: ignore[assignment] # Incompatible types in assignment (expression has type "ScheduleRecurringBlockGetSchema", variable has type "ScheduleRecurringBlockGetRequestArgsSchema")
        result = {"data": recurring_blocks, "meta": meta_info, "pagination": pagination}

        return schema.dump(result)

    @add_schedule_event.require()
    def post(self, practitioner_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._check_practitioner(practitioner_id)

        schema = ScheduleRecurringBlockPostRequestArgsSchema()
        try:
            request_json = request.json if request.is_json else None
            args = schema.load(request_json)
        except ValidationError as e:
            abort(400, message=e.messages)

        schedule = self.user.schedule
        if schedule is None:
            abort(403, message="Need a schedule to add an event!")

        starts_at = args["starts_at"]
        ends_at = args["ends_at"]
        until = args["until"]

        if ends_at - starts_at > datetime.timedelta(
            hours=RECURRING_AVAILABILITY_START_END_TIME_MAX_DIFFERENCE_IN_HOURS
        ):
            abort(
                400,
                message=f"End time needs to be within {RECURRING_AVAILABILITY_START_END_TIME_MAX_DIFFERENCE_IN_HOURS} "
                f"hours of start time",
            )

        if (
            starts_at.date()
            + relativedelta(
                months=RECURRING_AVAILABILITY_START_UNTIL_TIME_MAX_DIFFERENCE_IN_MONTHS
            )
            < until.date()
        ):
            abort(
                400,
                message=f"Until time needs to be within {RECURRING_AVAILABILITY_START_UNTIL_TIME_MAX_DIFFERENCE_IN_MONTHS}"
                f" months of start time",
            )

        if (
            datetime.datetime.utcnow().date()
            + relativedelta(
                months=RECURRING_AVAILABILITY_NOW_UNTIL_TIME_MAX_DIFFERENCE_IN_MONTHS
            )
            < until.date()
        ):
            abort(
                400,
                message=f"Until time needs to be within {RECURRING_AVAILABILITY_NOW_UNTIL_TIME_MAX_DIFFERENCE_IN_MONTHS}"
                f" months of current time",
            )

        recurring_schedule_availability_service = RecurringScheduleAvailabilityService()
        with ddtrace.tracer.trace(name=f"{__name__}.detect_conflict"):
            recurring_schedule_availability_service.detect_schedule_recurring_block_conflict(
                starts_at=starts_at,
                ends_at=ends_at,
                starts_range=starts_at,
                until_range=until,
                week_days_index=args["week_days_index"],
                frequency=args["frequency"],
                member_timezone=args["member_timezone"],
                schedule_id=schedule.id,
            )

        create_recurring_availability.delay(
            starts_at=args["starts_at"],
            ends_at=args["ends_at"],
            frequency=args["frequency"],
            until=args["until"],
            week_days_index=args["week_days_index"],
            member_timezone=args["member_timezone"],
            user_id=self.user.id,
        )

        return {}, 202
