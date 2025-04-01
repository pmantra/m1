from __future__ import annotations

import ddtrace
from marshmallow import fields as v3_fields
from marshmallow_v1 import Schema, fields
from maven.feature_flags import bool_variation
from sqlalchemy import and_

from models.questionnaires import (
    PROVIDER_ADDENDA_QUESTIONNAIRE_OID,
    ProviderAddendum,
    Questionnaire,
    RecordedAnswer,
    RecordedAnswerSet,
)
from storage.connection import db
from utils.launchdarkly import user_context
from views.questionnaires import (
    ProviderAddendumSchema,
    ProviderAddendumSchemaV3,
    QuestionnaireSchema,
    QuestionnaireSchemaV3,
    QuestionSetSchema,
    QuestionSetSchemaV3,
    RecordedAnswerSchema,
    RecordedAnswerSchemaV3,
    RecordedAnswerSetSchema,
    RecordedAnswerSetSchemaV3,
)
from views.schemas.common import MavenDateTime, MavenSchema
from views.schemas.common_v3 import BooleanWithDefault
from views.schemas.common_v3 import MavenDateTime as MavenDateTimeV3
from views.schemas.common_v3 import (
    MavenSchemaV3,
    NestedWithDefaultV3,
    StringWithDefaultV3,
)


class SessionMetaInfoSchema(Schema):
    draft = fields.Boolean(default=None)
    notes = fields.String()
    created_at = MavenDateTime()
    modified_at = MavenDateTime()


class SessionMetaInfoSchemaV3(MavenSchemaV3):
    draft = BooleanWithDefault(default=None)
    notes = StringWithDefaultV3(default="")
    created_at = MavenDateTimeV3()
    modified_at = MavenDateTimeV3()


class AppointmentNotesSchema(MavenSchema):
    """
    User is required to be passed in through the context and if this
    schema is nested, needs to be inherited from the parent
    """

    post_session = fields.Nested(SessionMetaInfoSchema)
    structured_internal_note = fields.Method("get_structured_internal_note")
    provider_addenda = fields.Method("get_provider_addenda")

    def get_structured_internal_note(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with ddtrace.tracer.trace(name=f"{__name__}.get_structured_internal_note"):
            question_sets_json, recorded_answers_json = [], []
            questionnaire_json, recorded_answer_set_json = None, None

            (
                recorded_answer_set,
                questionnaire,
            ) = self._get_recorded_answer_set_questionnaire(
                appointment_id=obj.id, user_id=obj.practitioner_id
            )

            if recorded_answer_set:
                recorded_answer_set_json = (
                    RecordedAnswerSetSchema().dump(recorded_answer_set).data
                )

                recorded_answers_json = (
                    RecordedAnswerSchema(many=True)
                    .dump(recorded_answer_set.recorded_answers)
                    .data
                )
            else:
                # Recorded answers that were created before the concept of recorded answer sets
                # being linked to appointments will be directly attached to the appointment themselves
                user = context.get("user")
                recorded_answers = self._get_legacy_recorded_answers(
                    appointment_id=obj.id, user_id=user.id
                )

                recorded_answers_json = (
                    RecordedAnswerSchema(many=True).dump(recorded_answers).data
                )

            if questionnaire is None:
                questionnaire = Questionnaire.get_structured_internal_note_for_pract(
                    obj.practitioner
                )

            if questionnaire:
                questionnaire_json = QuestionnaireSchema().dump(questionnaire).data
                question_sets_json = (
                    QuestionSetSchema(many=True).dump(questionnaire.question_sets).data
                )

            return {
                # TODO: get rid of this once clients are all using questionnaire instead
                "question_sets": question_sets_json,
                # TODO: get rid of this once clients are all using recorded_answer_set instead
                "recorded_answers": recorded_answers_json,
                "questionnaire": questionnaire_json,
                "recorded_answer_set": recorded_answer_set_json,
            }

    @staticmethod
    @ddtrace.tracer.wrap()
    def _get_recorded_answer_set_questionnaire(
        appointment_id: int, user_id: int
    ) -> tuple[RecordedAnswerSet, Questionnaire] | tuple[None, None]:
        result = (
            db.session.query(RecordedAnswerSet, Questionnaire)
            .filter(
                and_(
                    RecordedAnswerSet.appointment_id == appointment_id,
                    RecordedAnswerSet.source_user_id == user_id,
                )
            )
            .outerjoin(
                Questionnaire, RecordedAnswerSet.questionnaire_id == Questionnaire.id
            )
            .order_by(RecordedAnswerSet.submitted_at.desc())
            .first()
        )
        if result is None:
            return None, None
        return result

    @staticmethod
    @ddtrace.tracer.wrap()
    def _get_legacy_recorded_answers(
        appointment_id: int, user_id: int
    ) -> list[RecordedAnswer]:
        recorded_answers = (
            db.session.query(RecordedAnswer)
            .filter(
                and_(
                    RecordedAnswer.appointment_id == appointment_id,
                    RecordedAnswer.user_id == user_id,
                )
            )
            .all()
        )
        return recorded_answers

    def get_provider_addenda(self, obj, context) -> dict:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        with ddtrace.tracer.trace(name=f"{__name__}.get_provider_addenda"):

            user = context.get("user")
            provider_addenda_enabled = bool_variation(
                "release-mpractice-practitioner-addenda",
                user_context(user),
                default=False,
            )
            if not provider_addenda_enabled:
                return {}

            questionnaire = (
                db.session.query(Questionnaire)
                .filter(Questionnaire.oid == PROVIDER_ADDENDA_QUESTIONNAIRE_OID)
                .one_or_none()
            )
            if questionnaire is None:
                return {}
            provider_addenda = (
                db.session.query(ProviderAddendum)
                .filter(
                    (ProviderAddendum.appointment_id == obj.id)
                    & (ProviderAddendum.user_id == obj.practitioner_id)
                    & (ProviderAddendum.questionnaire_id == questionnaire.id)
                )
                .order_by(ProviderAddendum.submitted_at.asc())
            ).all()
            questionnaire_json = QuestionnaireSchema().dump(questionnaire).data
            provider_addenda_json = (
                ProviderAddendumSchema(many=True).dump(provider_addenda).data
            )
            return {
                "questionnaire": questionnaire_json,
                "provider_addenda": provider_addenda_json,
            }


class AppointmentNotesSchemaV3(MavenSchemaV3):
    """
    User is required to be passed in through the context and if this
    schema is nested, needs to be inherited from the parent
    """

    post_session = NestedWithDefaultV3(SessionMetaInfoSchemaV3)
    structured_internal_note = v3_fields.Method(
        "get_structured_internal_note", deserialize="no_op_deserialize"
    )
    provider_addenda = v3_fields.Method(
        "get_provider_addenda", deserialize="no_op_deserialize"
    )

    def no_op_deserialize(self, value):  # type: ignore[no-untyped-def]
        return value

    def get_structured_internal_note(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with ddtrace.tracer.trace(name=f"{__name__}.get_structured_internal_note"):
            question_sets_json, recorded_answers_json = [], []
            questionnaire_json, recorded_answer_set_json = None, None

            if hasattr(obj, "id") and hasattr(obj, "practitioner_id"):
                (
                    recorded_answer_set,
                    questionnaire,
                ) = self._get_recorded_answer_set_questionnaire(
                    appointment_id=obj.id, user_id=obj.practitioner_id
                )
            else:
                return None

            if recorded_answer_set:
                recorded_answer_set_json = RecordedAnswerSetSchemaV3().dump(
                    recorded_answer_set
                )

                recorded_answers_json = RecordedAnswerSchemaV3(many=True).dump(
                    recorded_answer_set.recorded_answers
                )
            else:
                # Recorded answers that were created before the concept of recorded answer sets
                # being linked to appointments will be directly attached to the appointment themselves
                user = self.context.get("user")
                if hasattr(obj, "id") and hasattr(user, "id"):
                    recorded_answers = self._get_legacy_recorded_answers(
                        appointment_id=obj.id, user_id=user.id  # type: ignore[union-attr]
                    )

                    recorded_answers_json = RecordedAnswerSchemaV3(many=True).dump(
                        recorded_answers
                    )

            if questionnaire is None:
                if hasattr(obj, "practitioner"):
                    questionnaire = (
                        Questionnaire.get_structured_internal_note_for_pract(
                            obj.practitioner
                        )
                    )

            if questionnaire:
                questionnaire_json = QuestionnaireSchemaV3().dump(questionnaire)
                question_sets_json = QuestionSetSchemaV3(many=True).dump(
                    questionnaire.question_sets
                )

            return {
                # TODO: get rid of this once clients are all using questionnaire instead
                "question_sets": question_sets_json,
                # TODO: get rid of this once clients are all using recorded_answer_set instead
                "recorded_answers": recorded_answers_json,
                "questionnaire": questionnaire_json,
                "recorded_answer_set": recorded_answer_set_json,
            }

    @staticmethod
    @ddtrace.tracer.wrap()
    def _get_recorded_answer_set_questionnaire(
        appointment_id: int, user_id: int
    ) -> tuple[RecordedAnswerSet, Questionnaire] | tuple[None, None]:
        result = (
            db.session.query(RecordedAnswerSet, Questionnaire)
            .filter(
                and_(
                    RecordedAnswerSet.appointment_id == appointment_id,
                    RecordedAnswerSet.source_user_id == user_id,
                )
            )
            .outerjoin(
                Questionnaire, RecordedAnswerSet.questionnaire_id == Questionnaire.id
            )
            .order_by(RecordedAnswerSet.submitted_at.desc())
            .first()
        )
        if result is None:
            return None, None
        return result

    @staticmethod
    @ddtrace.tracer.wrap()
    def _get_legacy_recorded_answers(
        appointment_id: int, user_id: int
    ) -> list[RecordedAnswer]:
        recorded_answers = (
            db.session.query(RecordedAnswer)
            .filter(
                and_(
                    RecordedAnswer.appointment_id == appointment_id,
                    RecordedAnswer.user_id == user_id,
                )
            )
            .all()
        )
        return recorded_answers

    def get_provider_addenda(self, obj) -> dict:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        with ddtrace.tracer.trace(name=f"{__name__}.get_provider_addenda"):

            user = self.context.get("user")
            if user:
                provider_addenda_enabled = bool_variation(
                    "release-mpractice-practitioner-addenda",
                    user_context(user),
                    default=False,
                )
                if not provider_addenda_enabled:
                    return {}
            else:
                return None  # type: ignore[return-value]

            questionnaire = (
                db.session.query(Questionnaire)
                .filter(Questionnaire.oid == PROVIDER_ADDENDA_QUESTIONNAIRE_OID)
                .one_or_none()
            )
            if questionnaire is None:
                return None  # type: ignore[return-value]
            else:
                provider_addenda = (
                    db.session.query(ProviderAddendum)
                    .filter(
                        (ProviderAddendum.appointment_id == obj.id)
                        & (ProviderAddendum.user_id == obj.practitioner_id)
                        & (ProviderAddendum.questionnaire_id == questionnaire.id)  # type: ignore[attr-defined]
                    )
                    .order_by(ProviderAddendum.submitted_at.asc())
                ).all()
                questionnaire_json = QuestionnaireSchemaV3().dump(questionnaire)
                provider_addenda_json = ProviderAddendumSchemaV3(many=True).dump(
                    provider_addenda
                )
            return {
                "questionnaire": questionnaire_json,
                "provider_addenda": provider_addenda_json,
            }
