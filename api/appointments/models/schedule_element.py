import datetime
from typing import Any

import dateutil.rrule
from sqlalchemy import Column, DateTime, Enum, Index, Integer, String
from sqlalchemy.orm import backref, relationship

from appointments.models.constants import ScheduleObject
from models import base
from utils.log import logger

log = logger(__name__)


class ScheduleElement(base.TimeLoggedModelBase, ScheduleObject):
    """
    To be deprecated. More notes below.

    This table was likely meant for a job to create recurring schedule
    events automatically, but that work was never completed.

    Instead, recurring availability will use a new ScheduleRecurringBlock instead.
    This model should eventually be deprecated once the admin tool that uses it is
    moved over to using the new version of recurring availability with ScheduleRecurringBlock
    or is removed.

    While the Schedule class does have a generate_occurrences function to create
    the recurring events, the job to call it hasn't been written yet.

    The class is currently used by the set_recurring_availability endpoint
    to create recurring ScheduleEvents, however, its usage does not
    actually add anything to the schedule_element table, i.e.,
    db.session.add() is never called on it.
    """

    __tablename__ = "schedule_element"
    constraints = (Index("idx_starts_at", "starts_at"),)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Tuple[Index]", base class "ModelBase" defined the type as "Tuple[()]")

    frequencies = (
        "YEARLY",
        "MONTHLY",
        "WEEKLY",
        "DAILY",
        "HOURLY",
        "MINUTELY",
        "SECONDLY",
    )

    description = Column(String(140))

    starts_at = Column(DateTime(), default=datetime.datetime.utcnow, nullable=False)
    # Should be minutes
    duration = Column(Integer)

    frequency = Column(Enum(*frequencies, name="frequency"), nullable=False)

    # TODO: support multiple days
    week_days_index = Column(Integer)
    month_day_index = Column(Integer)
    month_index = Column(Integer)

    count = Column(Integer, default=1)
    interval = Column(Integer)
    until = Column(DateTime(), nullable=True)

    schedule = relationship("Schedule", backref=backref("elements", lazy="dynamic"))

    def __repr__(self) -> str:
        return f"<ScheduleElement {self.id} [{self.frequency} x {self.count}]>"

    __str__ = __repr__

    @property
    def is_recurring(self) -> bool:
        return self.count > 1

    @property
    def rrule(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        _kwargs: dict[str, Any] = {"dtstart": self.starts_at}

        if self.week_days_index is not None:
            _kwargs["byweekday"] = self.week_days_index
        if self.month_day_index is not None:
            if self.month_index is not None:
                _kwargs["bymonth"] = self.month_index
            _kwargs["bymonthday"] = self.month_day_index

        if self.count:
            _kwargs["count"] = self.count
        if self.interval:
            _kwargs["interval"] = self.interval
        if self.until:
            _kwargs["until"] = self.until

        if self.is_recurring:
            freq = getattr(dateutil.rrule, self.frequency)
        else:
            freq = dateutil.rrule.DAILY

        log.info("rrule: %s, (%s)", freq, _kwargs)
        return dateutil.rrule.rrule(freq, **_kwargs)

    def occurrences(self, start_at=None, end_at=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        start_at = start_at or datetime.datetime.utcnow().date()
        end_at = end_at or (
            datetime.datetime.utcnow().date() + datetime.timedelta(days=30)
        )

        occurrences = []
        if isinstance(start_at, datetime.date):
            start_at = datetime.datetime.combine(start_at, datetime.time(0, 0, 0))
        if isinstance(end_at, datetime.date):
            end_at = datetime.datetime.combine(end_at, datetime.time(23, 59, 59))

        for starts in self.rrule.between(start_at, end_at):
            ends = starts + datetime.timedelta(minutes=(self.duration or 0))
            occurrences.append((starts, ends))

        log.debug(
            f"{self} -- Got {len(occurrences)} occurrences for date range: ({start_at} - {end_at})"
        )
        return occurrences
