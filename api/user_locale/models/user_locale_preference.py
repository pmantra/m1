from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from models import base


class UserLocalePreference(base.TimeLoggedModelBase):
    __tablename__ = "user_locale_preference"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, unique=True)
    user = relationship("User", foreign_keys=[user_id])
    locale = Column(String(255), nullable=False)
