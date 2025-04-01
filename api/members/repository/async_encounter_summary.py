from __future__ import annotations

import datetime
from typing import List

import ddtrace.ext
import sqlalchemy.orm.scoping
from sqlalchemy import desc

from common import stats
from members.models.async_encounter_summary import (
    AsyncEncounterSummary,
    AsyncEncounterSummaryAnswer,
)
from models.profiles import PractitionerProfile
from models.questionnaires import Questionnaire
from models.verticals_and_specialties import Vertical
from storage import connection
from utils.log import logger

log = logger(__name__)
trace_wrapper = ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.SQL)
metric_prefix = "api.members.repository.async_encounter_summary"

__all__ = "AsyncEncounterSummaryRepository"


class AsyncEncounterSummaryRepository:
    def __init__(self, session: sqlalchemy.orm.scoping.ScopedSession = None):  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        self.session = session or connection.db.session

    @trace_wrapper
    def get(self, *, async_encounter_summary_id: int) -> AsyncEncounterSummary | None:
        if not async_encounter_summary_id:
            return None

        return self.session.query(AsyncEncounterSummary).get(async_encounter_summary_id)

    @trace_wrapper
    def get_async_summaries(
        self,
        *,
        args: dict = None,  # type: ignore[assignment] # Incompatible default for argument "args" (default has type "None", argument has type "Dict[Any, Any]")
    ) -> List[AsyncEncounterSummary]:
        """
        Return async encounter summaries (sorted desc encounter date)
        """
        if args is None:
            args = {}

        user_id = args.get("user_id")
        if not user_id:
            return []

        async_encounter_summaries = (
            self.session.query(AsyncEncounterSummary)
            .filter(
                AsyncEncounterSummary.user_id == user_id,
            )
            .order_by(AsyncEncounterSummary.encounter_date.desc())
        )

        if args.get("scheduled_start"):
            async_encounter_summaries = async_encounter_summaries.filter(
                AsyncEncounterSummary.encounter_date >= args.get("scheduled_start")
            )

        if args.get("scheduled_end"):
            async_encounter_summaries = async_encounter_summaries.filter(
                AsyncEncounterSummary.encounter_date <= args.get("scheduled_end")
            )

        if args.get("my_encounters") and args.get("provider_id"):
            async_encounter_summaries = async_encounter_summaries.filter(
                AsyncEncounterSummary.provider_id == args.get("provider_id")
            )

        if args.get("verticals"):
            async_encounter_summaries = (
                async_encounter_summaries.join(
                    PractitionerProfile,
                    AsyncEncounterSummary.provider_id == PractitionerProfile.user_id,
                )
                .join(PractitionerProfile.verticals)
                .filter(Vertical.name.in_(args.get("verticals")))  # type: ignore[arg-type] # Argument 1 to "in_" of "ColumnOperators" has incompatible type "Optional[Any]"; expected "Union[Iterable[Any], BindParameter[Any], Select, Alias]"
            )

        if args.get("limit"):
            async_encounter_summaries = async_encounter_summaries.limit(
                args.get("limit")
            ).offset(args.get("offset"))

        return async_encounter_summaries.all()

    @ddtrace.tracer.wrap()
    def get_questionnaire_for_async_encounter_summary(
        self, async_encounter_id: int
    ) -> Questionnaire:
        questionnaire = (
            self.session.query(Questionnaire)
            .join(
                AsyncEncounterSummary,
                AsyncEncounterSummary.questionnaire_id == Questionnaire.id,
            )
            .filter(AsyncEncounterSummary.id == async_encounter_id)
            .group_by(Questionnaire.id)
            .order_by(desc(Questionnaire.id))
            .first()
        )
        return questionnaire if questionnaire else None

    @trace_wrapper
    def create(
        self,
        *,
        provider_id: int,
        user_id: int,
        questionnaire_id: int,
        encounter_date: datetime.datetime,
        async_encounter_summary_answers: list[dict],
    ) -> AsyncEncounterSummary | None:
        async_encounter_summary = AsyncEncounterSummary(
            provider_id=provider_id,
            user_id=user_id,
            questionnaire_id=questionnaire_id,
            encounter_date=encounter_date,
        )
        self.session.add(async_encounter_summary)

        try:
            self.session.commit()
        except Exception as e:
            log.error(
                "Failed to create async_encounter_summary record",
                error=str(e),
            )
            stats.increment(
                metric_name=f"{metric_prefix}.create",
                pod_name=stats.PodNames.MPRACTICE_CORE,
                tags=["error:true"],
            )
            return None

        for async_answer in async_encounter_summary_answers:
            async_encounter_summary.async_encounter_summary_answers.append(
                AsyncEncounterSummaryAnswer(
                    async_encounter_summary_id=async_encounter_summary.id,
                    question_id=async_answer["question_id"],
                    answer_id=async_answer.get("answer_id"),
                    text=async_answer.get("text"),
                    date=async_answer.get("date"),
                )
            )
        self.session.add(async_encounter_summary)

        try:
            self.session.commit()
        except Exception as e:
            log.error(
                "Failed to create async_encounter_summary_answer record",
                error=str(e),
            )
            stats.increment(
                metric_name=f"{metric_prefix}_answer.create",
                pod_name=stats.PodNames.MPRACTICE_CORE,
                tags=["error:true"],
            )
            return None

        return async_encounter_summary
