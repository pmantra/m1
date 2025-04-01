import enum

from sqlalchemy import Column, Enum, Integer, String, Text

from models.base import TimeLoggedModelBase
from utils.data import JSONAlchemy
from utils.log import logger

log = logger(__name__)


class Status(enum.Enum):
    pending = "PENDING"
    processed = "PROCESSED"
    failed = "FAILED"


class FailedVendorAPICall(TimeLoggedModelBase):
    __tablename__ = "failed_vendor_api_call"

    id = Column(Integer, primary_key=True)
    external_id = Column(String(50), unique=True)
    payload = Column(JSONAlchemy(Text(1000)), default={})
    called_by = Column(String(30))
    vendor_name = Column(String(30))
    api_name = Column(String(30))
    status = Column(Enum(Status))

    def __repr__(self) -> str:
        return (
            f"<FailedVendorAPICall[{self.id}] external_id: {self.external_id}, "
            f"created_at: {self.created_at}, modified_at: {self.modified_at}, "
            f"payload: {self.payload}, called_by: {self.called_by}, api_name: {self.api_name}, "
            f"vendor_name: {self.vendor_name}, status: {self.status}>"
        )

    __str__ = __repr__
