from __future__ import annotations

import dataclasses
from typing import List

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


@dataclasses.dataclass
class TranslatedMPracticeAnswer(MPracticeAnswer):
    pass


@dataclasses.dataclass
class TranslatedMPracticeQuestion(MPracticeQuestion):
    answers: List[TranslatedMPracticeAnswer] | None = None


@dataclasses.dataclass
class TranslatedMPracticeQuestionSet(MPracticeQuestionSet):
    questions: List[TranslatedMPracticeQuestion] | None = None


@dataclasses.dataclass
class TranslatedMPracticeQuestionnaire(MPracticeQuestionnaire):
    question_sets: List[TranslatedMPracticeQuestionSet] | None = None
    trigger_answer_ids: List[int] | None = None


@dataclasses.dataclass
class TranslatedMPracticeRecordedAnswer(MPracticeRecordedAnswer):
    payload: dict | None = None
    question_type: str | None = None


@dataclasses.dataclass
class TranslatedMPracticeRecordedAnswerSet(MPracticeRecordedAnswerSet):
    recorded_answers: List[TranslatedMPracticeRecordedAnswer] | None = None


@dataclasses.dataclass
class StructuredInternalNote:
    questionnaire: TranslatedMPracticeQuestionnaire | None = None
    question_sets: List[TranslatedMPracticeQuestionSet] | None = None
    recorded_answer_set: TranslatedMPracticeRecordedAnswerSet | None = None
    recorded_answers: List[TranslatedMPracticeRecordedAnswer] | None = None


@dataclasses.dataclass
class TranslatedMPracticeProviderAddendum(MPracticeProviderAddendum):
    provider_addendum_answers: List[MPracticeProviderAddendumAnswer] | None = None


@dataclasses.dataclass
class MPracticeProviderAddendaAndQuestionnaire:
    questionnaire: TranslatedMPracticeQuestionnaire | None = None
    provider_addenda: List[TranslatedMPracticeProviderAddendum] | None = None
