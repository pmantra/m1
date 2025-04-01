from marshmallow import fields

from views.schemas.base import (
    BooleanWithDefault,
    DataTimeWithDefaultV3,
    IntegerWithDefaultV3,
    MavenSchemaV3,
    StringWithDefaultV3,
)


class AnswerSchemaV3(MavenSchemaV3):
    id = StringWithDefaultV3(dump_default="", required=False)
    sort_order = IntegerWithDefaultV3(dump_default=0, required=False)
    text = StringWithDefaultV3(dump_default="", required=False)
    oid = StringWithDefaultV3(dump_default=None, required=False)
    soft_deleted_at = DataTimeWithDefaultV3(dump_default=None, required=False)


class QuestionSchemaV3(MavenSchemaV3):
    id = StringWithDefaultV3(dump_default="", required=False)
    sort_order = IntegerWithDefaultV3(dump_default=0, required=False)
    label = StringWithDefaultV3(dump_default="", required=False)
    type = StringWithDefaultV3(dump_default="", required=False)
    required = BooleanWithDefault(dump_default=None, required=False)
    oid = StringWithDefaultV3(dump_default=None, required=False)
    non_db_answer_options_json = StringWithDefaultV3(dump_default=None, required=False)
    soft_deleted_at = DataTimeWithDefaultV3(dump_default=None, required=False)
    answers = fields.List(fields.Nested(AnswerSchemaV3), required=False)


class QuestionSetSchemaV3(MavenSchemaV3):
    id = StringWithDefaultV3(dump_default="", required=False)
    oid = StringWithDefaultV3(dump_default=None, required=False)
    sort_order = IntegerWithDefaultV3(dump_default=0, required=False)
    prerequisite_answer_id = StringWithDefaultV3(dump_default=None, required=False)
    soft_deleted_at = DataTimeWithDefaultV3(dump_default=None, required=False)
    questions = fields.List(fields.Nested(QuestionSchemaV3), required=False)


class QuestionnaireSchemaV3(MavenSchemaV3):
    id = StringWithDefaultV3(dump_default="", required=False)
    sort_order = IntegerWithDefaultV3(dump_default=0, required=False)
    oid = StringWithDefaultV3(dump_default="", required=False)
    title_text = StringWithDefaultV3(dump_default=None, required=False)
    description_text = StringWithDefaultV3(dump_default=None, required=False)
    soft_deleted_at = DataTimeWithDefaultV3(dump_default=None, required=False)
    trigger_answer_ids = fields.List(
        StringWithDefaultV3(dump_default=None), required=False
    )
    question_sets = fields.List(fields.Nested(QuestionSetSchemaV3), required=False)


class RecordedAnswerSchemaV3(MavenSchemaV3):
    appointment_id = IntegerWithDefaultV3(dump_default=0, required=False)
    user_id = IntegerWithDefaultV3(dump_default=None, required=False)
    question_id = StringWithDefaultV3(dump_default="", required=False)
    question_type = StringWithDefaultV3(dump_default="", required=False)
    answer_id = StringWithDefaultV3(dump_default=None, required=False)
    text = StringWithDefaultV3(dump_default=None, required=False)
    date = fields.Date(dump_default=None, required=False)
    payload = fields.Dict(dump_default=None, required=False)


class RecordedAnswerSetSchemaV3(MavenSchemaV3):
    id = StringWithDefaultV3(dump_default="", required=False)
    questionnaire_id = StringWithDefaultV3(dump_default="", required=False)
    modified_at = DataTimeWithDefaultV3(dump_default=None, required=False)
    submitted_at = DataTimeWithDefaultV3(dump_default=None, required=False)
    source_user_id = IntegerWithDefaultV3(dump_default=0, required=False)
    draft = BooleanWithDefault(dump_default=None, required=False)
    appointment_id = IntegerWithDefaultV3(dump_default=0, required=False)
    recorded_answers = fields.List(
        fields.Nested(RecordedAnswerSchemaV3), required=False
    )


class ProviderAddendumAnswerSchemaV3(MavenSchemaV3):
    question_id = StringWithDefaultV3(dump_default="", required=False)
    answer_id = StringWithDefaultV3(dump_default=None, required=False)
    text = StringWithDefaultV3(dump_default="", required=False)
    date = fields.Date()


class ProviderAddendumSchemaV3(MavenSchemaV3):
    id = StringWithDefaultV3(dump_default="", required=False)
    questionnaire_id = StringWithDefaultV3(dump_default="", required=False)
    associated_answer_id = StringWithDefaultV3(dump_default="", required=False)
    associated_question_id = StringWithDefaultV3(dump_default="", required=False)
    submitted_at = DataTimeWithDefaultV3(dump_default=None, required=False)
    user_id = IntegerWithDefaultV3(dump_default=0, required=False)
    appointment_id = IntegerWithDefaultV3(dump_default=0, required=False)
    provider_addendum_answers = fields.List(
        fields.Nested(ProviderAddendumAnswerSchemaV3), required=False
    )


class StructuredInternalNoteSchemaV3(MavenSchemaV3):
    questionnaire = fields.Nested(QuestionnaireSchemaV3, required=False)
    question_sets = fields.List(fields.Nested(QuestionSetSchemaV3), required=False)
    recorded_answer_set = fields.Nested(RecordedAnswerSetSchemaV3, required=False)
    recorded_answers = fields.List(
        fields.Nested(RecordedAnswerSchemaV3), required=False
    )


class ProviderAddendaAndQuestionnaireSchemaV3(MavenSchemaV3):
    questionnaire = fields.Nested(QuestionnaireSchemaV3, required=False)
    provider_addenda = fields.List(
        fields.Nested(ProviderAddendumSchemaV3), required=False
    )
