from dataclasses import dataclass


@dataclass
class RecordedAnswer:
    question_id: str
    answer_id: str
    text: str
    appointment_id: int
    user_id: int
