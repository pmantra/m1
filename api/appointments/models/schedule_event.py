import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import backref, relationship

from appointments.models.constants import ScheduleObject
from appointments.models.schedule_recurring_block import (  # noqa: F401; having issues without explicit import
    ScheduleRecurringBlock,
)
from models import base
from utils.log import logger

log = logger(__name__)


class ScheduleEventNotFoundError(Exception):
    pass


class ScheduleEvent(base.TimeLoggedModelBase, ScheduleObject):
    __tablename__ = "schedule_event"
    constraints = (Index("idx_starts_at", "starts_at"), Index("idx_ends_at", "ends_at"))  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Tuple[Index, Index]", base class "ModelBase" defined the type as "Tuple[()]")

    description = Column(String(140))
    starts_at = Column(DateTime(), default=datetime.datetime.utcnow, nullable=False)
    ends_at = Column(DateTime(), nullable=False)

    schedule = relationship("Schedule", backref=backref("events", lazy="dynamic"))

    schedule_element_id = Column(
        Integer, ForeignKey("schedule_element.id"), nullable=True
    )
    schedule_recurring_block_id = Column(
        Integer, ForeignKey("schedule_recurring_block.id"), nullable=True
    )
    # ScheduleElement being used by admin's repeated availability tool
    schedule_element = relationship("ScheduleElement")
    schedule_recurring_block = relationship(
        "ScheduleRecurringBlock", back_populates="schedule_events"
    )

    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().__init__(*args, **kwargs)

    def __repr__(self) -> str:
        return (
            f"<ScheduleEvent ({self.schedule_id}) [{self.starts_at} - {self.ends_at}]>"
        )

    __str__ = __repr__

    @staticmethod
    def get_schedule_event_from_timestamp(schedule, timestamp):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Returns the schedule event which contains `timestamp`
        If `timestamp` occurs on the boundary of two contiguous events, returns the latter.

        Raises `ScheduleEventNotFoundError` if:
        * the timestamp is not in any schedule events; or
        * an unexpected error occurs
        """
        events = schedule.existing_events(timestamp, timestamp).all()
        if not events:
            log.error("No events found for timestamp")
            raise ScheduleEventNotFoundError("No events found for timestamp!")

        if len(events) > 1:
            log.warn(
                "Multiple events case: Found more events than expected",
                events=events,
                timestamp=timestamp,
            )
        return events[0]
