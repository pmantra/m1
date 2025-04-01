from marshmallow import ValidationError  # noqa: F401
from marshmallow import Schema, fields


class MinimalProductSchema(Schema):
    minutes = fields.Integer(required=True)
    price = fields.Float(required=True)


class VerticalProductSchema(Schema):
    vertical_id = fields.Integer(required=True)
    product = fields.Nested(MinimalProductSchema, required=True)
