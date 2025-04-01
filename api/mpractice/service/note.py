from __future__ import annotations

import json
from typing import List

import ddtrace
from sqlalchemy.orm.scoping import ScopedSession

from appointments.services.common import obfuscate_appointment_id
from authz.models.roles import ROLES
from models.questionnaires import (
    COACHING_NOTES_COACHING_PROVIDERS_OID,
    PROVIDER_ADDENDA_QUESTIONNAIRE_OID,
)
from mpractice.models.note import (
    MPracticeProviderAddendum,
    MPracticeQuestionnaire,
    MPracticeRecordedAnswer,
    MPracticeRecordedAnswerSet,
)
from mpractice.models.translated_note import (
    MPracticeProviderAddendaAndQuestionnaire,
    StructuredInternalNote,
    TranslatedMPracticeAnswer,
    TranslatedMPracticeProviderAddendum,
    TranslatedMPracticeQuestion,
    TranslatedMPracticeQuestionnaire,
    TranslatedMPracticeQuestionSet,
    TranslatedMPracticeRecordedAnswer,
    TranslatedMPracticeRecordedAnswerSet,
)
from mpractice.repository.mpractice_questionnaire import (
    MPracticeQuestionnaireRepository,
)
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class MPracticeNoteService:
    def __init__(
        self,
        session: ScopedSession | None = None,
        questionnaire_repo: MPracticeQuestionnaireRepository | None = None,
        include_soft_deleted_question_sets: bool | None = False,
    ):
        self.session = session or db.session
        self.questionnaire_repo = (
            questionnaire_repo
            or MPracticeQuestionnaireRepository(
                session=self.session,
                include_soft_deleted_question_sets=include_soft_deleted_question_sets,
            )
        )

    @ddtrace.tracer.wrap()
    def get_structured_internal_note(
        self, appointment_id: int, practitioner_id: int
    ) -> StructuredInternalNote | None:
        # load data from DB
        questionnaire = self.get_questionnaire(
            appointment_id=appointment_id, practitioner_id=practitioner_id
        )
        if not questionnaire:
            log.warn(f"No questionnaire found for appointment {appointment_id}")
            return None

        trigger_answer_ids = self.questionnaire_repo.get_trigger_answer_ids(
            questionnaire_id=questionnaire.id
        )
        recorded_answer_set = self.questionnaire_repo.get_recorded_answer_set(
            appointment_id=appointment_id, practitioner_id=practitioner_id
        )
        if recorded_answer_set:
            recorded_answers = self.get_recorded_answers(
                recorded_answer_set_id=recorded_answer_set.id,
                appointment_id=appointment_id,
                practitioner_id=practitioner_id,
            )
        else:
            recorded_answers = []

        # translate data models
        translated_question_sets = self.get_and_translate_question_sets(
            questionnaire_id=questionnaire.id
        )
        translated_questionnaire = self.translate_questionnaire(
            questionnaire=questionnaire,
            translated_question_sets=translated_question_sets,
            trigger_answer_ids=trigger_answer_ids,
        )

        if recorded_answer_set:
            appt_id_from_recorded_answer_set = recorded_answer_set.appointment_id
            translated_recorded_answers = self.translate_recorded_answers(
                recorded_answers=recorded_answers,
                appointment_id_from_recorded_answer_set=appt_id_from_recorded_answer_set,
            )
            translated_recorded_answer_set = self.translate_recorded_answer_set(
                recorded_answer_set=recorded_answer_set,
                translated_recorded_answers=translated_recorded_answers,
            )
        else:
            translated_recorded_answers = []
            translated_recorded_answer_set = None

        return StructuredInternalNote(
            questionnaire=translated_questionnaire,
            question_sets=translated_question_sets,
            recorded_answer_set=translated_recorded_answer_set,
            recorded_answers=translated_recorded_answers,
        )

    @ddtrace.tracer.wrap()
    def get_provider_addenda_and_questionnaire(
        self, appointment_id: int, practitioner_id: int
    ) -> MPracticeProviderAddendaAndQuestionnaire | None:
        questionnaire = self.questionnaire_repo.get_questionnaire_by_oid(
            PROVIDER_ADDENDA_QUESTIONNAIRE_OID
        )
        if not questionnaire:
            return None

        trigger_answer_ids = self.questionnaire_repo.get_trigger_answer_ids(
            questionnaire_id=questionnaire.id
        )
        translated_question_sets = self.get_and_translate_question_sets(
            questionnaire_id=questionnaire.id
        )
        translated_questionnaire = self.translate_questionnaire(
            questionnaire=questionnaire,
            translated_question_sets=translated_question_sets,
            trigger_answer_ids=trigger_answer_ids,
        )

        provider_addenda = self.questionnaire_repo.get_provider_addenda(
            appointment_id=appointment_id,
            practitioner_id=practitioner_id,
            questionnaire_id=questionnaire.id,
        )
        translated_provider_addendum = self.translate_provider_addenda(
            provider_addenda=provider_addenda
        )

        return MPracticeProviderAddendaAndQuestionnaire(
            questionnaire=translated_questionnaire,
            provider_addenda=translated_provider_addendum,
        )

    @ddtrace.tracer.wrap()
    def get_questionnaire(
        self, appointment_id: int, practitioner_id: int
    ) -> MPracticeQuestionnaire | None:
        questionnaire = (
            self.questionnaire_repo.get_questionnaire_by_recorded_answer_set(
                appointment_id=appointment_id, practitioner_id=practitioner_id
            )
        )
        if questionnaire:
            return questionnaire

        questionnaires = self.questionnaire_repo.get_questionnaires_by_practitioner(
            practitioner_id=practitioner_id
        )
        if questionnaires:
            questionnaire_id_to_roles = (
                self.questionnaire_repo.get_roles_for_questionnaires(
                    questionnaire_ids=[
                        questionnaire.id for questionnaire in questionnaires
                    ]
                )
            )
            for questionnaire in questionnaires:
                if (questionnaire.id not in questionnaire_id_to_roles) or (
                    ROLES.member not in questionnaire_id_to_roles.get(questionnaire.id)
                ):
                    return questionnaire

        questionnaire = self.questionnaire_repo.get_questionnaire_by_oid(
            oid=COACHING_NOTES_COACHING_PROVIDERS_OID
        )

        return questionnaire

    def get_recorded_answers(
        self, recorded_answer_set_id: int, appointment_id: int, practitioner_id: int
    ) -> List[MPracticeRecordedAnswer]:
        recorded_answers = (
            self.questionnaire_repo.get_recorded_answers_by_recorded_answer_set_id(
                recorded_answer_set_id
            )
        )
        if recorded_answers:
            return recorded_answers

        return self.questionnaire_repo.get_legacy_recorded_answers(
            appointment_id=appointment_id, practitioner_id=practitioner_id
        )

    def get_and_translate_question_sets(
        self, questionnaire_id: int
    ) -> List[TranslatedMPracticeQuestionSet]:
        """
        The structs are nested as follows:
            - questionnaire.question_sets
                - question_set.questions
                    - question.answers
        """
        result = []

        # question sets
        question_sets = self.questionnaire_repo.get_question_sets_by_questionnaire_id(
            questionnaire_id
        )
        question_set_ids = [question_set.id for question_set in question_sets]

        # questions grouped by question set
        questions = self.questionnaire_repo.get_questions_by_question_set_ids(
            question_set_ids
        )
        question_set_id_to_questions = {}
        question_ids = []
        for question in questions:
            question_set_id = question.question_set_id
            questions_by_question_set_id = question_set_id_to_questions.get(
                question_set_id, []
            )
            questions_by_question_set_id.append(question)
            question_set_id_to_questions[question_set_id] = questions_by_question_set_id
            question_ids.append(question.id)

        # answers grouped by question
        answers = self.questionnaire_repo.get_answers_by_question_ids(question_ids)
        question_id_to_answers = {}
        for answer in answers:
            question_id = answer.question_id
            answers_by_question_id = question_id_to_answers.get(question_id, [])
            answers_by_question_id.append(answer)
            question_id_to_answers[question_id] = answers_by_question_id

        for question_set in question_sets:
            translated_question_set = TranslatedMPracticeQuestionSet(
                **vars(question_set)
            )
            translated_question_set.questions = self.translate_questions(
                question_set_id=question_set.id,
                question_set_id_to_questions=question_set_id_to_questions,
                question_id_to_answers=question_id_to_answers,
            )
            result.append(translated_question_set)
        return result

    def translate_questions(
        self,
        question_set_id: int,
        question_set_id_to_questions: dict,
        question_id_to_answers: dict,
    ) -> List[TranslatedMPracticeQuestion]:
        result = []
        questions = question_set_id_to_questions.get(question_set_id, [])
        for question in questions:
            translated_question = TranslatedMPracticeQuestion(**vars(question))
            translated_question.answers = self.translate_answers(
                question_id=question.id, question_id_to_answers=question_id_to_answers
            )
            result.append(translated_question)
        return result

    def translate_answers(
        self, question_id: int, question_id_to_answers: dict
    ) -> List[TranslatedMPracticeAnswer]:
        answers = question_id_to_answers.get(question_id, [])
        return [TranslatedMPracticeAnswer(**vars(answer)) for answer in answers]

    @staticmethod
    def translate_questionnaire(
        questionnaire: MPracticeQuestionnaire,
        translated_question_sets: List[TranslatedMPracticeQuestionSet],
        trigger_answer_ids: List[int],
    ) -> TranslatedMPracticeQuestionnaire:
        translated_questionnaire = TranslatedMPracticeQuestionnaire(
            **vars(questionnaire)
        )
        translated_questionnaire.question_sets = translated_question_sets
        translated_questionnaire.trigger_answer_ids = trigger_answer_ids
        return translated_questionnaire

    def translate_recorded_answers(
        self,
        recorded_answers: List[MPracticeRecordedAnswer],
        appointment_id_from_recorded_answer_set: int | None,
    ) -> List[TranslatedMPracticeRecordedAnswer]:
        result = []
        for recorded_answer in recorded_answers:
            translated_recorded_answer = TranslatedMPracticeRecordedAnswer(
                **vars(recorded_answer)
            )
            if recorded_answer.question_type_in_enum:
                translated_recorded_answer.question_type = (
                    recorded_answer.question_type_in_enum.name
                )
            non_obfuscated_appt_id = (
                recorded_answer.appointment_id
                if recorded_answer.appointment_id
                else appointment_id_from_recorded_answer_set
            )
            if non_obfuscated_appt_id:
                translated_recorded_answer.appointment_id = obfuscate_appointment_id(
                    non_obfuscated_appt_id
                )
            translated_recorded_answer.text = self.get_text(
                text=recorded_answer.text, payload_string=recorded_answer.payload_string
            )
            translated_recorded_answer.payload = self.get_payload(
                text=recorded_answer.text, payload_string=recorded_answer.payload_string
            )
            result.append(translated_recorded_answer)
        return result

    @staticmethod
    def translate_recorded_answer_set(
        recorded_answer_set: MPracticeRecordedAnswerSet,
        translated_recorded_answers: List[TranslatedMPracticeRecordedAnswer],
    ) -> TranslatedMPracticeRecordedAnswerSet:
        translated_recorded_answer_set = TranslatedMPracticeRecordedAnswerSet(
            **vars(recorded_answer_set)
        )
        non_obfuscated_appt_id = recorded_answer_set.appointment_id
        if non_obfuscated_appt_id:
            translated_recorded_answer_set.appointment_id = obfuscate_appointment_id(
                non_obfuscated_appt_id
            )
        translated_recorded_answer_set.recorded_answers = translated_recorded_answers
        return translated_recorded_answer_set

    def translate_provider_addenda(
        self, provider_addenda: List[MPracticeProviderAddendum]
    ) -> List[TranslatedMPracticeProviderAddendum]:
        provider_addendum_ids = [
            provider_addendum.id for provider_addendum in provider_addenda
        ]
        provider_addenda_answers = self.questionnaire_repo.get_provider_addenda_answers(
            provider_addendum_ids
        )
        provider_addendum_id_to_answers = {}
        for answer in provider_addenda_answers:
            provider_addendum_id = answer.addendum_id
            answers_by_provider_addendum = provider_addendum_id_to_answers.get(
                provider_addendum_id, []
            )
            answers_by_provider_addendum.append(answer)
            provider_addendum_id_to_answers[
                provider_addendum_id
            ] = answers_by_provider_addendum

        result = []
        for provider_addendum in provider_addenda:
            translated_provider_addendum = TranslatedMPracticeProviderAddendum(
                **vars(provider_addendum)
            )
            provider_addenda_answers = provider_addendum_id_to_answers.get(
                provider_addendum.id, []
            )
            translated_provider_addendum.provider_addendum_answers = (
                provider_addenda_answers
            )
            translated_provider_addendum.appointment_id = obfuscate_appointment_id(
                provider_addendum.appointment_id
            )
            result.append(translated_provider_addendum)
        return result

    def get_text(self, text: str | None, payload_string: str | None) -> str | None:
        if text:
            return text
        # Translate payload back to text for clients that aren't using payload field yet
        elif payload_string:
            payload_json = self.get_payload_dict(payload_string=payload_string)
            if payload_json:
                return payload_json.get("text")
        return None

    def get_payload(self, payload_string: str | None, text: str | None) -> dict | None:
        if payload_string:
            return self.get_payload_dict(payload_string)
        # Translate text to payload for clients that aren't using text field anymore
        elif text:
            return {"text": text}
        return None

    @staticmethod
    def get_payload_dict(payload_string: str | None) -> dict | None:
        if not payload_string:
            return None
        try:
            return json.loads(payload_string)
        except ValueError as e:
            log.error("Failed to parse payload into json", exception=e)
            return None
