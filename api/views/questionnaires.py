from typing import List

from flask import request
from flask_restful import abort
from marshmallow import fields as ma_fields
from marshmallow_v1 import Schema, fields
from sqlalchemy import desc
from sqlalchemy.orm.exc import NoResultFound

from authn.models.user import User
from authz.models.roles import ROLES, Role
from common.services.api import PermissionedCareTeamResource, PermissionedUserResource
from models.profiles import practitioner_verticals
from models.questionnaires import (
    ASYNC_ENCOUNTER_QUESTIONNAIRE_OID,
    DraftUpdateAttemptException,
    Questionnaire,
    RecordedAnswer,
    RecordedAnswerSet,
    questionnaire_vertical,
)
from storage.connection import db
from views.schemas.base import (
    IntegerWithDefaultV3,
    ListWithDefaultV3,
    SchemaV3,
    StringWithDefaultV3,
)


class AnswerSchema(Schema):
    id = fields.String()
    sort_order = fields.Integer()
    text = fields.String()
    oid = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    soft_deleted_at = fields.DateTime()


class QuestionSchema(Schema):
    id = fields.String()
    sort_order = fields.Integer()
    label = fields.String()
    type = fields.Function(lambda obj: obj.type.value)
    required = fields.Boolean()
    oid = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    non_db_answer_options_json = fields.Raw(default=None)
    soft_deleted_at = fields.DateTime()
    answers = fields.List(fields.Nested(AnswerSchema))


class QuestionSetSchema(Schema):
    id = fields.String()
    oid = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    sort_order = fields.Integer()
    prerequisite_answer_id = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    soft_deleted_at = fields.DateTime()
    questions = fields.List(fields.Nested(QuestionSchema))


class QuestionnaireSchema(Schema):
    id = fields.String()
    sort_order = fields.Integer()
    oid = fields.String()
    title_text = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    description_text = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    soft_deleted_at = fields.DateTime()
    trigger_answer_ids = fields.Method("get_trigger_answer_ids")
    question_sets = fields.List(fields.Nested(QuestionSetSchema))

    def get_trigger_answer_ids(self, obj, _):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return [str(a.id) for a in obj.trigger_answers]


class AnswerSchemaV3(SchemaV3):
    id = StringWithDefaultV3(dump_default="")
    sort_order = IntegerWithDefaultV3(dump_default=0)
    text = StringWithDefaultV3(dump_default="")
    oid = StringWithDefaultV3(dump_default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    soft_deleted_at = ma_fields.DateTime()


class QuestionSchemaV3(SchemaV3):
    id = StringWithDefaultV3(default="")
    sort_order = IntegerWithDefaultV3(default=0)
    label = StringWithDefaultV3(default="")
    type = ma_fields.Method(serialize="get_type")
    required = ma_fields.Boolean()
    oid = ma_fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    non_db_answer_options_json = ma_fields.Raw(default=None)
    soft_deleted_at = ma_fields.DateTime()
    answers = ListWithDefaultV3(ma_fields.Nested(AnswerSchemaV3), default=[])

    def get_type(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if hasattr(obj, "type"):
            return obj.type.value
        else:
            return None


class QuestionSetSchemaV3(SchemaV3):
    id = StringWithDefaultV3(dump_default="", load_default="")
    oid = ma_fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    sort_order = IntegerWithDefaultV3(dump_default=0, load_default=0)
    prerequisite_answer_id = ma_fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    soft_deleted_at = ma_fields.DateTime()
    questions = ListWithDefaultV3(
        ma_fields.Nested(QuestionSchemaV3), dump_default=[], load_default=[]
    )


class QuestionnaireSchemaV3(SchemaV3):
    id = StringWithDefaultV3(default="")
    sort_order = IntegerWithDefaultV3(default=0)
    oid = StringWithDefaultV3(default="")
    title_text = ma_fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    description_text = ma_fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    soft_deleted_at = ma_fields.DateTime()
    trigger_answer_ids = ma_fields.Method(serialize="get_trigger_answer_ids")
    question_sets = ListWithDefaultV3(ma_fields.Nested(QuestionSetSchemaV3), default=[])

    def get_trigger_answer_ids(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if hasattr(obj, "trigger_answers"):
            return [str(a.id) for a in obj.trigger_answers]
        else:
            return None


class RecordedAnswerSchema(Schema):
    appointment_id = fields.Method("get_appt_id")
    user_id = fields.Integer(default=None)  # type: ignore[arg-type] # Argument "default" to "Integer" has incompatible type "None"; expected "int"
    question_id = fields.String()
    question_type = fields.Function(lambda rec_answer: rec_answer.question.type.value)
    answer_id = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    text = fields.Method("get_text")
    date = fields.Date()
    payload = fields.Method("get_payload")

    def get_appt_id(self, obj, _):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        from appointments.services.common import obfuscate_appointment_id

        if obj.appointment_id:
            return obfuscate_appointment_id(obj.appointment_id)
        elif obj.recorded_answer_set and obj.recorded_answer_set.appointment_id:
            return obfuscate_appointment_id(obj.recorded_answer_set.appointment_id)

    def get_text(self, obj, _):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if obj.text:
            return obj.text
        # Translate payload back to text for clients that aren't using payload field yet
        elif obj.payload:
            if obj.payload.get("text"):
                return obj.payload.get("text")

    def get_payload(self, obj, _):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if obj.payload:
            return obj.payload
        # Translate text to payload for clients that aren't using text field anymore
        elif obj.text:
            return {"text": obj.text}


class RecordedAnswerSchemaV3(SchemaV3):
    appointment_id = ma_fields.Method("get_appt_id")
    user_id = ma_fields.Integer(default=None)  # type: ignore[arg-type] # Argument "default" to "Integer" has incompatible type "None"; expected "int"
    question_id = ma_fields.String()
    question_type = ma_fields.Function(
        lambda rec_answer: rec_answer.question.type.value
    )
    answer_id = ma_fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    text = ma_fields.Method("get_text")
    date = ma_fields.Date()
    payload = ma_fields.Method("get_payload")

    def get_appt_id(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        from appointments.services.common import obfuscate_appointment_id

        if obj.appointment_id:
            return obfuscate_appointment_id(obj.appointment_id)
        elif obj.recorded_answer_set and obj.recorded_answer_set.appointment_id:
            return obfuscate_appointment_id(obj.recorded_answer_set.appointment_id)

    def get_text(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if obj.text:
            return obj.text
        # Translate payload back to text for clients that aren't using payload field yet
        elif obj.payload:
            if obj.payload.get("text"):
                return obj.payload.get("text")

    def get_payload(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if obj.payload:
            return obj.payload
        # Translate text to payload for clients that aren't using text field anymore
        elif obj.text:
            return {"text": obj.text}


class RecordedAnswerSetSchema(Schema):
    id = fields.String()
    questionnaire_id = fields.String()
    modified_at = fields.DateTime()
    submitted_at = fields.DateTime()
    source_user_id = fields.Integer()
    draft = fields.Boolean(default=None)
    appointment_id = fields.Method("get_appt_id")
    recorded_answers = fields.List(fields.Nested(RecordedAnswerSchema))

    def get_appt_id(self, obj, _):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        from appointments.services.common import obfuscate_appointment_id

        if obj.appointment_id:
            return obfuscate_appointment_id(obj.appointment_id)


class RecordedAnswerSetSchemaV3(SchemaV3):
    id = ma_fields.String()
    questionnaire_id = ma_fields.String()
    modified_at = ma_fields.DateTime()
    submitted_at = ma_fields.DateTime()
    source_user_id = ma_fields.Integer()
    draft = ma_fields.Boolean(default=None)
    appointment_id = ma_fields.Method("get_appt_id")
    recorded_answers = ma_fields.List(ma_fields.Nested(RecordedAnswerSchemaV3))

    def get_appt_id(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        from appointments.services.common import obfuscate_appointment_id

        if obj.appointment_id:
            return obfuscate_appointment_id(obj.appointment_id)


class ProviderAddendumAnswerSchema(Schema):
    question_id = fields.String()
    answer_id = fields.String(default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    text = fields.String()
    date = fields.Date()


class ProviderAddendumAnswerSchemaV3(SchemaV3):
    question_id = StringWithDefaultV3(dump_default="", load_default="")
    answer_id = StringWithDefaultV3(dump_default=None, load_default=None)  # type: ignore[arg-type] # Argument "default" to "String" has incompatible type "None"; expected "str"
    text = StringWithDefaultV3(dump_default="", load_default="")
    date = ma_fields.Date()


class ProviderAddendumSchema(Schema):
    id = fields.String()
    questionnaire_id = fields.String()
    associated_answer_id = fields.String()
    associated_question_id = fields.String()
    submitted_at = fields.DateTime()
    user_id = fields.Integer()
    appointment_id = fields.Method("get_appt_id")
    provider_addendum_answers = fields.List(fields.Nested(ProviderAddendumAnswerSchema))

    def get_appt_id(self, obj, _):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        from appointments.services.common import obfuscate_appointment_id

        if obj.appointment_id:
            return obfuscate_appointment_id(obj.appointment_id)


class ProviderAddendumSchemaV3(SchemaV3):
    id = ma_fields.String()
    questionnaire_id = ma_fields.String()
    associated_answer_id = ma_fields.String()
    associated_question_id = ma_fields.String()
    submitted_at = ma_fields.DateTime()
    user_id = ma_fields.Integer()
    appointment_id = ma_fields.Method("get_appt_id")
    provider_addendum_answers = ma_fields.List(
        ma_fields.Nested(ProviderAddendumAnswerSchemaV3)
    )

    def get_appt_id(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        from appointments.services.common import obfuscate_appointment_id

        if obj.appointment_id:
            return obfuscate_appointment_id(obj.appointment_id)


class QuestionnaireAndRecordedAnswerSetSchema(Schema):
    questionnaire = fields.Nested(QuestionnaireSchema)
    recorded_answer_set = fields.Nested(RecordedAnswerSetSchema, default=None)


class QuestionnairesSchema(Schema):
    data = fields.List(fields.Nested(QuestionnaireAndRecordedAnswerSetSchema))


class QuestionnairesResource(PermissionedCareTeamResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self.validate_get_params(request.args)
        user_id = request.args.get("user_id")
        try:
            user = db.session.query(User).filter(User.id == user_id).one()
        except NoResultFound:
            abort(404, message=f"User {user_id} invalid.")

        self._user_has_access_to_user_or_403(accessing_user=self.user, target_user=user)

        oid = request.args.get("oid")

        questionnaires = self._get_questionnaires_for_practitioner(user_id, oid)  # type: ignore[arg-type] # Argument 1 to "_get_questionnaires_for_practitioner" of "QuestionnairesResource" has incompatible type "Optional[Any]"; expected "str"
        # only gives you the latest answer set per questionnaire
        # even though that's not necessarily what you asked for...sorry
        data = [
            {
                "questionnaire": questionnaire,
                "recorded_answer_set": RecordedAnswerSet.create_composite_answer_set_of_latest_answers(
                    user_id=user_id, questionnaire=questionnaire
                ),
            }
            for questionnaire in questionnaires
        ]
        return QuestionnairesSchema().dump({"data": data}).data

    @staticmethod
    def validate_get_params(params):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not (params.get("user_id") and params.get("oid")):
            abort(400, message="Missing required parameter(s)")

    @staticmethod
    def _get_questionnaires_for_practitioner(
        practitioner_id: str, oid: str = None  # type: ignore[assignment] # Incompatible default for argument "oid" (default has type "None", argument has type "str")
    ) -> List[Questionnaire]:
        # For async encounter questionnaires we want to get questionnaires that apply to the practitioner's vertical
        if oid == ASYNC_ENCOUNTER_QUESTIONNAIRE_OID:
            questionnaires = (
                db.session.query(Questionnaire, practitioner_verticals.c.user_id)
                .join(questionnaire_vertical)
                .join(
                    practitioner_verticals,
                    questionnaire_vertical.c.vertical_id
                    == practitioner_verticals.c.vertical_id,
                )
                .filter(practitioner_verticals.c.user_id == practitioner_id)
                .filter(~Questionnaire.roles.any(Role.name == ROLES.member))
            )

            questionnaires = questionnaires.filter(Questionnaire.oid.startswith(oid))

            questionnaires = (
                questionnaires.group_by(
                    Questionnaire.id, practitioner_verticals.c.user_id
                )
                .order_by(desc(Questionnaire.id))
                .all()
            )

            return [q.Questionnaire for q in questionnaires]
        else:
            questionnaires = Questionnaire.query.filter(Questionnaire.oid == oid).all()

            return questionnaires


class RecordedAnswerSetValidationMixin:
    def validate_post_params(self, params):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not (
            params.get("submitted_at")
            and params.get("source_user_id")
            and params.get("questionnaire_id")
            and params.get("recorded_answers")
        ):
            abort(400, message="Missing required parameter(s)")
        if self.user.id != params["source_user_id"]:  # type: ignore[attr-defined] # "RecordedAnswerSetValidationMixin" has no attribute "user"
            abort(403, message="Cannot submit recorded answer set for this user")


class RecordedAnswerSetsResource(
    PermissionedUserResource, RecordedAnswerSetValidationMixin
):
    def post(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        from appointments.services.common import deobfuscate_appointment_id
        from appointments.utils.appointment_utils import check_appointment_by_ids

        request_json = request.json if request.is_json else None
        self._user_or_404(user_id)
        self.validate_post_params(request_json)
        appt_id = request_json.get("appointment_id")

        check_appointment_by_ids(
            [appt_id and deobfuscate_appointment_id(appt_id)], True
        )

        rec_answer_set = RecordedAnswerSet(
            submitted_at=request_json["submitted_at"],
            source_user_id=user_id,
            questionnaire_id=request_json["questionnaire_id"],
            appointment_id=appt_id and deobfuscate_appointment_id(appt_id),
            draft=request_json.get("draft"),
        )
        db.session.add(rec_answer_set)
        for recorded_answer in request_json["recorded_answers"]:
            rec_answer_set.recorded_answers.append(
                RecordedAnswer(
                    user_id=user_id,
                    question_id=recorded_answer.get("question_id"),
                    answer_id=recorded_answer.get("answer_id"),
                    text=recorded_answer.get("text"),
                    payload=recorded_answer.get("payload"),
                )
            )
        db.session.commit()
        questionnaire = Questionnaire.query.filter(
            Questionnaire.id == request_json["questionnaire_id"]
        ).one()
        composite_answer_set = (
            RecordedAnswerSet.create_composite_answer_set_of_latest_answers(
                user_id=user_id, questionnaire=questionnaire
            )
        )
        return RecordedAnswerSetSchema().dump(composite_answer_set), 201

    def validate_post_params(self, params):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not (
            params.get("submitted_at")
            and params.get("source_user_id")
            and params.get("questionnaire_id")
            and params.get("recorded_answers")
        ):
            abort(400, message="Missing required parameter(s)")
        if self.user.id != params["source_user_id"]:
            abort(403, message="Cannot submit recorded answer set for this user")


class RecordedAnswerSetResource(
    PermissionedUserResource, RecordedAnswerSetValidationMixin
):
    def put(self, user_id, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._user_or_404(user_id)
        request_json = request.json if request.is_json else None
        self.validate_put_params(request_json)
        try:
            rec_answer_set = RecordedAnswerSet.create_or_update(
                id=id, attrs=request_json
            )
        except DraftUpdateAttemptException as e:
            abort(409, message=e.args[0])
        db.session.add(rec_answer_set)
        db.session.commit()
        return RecordedAnswerSetSchema().dump(rec_answer_set), 200

    def validate_put_params(self, params):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if params.get("draft") is None:
            abort(400, message="Missing required parameter(s)")
        self.validate_post_params(params)
