from __future__ import annotations

from typing import List, Mapping
from unittest.mock import MagicMock

import pytest

from authz.models.roles import ROLES
from models.questionnaires import COACHING_NOTES_COACHING_PROVIDERS_OID
from mpractice.models.note import (
    MPracticeAnswer,
    MPracticeProviderAddendum,
    MPracticeProviderAddendumAnswer,
    MPracticeQuestion,
    MPracticeQuestionnaire,
    MPracticeQuestionSet,
    MPracticeRecordedAnswer,
    MPracticeRecordedAnswerSet,
)
from mpractice.models.translated_note import (
    MPracticeProviderAddendaAndQuestionnaire,
    TranslatedMPracticeAnswer,
    TranslatedMPracticeProviderAddendum,
    TranslatedMPracticeQuestion,
    TranslatedMPracticeQuestionnaire,
    TranslatedMPracticeQuestionSet,
    TranslatedMPracticeRecordedAnswer,
)
from mpractice.service.note import MPracticeNoteService


class TestMPracticeNoteService:
    def test_get_structured_internal_note_complete_data(
        self,
        note_service: MPracticeNoteService,
        mock_mpractice_questionnaire_repo: MagicMock,
        questionnaire: MPracticeQuestionnaire,
        trigger_answer_ids: List[int],
        recorded_answer_set: MPracticeRecordedAnswerSet,
        recorded_answer: MPracticeRecordedAnswer,
        question_set: MPracticeQuestionSet,
        question: MPracticeQuestion,
        answer: MPracticeAnswer,
        translated_questionnaire: TranslatedMPracticeQuestionnaire,
        translated_question_set: TranslatedMPracticeQuestionSet,
        translated_recorded_answer_set: TranslatedMPracticeRecordedAnswer,
        translated_recorded_answer: TranslatedMPracticeAnswer,
    ):
        mock_mpractice_questionnaire_repo.get_questionnaire_by_recorded_answer_set.return_value = (
            questionnaire
        )
        mock_mpractice_questionnaire_repo.get_trigger_answer_ids.return_value = (
            trigger_answer_ids
        )
        mock_mpractice_questionnaire_repo.get_recorded_answer_set.return_value = (
            recorded_answer_set
        )
        mock_mpractice_questionnaire_repo.get_recorded_answers_by_recorded_answer_set_id.return_value = [
            recorded_answer
        ]
        mock_mpractice_questionnaire_repo.get_question_sets_by_questionnaire_id.return_value = [
            question_set
        ]
        mock_mpractice_questionnaire_repo.get_questions_by_question_set_ids.return_value = [
            question
        ]
        mock_mpractice_questionnaire_repo.get_answers_by_question_ids.return_value = [
            answer
        ]

        result = note_service.get_structured_internal_note(
            appointment_id=1, practitioner_id=1
        )
        assert result.questionnaire == translated_questionnaire
        assert result.question_sets == [translated_question_set]
        assert result.recorded_answer_set == translated_recorded_answer_set
        assert result.recorded_answers == [translated_recorded_answer]

    def test_get_structured_internal_note_without_questionnaire(
        self,
        note_service: MPracticeNoteService,
        mock_mpractice_questionnaire_repo: MagicMock,
    ):
        mock_mpractice_questionnaire_repo.get_questionnaire_by_recorded_answer_set.return_value = (
            None
        )
        mock_mpractice_questionnaire_repo.get_questionnaires_by_practitioner.return_value = (
            []
        )
        mock_mpractice_questionnaire_repo.get_questionnaire_by_oid.return_value = None
        result = note_service.get_structured_internal_note(
            appointment_id=1, practitioner_id=1
        )
        assert result is None

    def test_get_structured_internal_note_without_recorded_answer_set(
        self,
        note_service: MPracticeNoteService,
        mock_mpractice_questionnaire_repo: MagicMock,
        questionnaire: MPracticeQuestionnaire,
        question_set: MPracticeQuestionSet,
        question: MPracticeQuestion,
        answer: MPracticeAnswer,
        trigger_answer_ids: List[int],
        translated_questionnaire: TranslatedMPracticeQuestionnaire,
        translated_question_set: TranslatedMPracticeQuestionSet,
    ):
        mock_mpractice_questionnaire_repo.get_questionnaire_by_recorded_answer_set.return_value = (
            questionnaire
        )
        mock_mpractice_questionnaire_repo.get_trigger_answer_ids.return_value = (
            trigger_answer_ids
        )
        mock_mpractice_questionnaire_repo.get_recorded_answer_set.return_value = None
        mock_mpractice_questionnaire_repo.get_question_sets_by_questionnaire_id.return_value = [
            question_set
        ]
        mock_mpractice_questionnaire_repo.get_questions_by_question_set_ids.return_value = [
            question
        ]
        mock_mpractice_questionnaire_repo.get_answers_by_question_ids.return_value = [
            answer
        ]

        result = note_service.get_structured_internal_note(
            appointment_id=1, practitioner_id=1
        )
        assert result.questionnaire == translated_questionnaire
        assert result.question_sets == [translated_question_set]
        assert result.recorded_answer_set is None
        assert result.recorded_answers == []

    @pytest.mark.parametrize(
        argnames="questionnaire_by_recorded_answer_set,questionnaires_by_practitioner,questionnaire_id_to_roles,questionnaire_by_oid,expected_questionnaire",
        argvalues=[
            (None, [], {}, None, None),
            (
                MPracticeQuestionnaire(
                    id=1, sort_order=1, oid=COACHING_NOTES_COACHING_PROVIDERS_OID
                ),
                [],
                {},
                None,
                MPracticeQuestionnaire(
                    id=1, sort_order=1, oid=COACHING_NOTES_COACHING_PROVIDERS_OID
                ),
            ),
            (
                None,
                [
                    MPracticeQuestionnaire(
                        id=2,
                        sort_order=2,
                        oid=COACHING_NOTES_COACHING_PROVIDERS_OID,
                    ),
                    MPracticeQuestionnaire(
                        id=3, sort_order=3, oid="ca_structured_notes_v3"
                    ),
                ],
                {2: [ROLES.member], 3: [ROLES.practitioner]},
                None,
                MPracticeQuestionnaire(
                    id=3, sort_order=3, oid="ca_structured_notes_v3"
                ),
            ),
            (
                None,
                [],
                {},
                MPracticeQuestionnaire(
                    id=3, sort_order=3, oid=COACHING_NOTES_COACHING_PROVIDERS_OID
                ),
                MPracticeQuestionnaire(
                    id=3, sort_order=3, oid=COACHING_NOTES_COACHING_PROVIDERS_OID
                ),
            ),
        ],
        ids=[
            "no_questionnaire",
            "has_questionnaire_by_recorded_answer_set",
            "has_multiple_questionnaires_by_practitioner",
            "has_questionnaire_by_oid",
        ],
    )
    def test_get_questionnaire(
        self,
        note_service: MPracticeNoteService,
        mock_mpractice_questionnaire_repo: MagicMock,
        questionnaire_by_recorded_answer_set: MPracticeQuestionnaire,
        questionnaires_by_practitioner: List[MPracticeQuestionnaire],
        questionnaire_id_to_roles: Mapping[int, List],
        questionnaire_by_oid: MPracticeQuestionnaire,
        expected_questionnaire: MPracticeQuestionnaire,
    ):
        mock_mpractice_questionnaire_repo.get_questionnaire_by_recorded_answer_set.return_value = (
            questionnaire_by_recorded_answer_set
        )
        mock_mpractice_questionnaire_repo.get_questionnaires_by_practitioner.return_value = (
            questionnaires_by_practitioner
        )
        mock_mpractice_questionnaire_repo.get_questionnaire_by_oid.return_value = (
            questionnaire_by_oid
        )
        mock_mpractice_questionnaire_repo.get_roles_for_questionnaires.return_value = (
            questionnaire_id_to_roles
        )
        result = note_service.get_questionnaire(appointment_id=1, practitioner_id=2)
        assert result == expected_questionnaire

    @pytest.mark.parametrize(
        argnames="non_legacy_recorded_answers,legacy_recorded_answers,expected_recorded_answers",
        argvalues=[
            ([], [], []),
            (
                [MPracticeRecordedAnswer(question_id=1, user_id=3)],
                [],
                [MPracticeRecordedAnswer(question_id=1, user_id=3)],
            ),
            (
                [],
                [MPracticeRecordedAnswer(question_id=2, user_id=3)],
                [MPracticeRecordedAnswer(question_id=2, user_id=3)],
            ),
        ],
        ids=[
            "no_recorded_answers",
            "has_non_legacy_recorded_answers_no_legacy_recorded_answers",
            "no_non_legacy_recorded_answers_has_legacy_recorded_answers",
        ],
    )
    def test_get_recorded_answers(
        self,
        note_service: MPracticeNoteService,
        mock_mpractice_questionnaire_repo: MagicMock,
        non_legacy_recorded_answers: List[MPracticeRecordedAnswer],
        legacy_recorded_answers: List[MPracticeRecordedAnswer],
        expected_recorded_answers: List[MPracticeRecordedAnswer],
    ):
        mock_mpractice_questionnaire_repo.get_recorded_answers_by_recorded_answer_set_id.return_value = (
            non_legacy_recorded_answers
        )
        mock_mpractice_questionnaire_repo.get_legacy_recorded_answers.return_value = (
            legacy_recorded_answers
        )
        result = note_service.get_recorded_answers(
            recorded_answer_set_id=1, appointment_id=2, practitioner_id=3
        )
        assert result == expected_recorded_answers

    def test_get_and_translate_question_sets(
        self,
        note_service: MPracticeNoteService,
        mock_mpractice_questionnaire_repo: MagicMock,
        answer: MPracticeAnswer,
        question: MPracticeQuestion,
        question_set: MPracticeQuestionSet,
        translated_question_set: TranslatedMPracticeQuestionSet,
    ):
        mock_mpractice_questionnaire_repo.get_answers_by_question_ids.return_value = [
            answer
        ]
        mock_mpractice_questionnaire_repo.get_questions_by_question_set_ids.return_value = [
            question
        ]
        mock_mpractice_questionnaire_repo.get_question_sets_by_questionnaire_id.return_value = [
            question_set
        ]
        result = note_service.get_and_translate_question_sets(questionnaire_id=1)
        assert result == [translated_question_set]

    def test_translate_questions(
        self,
        note_service: MPracticeNoteService,
        question: MPracticeQuestion,
        answer: MPracticeAnswer,
        translated_question: TranslatedMPracticeQuestion,
    ):
        question_set_id_to_questions = {1: [question]}
        question_id_to_answers = {1: [answer]}
        result = note_service.translate_questions(
            question_set_id=1,
            question_set_id_to_questions=question_set_id_to_questions,
            question_id_to_answers=question_id_to_answers,
        )
        assert result == [translated_question]

    def test_translate_answers(
        self,
        note_service: MPracticeNoteService,
        answer: MPracticeAnswer,
        translated_answer: TranslatedMPracticeAnswer,
    ):
        result = note_service.translate_answers(
            question_id=1, question_id_to_answers={1: [answer]}
        )
        assert result == [translated_answer]

    def test_translate_questionnaire(
        self,
        note_service: MPracticeNoteService,
        mock_mpractice_questionnaire_repo: MagicMock,
        questionnaire: MPracticeQuestionnaire,
        translated_question_set: TranslatedMPracticeQuestionSet,
        trigger_answer_ids: List[int],
        translated_questionnaire: TranslatedMPracticeQuestionnaire,
    ):
        result = note_service.translate_questionnaire(
            questionnaire=questionnaire,
            translated_question_sets=[translated_question_set],
            trigger_answer_ids=trigger_answer_ids,
        )
        assert result == translated_questionnaire

    def test_translate_recorded_answers_when_appointment_id_exists_in_recorded_answer(
        self,
        note_service: MPracticeNoteService,
        recorded_answer: MPracticeRecordedAnswer,
        translated_recorded_answer: TranslatedMPracticeRecordedAnswer,
    ):
        result = note_service.translate_recorded_answers(
            recorded_answers=[recorded_answer],
            appointment_id_from_recorded_answer_set=None,
        )
        assert result == [translated_recorded_answer]

    def test_translate_recorded_answers_when_appointment_id_does_not_exist_in_recorded_answer(
        self,
        note_service: MPracticeNoteService,
        recorded_answer_without_appointment_id: MPracticeRecordedAnswer,
        translated_recorded_answer: TranslatedMPracticeRecordedAnswer,
    ):
        result = note_service.translate_recorded_answers(
            recorded_answers=[recorded_answer_without_appointment_id],
            appointment_id_from_recorded_answer_set=1,
        )
        assert result == [translated_recorded_answer]

    def test_translate_recorded_answer_set(
        self,
        note_service: MPracticeNoteService,
        recorded_answer_set: MPracticeRecordedAnswerSet,
        translated_recorded_answer: TranslatedMPracticeRecordedAnswer,
        translated_recorded_answer_set: TranslatedMPracticeRecordedAnswer,
    ):
        result = note_service.translate_recorded_answer_set(
            recorded_answer_set=recorded_answer_set,
            translated_recorded_answers=[translated_recorded_answer],
        )
        assert result == translated_recorded_answer_set

    def test_get_provider_addenda_and_questionnaire_no_data(
        self,
        note_service: MPracticeNoteService,
        mock_mpractice_questionnaire_repo: MagicMock,
    ):
        mock_mpractice_questionnaire_repo.get_questionnaire_by_oid.return_value = None
        result = note_service.get_provider_addenda_and_questionnaire(
            appointment_id=1, practitioner_id=1
        )
        assert result is None

    def test_get_provider_addenda_and_questionnaire_returns_expected_data(
        self,
        note_service: MPracticeNoteService,
        mock_mpractice_questionnaire_repo: MagicMock,
        questionnaire: MPracticeQuestionnaire,
        trigger_answer_ids: List[int],
        recorded_answer_set: MPracticeRecordedAnswerSet,
        recorded_answer: MPracticeRecordedAnswer,
        question_set: MPracticeQuestionSet,
        question: MPracticeQuestion,
        answer: MPracticeAnswer,
        translated_questionnaire: TranslatedMPracticeQuestionnaire,
        translated_question_set: TranslatedMPracticeQuestionSet,
        translated_recorded_answer_set: TranslatedMPracticeRecordedAnswer,
        translated_recorded_answer: TranslatedMPracticeAnswer,
        provider_addendum: MPracticeProviderAddendum,
        provider_addendum_answer: MPracticeProviderAddendumAnswer,
        translated_provider_addendum: TranslatedMPracticeProviderAddendum,
    ):
        mock_mpractice_questionnaire_repo.get_questionnaire_by_oid.return_value = (
            questionnaire
        )
        mock_mpractice_questionnaire_repo.get_trigger_answer_ids.return_value = (
            trigger_answer_ids
        )
        mock_mpractice_questionnaire_repo.get_recorded_answer_set.return_value = (
            recorded_answer_set
        )
        mock_mpractice_questionnaire_repo.get_recorded_answers_by_recorded_answer_set_id.return_value = [
            recorded_answer
        ]
        mock_mpractice_questionnaire_repo.get_question_sets_by_questionnaire_id.return_value = [
            question_set
        ]
        mock_mpractice_questionnaire_repo.get_questions_by_question_set_ids.return_value = [
            question
        ]
        mock_mpractice_questionnaire_repo.get_answers_by_question_ids.return_value = [
            answer
        ]
        mock_mpractice_questionnaire_repo.get_provider_addenda.return_value = [
            provider_addendum
        ]
        mock_mpractice_questionnaire_repo.get_provider_addenda_answers.return_value = [
            provider_addendum_answer
        ]

        result = note_service.get_provider_addenda_and_questionnaire(
            appointment_id=1, practitioner_id=1
        )
        expected = MPracticeProviderAddendaAndQuestionnaire(
            questionnaire=translated_questionnaire,
            provider_addenda=[translated_provider_addendum],
        )
        assert result == expected

    def test_translate_provider_addenda(
        self,
        note_service: MPracticeNoteService,
        mock_mpractice_questionnaire_repo: MagicMock,
        provider_addendum: MPracticeProviderAddendum,
        provider_addendum_answer: MPracticeProviderAddendumAnswer,
        translated_provider_addendum: TranslatedMPracticeProviderAddendum,
    ):
        mock_mpractice_questionnaire_repo.get_provider_addenda_answers.return_value = [
            provider_addendum_answer
        ]
        result = note_service.translate_provider_addenda(
            provider_addenda=[provider_addendum]
        )
        assert result == [translated_provider_addendum]

    @pytest.mark.parametrize(
        argnames="text,payload_string,expected_text",
        argvalues=[
            (None, None, None),
            ("abc", None, "abc"),
            (None, '{"text": "abc"}', "abc"),
        ],
        ids=[
            "no_data",
            "has_text",
            "has_payload",
        ],
    )
    def test_get_text(
        self,
        note_service: MPracticeNoteService,
        text: str,
        payload_string: str,
        expected_text: str | None,
    ):
        result = note_service.get_text(text=text, payload_string=payload_string)
        assert result == expected_text

    @pytest.mark.parametrize(
        argnames="payload,text,expected_payload",
        argvalues=[
            (None, None, None),
            ('{"text": "abc", "other": "bcd"}', None, {"text": "abc", "other": "bcd"}),
            (None, "abc", {"text": "abc"}),
        ],
        ids=[
            "no_data",
            "has_payload",
            "has_text",
        ],
    )
    def test_get_payload(
        self,
        note_service: MPracticeNoteService,
        payload: str,
        text: str,
        expected_payload: dict | None,
    ):
        result = note_service.get_payload(payload_string=payload, text=text)
        assert result == expected_payload

    @pytest.mark.parametrize(
        argnames="payload_string,payload_json",
        argvalues=[
            (None, None),
            ('{"text": "abc"}', {"text": "abc"}),
            ("abcdef", None),
        ],
        ids=["no_data", "non_empty_payload", "invalid_payload"],
    )
    def test_get_payload_dict(
        self,
        note_service: MPracticeNoteService,
        payload_string: str | None,
        payload_json: str | None,
    ):
        result = note_service.get_payload_dict(payload_string=payload_string)
        assert result == payload_json
