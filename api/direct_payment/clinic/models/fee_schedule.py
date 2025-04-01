from sqlalchemy import BigInteger, Column, Date, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from models.base import TimeLoggedSnowflakeModelBase


class FeeSchedule(TimeLoggedSnowflakeModelBase):
    __tablename__ = "fee_schedule"

    name = Column(String(190), nullable=False, unique=True)
    deleted_at = Column(Date, default=None, nullable=True)
    fee_schedule_global_procedures = relationship("FeeScheduleGlobalProcedures")

    def __repr__(self) -> str:
        return f"FeeSchedule {self.id} for {self.name}"


class FeeScheduleGlobalProcedures(TimeLoggedSnowflakeModelBase):
    __tablename__ = "fee_schedule_global_procedures"

    fee_schedule_id = Column(
        BigInteger,
        ForeignKey("fee_schedule.id"),
        nullable=False,
    )
    fee_schedule = relationship("FeeSchedule")
    global_procedure_id = Column(String(36))
    cost = Column(Integer, nullable=False)

    def __repr__(self) -> str:
        return f"FeeSchedule {self.fee_schedule_id} for Global Procedure {self.global_procedure_id}]"
