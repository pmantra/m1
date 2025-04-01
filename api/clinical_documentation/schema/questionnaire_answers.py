from marshmallow import fields

from views.schemas.base import MavenSchemaV3


class AnswersSchemaV3(MavenSchemaV3):
    # Note that this schema is passed in in a list in the request.
    question_id = fields.Integer()
    answer_id = fields.Integer(required=False, allow_none=True)
    text = fields.String()
    appointment_id = fields.Integer()
    user_id = fields.Integer()
