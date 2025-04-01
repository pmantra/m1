"""
Script that contains the functions used to process NEW customer bills over a time range.
"""
import uuid
from datetime import datetime, timezone
from traceback import format_exc
from typing import Dict, List, NamedTuple

from common.payments_gateway import PaymentsGatewayException
from direct_payment.billing.billing_service import BillingService
from direct_payment.billing.constants import INTERNAL_TRUST_PAYMENT_GATEWAY_URL
from direct_payment.billing.models import Bill, BillStatus
from utils.log import logger

log = logger(__name__)

SUCCESSFUL_BILL_STATUSES = {BillStatus.PROCESSING, BillStatus.PAID}


class ProcessingStatus(NamedTuple):
    success_flag: bool
    status_message: str


def _process_bills(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    billing_service, bills: List[Bill], dry_run: bool
) -> Dict[uuid.UUID, ProcessingStatus]:
    to_return = {}

    for i, bill in enumerate(bills):
        bill_uuid = str(bill.uuid)
        log.info(f"Processing {i+1} of {len(bills)}")
        log.info(
            "Processing bill:",
            bill_id=str(bill.id),
            bill_uuid=bill_uuid,
            bill_payor_id=str(bill.payor_id),
        )
        if dry_run:
            bill_processing_status = ProcessingStatus(True, "Dry Run")
        else:
            try:
                bill = billing_service.set_new_bill_to_processing(bill)
                bill_processing_status = ProcessingStatus(
                    bill.status in SUCCESSFUL_BILL_STATUSES, bill.status.value
                )
            except PaymentsGatewayException as e:
                log.error(
                    "PaymentsGatewayException while processing bill",
                    bill_id=str(bill.id),
                    bill_uuid=bill_uuid,
                    bill_payor_id=str(bill.payor_id),
                    reason=format_exc(),
                )
                # The gateway has returned a failure - but this does not mean we failed to process it
                bill_processing_status = ProcessingStatus(
                    True, f"message: {e.message}, code: {e.code}"
                )
            except Exception as e:
                log.error(
                    "Error while processing bill.",
                    bill_id=str(bill.id),
                    bill_uuid=bill_uuid,
                    bill_payor_id=str(bill.payor_id),
                    reason=format_exc(),
                )
                # An unknown exception is logged as a failure
                bill_processing_status = ProcessingStatus(False, type(e).__name__)
        to_return[bill.uuid] = bill_processing_status
    return to_return


def _get_bills_to_process_by_threshold(billing_service: BillingService) -> List[Bill]:
    processing_time_threshold = datetime.now(timezone.utc)
    log.info(
        "NEW member bill processing using processing time threshold.",
        processing_time_threshold=processing_time_threshold,
    )
    bills = billing_service.get_processable_new_member_bills_y(
        processing_time_threshold=processing_time_threshold
    )
    bill_ids = ",".join(map(str, (b.id for b in bills)))

    log.info(
        "Bills swept in by processing_scheduled_at_or_after <= processing_time_threshold:",
        bill_cnt=len(bills),
        bill_ids=bill_ids,
        bill_processing_time_threshold=str(processing_time_threshold),
    )
    return bills


def process_member_bills_driver(
    dry_run: bool = True,
) -> Dict[uuid.UUID, ProcessingStatus]:
    """
    @param start_date: Start date
    @type start_date: datetime.date
    @param end_date: End date
    @type end_date: datetime.date
    @param dry_run: If True will not call the payment service or change bills status. Default True
    @type dry_run: bool
    @return: Dictionary of bill UUIDs mapped to a processing status message.
    @rtype: Dict[uuid.UUID, ProcessingStatus]
    """
    log.info(
        "Processing member bills.",
        dry_run=dry_run,
        payment_gateway_base_url=INTERNAL_TRUST_PAYMENT_GATEWAY_URL,
    )
    billing_service = BillingService(
        session=None, payment_gateway_base_url=INTERNAL_TRUST_PAYMENT_GATEWAY_URL  # type: ignore[arg-type] # Argument "session" to "BillingService" has incompatible type "None"; expected "scoped_session"
    )
    # Get the bills
    bills = _get_bills_to_process_by_threshold(billing_service)
    # process the bills
    to_return = _process_bills(billing_service, bills, dry_run)
    return to_return
