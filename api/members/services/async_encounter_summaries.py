from typing import List, Tuple

import ddtrace
import sqlalchemy

from members.models.async_encounter_summary import AsyncEncounterSummary
from members.repository.async_encounter_summary import AsyncEncounterSummaryRepository
from models.profiles import PractitionerProfile, practitioner_verticals
from models.questionnaires import Answer, Question, Questionnaire
from models.verticals_and_specialties import Vertical
from storage.connection import db


class AsyncEncounterSummariesService:
    def __init__(
        self,
        session: sqlalchemy.orm.scoping.ScopedSession = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        async_encounter_summary_repository: AsyncEncounterSummaryRepository = None,  # type: ignore[assignment] # Incompatible default for argument "async_encounter_summary_repository" (default has type "None", argument has type "AsyncEncounterSummaryRepository")
    ):
        self.session = session or db.session
        self.repository = (
            async_encounter_summary_repository
            or AsyncEncounterSummaryRepository(session=session)
        )

    @ddtrace.tracer.wrap()
    def get(self, args: dict = None) -> List[AsyncEncounterSummary]:  # type: ignore[assignment] # Incompatible default for argument "args" (default has type "None", argument has type "Dict[Any, Any]")
        return self.repository.get_async_summaries(args=args)

    @ddtrace.tracer.wrap()
    def build_async_encounter_provider_data(
        self, async_encounter_summaries: List[AsyncEncounterSummary]
    ) -> (Tuple)[dict, dict]:
        provider_name = {}
        provider_vertical = {}
        for async_encounter in async_encounter_summaries:
            practitioner_profile = (
                db.session.query(PractitionerProfile)
                .join(practitioner_verticals)
                .join(Vertical)
                .filter(PractitionerProfile.user_id == async_encounter.provider_id)
                .one_or_none()
            )
            if practitioner_profile.first_name:
                provider_name[async_encounter.id] = {
                    "first_name": practitioner_profile.first_name
                }
            else:
                provider_name[async_encounter.id] = {"first_name": ""}
            if practitioner_profile.last_name:
                provider_name[async_encounter.id][
                    "last_name"
                ] = practitioner_profile.last_name
            else:
                provider_name[async_encounter.id]["last_name"] = ""
            provider_vertical[async_encounter.id] = [
                vertical.name for vertical in practitioner_profile.verticals
            ]
        return provider_name, provider_vertical

    @ddtrace.tracer.wrap()
    def build_async_encounter_questionnaire_data(
        self, async_encounter_summaries: List[AsyncEncounterSummary]
    ) -> dict:
        questionnaire = {}

        questionnaire_ids = [
            async_encounter.questionnaire_id
            for async_encounter in async_encounter_summaries
        ]
        questionnaires_data = self._get_questionnaires_by_ids(questionnaire_ids)

        for async_encounter in async_encounter_summaries:
            # Pre fetch the nested questionnaire data and pass into context
            questionnaire_data = [
                questionnaire
                for questionnaire in questionnaires_data
                if questionnaire.id == async_encounter.questionnaire_id
            ][0]

            question_sets_data = [
                question_set.to_dict()
                for question_set in questionnaire_data.question_sets
            ]
            trigger_answer_ids = [str(a.id) for a in questionnaire_data.trigger_answers]

            questionnaire[async_encounter.id] = {
                "questionnaire": questionnaire_data.to_dict(),
            }
            questionnaire[async_encounter.id]["questionnaire"][
                "question_sets"
            ] = question_sets_data
            questionnaire[async_encounter.id]["questionnaire"][
                "trigger_answer_ids"
            ] = trigger_answer_ids

            for question_set in questionnaire[async_encounter.id]["questionnaire"][
                "question_sets"
            ]:
                questions_data = self._get_questions_by_question_set(question_set["id"])
                question_set["questions"] = [
                    question.to_dict() for question in questions_data
                ]

                for question in question_set["questions"]:
                    answer_data = self._get_answers_by_question(question["id"])
                    question["answers"] = [answer.to_dict() for answer in answer_data]

        return questionnaire

    @ddtrace.tracer.wrap()
    def _get_questionnaires_by_ids(
        self, questionnaire_ids: List[int]
    ) -> List[Questionnaire]:
        return Questionnaire.query.filter(Questionnaire.id.in_(questionnaire_ids)).all()

    @ddtrace.tracer.wrap()
    def _get_questions_by_question_set(self, question_set_id: int) -> List[Question]:
        return Question.query.filter_by(question_set_id=question_set_id).all()

    @ddtrace.tracer.wrap()
    def _get_answers_by_question(self, question_id: int) -> List[Answer]:
        return Answer.query.filter_by(question_id=question_id).all()
