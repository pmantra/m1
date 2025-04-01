from sqlalchemy import BigInteger, Boolean, Column, Integer

from models.base import TimeLoggedModelBase


class SmsNotificationsConsent(TimeLoggedModelBase):
    __tablename__ = "sms_notifications_consent"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, unique=True, nullable=False)
    sms_messaging_notifications_enabled = Column(Boolean, default=False, nullable=False)
