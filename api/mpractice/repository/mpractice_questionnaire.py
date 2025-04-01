from __future__ import annotations

import functools
from typing import List, Mapping

import ddtrace
import sqlalchemy

from appointments.utils import query_utils
from models.questionnaires import (
    ASYNC_ENCOUNTER_QUESTIONNAIRE_OID,
    Questionnaire,
    QuestionTypes,
)
from mpractice.error import MissingQueryError, QueryNotFoundError
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
from storage.repository.base import BaseRepository

__all__ = ("MPracticeQuestionnaireRepository",)

trace_wrapper = ddtrace.tracer.wrap(
    span_type=ddtrace.ext.SpanTypes.SQL,
)


class MPracticeQuestionnaireRepository(BaseRepository[MPracticeQuestionnaire]):
    model = MPracticeQuestionnaire

    def __init__(
        self,
        session: sqlalchemy.orm.scoping.ScopedSession = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        is_in_uow: bool = False,
        include_soft_deleted_question_sets: bool | None = False,
    ):
        super().__init__(session=session, is_in_uow=is_in_uow)
        queries = query_utils.load_queries_from_file(
            "mpractice/repository/queries/questionnaire.sql"
        )
        if len(queries) == 0:
            raise QueryNotFoundError()
        if len(queries) != 16:
            raise MissingQueryError()

        self._get_recorded_answer_set_query = queries[0]
        self._get_questionnaire_by_recorded_answer_set_query = queries[1]
        self._get_questionnaires_by_practitioner_query = queries[2]
        self._get_questionnaire_by_oid_query = queries[3]
        self._get_question_sets_by_questionnaire_id_query = queries[4]
        self._get_questions_by_question_set_ids_query = queries[5]
        self._get_answers_by_question_ids_query = queries[6]
        self._get_recorded_answers_by_recorded_answer_set_id_query = queries[7]
        self._get_legacy_recorded_answers_query = queries[8]
        self._get_roles_for_questionnaires_query = queries[9]
        self._get_trigger_answer_ids_query = queries[10]
        self._get_provider_addendum_query = queries[11]
        self._get_provider_addenda_answers_query = queries[12]
        self._get_question_sets_by_questionnaire_id_with_soft_deleted_data_query = (
            queries[13]
        )
        self._get_questions_by_question_set_ids_with_soft_deleted_data_query = queries[
            14
        ]
        self._get_answers_by_question_ids_with_soft_deleted_data_query = queries[15]

        self._include_soft_deleted_question_sets = include_soft_deleted_question_sets

    def get_recorded_answer_set(
        self, appointment_id: int, practitioner_id: int
    ) -> MPracticeRecordedAnswerSet | None:
        row = self.session.execute(
            self._get_recorded_answer_set_query,
            {"appointment_id": appointment_id, "practitioner_id": practitioner_id},
        ).first()
        if row is None:
            return None
        return MPracticeRecordedAnswerSet(**row)

    def get_questionnaire_by_recorded_answer_set(
        self, appointment_id: int, practitioner_id: int
    ) -> MPracticeQuestionnaire | None:
        row = self.session.execute(
            self._get_questionnaire_by_recorded_answer_set_query,
            {"appointment_id": appointment_id, "practitioner_id": practitioner_id},
        ).first()
        if row is None:
            return None
        return MPracticeQuestionnaire(**row)

    def get_questionnaires_by_practitioner(
        self, practitioner_id: int
    ) -> List[MPracticeQuestionnaire]:
        rows = self.session.execute(
            self._get_questionnaires_by_practitioner_query,
            {
                "practitioner_id": practitioner_id,
                "async_encounter_oid_prefix": f"{ASYNC_ENCOUNTER_QUESTIONNAIRE_OID}%",
            },
        ).fetchall()
        if rows is None:
            return []
        return [MPracticeQuestionnaire(**row) for row in rows]

    def get_questionnaire_by_oid(self, oid: str) -> MPracticeQuestionnaire | None:
        row = self.session.execute(
            self._get_questionnaire_by_oid_query, {"oid": oid}
        ).first()
        if row is None:
            return None
        return MPracticeQuestionnaire(**row)

    def get_question_sets_by_questionnaire_id(
        self, questionnaire_id: int
    ) -> List[MPracticeQuestionSet]:
        if self._include_soft_deleted_question_sets:
            query = (
                self._get_question_sets_by_questionnaire_id_with_soft_deleted_data_query
            )
        else:
            query = self._get_question_sets_by_questionnaire_id_query

        rows = self.session.execute(
            query,
            {"questionnaire_id": questionnaire_id},
        ).fetchall()
        if rows is None:
            return []
        return [MPracticeQuestionSet(**row) for row in rows]

    def get_questions_by_question_set_ids(
        self, question_set_ids: List[int]
    ) -> List[MPracticeQuestion]:
        if not question_set_ids:
            return []

        if self._include_soft_deleted_question_sets:
            query = self._get_questions_by_question_set_ids_with_soft_deleted_data_query
        else:
            query = self._get_questions_by_question_set_ids_query

        rows = self.session.execute(
            query,
            {"question_set_ids": question_set_ids},
        ).fetchall()
        if rows is None:
            return []
        return [MPracticeQuestion(**row) for row in rows]

    def get_answers_by_question_ids(
        self, question_ids: List[int]
    ) -> List[MPracticeAnswer]:
        if not question_ids:
            return []

        if self._include_soft_deleted_question_sets:
            query = self._get_answers_by_question_ids_with_soft_deleted_data_query
        else:
            query = self._get_answers_by_question_ids_query

        rows = self.session.execute(query, {"question_ids": question_ids}).fetchall()
        if rows is None:
            return []
        return [MPracticeAnswer(**row) for row in rows]

    def get_recorded_answers_by_recorded_answer_set_id(
        self, recorded_answer_set_id: int
    ) -> List[MPracticeRecordedAnswer]:
        rows = self.session.execute(
            self._get_recorded_answers_by_recorded_answer_set_id_query,
            {"recorded_answer_set_id": recorded_answer_set_id},
        ).fetchall()
        return self.create_recorded_answers_from_rows(rows)

    def get_legacy_recorded_answers(
        self, appointment_id: int, practitioner_id: int
    ) -> List[MPracticeRecordedAnswer]:
        """
        Recorded answers that were created before the concept of recorded answer sets
        """
        rows = self.session.execute(
            self._get_legacy_recorded_answers_query,
            {"appointment_id": appointment_id, "practitioner_id": practitioner_id},
        ).fetchall()
        return self.create_recorded_answers_from_rows(rows)

    def get_roles_for_questionnaires(
        self, questionnaire_ids: List[int]
    ) -> Mapping[int, List]:
        if not questionnaire_ids:
            return {}

        rows = self.session.execute(
            self._get_roles_for_questionnaires_query,
            {"questionnaire_ids": questionnaire_ids},
        ).fetchall()
        if rows is None:
            return {}

        questionnaire_id_to_roles = {}
        last_seen_questionnaire_id = None
        for row in rows:
            questionnaire_id = row["questionnaire_id"]
            role = row["role_name"]
            if questionnaire_id != last_seen_questionnaire_id:
                questionnaire_id_to_roles[questionnaire_id] = [role]
                last_seen_questionnaire_id = questionnaire_id
            else:
                questionnaire_id_to_roles[questionnaire_id].append(role)
        return questionnaire_id_to_roles

    def get_trigger_answer_ids(self, questionnaire_id: int) -> List[int]:
        rows = self.session.execute(
            self._get_trigger_answer_ids_query, {"questionnaire_id": questionnaire_id}
        ).fetchall()
        return [row.id for row in rows]

    def get_provider_addenda(
        self, appointment_id: int, practitioner_id: int, questionnaire_id: int
    ) -> List[MPracticeProviderAddendum]:
        rows = self.session.execute(
            self._get_provider_addendum_query,
            {
                "appointment_id": appointment_id,
                "practitioner_id": practitioner_id,
                "questionnaire_id": questionnaire_id,
            },
        )
        if rows is None:
            return []
        return [MPracticeProviderAddendum(**row) for row in rows]

    def get_provider_addenda_answers(
        self, addendum_ids: List[int]
    ) -> List[MPracticeProviderAddendumAnswer]:
        if not addendum_ids:
            return []
        rows = self.session.execute(
            self._get_provider_addenda_answers_query, {"addendum_ids": addendum_ids}
        )
        if rows is None:
            return []
        return [MPracticeProviderAddendumAnswer(**row) for row in rows]

    @staticmethod
    def create_recorded_answers_from_rows(
        rows: List[sqlalchemy.engine.Row],  # type: ignore[name-defined] # Name "sqlalchemy.engine.Row" is not defined
    ) -> [MPracticeRecordedAnswer]:  # type: ignore[valid-type] # Bracketed expression "[...]" is not valid as a type
        result = []
        for row in rows:
            recorded_answer = MPracticeRecordedAnswer(**row)
            if row.question_type_in_enum:
                recorded_answer.question_type_in_enum = QuestionTypes(
                    row.question_type_in_enum
                )
            result.append(recorded_answer)
        return result

    @classmethod
    @functools.lru_cache(maxsize=1)
    def make_table(cls) -> sqlalchemy.Table:
        return Questionnaire.__table__

    @classmethod
    @functools.lru_cache(maxsize=1)
    def table_columns(cls) -> tuple[sqlalchemy.sql.ColumnElement, ...]:  # type: ignore[override] # Signature of "table_columns" incompatible with supertype "BaseRepository"
        return ()
