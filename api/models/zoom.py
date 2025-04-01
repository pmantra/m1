import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import backref, relationship

from models.base import ModelBase


class UserWebinarStatus(str, enum.Enum):
    REGISTERED = "registered"
    ATTENDED = "attended"
    MISSED = "missed"

    def __repr__(self) -> str:
        return self.value

    __str__ = __repr__


class UserWebinar(ModelBase):
    __tablename__ = "user_webinars"

    user_id = Column(
        Integer, ForeignKey("user.id", ondelete="CASCADE"), primary_key=True
    )
    webinar_id = Column(
        Integer, ForeignKey("webinar.id", ondelete="CASCADE"), primary_key=True
    )
    registrant_id = Column(String(100))
    status = Column(
        Enum(UserWebinarStatus, native_enum=False),
        nullable=False,
        default=UserWebinarStatus.REGISTERED,
    )

    user = relationship(
        "User", backref=backref("webinar_association", cascade="all, delete-orphan")
    )
    webinar = relationship(
        "Webinar", backref=backref("user_association", cascade="all, delete-orphan")
    )


class Webinar(ModelBase):
    __tablename__ = "webinar"

    id = Column(Integer, primary_key=True)
    uuid = Column(String(100), nullable=False)
    host_id = Column(String(100), nullable=False)
    topic = Column(String(100), nullable=False)
    type = Column(String(1))
    duration = Column(Integer)
    timezone = Column(String(100), nullable=False)
    created_at = Column(DateTime, nullable=False)
    join_url = Column(String(100))
    # this is truncated by the Zoom API when fetching all webinars, but not when fetching a specific one
    agenda = Column(String(250))
    start_time = Column(DateTime, nullable=False)

    users = association_proxy(
        "user_association", "user", creator=lambda x: UserWebinar(user=x)
    )

    def __repr__(self) -> str:
        return f"<Webinar {self.id} [{self.start_time.strftime('%Y-%m-%dT%H:%M:%SZ')}]>"

    __str__ = __repr__
