import datetime
import enum

from sqlalchemy import (
    DATE,
    TIMESTAMP,
    BigInteger,
    Column,
    DateTime,
    Enum,
    Integer,
    String,
    Text,
    func,
)

from models import base
from models.base import TimeLoggedSnowflakeModelBase


class GDPRRequestStatus(enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"


class GDPRRequestSource(enum.Enum):
    MEMBER = "MEMBER"
    ADMIN = "ADMIN"


class GDPRUserRequest(TimeLoggedSnowflakeModelBase):
    __tablename__ = "gdpr_user_request"

    user_id = Column(Integer)
    user_email = Column(String(120))
    status = Column(
        Enum(GDPRRequestStatus), nullable=False, default=GDPRRequestStatus.PENDING
    )
    source = Column(Enum(GDPRRequestSource), nullable=False)
    created_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        doc="When this record was created.",
    )

    def __repr__(self) -> str:
        return f"<GDPRUserRequest user_id={self.user_id} status={self.status}>"


class GDPRDeletionBackup(base.ModelBase):
    __tablename__ = "gdpr_deletion_backup"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    data = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    restoration_errors = Column(Text, nullable=True)
    requested_date = Column(DATE, nullable=False)
