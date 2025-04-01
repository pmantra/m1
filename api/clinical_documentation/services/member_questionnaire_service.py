from __future__ import annotations

from typing import Optional

from maven import feature_flags
from sqlalchemy.orm.scoping import ScopedSession

from clinical_documentation.models.questionnaire import QuestionnaireStruct
from clinical_documentation.models.translated_questionnaire import (
    TranslatedAnswerStruct,
    TranslatedQuestionnaireStruct,
    TranslatedQuestionSetStruct,
    TranslatedQuestionStruct,
)
from clinical_documentation.repository.member_questionnaires import (
    MemberQuestionnaireRepository,
)
from l10n.db_strings.slug_backfill import BackfillL10nSlugs
from l10n.db_strings.translate import TranslateDBFields
from storage.connection import db
from utils.launchdarkly import user_context


class MemberQuestionnairesService:
    def __init__(
        self,
        session: Optional[ScopedSession] = None,
    ):
        self.session = session or db.session
        self.repo = MemberQuestionnaireRepository(session=self.session)

    def get_questionnaires(self) -> list[TranslatedQuestionnaireStruct]:
        return self._translate_questionnaire(self.repo.get_questionnaires())

    def _translate_questionnaire(
        self, questionnaires: list[QuestionnaireStruct]
    ) -> list[TranslatedQuestionnaireStruct]:
        # This method currently doesn't do any logical transformations, it's purely to turn one type into another
        # identical type.
        return [
            TranslatedQuestionnaireStruct(
                id_=qr.id_,
                oid=qr.oid,
                sort_order=qr.sort_order,
                title_text=qr.title_text,
                description_text=qr.description_text,
                intro_appointment_only=qr.intro_appointment_only,
                track_name=qr.track_name,
                question_sets=[
                    TranslatedQuestionSetStruct(
                        id_=qs.id_,
                        questionnaire_id=qs.questionnaire_id,
                        sort_order=qs.sort_order,
                        oid=qs.oid,
                        questions=[
                            TranslatedQuestionStruct(
                                id_=q.id_,
                                oid=q.oid,
                                question_set_id=q.question_set_id,
                                sort_order=q.sort_order,
                                label=q.label,
                                type_=q.type_,
                                required=q.required,
                                answers=[
                                    TranslatedAnswerStruct(
                                        id_=a.id_,
                                        oid=a.oid,
                                        text=a.text,
                                        sort_order=a.sort_order,
                                    )
                                    for a in q.answers
                                ],
                            )
                            for q in qs.questions
                        ],
                    )
                    for qs in qr.question_sets
                ],
                trigger_answer_ids=qr.trigger_answer_ids,
            )
            for qr in questionnaires
        ]

    def get_vertical_specific_member_rating_questionnaire_oids_by_product_id(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self, product_ids, user
    ) -> dict[int, list[str]]:
        if not feature_flags.bool_variation(
            "experiment-post-appointment-questionnaire-from-vertical",
            user_context(user),
            default=False,
        ):
            return {}

        return self.repo.get_vertical_specific_member_rating_questionnaire_oids_by_product_id(
            product_ids
        )

    @staticmethod
    def localize_questionnaires(
        questionnaires: list[TranslatedQuestionnaireStruct],
    ) -> None:
        """
        NOTE: This method must be called with a locale set (from flask or "flask_babel.force_locale")
        """
        for questionnaire in questionnaires:
            questionnaire.title_text = TranslateDBFields().get_translated_questionnaire(
                questionnaire.oid, "title_text", questionnaire.title_text
            )
            questionnaire.description_text = (
                TranslateDBFields().get_translated_questionnaire(
                    questionnaire.oid,
                    "description_text",
                    questionnaire.description_text,
                )
            )
            for question_set in questionnaire.question_sets:
                for question in question_set.questions:
                    question_slug = BackfillL10nSlugs.generate_question_slug(
                        questionnaire.oid,
                        question_set.oid,
                        question.oid,
                    )
                    question.label = TranslateDBFields().get_translated_question(
                        question_slug, "label", question.label
                    )

                    for answer in question.answers:
                        answer_slug = BackfillL10nSlugs.generate_answer_slug(
                            questionnaire.oid,
                            question_set.oid,
                            question.oid,
                            answer.oid,
                        )
                        answer.text = TranslateDBFields().get_translated_answer(
                            answer_slug, "text", answer.text
                        )
