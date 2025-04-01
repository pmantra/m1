from __future__ import annotations

import dataclasses
import datetime

from models.questionnaires import QuestionTypes


@dataclasses.dataclass
class MPracticeAnswer:
    id: int
    sort_order: int
    # In the DB table schema, oid can be null, but in practice it should be non-null.
    # This is to prevent bugs surface in MPC-3798 and MPC-3856.
    oid: str
    question_id: int
    text: str | None = None
    soft_deleted_at: datetime.datetime | None = None


@dataclasses.dataclass
class MPracticeQuestion:
    id: int
    sort_order: int
    label: str
    type: str
    required: bool
    question_set_id: int
    # In the DB table schema, oid can be null, but in practice it should be non-null.
    # This is to prevent bugs surface in MPC-3798 and MPC-3856.
    oid: str
    non_db_answer_options_json: str | None = None
    soft_deleted_at: datetime.datetime | None = None


@dataclasses.dataclass
class MPracticeQuestionSet:
    id: int
    sort_order: int
    # In the DB table schema, oid can be null, but in practice it should be non-null.
    # This is to prevent bugs surface in MPC-3798 and MPC-3856.
    oid: str
    prerequisite_answer_id: int | None = None
    soft_deleted_at: datetime.datetime | None = None


@dataclasses.dataclass
class MPracticeQuestionnaire:
    id: int
    sort_order: int
    # In the DB table schema, oid can be null, but in practice it should be non-null.
    # This is to prevent bugs surface in MPC-3798 and MPC-3856.
    oid: str
    description_text: str | None = None
    title_text: str | None = None
    soft_deleted_at: datetime.datetime | None = None


@dataclasses.dataclass
class MPracticeRecordedAnswer:
    question_id: int
    user_id: int
    appointment_id: int | None = None
    question_type_in_enum: QuestionTypes | None = None
    answer_id: int | None = None
    text: str | None = None
    date: datetime.date | None = None
    payload_string: str | None = None


@dataclasses.dataclass
class MPracticeRecordedAnswerSet:
    id: int
    source_user_id: int
    appointment_id: int | None = None
    questionnaire_id: int | None = None
    draft: bool | None = None
    modified_at: datetime.datetime | None = None
    submitted_at: datetime.datetime | None = None


@dataclasses.dataclass
class MPracticeProviderAddendumAnswer:
    question_id: int
    addendum_id: int
    answer_id: int | None = None
    text: str | None = None
    date: datetime.date | None = None


@dataclasses.dataclass
class MPracticeProviderAddendum:
    id: int
    questionnaire_id: int
    user_id: int
    appointment_id: int
    submitted_at: datetime.datetime
    associated_answer_id: int | None = None


@dataclasses.dataclass
class SessionMetaInfo:
    created_at: datetime.datetime | None = None
    draft: bool | None = None
    notes: str | None = None
