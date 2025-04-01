from marshmallow import Schema, fields


class PostTestProvidersSchema(Schema):
    vertical_name = fields.String(required=False, load_default="Care Advocate")
    state_name = fields.String(required=False, load_default="New York")
    timezone = fields.String(required=False, load_default="America/New_York")
