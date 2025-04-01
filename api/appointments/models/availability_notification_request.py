from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from models import base
from utils.data import JSONAlchemy


class AvailabilityNotificationRequest(base.TimeLoggedModelBase):

    __tablename__ = "availability_notification_request"

    id = Column(Integer, primary_key=True)

    member_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    member = relationship("User", foreign_keys=member_id)

    practitioner_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    practitioner = relationship("User", foreign_keys=practitioner_id)

    notified_at = Column(DateTime(), nullable=True, default=None)
    cancelled_at = Column(DateTime(), nullable=True, default=None)

    json = Column(JSONAlchemy(Text), default={})

    member_timezone = Column(String(50), nullable=False, default="America/New_York")

    def __repr__(self) -> str:
        return f"<AvailabilityNotificationRequest {self.member_id} from {self.practitioner_id}>"

    __str__ = __repr__

    @property
    def note(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        _json = self.json or {}
        return _json.get("note")
