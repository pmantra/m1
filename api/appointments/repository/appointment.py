from __future__ import annotations

from typing import List

import ddtrace.ext
import sqlalchemy.exc
import sqlalchemy.orm
from sqlalchemy.orm.query import Query

from appointments.models.appointment import Appointment
from appointments.models.constants import PRIVACY_CHOICES
from authn.models.user import User
from models.products import Product
from storage import connection
from utils.log import logger

log = logger(__name__)
trace_wrapper = ddtrace.tracer.wrap(
    span_type=ddtrace.ext.SpanTypes.SQL,
)


class AppointmentRepository:
    """A data repository for managing the essential units-of-work for appointments."""

    __slots__ = ("session",)

    def __init__(self, session: sqlalchemy.orm.Session = None):  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "Session")
        self.session = session or connection.db.session().using_bind("default")

    @trace_wrapper
    def get_by_id(self, appointment_id: int) -> Appointment | None:
        return (
            self.session.query(Appointment).filter_by(id=appointment_id).one_or_none()
        )

    @trace_wrapper
    def get_by_member_id(self, member_id: int) -> List[Appointment] | None:
        member = self.session.query(User).get(member_id)
        if member and member.schedule:
            return (
                self.session.query(Appointment)
                .filter(Appointment.member_schedule_id == member.schedule.id)
                .all()
            )
        return None

    @trace_wrapper
    def get_appointments_paginated(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self,
        args: dict | None = None,
        **kwags,
    ) -> tuple[dict, list[Appointment] | list[None]]:
        """Get list of upcoming appointments with optional args and pagination"""
        # guard against None args
        if args is None:
            args = {}

        appointments_query = self._get_appointments(args, **kwags)
        if not appointments_query:
            return {}, []

        # pagination defaults
        limit = args.get("limit") or 5
        offset = args.get("offset") or 0

        # TODO: Add order_direction in query
        order_direction = args.get("order_direction") or "asc"

        total_records = appointments_query.count()
        appointment_records = appointments_query.limit(limit).offset(offset).all()

        pagination = {
            "total": total_records,
            "limit": limit,
            "offset": offset,
            "order_direction": order_direction,
        }

        return pagination, appointment_records

    def _get_appointments(self, args: dict, **kwargs) -> Query | None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        query = self.session.query(Appointment)
        if args.get("scheduled_start"):
            query = query.filter(Appointment.scheduled_start >= args["scheduled_start"])
        if args.get("scheduled_start_before"):
            query = query.filter(
                Appointment.scheduled_start < args["scheduled_start_before"]
            )
        if args.get("scheduled_end_range"):
            query = query.filter(
                Appointment.scheduled_end >= args["scheduled_end_range"][0],
                Appointment.scheduled_end <= args["scheduled_end_range"][1],
            )
        if args.get("scheduled_end"):
            query = query.filter(Appointment.scheduled_end <= args["scheduled_end"])
        if args.get("practitioner_id"):
            query = query.join(Product).filter(
                Product.user_id == args["practitioner_id"]
            )

        member = None
        if "member" in kwargs and kwargs.get("member"):
            member = kwargs.pop("member")
            member_id = member.id
        elif args.get("member_id"):
            member_id = args["member_id"]
            member = self.session.query(User).get(member_id)

        if member:
            member_schedule_id = member.schedule.id if member.schedule else None
            query = query.filter(Appointment.member_schedule_id == member_schedule_id)

            if int(args["current_user_id"]) != member_id and not member_schedule_id:
                query = query.filter(Appointment.privacy != PRIVACY_CHOICES.anonymous)

        if args.get("schedule_event_ids"):
            query = query.filter(
                Appointment.schedule_event_id.in_(args["schedule_event_ids"])
            )
        if args.get("exclude_statuses"):
            if args["exclude_statuses"] == ["CANCELLED"]:
                query = query.filter(Appointment.cancelled_at == None)
            else:
                log.info(
                    "Bad exclude_statuses arg - not filtering: %s",
                    args["exclude_statuses"],
                )
        if args.get("purposes"):
            query = query.filter(Appointment.purpose.in_(args["purposes"]))
        if args.get("order_direction"):
            query = query.order_by(
                getattr(Appointment.scheduled_start, args["order_direction"])()
            )
        return query
