from __future__ import annotations

from appointments.utils import query_utils
from appointments.utils.appointment_utils import check_appointment_by_ids
from clinical_documentation.models.questionnaire_answers import (
    RecordedAnswer as RecordedAnswerStruct,
)
from models.questionnaires import RecordedAnswer
from utils.log import logger

log = logger(__name__)


class QuestionnaireAnswersRepository:
    def __init__(self, session):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.session = session
        queries = query_utils.load_queries_from_file(
            "clinical_documentation/repository/queries/questionnaire_answers.sql"
        )
        self._get_distinct_questionnaire_ids_from_question_ids_query = queries[0]
        self._delete_existing_recorded_answers_query = queries[1]
        self._insert_recorded_answers_query_template = queries[2]

    def get_distinct_questionnaire_ids_from_question_ids(
        self, question_ids: list[str]
    ) -> set[int]:
        if not question_ids:
            log.warn("No question_ids given, returning empty set")
            return set()

        results = self.session.execute(
            self._get_distinct_questionnaire_ids_from_question_ids_query,
            {
                "question_ids": question_ids,
            },
        )
        return {result[0] for result in results}

    def delete_existing_recorded_answers(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, appointment_id: int, questionnaire_id: int
    ):
        self.session.execute(
            self._delete_existing_recorded_answers_query,
            {"appointment_id": appointment_id, "questionnaire_id": questionnaire_id},
        )
        return

    def insert_recorded_answers(self, recorded_answers: list[RecordedAnswerStruct]):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # We are using this ORM model to insert rows because:
        # 1) the SQL schema is not set up to generate IDs and timestamps
        # 2) bulk inserts with raw SQL are not well supported.
        # There are workarounds but it seemed less hacky to just use the ORM model.

        check_appointment_by_ids(
            [recorded_answer.appointment_id for recorded_answer in recorded_answers],
            True,
        )

        objects_to_insert = [
            RecordedAnswer(
                text=answer.text,
                appointment_id=answer.appointment_id,
                question_id=answer.question_id,
                answer_id=answer.answer_id,
                user_id=answer.user_id,
            )
            for answer in recorded_answers
        ]
        self.session.bulk_save_objects(objects_to_insert)
