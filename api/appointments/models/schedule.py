from __future__ import annotations

import datetime

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from appointments.models.constants import REGENERATION_DAYS
from appointments.models.schedule_element import ScheduleElement
from appointments.models.schedule_event import ScheduleEvent
from authn.models.user import User
from models import base
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class Schedule(base.TimeLoggedModelBase):
    __tablename__ = "schedule"

    id = Column(Integer, primary_key=True)
    name = Column(String(140), nullable=False)

    user_id = Column(Integer, ForeignKey("user.id"), unique=True)
    user = relationship("User")

    schedule_recurring_blocks = relationship(
        "ScheduleRecurringBlock", back_populates="schedule"
    )

    def __repr__(self) -> str:
        return f"<Schedule {self.id} [User {self.user_id}]>"

    __str__ = __repr__

    def availability_minutes_in_window(
        self,
        starts_at: datetime.datetime | None = None,
        ends_at: datetime.datetime | None = None,
    ) -> int:
        if not ends_at:
            ends_at = datetime.datetime.utcnow()
        if not starts_at:
            starts_at = ends_at - datetime.timedelta(days=30)

        avail_mins = 0
        all_availability = self.existing_events(starts_at, ends_at).all()

        for avail in all_availability:
            mins = (avail.ends_at - avail.starts_at).total_seconds() // 60
            avail_mins += mins

        return int(avail_mins)

    def existing_events(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        starts_at: datetime.datetime,
        ends_at: datetime.datetime,
        recurring: bool = True,
    ):
        """
        This returns all events that intersect, are contained by,
        or contain the date range provided.

        If passed recurring=False, will exclude schedule_events that are tied to a schedule_recurring_block,
        otherwise, will by default include all schedule_events to retain existing behavior.

        All 4 of these example date ranges (the lines) will count the
        example event below as existing.

        +-------------------------------------+
                      +---------+
         +----------+             +----------+
                +----------------------+
                |                      |
                |    ScheduleEvent     |
                |                      |
                +----------------------+

        """
        existing = self.events.filter(
            (
                (
                    (ScheduleEvent.starts_at <= starts_at)
                    & (ScheduleEvent.ends_at >= ends_at)
                )
                | (
                    (ScheduleEvent.starts_at >= starts_at)
                    & (ScheduleEvent.ends_at >= ends_at)
                    & (ScheduleEvent.starts_at <= ends_at)
                )
                | (
                    (ScheduleEvent.starts_at >= starts_at)
                    & (ScheduleEvent.ends_at <= ends_at)
                )
                | (
                    (ScheduleEvent.starts_at <= starts_at)
                    & (ScheduleEvent.ends_at <= ends_at)
                    & (ScheduleEvent.ends_at >= starts_at)
                )
            )
        )
        if not recurring:
            existing = existing.filter(
                ScheduleEvent.schedule_recurring_block_id.is_(None)
            )

        return existing

    def generate_occurrences(
        self,
        start_at: datetime.datetime | None = None,
        end_at: datetime.datetime | None = None,
    ) -> None:
        """This method is to be used to automatically create the recurring
        schedule events based on schedule elements. It is currently not
        being called anywhere and is likely meant to be called by a cronjob
        yet to be written.
        """
        start_at = start_at or datetime.datetime.utcnow()
        end_at = end_at or (
            datetime.datetime.utcnow() + datetime.timedelta(days=REGENERATION_DAYS)
        )

        elements = self.elements.filter(ScheduleElement.starts_at >= start_at)

        occurrences = []
        for element in elements:
            occurrences.extend(element.occurrences(start_at, end_at))

        for occurrence in occurrences:
            event = ScheduleEvent(starts_at=occurrence[0], ends_at=occurrence[1])

            # TODO: make this smarter than an exact match - detect conflicts
            existing = (
                db.session.query(ScheduleEvent)
                .filter(
                    ScheduleEvent.starts_at == event.starts_at,
                    ScheduleEvent.ends_at == event.ends_at,
                    ScheduleEvent.schedule_id == self.id,
                )
                .first()
            )

            if existing:
                log.debug("%s is a duplicate with %s", event, existing)
            else:
                log.debug("Adding %s", event)
                db.session.add(event)

        db.session.commit()


def add_schedule_for_user(user: User) -> None:
    schedule = Schedule()

    schedule.name = f"Schedule for {user.full_name}"
    schedule.user = user

    db.session.add(schedule)
    db.session.flush()
    log.info("Added %s for %s", schedule, user)
