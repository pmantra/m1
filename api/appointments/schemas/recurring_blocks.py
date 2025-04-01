from __future__ import annotations

import pytz
from marshmallow import ValidationError, fields, validate

from appointments.models.constants import ScheduleFrequencies
from views.schemas.base import (
    IntegerWithDefaultV3,
    ListWithDefaultV3,
    MavenDateTimeV3,
    MavenSchemaV3,
    NestedWithDefaultV3,
    PaginableArgsSchemaV3,
    PaginableOutputSchemaV3,
    StringWithDefaultV3,
)


def validate_index(value: int) -> int:
    if 0 <= value <= 6:
        return value
    raise ValidationError("Invalid week_day_index! Must be between 0-6!")


def validate_timezone(value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if value in pytz.all_timezones:
        return value
    raise ValidationError("Incorrect timezone passed!")


class ScheduleRecurringBlockPostRequestArgsSchema(MavenSchemaV3):
    starts_at = MavenDateTimeV3(required=True)
    ends_at = MavenDateTimeV3(required=True)
    frequency = StringWithDefaultV3(
        required=True, validate=validate.OneOf([f.value for f in ScheduleFrequencies])
    )
    until = MavenDateTimeV3(required=True)
    week_days_index = ListWithDefaultV3(
        fields.Integer(validate=validate_index), required=False, load_default=[]
    )
    member_timezone = StringWithDefaultV3(required=True, validate=validate_timezone)


class ScheduleRecurringBlockGetRequestArgsSchema(PaginableArgsSchemaV3):
    starts_at = MavenDateTimeV3(required=True)
    until = MavenDateTimeV3(required=True)


class ScheduleEventsSchema(MavenSchemaV3):
    id = IntegerWithDefaultV3(dump_default=0, required=True)
    starts_at = MavenDateTimeV3(required=True)
    ends_at = MavenDateTimeV3(required=True)


class ScheduleRecurringBlockSchema(MavenSchemaV3):
    id = IntegerWithDefaultV3(dump_default=0, required=True)
    schedule_id = IntegerWithDefaultV3(dump_default=0, required=True)
    schedule_events = NestedWithDefaultV3(
        ScheduleEventsSchema, many=True, dump_default=[]
    )
    starts_at = MavenDateTimeV3(required=True)
    ends_at = MavenDateTimeV3(required=True)
    until = MavenDateTimeV3(required=True)
    frequency = StringWithDefaultV3(
        required=True, validate=validate.OneOf([f.value for f in ScheduleFrequencies])
    )
    week_days_index = ListWithDefaultV3(fields.Int(), required=False)


class ScheduleRecurringBlockGetMetaSchema(MavenSchemaV3):
    user_id = IntegerWithDefaultV3(dump_default=0, required=False)
    starts_at = MavenDateTimeV3(required=False)
    until = MavenDateTimeV3(required=False)


class ScheduleRecurringBlockGetSchema(PaginableOutputSchemaV3):
    data = NestedWithDefaultV3(ScheduleRecurringBlockSchema, many=True, dump_default=[])  # type: ignore[assignment] # Incompatible types in assignment (expression has type "NestedWithDefaultV3", base class "PaginableOutputSchemaV3" defined the type as "RawWithDefaultV3")
    meta = fields.Nested(ScheduleRecurringBlockGetMetaSchema)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchemaV3" defined the type as "RawWithDefaultV3")
