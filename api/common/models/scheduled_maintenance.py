from sqlalchemy import Column, DateTime, Integer, UniqueConstraint

from models import base


class ScheduledMaintenance(base.TimeLoggedModelBase):
    """
    Scheduled maintenance for downtime, upgrade etc.
    """

    __tablename__ = "scheduled_maintenance"
    constraints = (
        UniqueConstraint(
            "scheduled_start", "scheduled_end", name="scheduled_start_end"
        ),
    )

    id = Column(Integer, primary_key=True)
    scheduled_start = Column(DateTime(), nullable=False)
    scheduled_end = Column(DateTime(), nullable=False)

    def __repr__(self) -> str:
        return f"<ScheduledMaintenance {self.id} from {self.scheduled_start} to {self.scheduled_end}>"

    __str__ = __repr__
