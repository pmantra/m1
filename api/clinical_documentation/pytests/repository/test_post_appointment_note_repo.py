from flask_sqlalchemy import SQLAlchemy

from appointments.models.appointment_meta_data import AppointmentMetaData
from clinical_documentation.models.note import PostAppointmentNote
from clinical_documentation.repository.post_appointment_note import (
    PostAppointmentNoteRepository,
)
from pytests.db_util import enable_db_performance_warnings


class TestProviderAppointmentRepository:
    def test_get_post_appointment_notes_by_ids_no_data(
        self, db: SQLAlchemy, post_appointment_note_repo: PostAppointmentNoteRepository
    ):
        with enable_db_performance_warnings(database=db, failure_threshold=2):
            result = post_appointment_note_repo.get_post_appointment_notes_by_appointment_ids(
                [1, 2]
            )
            assert result == []

    def test_get_post_appointment_notes_by_ids(
        self,
        db: SQLAlchemy,
        post_appointment_note_repo: PostAppointmentNoteRepository,
        app_metadata: [AppointmentMetaData],
    ):
        with enable_db_performance_warnings(database=db, failure_threshold=2):
            result = post_appointment_note_repo.get_post_appointment_notes_by_appointment_ids(
                [
                    app_metadata[0].appointment_id,
                    app_metadata[1].appointment_id,
                    app_metadata[2].appointment_id,
                ]
            )
            expected = [
                self._translate_appointment_metadata_to_post_appointment_notes(
                    app_metadata[1]
                ),
                self._translate_appointment_metadata_to_post_appointment_notes(
                    app_metadata[2]
                ),
            ]
            assert result == expected

    def _translate_appointment_metadata_to_post_appointment_notes(
        self, app_metadata: AppointmentMetaData
    ) -> PostAppointmentNote:
        return PostAppointmentNote(
            id=app_metadata.id,
            appointment_id=app_metadata.appointment_id,
            created_at=app_metadata.created_at,
            content=app_metadata.content,
            draft=app_metadata.draft,
            modified_at=app_metadata.modified_at,
            message_id=app_metadata.message_id,
        )
