from dataclasses import dataclass

from marshmallow import Schema, fields


class NeedsGetSchema(Schema):
    id = fields.Integer(required=False)
    name = fields.String(required=False)
    provider_id = fields.String(required=False)
    track_name = fields.String(required=False)


@dataclass
class NeedsGetResultStruct:
    __slots__ = ("id", "name", "description")
    id: int
    name: str
    description: str
