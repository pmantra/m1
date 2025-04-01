from dataclasses import dataclass
from typing import List


# NB: trailing_underscore_names_ like id_ and type_ in this file are to avoid shadowing
# the python built-ins with the same name.
@dataclass
class AnswerStruct:
    id_: int
    oid: str
    text: str
    sort_order: int


@dataclass
class QuestionStruct:
    id_: int
    oid: str
    question_set_id: int
    sort_order: int
    label: str
    type_: str
    required: bool
    answers: List[AnswerStruct]


@dataclass
class QuestionSetStruct:
    id_: int
    questionnaire_id: int
    sort_order: int
    oid: str
    questions: List[QuestionStruct]


@dataclass
class QuestionnaireStruct:
    id_: int
    oid: str
    sort_order: int
    title_text: str
    description_text: str
    intro_appointment_only: bool
    track_name: str
    question_sets: List[QuestionSetStruct]
    trigger_answer_ids: List[str]
