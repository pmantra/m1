import hashlib
from datetime import datetime
from typing import List, Optional

from models.failed_external_api_call import FailedVendorAPICall, Status
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class FailedVendorAPICallRecorder:
    def __init__(self) -> None:
        self.db = db

    @staticmethod
    def generate_external_id(
        user_id: str, called_by: str, vendor_name: str, api_name: str
    ) -> str:
        return hashlib.sha1(
            f"{user_id}_{called_by}_{vendor_name}.{api_name}_{datetime.utcnow().timestamp()}".encode()
        ).hexdigest()

    def create_record(
        self,
        external_id: str,
        payload: dict,
        called_by: str,
        vendor_name: str,
        api_name: str,
        status: Status,
    ) -> Optional[FailedVendorAPICall]:
        try:
            failed_call = FailedVendorAPICall(
                external_id=external_id,
                payload=payload,
                called_by=called_by,
                vendor_name=vendor_name,
                api_name=api_name,
                status=status,
            )

            self.db.session.add(failed_call)
            self.db.session.commit()

            return failed_call
        except Exception as e:
            log.error(
                "Error in create_record",
                exception_type=e.__class__.__name__,
                exception_message=str(e),
                external_id=external_id,
                called_by=called_by,
                vendor_name=vendor_name,
                api_name=api_name,
                status=status,
            )
            return None

    def set_status(self, id: int, new_status: Status) -> bool:
        try:
            failed_call_record = FailedVendorAPICall.query.filter_by(id=id).one()
            if failed_call_record is not None:
                failed_call_record.status = new_status
                self.db.session.commit()
                return True
            return False
        except Exception as e:
            log.error(
                "Error in set_status",
                id=id,
                exception_type=e.__class__.__name__,
                exception_message=str(e),
            )
            return False

    def get_record_by_status(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self, start_time, end_time, status: Status
    ) -> List[FailedVendorAPICall]:
        try:
            return (
                (
                    (self.db.session.query(FailedVendorAPICall)).filter(
                        FailedVendorAPICall.modified_at.between(start_time, end_time)
                    )
                ).filter(FailedVendorAPICall.status == status)
            ).all()
        except Exception as e:
            log.error(
                "Error in get_record_by_status",
                start_time=start_time,
                end_time=end_time,
                status=status,
                exception_type=e.__class__.__name__,
                exception_message=str(e),
            )
            return []

    def get_record_by_id(self, id) -> Optional[FailedVendorAPICall]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        try:
            return (
                (self.db.session.query(FailedVendorAPICall))
                .filter(FailedVendorAPICall.id == id)
                .one()
            )
        except Exception as e:
            log.error(
                "Error in get_record_by_id",
                id=id,
                exception_type=e.__class__.__name__,
                exception_message=str(e),
            )
            return None

    def get_record_by_external_id(self, external_id) -> Optional[FailedVendorAPICall]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        try:
            return (
                (self.db.session.query(FailedVendorAPICall))
                .filter(FailedVendorAPICall.external_id == external_id)
                .one()
            )
        except Exception as e:
            log.error(
                "Error in get_record_by_external_id",
                id=id,
                exception_type=e.__class__.__name__,
                exception_message=str(e),
            )
            return None
