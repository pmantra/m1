import datetime
import enum
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    event,
    func,
)
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapper, contains_eager, relationship
from sqlalchemy.sql.expression import and_

from models.base import ModelBase, TimeLoggedModelBase
from models.tracks import member_track
from models.tracks.track import PhaseType
from storage.connection import db

EVENT_REGISTRATION_PAGE_URL = "/app/event-registration/{event_id}"


class Cadences(enum.Enum):
    MONTHLY = "MONTHLY"
    WEEKLY = "WEEKLY"


class VirtualEvent(TimeLoggedModelBase):
    __tablename__ = "virtual_event"

    id = Column(Integer, primary_key=True)
    title = Column(String(128), nullable=False)
    registration_form_url = Column(String(255), nullable=True)
    description = Column(String(500), nullable=False)
    scheduled_start = Column(DateTime, nullable=False)
    scheduled_end = Column(DateTime, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    rsvp_required = Column(Boolean, default=True, nullable=False)
    host_image_url = Column(String(1024))
    host_name = Column(String(256), nullable=False)
    cadence = Column(Enum(Cadences), nullable=True)
    event_image_url = Column(String(255), nullable=True)
    host_specialty = Column(String(120), nullable=False)
    provider_profile_url = Column(String(255), nullable=True)
    description_body = Column(String(500), nullable=False)
    what_youll_learn_body = Column(String(500), nullable=False)
    what_to_expect_body = Column(String(500), nullable=True)
    webinar_id = Column(BigInteger)
    virtual_event_category_id = Column(
        ForeignKey("virtual_event_category.id"), nullable=False
    )

    virtual_event_category = relationship("VirtualEventCategory", uselist=False)
    user_registrations = relationship("VirtualEventUserRegistration")

    @classmethod
    def available_for_registration(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        now = datetime.datetime.utcnow()
        registration_cutoff = now + datetime.timedelta(days=1)
        events = db.session.query(cls).filter(
            cls.scheduled_end >= registration_cutoff, cls.active.is_(True)
        )
        return events


def upsert_event_from_index(mapper: Mapper, connect: Connection, target: Any) -> None:
    from utils import index_resources

    index_resources.upsert_event_from_index(target)


def remove_event_from_index(mapper: Mapper, connect: Connection, target: Any) -> None:
    from utils import index_resources

    index_resources.remove_event_from_index(target)


# Use after_insert to ensure the event ID is assigned
event.listen(VirtualEvent, "after_insert", upsert_event_from_index)
event.listen(VirtualEvent, "after_update", upsert_event_from_index)
event.listen(VirtualEvent, "before_delete", remove_event_from_index)


class VirtualEventUserRegistration(ModelBase):
    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey("user.id"), nullable=False)
    virtual_event_id = Column(ForeignKey("virtual_event.id"), nullable=False)


class VirtualEventCategory(TimeLoggedModelBase):
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False, unique=True)

    def __repr__(self) -> str:
        return f"VirtualEventCategory[{self.id}]: {self.name}"


class VirtualEventCategoryTrack(TimeLoggedModelBase):
    id = Column(Integer, primary_key=True)
    track_name = Column(String(120), nullable=False)
    virtual_event_category_id = Column(
        Integer, ForeignKey("virtual_event_category.id"), nullable=False
    )
    category = relationship("VirtualEventCategory")
    availability_start_week = Column(Integer)
    availability_end_week = Column(Integer)

    constraints = (UniqueConstraint("track_name", "virtual_event_category_id"),)


def validate_start_and_end_weeks(mapper, connect, target):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if target.availability_start_week and target.availability_end_week:
        if target.availability_start_week > target.availability_end_week:
            raise ValueError("Start week must not be after end week")


event.listen(VirtualEventCategoryTrack, "before_update", validate_start_and_end_weeks)
event.listen(VirtualEventCategoryTrack, "before_insert", validate_start_and_end_weeks)


def get_valid_virtual_events_for_track(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    track: member_track.MemberTrack,
    user_id: Optional[int] = None,
    results_limit: Optional[int] = None,
):
    current_week = None
    if track.phase_type == PhaseType.WEEKLY:
        # ignore the _WEEK_OFFSET that adds 39 to postpartum
        # instead calculate "real weeks" from anchor date to today
        current_week = track.week_at(track.anchor_date, datetime.date.today())

    category_track_assocs = VirtualEventCategoryTrack.query.filter_by(
        track_name=track.name
    )

    # Filtering by the user's current week falling between any configured
    # start week/end week must be done outside the main query because
    # doing less than/greater than comparisons with a nullable column cannot
    # be short-circuited in the SQLAlchemy query
    # See https://github.com/sqlalchemy/sqlalchemy/issues/5061#issuecomment-569479845
    track_assoc_ids = [
        assoc.id
        for assoc in category_track_assocs
        if (
            (assoc.availability_start_week is None)
            or (current_week and (assoc.availability_start_week <= current_week))
        )
        and (
            (assoc.availability_end_week is None)
            or (current_week and (assoc.availability_end_week >= current_week))
        )
    ]

    virtual_events_query = (
        db.session.query(VirtualEvent)
        .join(VirtualEventCategory)
        .join(VirtualEventCategoryTrack)
        .outerjoin(
            VirtualEventUserRegistration,
            and_(
                VirtualEventUserRegistration.user_id == user_id,
                VirtualEventUserRegistration.virtual_event_id == VirtualEvent.id,
            ),
        )
        .options(contains_eager(VirtualEvent.user_registrations))
        .filter(VirtualEvent.active.is_(True))
        .filter(VirtualEvent.scheduled_start >= func.now())
        .filter(VirtualEventCategoryTrack.id.in_(track_assoc_ids))
        .order_by(VirtualEvent.scheduled_start.asc())
    )

    if results_limit:
        virtual_events_query = virtual_events_query.limit(results_limit)

    virtual_events = virtual_events_query.all()

    return virtual_events


def user_is_registered_for_event(user_id: int, virtual_event_id: int) -> bool:
    existing_user_registration = (
        db.session.query(VirtualEventUserRegistration)
        .filter(
            (VirtualEventUserRegistration.user_id == user_id)
            & (VirtualEventUserRegistration.virtual_event_id == virtual_event_id)
        )
        .first()
    )
    return existing_user_registration is not None


def get_virtual_event_with_registration_for_one_user(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    virtual_event_id: int, user_id: int
):
    return (
        VirtualEvent.query.filter_by(id=virtual_event_id)
        .outerjoin(
            VirtualEventUserRegistration,
            and_(
                VirtualEventUserRegistration.user_id == user_id,
                VirtualEventUserRegistration.virtual_event_id == VirtualEvent.id,
            ),
        )
        .options(contains_eager(VirtualEvent.user_registrations))
        .one_or_none()
    )
