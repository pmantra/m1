import json

from rq.timeouts import JobTimeoutException
from sqlalchemy.orm import load_only

from appointments.models.payments import FeeAccountingEntry
from common.services.api import even_chunks
from storage.connection import db
from tasks.queues import job
from utils.log import logger

log = logger(__name__)


def add_practitioner_id_to_fees(max_n_fees=50000):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    fees_ids_with_no_practitioner_ids = [
        f.id
        for f in db.session.query(FeeAccountingEntry)
        .options(load_only("id"))
        .filter(FeeAccountingEntry.practitioner_id.is_(None))
        .limit(max_n_fees)
    ]
    chunks = list(even_chunks(fees_ids_with_no_practitioner_ids, 5000))
    log.info(
        "Will add practitioner_id to fees",
        total_fees_to_process=len(fees_ids_with_no_practitioner_ids),
        chunk_count=len(chunks),
    )
    for chunk in chunks:
        add_practitioner_id_to_fees_chunk.delay(chunk)


@job
def add_practitioner_id_to_fees_chunk(fees_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    fees_to_process = FeeAccountingEntry.query.filter(
        FeeAccountingEntry.id.in_(fees_ids)
    ).all()

    exceptions = {}
    successfully_processed_fees_ids = []
    for fee in fees_to_process:
        try:
            fee.practitioner_id = fee.recipient.id
            db.session.add(fee)
            successfully_processed_fees_ids.append(fee.id)
        except JobTimeoutException as e:
            exceptions[fee.id] = f"JobTimeoutException: {e}"
        except Exception as e:
            exceptions[fee.id] = f"Regular exception: {e}"

    db.session.commit()

    if exceptions:
        log.warning(
            "Exceptions occur when running add_practitioner_id_to_fees_chunk",
            failed_fees_ids=list(exceptions.keys()),
            exceptions=json.dumps(exceptions),
        )
        if successfully_processed_fees_ids:
            log.info(
                "Successfully added practitioner ids to some fees in chunk",
                fees_ids=successfully_processed_fees_ids,
            )
    else:
        log.info(
            "Successfully added practitioner ids to all fees in chunk",
            fees_ids=fees_ids,
        )
