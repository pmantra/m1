from marshmallow import fields

from views.schemas.base import (
    BooleanWithDefault,
    IntegerWithDefaultV3,
    MavenSchemaV3,
    StringWithDefaultV3,
)


# NB: trailing_underscore_names_ like id_ and type_ in this file are to avoid shadowing
# the python built-ins with the same name.
class AnswerSchemaV3(MavenSchemaV3):
    id_ = fields.String(required=True, data_key="id")
    text = StringWithDefaultV3(dump_default="", required=False)
    sort_order = IntegerWithDefaultV3(dump_default=None, required=True)


class QuestionSchemaV3(MavenSchemaV3):
    id_ = fields.String(required=True, data_key="id")
    sort_order = IntegerWithDefaultV3(dump_default=None, required=True)
    label = StringWithDefaultV3(dump_default="", required=False)
    type_ = StringWithDefaultV3(dump_default="", required=True, data_key="type")
    required = BooleanWithDefault(required=True)
    answers = fields.List(fields.Nested(AnswerSchemaV3))


class QuestionSetSchemaV3(MavenSchemaV3):
    id_ = fields.String(required=True, data_key="id")
    sort_order = IntegerWithDefaultV3(dump_default=None, required=True)
    oid = StringWithDefaultV3(dump_default="", required=True)
    questions = fields.List(fields.Nested(QuestionSchemaV3))


class QuestionnaireSchemaV3(MavenSchemaV3):
    id_ = fields.String(required=True, data_key="id")
    sort_order = IntegerWithDefaultV3(dump_default=None, required=True)
    oid = StringWithDefaultV3(dump_default="", required=True)
    title_text = StringWithDefaultV3(dump_default="", required=False)
    description_text = StringWithDefaultV3(dump_default="", required=False)
    intro_appointment_only = BooleanWithDefault(dump_default="", required=False)
    track_name = StringWithDefaultV3(dump_default="", required=False)
    question_sets = fields.List(fields.Nested(QuestionSetSchemaV3))
    trigger_answer_ids = fields.List(fields.String())


class GetMemberQuestionnairesResponseSchemaV3(MavenSchemaV3):
    questionnaires = fields.List(fields.Nested(QuestionnaireSchemaV3, required=True))
