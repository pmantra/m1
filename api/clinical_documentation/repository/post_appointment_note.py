from __future__ import annotations

import functools
from typing import List

import ddtrace.ext
import sqlalchemy.orm

from appointments.models.appointment_meta_data import AppointmentMetaData
from appointments.utils import query_utils
from clinical_documentation.error import MissingQueryError, QueryNotFoundError
from clinical_documentation.models.note import PostAppointmentNote
from storage.repository.base import BaseRepository

__all__ = ("PostAppointmentNoteRepository",)


trace_wrapper = ddtrace.tracer.wrap(
    span_type=ddtrace.ext.SpanTypes.SQL,
)


class PostAppointmentNoteRepository(BaseRepository[PostAppointmentNote]):
    model = PostAppointmentNote

    @ddtrace.tracer.wrap()
    def __init__(
        self,
        session: sqlalchemy.orm.scoping.ScopedSession = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        is_in_uow: bool = False,
    ):
        super().__init__(session=session, is_in_uow=is_in_uow)
        queries = query_utils.load_queries_from_file(
            "clinical_documentation/repository/queries/post_appointment_note.sql"
        )
        if len(queries) == 0:
            raise QueryNotFoundError()
        if len(queries) != 1:
            raise MissingQueryError()
        self._get_post_session_notes_query = queries[0]

    @ddtrace.tracer.wrap()
    def get_post_appointment_notes_by_appointment_ids(
        self, appointment_ids: List[int]
    ) -> List[PostAppointmentNote]:
        """
        Retrieves the most recent notes for each appointment from a list of appointment IDs.

        The notes are selected based on the most recent modification time (`modified_at`),
        and in case of ties, the most recent creation time (`created_at`) is considered, then
        finally `id` is considered.
        The results are ordered first by appointment ID, and within the same ID by modification
        and creation times in descending order, ensuring that the most recent entries are
        processed first.

        Parameters:
            appointment_ids (List[int]): A list of integer IDs for which notes are to be fetched.
                                         If the list is empty, the function returns immediately
                                         with an empty list.

        Returns:
            List[PostAppointmentNote]: A list of `PostAppointmentNote` instances, each containing
                                       the most recent note for an appointment ID. Only the most
                                       recent note per appointment ID is included in the result.
                                       If no notes are found for the provided IDs, an empty list
                                       is returned.
        """
        if not appointment_ids:
            return []
        rows = self.session.execute(
            self._get_post_session_notes_query, {"appointment_ids": appointment_ids}
        ).fetchall()
        if rows is None:
            return []

        final_note_list = []
        last_seen_appointment_id = None
        for row in rows:
            if row["appointment_id"] != last_seen_appointment_id:
                final_note_list.append(PostAppointmentNote(**row))
                last_seen_appointment_id = row["appointment_id"]

        return final_note_list

    @classmethod
    @functools.lru_cache(maxsize=1)
    def make_table(cls) -> sqlalchemy.Table:
        return cls.post_appointment_note_table()

    @classmethod
    def table_columns(cls) -> tuple[sqlalchemy.sql.ColumnElement, ...]:  # type: ignore[override] # Return type "Tuple[ColumnElement[Any], ...]" of "table_columns" incompatible with return type "Tuple[Column[Any], ...]" in supertype "BaseRepository"
        return ()

    @classmethod
    @functools.lru_cache(maxsize=1)
    def post_appointment_note_table(cls) -> sqlalchemy.Table:
        return AppointmentMetaData.__table__
