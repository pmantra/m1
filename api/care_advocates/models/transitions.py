import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from models.base import TimeLoggedModelBase


# Value isn't currently used, just descriptive
class CareAdvocateMemberTransitionSender(str, enum.Enum):
    OLD_CX = "Messge from Old CX"
    NEW_CX = "Message from New CX"


class CareAdvocateMemberTransitionResponse(str, enum.Enum):
    SUCCESS = ""
    REASSIGN_EXCEPTION = "Could not reassign advocate due to unhandled exception"
    MESSAGE_EXCEPTION = (
        "Could not send care advocate reassignment message due to unhandled exception"
    )


class CareAdvocateMemberTransitionLog(TimeLoggedModelBase):
    __tablename__ = "ca_member_transition_log"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"))
    user = relationship("User")
    date_completed = Column(DateTime)
    date_scheduled = Column(DateTime)
    uploaded_filename = Column(String(100))
    uploaded_content = Column(Text)

    def __repr__(self) -> str:
        return f"<User ID [{self.user_id}] had a transition using file [{self.uploaded_filename}]>"

    __str__ = __repr__

    @property
    def date_transition(self) -> DateTime:
        return self.date_completed if self.date_completed else self.date_scheduled  # type: ignore[return-value] # Incompatible return value type (got "Optional[datetime]", expected "DateTime")


class CareAdvocateMemberTransitionTemplate(TimeLoggedModelBase):
    __tablename__ = "ca_member_transition_template"

    id = Column(Integer, primary_key=True)
    message_type = Column(String(100))
    message_description = Column(String(100))
    message_body = Column(String(1000))
    sender = Column(Enum(CareAdvocateMemberTransitionSender))
    slug = Column(String(128), unique=True)

    def __repr__(self) -> str:
        return f"<Message type [{self.message_type}]: {self.message_description}>"

    __str__ = __repr__
