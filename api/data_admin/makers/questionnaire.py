import datetime
import random
from itertools import chain

from flask import flash

from appointments.utils.appointment_utils import check_appointment_by_ids
from authn.models.user import User
from authz.models.roles import Role
from data_admin.maker_base import _MakerBase
from models.questionnaires import (
    COACHING_NOTES_COACHING_PROVIDERS_OID,
    Answer,
    Question,
    Questionnaire,
    QuestionSet,
    QuestionTypes,
    RecordedAnswer,
    RecordedAnswerSet,
)
from models.verticals_and_specialties import Vertical
from storage.connection import db
from views.schemas.common import MavenDateTime, MavenSchema
from wheelhouse.marshmallow_v1.marshmallow_v1 import fields


class QuestionnaireSchema(MavenSchema):
    sort_order = fields.Integer()
    oid = fields.String()
    title_text = fields.String()
    description_text = fields.String()
    intro_appointment_only = fields.Boolean()
    track_name = fields.String()


class QuestionSetSchema(MavenSchema):
    sort_order = fields.Integer()
    oid = fields.String()
    questionnaire_id = fields.Integer()
    soft_deleted_at = MavenDateTime()


class QuestionSchema(MavenSchema):
    question_set_id = fields.Integer()
    sort_order = fields.Integer()
    label = fields.String()
    # Had to write this as question_type to not conflict with maker
    question_type = fields.Enum(
        choices=[t.value for t in QuestionTypes], default=QuestionTypes.TEXT.value
    )
    required = fields.Boolean(default=False)
    oid = fields.String()
    soft_deleted_at = MavenDateTime()


class AnswerSchema(MavenSchema):
    question_id = fields.Integer()
    sort_order = fields.Integer()
    text = fields.String()
    oid = fields.String()
    soft_deleted_at = MavenDateTime()


class QuestionnaireMaker(_MakerBase):
    spec_class = QuestionnaireSchema()  # type: ignore[assignment] # Incompatible types in assignment (expression has type "QuestionnaireSchema", base class "_MakerBase" defined the type as "None")

    def create_object(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        spec_data = self.spec_class.load(spec).data  # type: ignore[has-type] # Cannot determine type of "spec_class"
        questionnaire = Questionnaire(
            sort_order=spec_data.get("sort_order"),
            oid=spec_data.get("oid"),
            title_text=spec_data.get("title_text"),
            description_text=spec_data.get("description_text"),
            intro_appointment_only=spec_data.get("intro_appointment_only"),
            track_name=spec_data.get("track_name"),
        )

        if "verticals" in spec and isinstance(spec.get("verticals"), list):
            for vertical_name in spec.get("verticals"):
                vertical = Vertical.query.filter_by(name=vertical_name).first()
                if vertical:
                    questionnaire.verticals.append(vertical)
                else:
                    flash(f"No vertical exists with name: '{vertical_name}'", "error")

        if "roles" in spec and isinstance(spec.get("roles"), list):
            for role_name in spec.get("roles"):
                role = Role.query.filter_by(name=role_name).first()
                if role:
                    questionnaire.roles.append(role)
                else:
                    flash(f"No role exists with name: '{role_name}'", "error")

        db.session.add(questionnaire)
        db.session.flush()

        # If this questionnaire fixture is coming from the questionnaire export script,
        # we may need to set question_set.prerequisite_answer_id's after everything is
        # created because we do not know the answer id's until everything else is done.
        # We will create a mapping object here and pass it down, if it is populated we
        # will make the updates.
        prerequisite_answer_id_mapping = {}
        question_set_with_prerequisite_answer_id = []

        if "question_sets" in spec and isinstance(spec.get("question_sets"), list):
            for qs_spec in spec.get("question_sets"):
                question_set = QuestionSetMaker().create_object_and_flush(
                    qs_spec, questionnaire.id, prerequisite_answer_id_mapping
                )
                if qs_spec.get("prerequisite_answer_id") is not None:
                    question_set_with_prerequisite_answer_id.append(
                        (question_set, qs_spec.get("prerequisite_answer_id"))
                    )

        if len(prerequisite_answer_id_mapping) and len(
            question_set_with_prerequisite_answer_id
        ):
            for (
                question_set,
                prerequisite_answer_id,
            ) in question_set_with_prerequisite_answer_id:
                prerequisite_answer_id = prerequisite_answer_id_mapping.get(
                    prerequisite_answer_id
                )
                if prerequisite_answer_id is not None:
                    question_set.prerequisite_answer_id = prerequisite_answer_id
                    db.session.add(question_set)

        return questionnaire


class QuestionSetMaker(_MakerBase):
    spec_class = QuestionSetSchema()  # type: ignore[assignment] # Incompatible types in assignment (expression has type "QuestionSetSchema", base class "_MakerBase" defined the type as "None")

    def create_object(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self, spec, questionnaire_id=None, prerequisite_answer_id_mapping=None
    ):
        spec_data = self.spec_class.load(spec).data  # type: ignore[has-type] # Cannot determine type of "spec_class"
        question_set = QuestionSet(
            sort_order=spec_data.get("sort_order"),
            oid=spec_data.get("oid"),
            questionnaire_id=spec_data.get("questionnaire_id", questionnaire_id),
            soft_deleted_at=spec_data.get("soft_deleted_at"),
        )

        db.session.add(question_set)
        db.session.flush()

        if "questions" in spec and isinstance(spec.get("questions"), list):
            for q_spec in spec.get("questions"):
                QuestionMaker().create_object_and_flush(
                    q_spec, question_set.id, prerequisite_answer_id_mapping
                )

        return question_set


class QuestionMaker(_MakerBase):
    spec_class = QuestionSchema()  # type: ignore[assignment] # Incompatible types in assignment (expression has type "QuestionSchema", base class "_MakerBase" defined the type as "None")

    def create_object(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self, spec, question_set_id=None, prerequisite_answer_id_mapping=None
    ):
        spec_data = self.spec_class.load(spec).data  # type: ignore[has-type] # Cannot determine type of "spec_class"

        question = Question(
            question_set_id=spec_data.get("question_set_id", question_set_id),
            sort_order=spec_data.get("sort_order"),
            label=spec_data.get("label"),
            type=spec_data.get("question_type"),
            required=spec_data.get("required"),
            oid=spec_data.get("oid"),
            soft_deleted_at=spec_data.get("soft_deleted_at"),
        )

        db.session.add(question)
        db.session.flush()

        if "answers" in spec and isinstance(spec.get("answers"), list):
            for answer_spec in spec.get("answers"):
                AnswerMaker().create_object_and_flush(
                    answer_spec, question.id, prerequisite_answer_id_mapping
                )

        return question


class AnswerMaker(_MakerBase):
    spec_class = AnswerSchema()  # type: ignore[assignment] # Incompatible types in assignment (expression has type "AnswerSchema", base class "_MakerBase" defined the type as "None")

    def create_object(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self, spec, question_id=None, prerequisite_answer_id_mapping=None
    ):
        spec_data = self.spec_class.load(spec).data  # type: ignore[has-type] # Cannot determine type of "spec_class"
        answer = Answer(
            question_id=spec_data.get("question_id", question_id),
            sort_order=spec_data.get("sort_order"),
            text=spec_data.get("text"),
            oid=spec_data.get("oid"),
            soft_deleted_at=spec_data.get("soft_deleted_at"),
        )

        db.session.add(answer)
        db.session.flush()
        if spec.get("id") is not None and prerequisite_answer_id_mapping is not None:
            prerequisite_answer_id_mapping[spec.get("id")] = answer.id

        return answer


class RecordedAnswerSetMaker(_MakerBase):
    def _get_questionnaire(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        questionnaire_type = spec.get(
            "questionnaire_name", COACHING_NOTES_COACHING_PROVIDERS_OID
        )
        return Questionnaire.query.filter(Questionnaire.oid == questionnaire_type).one()

    def create_object(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = User.query.filter_by(email=spec.get("user")).first()
        if not user:
            flash(f"User Not Found. {spec.get('user')}", "error")
            return

        questionnaire = self._get_questionnaire(spec)
        if not questionnaire:
            flash("Questionnaire Not Found.", "error")
            return

        check_appointment_by_ids([spec.get("appointment_id", None)], True)

        answer_set = RecordedAnswerSet(
            source_user_id=user.id,
            submitted_at=datetime.datetime.now(),
            questionnaire_id=questionnaire.id,
            draft=spec.get("draft", False),
            appointment_id=spec.get("appointment_id", None),
        )
        db.session.add(answer_set)
        db.session.flush()
        self._fill_questionnaire_data(answer_set, user, questionnaire)
        return answer_set

    def _fill_questionnaire_data(self, answer_set, user, questionnaire):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        questions = chain.from_iterable(
            [question_set.questions for question_set in questionnaire.question_sets]
        )

        check_appointment_by_ids([answer_set.appointment_id], True)
        for question in questions:
            expected_json_keys = question.expected_json_option_keys_for_type()
            if question.type == QuestionTypes.TEXT:
                new_recorded_answer = RecordedAnswer(
                    appointment_id=answer_set.appointment_id,
                    question_id=question.id,
                    user_id=user.id,
                    recorded_answer_set_id=answer_set.id,
                    text=f"Generic free text response for question {question.id}",
                )
                db.session.add(new_recorded_answer)
            elif question.answers:
                answer = random.choice(question.answers)
                new_recorded_answer = RecordedAnswer(
                    appointment_id=answer_set.appointment_id,
                    question_id=question.id,
                    user_id=user.id,
                    recorded_answer_set_id=answer_set.id,
                    answer_id=answer.id,
                )
                db.session.add(new_recorded_answer)
            elif expected_json_keys:
                for expected_key in expected_json_keys:
                    answer_payload = random.choice(question.json[expected_key])
                    new_recorded_answer = RecordedAnswer(
                        appointment_id=answer_set.appointment_id,
                        question_id=question.id,
                        user_id=user.id,
                        recorded_answer_set_id=answer_set.id,
                        payload=answer_payload,
                    )
                    db.session.add(new_recorded_answer)
            else:
                flash(
                    f"Unexpected question type {question.id} for Recorded Answer Set associated with Questionnaire {questionnaire.oid}.",
                    "error",
                )
                return
            db.session.flush()
            return
