from __future__ import annotations

import ddtrace.ext
import sqlalchemy.exc
import sqlalchemy.orm
from sqlalchemy import desc

from appointments.models.appointment_meta_data import (
    AppointmentMetaData,
    PostAppointmentNoteUpdate,
)
from appointments.models.constants import AppointmentMetaDataTypes
from storage import connection
from utils.exceptions import DraftUpdateAttemptException
from utils.log import logger

log = logger(__name__)
trace_wrapper = ddtrace.tracer.wrap(
    span_type=ddtrace.ext.SpanTypes.SQL,
)


class AppointmentMetaDataRepository:
    """A data repository for managing the essential units-of-work for post appointment notes."""

    __slots__ = ("session",)

    def __init__(self, session: sqlalchemy.orm.Session = None):  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "Session")
        self.session = session or connection.db.session().using_bind("default")

    @ddtrace.tracer.wrap()
    def get_by_appointment_id(self, appointment_id: int) -> AppointmentMetaData | None:
        return (
            self.session.query(AppointmentMetaData)
            .filter_by(appointment_id=appointment_id)
            .order_by(
                desc(AppointmentMetaData.modified_at),
                desc(AppointmentMetaData.created_at),
                desc(AppointmentMetaData.id),
            )
            .first()
        )

    @ddtrace.tracer.wrap()
    def create(
        self, content: str, draft: bool, appointment_id: int
    ) -> AppointmentMetaData:
        """
        create post appointment note.
        """
        return AppointmentMetaData(
            type=AppointmentMetaDataTypes.PRACTITIONER_NOTE,
            content=content,
            draft=draft,
            appointment_id=appointment_id,
        )

    @ddtrace.tracer.wrap()
    def update(
        self, note: AppointmentMetaData, content: str, draft: bool
    ) -> AppointmentMetaData:
        """
        update post appointment note.
        """
        note.content = content
        note.draft = draft
        return note

    @ddtrace.tracer.wrap()
    def create_or_update(
        self, appointment_id: int, content: str, draft: bool
    ) -> PostAppointmentNoteUpdate:
        latest_note: AppointmentMetaData = self.get_by_appointment_id(
            appointment_id=appointment_id
        )
        if latest_note is None:
            log.info(
                "Create a post appointment note.",
                draft=draft,
                appointment_id=appointment_id,
            )
            return PostAppointmentNoteUpdate(
                post_session=self.create(content, draft, appointment_id),
                should_send=not draft,
            )

        if (latest_note.content == content) and (latest_note.draft == draft):
            return PostAppointmentNoteUpdate(
                post_session=latest_note, should_send=False
            )

        if latest_note.draft is False:
            raise DraftUpdateAttemptException(
                f"Cannot re-submit appointment {appointment_id}'s post appointment note"
            )

        latest_note.content = content
        latest_note.draft = draft
        log.info(
            "Update a post appointment note.",
            draft=draft,
            appointment_id=appointment_id,
        )
        return PostAppointmentNoteUpdate(
            post_session=latest_note, should_send=not draft
        )
