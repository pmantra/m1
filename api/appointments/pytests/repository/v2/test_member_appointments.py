import datetime

from appointments.repository.v2.member_appointments import (
    MemberAppointmentsListRepository,
)
from storage.connection import db


class TestMemberAppointmentsRepository:
    def test_get_payment_pending_appointment_ids(self, valid_appointment, factories):
        now = datetime.datetime.utcnow()

        cancelled = valid_appointment(cancelled_at=now)

        disputed = valid_appointment(disputed_at=now)

        in_five_minutes = now + datetime.timedelta(minutes=5)
        scheduled = valid_appointment(scheduled_start=in_five_minutes)
        factories.CreditFactory(
            amount=1, appointment_id=scheduled.id, user_id=scheduled.member.id
        )

        occurring = valid_appointment(
            member_started_at=now, practitioner_started_at=now
        )

        paid = valid_appointment(member_ended_at=now, practitioner_ended_at=now)
        factories.CreditFactory(
            amount=1, appointment_id=paid.id, user_id=paid.member.id, used_at=now
        )

        pending = valid_appointment(member_ended_at=now, practitioner_ended_at=now)
        pending_2 = valid_appointment(member_ended_at=now, practitioner_ended_at=now)

        repo = MemberAppointmentsListRepository(db.session)
        pending_ids = repo.get_payment_pending_appointment_ids()

        assert pending.id in pending_ids
        assert pending_2.id in pending_ids

        assert cancelled.id not in pending_ids
        assert disputed.id not in pending_ids
        assert scheduled.id not in pending_ids
        assert occurring.id not in pending_ids
        assert paid.id not in pending_ids
