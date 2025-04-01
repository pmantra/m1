from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from models.base import TimeLoggedModelBase
from utils.log import logger

log = logger(__name__)


class MemberBenefit(TimeLoggedModelBase):
    __tablename__ = "member_benefit"

    id = Column(Integer, primary_key=True)

    benefit_id: str = Column(
        String,
        unique=True,
        nullable=False,
        doc="Member facing benefit ID",
    )

    user_id: int = Column(
        BigInteger,
        ForeignKey("user.id"),
        unique=True,
        nullable=False,
        doc="User ID associated with benefit ID",
    )

    member = relationship("User", back_populates="member_benefit", uselist=False)

    started_at: datetime | None = Column(
        DateTime,
        nullable=True,
        default=datetime.utcnow(),
        doc="The effective date, if null, this means the benefit ID has been soft deleted",
    )

    def __repr__(self) -> str:
        return (
            f"<MemberBenefit benefit_id={self.benefit_id} user_id={str(self.user_id)}>"
        )
