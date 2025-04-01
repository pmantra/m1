from __future__ import annotations

import dataclasses
import datetime
from dataclasses import field

from flask_restful import abort

from models.questionnaires import QuestionTypes


@dataclasses.dataclass
class PostAppointmentNote:
    id: int
    appointment_id: int
    created_at: datetime.datetime
    modified_at: datetime.datetime
    content: str = field(default="")
    draft: bool | None = None
    message_id: int | None = None


@dataclasses.dataclass
class QuestionnaireV2:
    id: int
    sort_order: int
    # In the DB table schema, oid can be null, but in practice it should be non-null.
    # This is to prevent bugs surface in MPC-3798 and MPC-3856.
    oid: str
    title_text: str | None = None
    description_text: str | None = None
    name: str | None = None
    soft_deleted_at: datetime.datetime | None = None
    intro_appointment_only: bool | None = None
    track_name: str | None = None


@dataclasses.dataclass
class ProviderAddendumV2:
    id: int
    questionnaire_id: int
    user_id: int
    appointment_id: int
    submitted_at: datetime.datetime
    associated_answer_id: int | None = None


@dataclasses.dataclass
class AnswerV2:
    id: int
    sort_order: int
    # In the DB table schema, oid can be null, but in practice it should be non-null.
    # This is to prevent bugs surface in MPC-3798 and MPC-3856.
    oid: str
    question_id: int
    text: str | None = None
    soft_deleted_at: datetime.datetime | None = None


@dataclasses.dataclass
class QuestionSetV2:
    id: int
    sort_order: int
    # In the DB table schema, oid can be null, but in practice it should be non-null.
    # This is to prevent bugs surface in MPC-3798 and MPC-3856.
    oid: str
    prerequisite_answer_id: int | None = None
    soft_deleted_at: datetime.datetime | None = None


@dataclasses.dataclass
class ProviderAddendumAnswerV2:
    question_id: int
    addendum_id: int
    answer_id: int | None = None
    text: str | None = None
    date: datetime.date | None = None


@dataclasses.dataclass
class QuestionV2:
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
class RecordedAnswerV2:
    question_id: int
    user_id: int
    appointment_id: int | None = None
    question_type_in_enum: QuestionTypes | None = None
    answer_id: int | None = None
    text: str | None = None
    date: datetime.date | None = None
    payload_string: str | None = None

    def __post_init__(self) -> None:
        try:
            if self.question_type_in_enum is not None and isinstance(
                self.question_type_in_enum, str
            ):
                self.question_type_in_enum = QuestionTypes(self.question_type_in_enum)
        except ValueError:
            abort(
                422, description=f"Invalid question type: {self.question_type_in_enum}"
            )


@dataclasses.dataclass
class RecordedAnswerSetV2:
    id: int
    source_user_id: int
    appointment_id: int | None = None
    questionnaire_id: int | None = None
    draft: bool | None = None
    modified_at: datetime.datetime | None = None
    submitted_at: datetime.datetime | None = None
