from marshmallow import Schema, fields

from direct_payment.clinic.schemas.fee_schedule import FeeScheduleSchema


class FertilityClinicLocationSchema(Schema):
    id = fields.Integer(required=True)
    name = fields.String(required=True)
    address_1 = fields.String(required=True)
    address_2 = fields.String()
    city = fields.String(required=True)
    subdivision_code = fields.String(required=True)
    postal_code = fields.String(required=True)
    country_code = fields.String()
    phone_number = fields.String()
    email = fields.String()


class FertilityClinicsSchema(Schema):
    id = fields.Integer(required=True)
    name = fields.String(required=True)
    affiliated_network = fields.String()
    fee_schedule_id = fields.Integer(required=True)
    payments_recipient_id = fields.String()
    fee_schedule = fields.Nested(FeeScheduleSchema, required=True)
    notes = fields.String()
    locations = fields.Nested(FertilityClinicLocationSchema, many=True)


class FertilityClinicArgsSchema(Schema):
    payments_recipient_id = fields.String(required=True)
