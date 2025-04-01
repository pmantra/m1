from marshmallow_v1 import Schema, fields

from views.schemas.common import PaginableArgsSchema, PaginableOutputSchema


class AvailabilitySchema(Schema):
    start_time = fields.DateTime()
    end_time = fields.DateTime()


class PractitionerAvailabilitiesDataSchema(Schema):
    availabilities = fields.Nested(AvailabilitySchema, many=True)
    duration = fields.Int()
    practitioner_id = fields.Int()
    product_id = fields.Int()
    product_price = fields.Float()
    total_available_credits = fields.Int()


class PractitionersAvailabilitiesSchema(PaginableOutputSchema):
    data = fields.Nested(PractitionerAvailabilitiesDataSchema, many=True)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchema" defined the type as "Raw")


class PractitionersAvailabilitiesPostSchema(PaginableArgsSchema):
    practitioner_ids = fields.List(fields.Int())
    can_prescribe = fields.Boolean()
    provider_type = fields.String()
    start_time = fields.DateTime()
    end_time = fields.DateTime()
    provider_steerage_sort = fields.Boolean()


class PractitionerDatesAvailablePostSchema(Schema):
    practitioner_ids = fields.List(fields.Int())
    member_timezone = fields.String()
    can_prescribe = fields.Boolean()
    provider_type = fields.String()
    start_time = fields.DateTime()
    end_time = fields.DateTime()


class PractitionerDatesAvailableDataSchema(Schema):
    date = fields.String()
    hasAvailability = fields.Boolean()


class PractitionerDatesAvailableSchema(PaginableOutputSchema):
    data = fields.Nested(PractitionerDatesAvailableDataSchema, many=True)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchema" defined the type as "Raw")
