from marshmallow import Schema, fields


class VideoSessionSchema(Schema):
    id = fields.String()


class VideoSessionSchemaV2(Schema):
    session_id = fields.String()


class VideoSessionTokenSchema(Schema):
    session_id = fields.String()
    token = fields.String()
