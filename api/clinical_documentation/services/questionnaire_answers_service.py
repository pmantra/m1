from __future__ import annotations

from typing import Optional

from sqlalchemy.orm.scoping import ScopedSession

from clinical_documentation.error import InvalidRecordedAnswersError
from clinical_documentation.models.questionnaire_answers import RecordedAnswer
from clinical_documentation.repository.questionnaire_answers import (
    QuestionnaireAnswersRepository,
)
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class QuestionnaireAnswerService:
    def __init__(
        self,
        session: Optional[ScopedSession] = None,
    ):
        self.session = session or db.session
        self.repo = QuestionnaireAnswersRepository(session=self.session)

    def submit_answers(self, answers: list[RecordedAnswer]):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        question_ids = [answer.question_id for answer in answers]
        questionnaire_ids = self.repo.get_distinct_questionnaire_ids_from_question_ids(
            question_ids
        )
        appointment_ids = {answer.appointment_id for answer in answers}

        # Make sure that all of the questions submitted are from a single appointment
        # We are able to delete all of the existing recorded answers from this appointment for
        # that questionnaire, so we want to be safe.
        if len(appointment_ids) != 1:
            raise InvalidRecordedAnswersError(
                f"Invalid number of appointment_ids in the answers: {answers}"
            )
        # In the future we could consider also limiting the number of questionnaires
        # here with a check for safety. We considered limiting it to 1, but it turns out
        # we submit 2 questionnaires together for the member rating.
        log.info(
            f"Updating recorded_answers for questionnaires {questionnaire_ids} and appointment {appointment_ids}"
        )

        self.repo.delete_existing_recorded_answers(
            questionnaire_id=next(iter(questionnaire_ids)),
            appointment_id=next(iter(appointment_ids)),
        )
        self.repo.insert_recorded_answers(answers)
        self.session.commit()
