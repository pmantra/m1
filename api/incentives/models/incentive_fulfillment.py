import enum

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from geography import repository as geography_repository
from incentives.models.incentive import IncentiveAction
from models import base
from models.profiles import MemberProfile
from storage.connection import db


class IncentiveStatus(enum.Enum):
    SEEN = "Seen"
    EARNED = "Earned"
    PROCESSING = "Processing"
    FULFILLED = "Fulfilled"


class IncentiveFulfillment(base.TimeLoggedModelBase):
    __tablename__ = "incentive_fulfillment"
    __table_args__ = (UniqueConstraint("incentivized_action", "member_track_id"),)

    id = Column(Integer, primary_key=True)

    incentive_id = Column(Integer, ForeignKey("incentive.id"), nullable=False)
    incentive = relationship("Incentive")

    member_track_id = Column(Integer, ForeignKey("member_track.id"), nullable=False)
    member_track = relationship("MemberTrack")

    incentivized_action = Column(Enum(IncentiveAction), nullable=False)
    status = Column(Enum(IncentiveStatus), nullable=False)
    tracking_number = Column(String(120))

    date_seen = Column(DateTime)
    date_earned = Column(DateTime)
    date_issued = Column(DateTime)

    def __repr__(self) -> str:
        return f"<IncentiveFulfillment {self.id}>"

    @property
    def member_country_name(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        countries_repo = geography_repository.CountryRepository()
        country_code = (
            db.session.query(MemberProfile.country_code)
            .filter(MemberProfile.user_id == self.member_track.user_id)
            .first()
        )
        country_code = country_code[0] if country_code else None
        country = countries_repo.get(country_code=country_code)
        return country.name if country else None
