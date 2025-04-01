from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import relationship

from models.base import TimeLoggedModelBase


class MemberSavedResource(TimeLoggedModelBase):
    __tablename__ = "member_resources"

    member_id = Column(
        Integer,
        ForeignKey("member_profile.user_id", ondelete="cascade"),
        primary_key=True,
    )
    resource_id = Column(
        Integer, ForeignKey("resource.id", ondelete="cascade"), primary_key=True
    )

    resource = relationship("Resource")
