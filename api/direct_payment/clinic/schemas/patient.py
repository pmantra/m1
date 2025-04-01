from marshmallow import Schema, fields


class PatientLookupPOSTRequestSchema(Schema):
    benefit_id = fields.String(required=True)
    last_name = fields.String(required=True)
    date_of_birth = fields.Date(required=True)
