from sqlalchemy import Column, Date, SmallInteger, String

from models.base import TimeLoggedSnowflakeModelBase


class ReimbursementWalletGlobalProcedures(TimeLoggedSnowflakeModelBase):
    __tablename__ = "reimbursement_wallet_global_procedures"

    name = Column(String(190), nullable=False, unique=True)
    credits = Column(SmallInteger, nullable=False)
    annual_limit = Column(SmallInteger, nullable=True)
    deleted_at = Column(Date, default=None, nullable=True)

    def __repr__(self) -> str:
        return f"Global Procedure: {self.name}"
