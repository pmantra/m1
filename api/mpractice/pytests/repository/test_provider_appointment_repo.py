import json
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

from mpractice.models.appointment import ProviderAppointment
from mpractice.models.note import SessionMetaInfo
from mpractice.repository.provider_appointment import ProviderAppointmentRepository
from pytests import freezegun
from pytests.db_util import enable_db_performance_warnings
from pytests.factories import (
    AppointmentFactory,
    AppointmentMetaDataFactory,
    NeedAppointmentFactory,
    NeedFactory,
)


class TestProviderAppointmentRepository:
    def test_get_appointment_by_id_no_data(
        self, db: SQLAlchemy, provider_appointment_repo: ProviderAppointmentRepository
    ):
        with enable_db_performance_warnings(database=db, failure_threshold=2):
            result = provider_appointment_repo.get_appointment_by_id(1)
            assert result is None

    @freezegun.freeze_time("2024-03-05 17:49:00")
    def test_get_appointment_by_id_with_data(
        self, db: SQLAlchemy, provider_appointment_repo: ProviderAppointmentRepository
    ):
        appointment = AppointmentFactory.create()
        need = NeedFactory.create(name="test name", description="test description")
        NeedAppointmentFactory.create(appointment_id=appointment.id, need_id=need.id)

        with enable_db_performance_warnings(database=db, failure_threshold=2):
            result = provider_appointment_repo.get_appointment_by_id(appointment.id)
            expected = ProviderAppointment(
                id=appointment.id,
                privacy=appointment.privacy,
                json=json.dumps(appointment.json),
                video=json.dumps(appointment.video),
                client_notes=appointment.client_notes,
                privilege_type=appointment.privilege_type,
                scheduled_start=appointment.scheduled_start,
                scheduled_end=appointment.scheduled_end,
                cancelled_at=appointment.cancelled_at,
                cancellation_policy_name=appointment.cancellation_policy.name,
                disputed_at=appointment.disputed_at,
                member_started_at=appointment.member_started_at,
                member_ended_at=appointment.member_ended_at,
                practitioner_started_at=appointment.practitioner_started_at,
                practitioner_ended_at=appointment.practitioner_ended_at,
                phone_call_at=appointment.phone_call_at,
                need_id=need.id,
                need_name=need.name,
                need_description=need.description,
                vertical_id=appointment.product.vertical.id,
                member_id=appointment.member_schedule.user_id,
                practitioner_id=appointment.product.user_id,
                purpose=appointment.purpose,
            )
            assert result == expected

    def test_get_latest_post_session_no_data(
        self, db: SQLAlchemy, provider_appointment_repo: ProviderAppointmentRepository
    ):
        appointment = AppointmentFactory.create()
        with enable_db_performance_warnings(database=db, failure_threshold=2):
            result = provider_appointment_repo.get_latest_post_session_note(
                appointment_id=appointment.id
            )
            assert result is None

    def test_get_latest_post_session_note_with_data(
        self, db: SQLAlchemy, provider_appointment_repo: ProviderAppointmentRepository
    ):
        appointment = AppointmentFactory.create()
        AppointmentMetaDataFactory.create(
            appointment_id=appointment.id,
            content="post session notes 1",
            draft=True,
            created_at=datetime(2024, 1, 1, 10, 0, 0),
            modified_at=datetime(2024, 1, 1, 12, 0, 0),
        )
        latest_post_session_note = AppointmentMetaDataFactory.create(
            appointment_id=appointment.id,
            content="post session notes 2",
            draft=False,
            created_at=datetime(2024, 2, 1, 10, 0, 0),
            modified_at=datetime(2024, 2, 2, 10, 0, 0),
        )
        AppointmentMetaDataFactory.create(
            appointment_id=appointment.id,
            content="post session notes 3",
            draft=True,
            created_at=datetime(2024, 2, 1, 10, 0, 0),
            modified_at=datetime(2024, 2, 1, 12, 0, 0),
        )

        with enable_db_performance_warnings(database=db, failure_threshold=2):
            result = provider_appointment_repo.get_latest_post_session_note(
                appointment_id=appointment.id
            )
            expected = SessionMetaInfo(
                created_at=latest_post_session_note.created_at,
                draft=latest_post_session_note.draft,
                notes=latest_post_session_note.content,
            )
            assert result == expected
