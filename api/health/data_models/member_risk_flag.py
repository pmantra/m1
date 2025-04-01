from datetime import date
from typing import Optional

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Query, relationship
from sqlalchemy.sql import or_

from health.data_models.risk_flag import RiskFlag
from models import base


# Use MemberRiskService to set/clear MemberRiskFlags - do not create them directly
# MemberRiskService maintains the following properties:
#   On any given date:
#     1. A member will only have at most one active instance of a particular risk
#     2. Though a member may have multiple inactive instances of a particular risk
#        When a risk is set/cleared multiple times in a day, multiple inactive rows with same start/end would be added
# Note about start/end dates:
#   start - the date the risk became active.  None = existed prior to June 11 2024
#   end - the date the risk is no longer active (ie it was active the day before).  None = currently active
#   when start=end, the risk should be considered never active
#   start & end are not datetime because the time granularity shouldn't matter
#     when considering the implications of the risk on a member
#     it also makes querying easier if we don't have to filter on time
class MemberRiskFlag(base.TimeLoggedModelBase):
    __tablename__ = "member_risk_flag"

    def __repr__(self) -> str:
        return (
            f"<MemberRiskFlag: UserID: {self.user_id} RiskFlagID: {self.risk_flag_id}>"
        )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    risk_flag_id = Column(Integer, ForeignKey("risk_flag.id"), nullable=False)

    risk_flag = relationship(RiskFlag)

    value = Column(Integer)
    start = Column(Date)
    end = Column(Date)
    confirmed_at = Column(DateTime)

    modified_by = Column(Integer)
    modified_reason = Column(String(255))

    def is_active(self, on_date: Optional[date] = None) -> bool:
        if on_date is None:
            on_date = date.today()
        if self.end is not None and self.end <= on_date:
            return False
        if self.start is not None and self.start > on_date:
            return False
        return True

    # function to filter out risks where a risk was not active for a day
    # could happen if a flag was added and then removed same day
    # (maybe momentarily due to partial data or updated info during the day)
    def is_ever_active(self) -> bool:
        if self.start is None or self.end is None:
            return True
        return self.start < self.end

    def filter_active_on_date(self, query: Query, active_on: date) -> Query:
        return query.filter(  # type: ignore
            or_(MemberRiskFlag.start.is_(None), MemberRiskFlag.start <= active_on),
            or_(MemberRiskFlag.end.is_(None), MemberRiskFlag.end > active_on),
        )
