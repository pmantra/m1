from marshmallow_v1 import Schema, fields


class AvailabilitiesMemberTimesSchema(Schema):
    start_time = fields.String(required=True)
    end_time = fields.String(required=True)
    start_date = fields.String(required=True)
    end_date = fields.String(required=False)


class AvailabilityNotificationRequestPOSTSchema(Schema):
    practitioner_id = fields.Integer(required=True, nullable=False)
    availabilities = fields.List(
        fields.Nested(AvailabilitiesMemberTimesSchema), required=True, nullable=False
    )
    member_timezone = fields.String(required=True, nullable=False)

    class Meta:
        strict = True
