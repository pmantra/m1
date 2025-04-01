import datetime
from typing import Any, Tuple

from werkzeug.utils import secure_filename

from direct_payment.pharmacy.constants import (
    SMP_CANCELED_FILE_PREFIX,
    SMP_REIMBURSEMENT_FILE_PREFIX,
    SMP_SCHEDULED_FILE_PREFIX,
    SMP_SHIPPED_FILE_PREFIX,
)
from direct_payment.pharmacy.tasks.libs.common import get_smp_ingestion_file
from direct_payment.pharmacy.tasks.libs.rx_file_processor import process_smp_file
from direct_payment.pharmacy.tasks.libs.smp_cancelled_file import CancelledFileProcessor
from direct_payment.pharmacy.tasks.libs.smp_reimbursement_file import (
    ReimbursementFileProcessor,
)
from direct_payment.pharmacy.tasks.libs.smp_scheduled_file import ScheduledFileProcessor
from direct_payment.pharmacy.tasks.libs.smp_shipped_file import ShippedFileProcessor
from tasks.queues import job
from utils.log import logger

log = logger(__name__)

SMP_FILE_PREFIX = {
    "SCHEDULED": SMP_SCHEDULED_FILE_PREFIX,
    "SHIPPED": SMP_SHIPPED_FILE_PREFIX,
    "CANCELLED": SMP_CANCELED_FILE_PREFIX,
    "REIMBURSEMENT": SMP_REIMBURSEMENT_FILE_PREFIX,
}
SMP_FILE_PROCESSORS = {
    "SCHEDULED": ScheduledFileProcessor(),
    "SHIPPED": ShippedFileProcessor(),
    "CANCELLED": CancelledFileProcessor(),
    "REIMBURSEMENT": ReimbursementFileProcessor(),
}


def generate_smp_file(file_type: str, file_date: datetime.date) -> Tuple[Any, str]:
    file_prefix = SMP_FILE_PREFIX.get(file_type, "")
    temp_file = get_smp_ingestion_file(file_prefix, file_type, file_date)
    filename = secure_filename(f"SMP_RX_{file_type}_manual_download_{file_date}.csv")
    return temp_file, filename


@job(service_ns="pharmacy", team_ns="payments_platform")
def process_rx_job(file_type: str, date: datetime.datetime) -> None:
    func = SMP_FILE_PROCESSORS[file_type]
    process_smp_file(processor=func, input_date=date)
