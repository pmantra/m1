from marshmallow_v1 import Schema, fields


class FooSerializer(Schema):
    _id = fields.Integer()
