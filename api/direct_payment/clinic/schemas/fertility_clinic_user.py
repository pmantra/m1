from marshmallow import Schema, fields

from direct_payment.clinic.schemas.fertility_clinics import FertilityClinicsSchema


class FertilityClinicUserProfileSchema(Schema):
    id = fields.Integer(required=True)
    first_name = fields.String(required=True)
    last_name = fields.String(required=True)
    email = fields.String(required=True)
    user_id = fields.Integer(required=True)
    role = fields.String(required=True)
    clinics = fields.Nested(FertilityClinicsSchema, many=True)
