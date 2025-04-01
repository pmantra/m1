from sqlalchemy import Column, DateTime, Integer

from models import base


class RescheduleHistory(base.TimeLoggedModelBase):
    __tablename__ = "reschedule_history"

    id = Column(Integer, primary_key=True)
    appointment_id = Column(Integer, nullable=False)
    scheduled_start = Column(DateTime, nullable=False)
    scheduled_end = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)
    modified_at = Column(DateTime, nullable=False)

    def __repr__(self) -> str:
        return f"<Appointment {self.appointment_id} was rescheduled from {self.scheduled_start}>"

    __str__ = __repr__
