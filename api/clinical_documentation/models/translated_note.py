from __future__ import annotations

import dataclasses
from typing import List

from clinical_documentation.models.note import (
    AnswerV2,
    PostAppointmentNote,
    ProviderAddendumAnswerV2,
    ProviderAddendumV2,
    QuestionnaireV2,
    QuestionSetV2,
    QuestionV2,
    RecordedAnswerSetV2,
    RecordedAnswerV2,
)


@dataclasses.dataclass
class TranslatedPostAppointmentNote(PostAppointmentNote):
    pass


@dataclasses.dataclass
class TranslatedPostAppointmentNotes:
    post_appointment_notes: List[TranslatedPostAppointmentNote]


@dataclasses.dataclass
class TranslatedQuestionV2(QuestionV2):
    answers: List[TranslatedAnswerV2] | None = None


@dataclasses.dataclass
class MPracticeProviderAddendaAndQuestionnaire:
    questionnaire: TranslatedQuestionnaireV2 | None = None
    provider_addenda: List[TranslatedProviderAddendumV2] | None = None


@dataclasses.dataclass
class TranslatedQuestionnaireV2(QuestionnaireV2):
    question_sets: List[TranslatedQuestionSetV2] | None = None
    trigger_answer_ids: List[int] | None = None


@dataclasses.dataclass
class TranslatedProviderAddendumV2(ProviderAddendumV2):
    provider_addendum_answers: List[ProviderAddendumAnswerV2] | None = None


@dataclasses.dataclass
class TranslatedQuestionSetV2(QuestionSetV2):
    questions: List[TranslatedQuestionV2] | None = None


@dataclasses.dataclass
class TranslatedAnswerV2(AnswerV2):
    pass


@dataclasses.dataclass
class TranslatedRecordedAnswerV2(RecordedAnswerV2):
    payload: dict | None = None
    question_type: str | None = None


@dataclasses.dataclass
class TranslatedRecordedAnswerSetV2(RecordedAnswerSetV2):
    recorded_answers: List[TranslatedRecordedAnswerV2] | None = None


@dataclasses.dataclass
class StructuredInternalNote:
    questionnaire: TranslatedQuestionnaireV2 | None = None
    question_sets: List[TranslatedQuestionSetV2] | None = None
    recorded_answer_set: TranslatedRecordedAnswerSetV2 | None = None
    recorded_answers: List[TranslatedRecordedAnswerV2] | None = None
