from datetime import date

from dateutil.relativedelta import relativedelta
from sqlalchemy import func

from appointments.models.payments import FeeAccountingEntry
from common.services.api import even_chunks
from messaging.models.messaging import Message
from storage.connection import db
from tasks.queues import job
from utils.log import logger

log = logger(__name__)


@job
def update_old_message_fees_created_at(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    msg_start_date: date,
    msg_end_date: date,
    fae_date_created: date,
    chunk_size: int = 500,
):
    # Add 1 to msg_end_date because it would not include the last day otherwise
    msg_end_date = msg_end_date + relativedelta(days=1)

    # Fees created on provided date, without an invoice, with messages created within provided range
    fees = (
        FeeAccountingEntry.query.join(Message)
        .filter(
            func.date(FeeAccountingEntry.created_at) == fae_date_created,
            FeeAccountingEntry.invoice_id == None,
            Message.created_at >= msg_start_date,
            Message.created_at < msg_end_date,
        )
        .all()
    )
    chunks = list(even_chunks(fees, chunk_size))
    for chunk in chunks:
        update_old_message_fees_created_at_chunk.delay(chunk)
        db.session.commit()
    log.info("Message Fee Fix: updated fees", count=len(fees))

    return len(fees)


@job
def update_old_message_fees_created_at_chunk(chunk):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # Fix the FeeAccountingEntry.created_at (bad database practice, but what we need)
    for fee in chunk:
        fee.created_at = fee.message.created_at
        db.session.add(fee)
        log.info(
            "Message Fee Fix: updated message fee",
            fae_id=fee.id,
            fae_created_at=fee.created_at,
            msg_id=fee.message.id,
            msg_created_at=fee.message.created_at,
        )
