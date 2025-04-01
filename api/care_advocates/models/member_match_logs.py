import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from models import base


class MemberMatchLog(base.ModelBase):
    __tablename__ = "ca_member_match_log"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    care_advocate_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    # Duplicate user data captured here due to infrastructure not set up in big query
    # Once big query migrates to new infra, can drop following columns: country, org, track, user flags
    organization_id = Column(Integer, ForeignKey("organization.id"), nullable=True)
    track = Column(String(120), nullable=True)
    user_flag_ids = Column(String(255), nullable=True)
    attempts = Column(Integer, nullable=False)
    matched_at = Column(DateTime(), default=datetime.datetime.utcnow, nullable=False)
    country_code = Column(String(2), nullable=True)
