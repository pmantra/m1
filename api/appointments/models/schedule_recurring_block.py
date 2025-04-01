import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import relationship

from appointments.models.constants import ScheduleFrequencies
from models import base
from utils.log import logger

log = logger(__name__)


class ScheduleRecurringBlock(base.TimeLoggedModelBase):
    __tablename__ = "schedule_recurring_block"

    id = Column(Integer, primary_key=True)
    starts_at = Column(DateTime(), default=datetime.datetime.utcnow, nullable=False)
    ends_at = Column(DateTime(), default=datetime.datetime.utcnow, nullable=False)
    frequency = Column(Enum(ScheduleFrequencies), nullable=False)
    until = Column(DateTime(), default=None, nullable=True)
    latest_date_events_created = Column(DateTime(), default=None, nullable=True)

    schedule_id = Column(Integer, ForeignKey("schedule.id"))

    schedule = relationship("Schedule", back_populates="schedule_recurring_blocks")

    schedule_events = relationship(
        "ScheduleEvent",
        back_populates="schedule_recurring_block",
        cascade="all, delete-orphan",
    )

    week_day_indices = relationship(
        "ScheduleRecurringBlockWeekdayIndex", back_populates="schedule_recurring_block"
    )


class ScheduleRecurringBlockWeekdayIndex(base.ModelBase):
    __tablename__ = "schedule_recurring_block_weekday_index"

    id = Column(Integer, primary_key=True)
    week_days_index = Column(Integer, nullable=False)
    schedule_recurring_block_id = Column(
        Integer, ForeignKey("schedule_recurring_block.id")
    )

    schedule_recurring_block = relationship(
        "ScheduleRecurringBlock", back_populates="week_day_indices"
    )
