import datetime
from typing import List

from sqlalchemy import Column, Date, ForeignKey, Integer, Time

from models.base import ModelBase


class AvailabilityRequestMemberTimes(ModelBase):
    __tablename__ = "availability_request_member_times"

    id = Column(Integer, primary_key=True)
    availability_notification_request_id = Column(
        Integer, ForeignKey("availability_notification_request.id"), nullable=False
    )

    start_time = Column(Time(), nullable=False)
    end_time = Column(Time(), nullable=False)

    start_date = Column(Date(), nullable=False)
    end_date = Column(Date(), nullable=False)

    def __repr__(self) -> str:
        return f"<AvailabilityRequestMemberTimes for notification request id {self.availability_notification_request_id}>"

    __str__ = __repr__

    def separate_by_day(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        separated: List[AvailabilityRequestMemberTimes] = []

        current_date = self.start_date
        one_day = datetime.timedelta(days=1)
        while current_date <= self.end_date:
            separated.append(
                AvailabilityRequestMemberTimes(
                    availability_notification_request_id=self.availability_notification_request_id,
                    start_time=self.start_time,
                    end_time=self.end_time,
                    start_date=current_date,
                    end_date=current_date,  # will be equal
                )
            )
            current_date += one_day
        return separated
