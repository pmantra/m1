from __future__ import annotations

from marshmallow import ValidationError, fields

from appointments.models.schedule_event import ScheduleEvent
from views.schemas.base import (
    BooleanWithDefault,
    IntegerWithDefaultV3,
    MavenDateTimeV3,
    MavenSchemaV3,
    NestedWithDefaultV3,
    PaginableArgsSchemaV3,
    PaginableOutputSchemaV3,
    StringWithDefaultV3,
)


def validate_state(value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if value in ScheduleEvent.states:
        return value
    raise ValidationError("Invalid ScheduleEvent state!")


class EventSchemaV3(MavenSchemaV3):
    id = IntegerWithDefaultV3(default=0, required=False)
    state = StringWithDefaultV3(required=True, validate=validate_state)
    starts_at = MavenDateTimeV3(required=True)
    ends_at = MavenDateTimeV3(required=True)


class EventsGetSchemaV3(PaginableArgsSchemaV3):
    starts_at = MavenDateTimeV3(required=False, allow_none=True)
    ends_at = MavenDateTimeV3(required=False, allow_none=True)
    recurring = BooleanWithDefault(required=False, load_default=True, dump_default=True)


class EventsMetaSchemaV3(MavenSchemaV3):
    user_id = IntegerWithDefaultV3(dump_default=0, required=False)
    starts_at = MavenDateTimeV3(required=False)
    ends_at = MavenDateTimeV3(required=False)


class SchedulingConstraints(MavenSchemaV3):
    prep_buffer = fields.Integer(required=True)
    booking_buffer = fields.Integer(required=True)
    max_capacity = fields.Integer(required=True)
    daily_intro_capacity = fields.Integer(required=True)


class MaintenanceWindow(MavenSchemaV3):
    scheduled_start = MavenDateTimeV3(required=False)
    scheduled_end = MavenDateTimeV3(required=False)


class EventsSchemaV3(PaginableOutputSchemaV3):
    data = NestedWithDefaultV3(EventSchemaV3, many=True, dump_default=[])  # type: ignore[assignment] # Incompatible types in assignment (expression has type "NestedWithDefaultV3", base class "PaginableOutputSchemaV3" defined the type as "RawWithDefaultV3")
    meta = fields.Nested(EventsMetaSchemaV3)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchemaV3" defined the type as "RawWithDefaultV3")
    provider_scheduling_constraints = fields.Nested(SchedulingConstraints)
    maintenance_windows = fields.Nested(MaintenanceWindow, many=True)
