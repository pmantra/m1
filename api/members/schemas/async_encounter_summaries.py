from dateutil.parser import parse
from marshmallow import Schema, ValidationError, fields, validates_schema

from views.schemas.common_v3 import PaginableArgsSchemaV3, PaginableOutputSchemaV3


# Questions schemas ported over to avoid marshmallow_v1 version conflict errors
class AnswerSchema(Schema):
    id = fields.String()
    sort_order = fields.Integer()
    text = fields.String()
    oid = fields.String(default=None)
    soft_deleted_at = fields.DateTime()


class QuestionSchema(Schema):
    id = fields.String()
    sort_order = fields.Integer()
    label = fields.String()
    type = fields.Function(lambda obj: obj["type"].value)
    required = fields.Boolean()
    oid = fields.String(default=None)
    non_db_answer_options_json = fields.Raw(default=None)
    soft_deleted_at = fields.DateTime()
    answers = fields.List(fields.Nested(AnswerSchema))


class QuestionSetSchema(Schema):
    id = fields.String()
    oid = fields.String(default=None)
    sort_order = fields.Integer()
    prerequisite_answer_id = fields.String(default=None)
    soft_deleted_at = fields.DateTime()
    questions = fields.List(fields.Nested(QuestionSchema))


class QuestionnaireSchema(Schema):
    id = fields.String()
    sort_order = fields.Integer()
    oid = fields.String()
    title_text = fields.String(default=None)
    description_text = fields.String(default=None)
    soft_deleted_at = fields.DateTime()
    trigger_answer_ids = fields.List(fields.String())
    question_sets = fields.List(fields.Nested(QuestionSetSchema))


class AsyncEncounterSummaryAnswersSchema(Schema):
    question_id = fields.String(required=True)
    answer_id = fields.String()
    text = fields.String()
    date = fields.DateTime()

    @validates_schema
    def validate_answered_field_present(self, data, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if data.get("answer_id") or data.get("text") or data.get("date"):
            return True
        else:
            raise ValidationError("There must be one answer present for the question")


class AsyncEncounterSummariesSchema(Schema):
    async_encounter_summary_answers = fields.List(
        fields.Nested(AsyncEncounterSummaryAnswersSchema, required=True)
    )
    questionnaire_id = fields.String(required=True)
    encounter_date = fields.DateTime(required=True)
    created_at = fields.DateTime()


class AsyncEncounterSummariesPostSchema(AsyncEncounterSummariesSchema):
    id = fields.Integer(required=True)
    provider_id = fields.Integer(required=True)


class AsyncEncounterSummarySchema(Schema):
    async_encounter_summary = fields.Nested(
        AsyncEncounterSummariesSchema, required=True
    )


class AsyncEncounterSummaryPostSchema(Schema):
    async_encounter_summary = fields.Nested(
        AsyncEncounterSummariesPostSchema, required=True
    )


class AsyncEncounterSummaryGetSchema(AsyncEncounterSummariesSchema):
    id = fields.Integer()
    provider_id = fields.String()
    provider_first_name = fields.Method("get_provider_first_name")
    provider_last_name = fields.Method("get_provider_last_name")
    provider_verticals = fields.Method("get_provider_verticals")
    questionnaire = fields.Method("build_questionnaire_data")

    def get_provider_first_name(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        async_encounter_summary_id = obj.id

        first_name = (
            self.context.get("provider_name", {})
            .get(async_encounter_summary_id)
            .get("first_name")
        )

        return first_name if first_name else ""

    def get_provider_last_name(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        async_encounter_summary_id = obj.id

        last_name = (
            self.context.get("provider_name", {})
            .get(async_encounter_summary_id)
            .get("last_name")
        )

        return last_name if last_name else ""

    def get_provider_verticals(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        async_encounter_summary_id = obj.id

        provider_verticals = self.context.get("provider_verticals", {}).get(
            async_encounter_summary_id, []
        )

        return provider_verticals

    def build_questionnaire_data(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        async_encounter_summary_id = obj.id
        questionnaire = self.context.get("questionnaire", {}).get(
            async_encounter_summary_id, {}
        )

        schema = QuestionnaireSchema()
        return schema.dump(questionnaire["questionnaire"])


class AsyncEncounterSummariesGetSchema(PaginableOutputSchemaV3):
    data = fields.Nested(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchemaV3" defined the type as "Raw")
        AsyncEncounterSummaryGetSchema,
        many=True,
    )


class AsyncEncounterSummariesGetArgsSchema(PaginableArgsSchemaV3):
    scheduled_start = fields.Method(deserialize="parse_datetime")
    scheduled_end = fields.Method(deserialize="parse_datetime")
    my_encounters = fields.Boolean(default=False)
    provider_types = fields.List(fields.String())

    # Because this uses new marshmallow, it needs special parsing vs marshmallow_v1
    # On web we send in MM/DD/YYYY, so we want to parser to know Month is first in a ##/##/####
    def parse_datetime(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return parse(value, dayfirst=False)
