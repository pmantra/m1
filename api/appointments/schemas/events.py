import datetime

from marshmallow_v1 import ValidationError, fields

from appointments.models.schedule_event import ScheduleEvent
from views.schemas.common import (
    BooleanDefaultNoneField,
    MavenDateTime,
    MavenSchema,
    PaginableArgsSchema,
    PaginableOutputSchema,
)


def validate_state(value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if value in ScheduleEvent.states:
        return value
    raise ValidationError("Invalid ScheduleEvent state!")


class EventSchema(MavenSchema):
    id = fields.Integer(required=False)
    state = fields.String(required=True, validate=validate_state)
    starts_at = MavenDateTime(required=True)
    ends_at = MavenDateTime(required=True)

    class Meta:
        strict = True


@EventSchema.validator
def validate_dates(self, data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if data["ends_at"] <= datetime.datetime.utcnow():
        raise ValidationError("ends_at must be in the future!")
    if data["starts_at"] >= data["ends_at"]:
        raise ValidationError("ends_at must be greater than starts_at!")


class EventsGetSchema(PaginableArgsSchema):
    starts_at = MavenDateTime(required=False)
    ends_at = MavenDateTime(required=False)
    recurring = BooleanDefaultNoneField(required=False, default=True)


class EventsMetaSchema(MavenSchema):
    user_id = fields.Integer(required=False)
    starts_at = MavenDateTime(required=False)
    ends_at = MavenDateTime(required=False)


class EventsSchema(PaginableOutputSchema):
    data = fields.Nested(EventSchema, many=True)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchema" defined the type as "Raw")
    meta = fields.Nested(EventsMetaSchema)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchema" defined the type as "Raw")
