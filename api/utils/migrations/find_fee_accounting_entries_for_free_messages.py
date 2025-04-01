from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, literal_column
from sqlalchemy.orm import aliased

from appointments.models.payments import FeeAccountingEntry, FeeAccountingEntryTypes
from messaging.models.messaging import MessageCredit
from storage.connection import db
from utils.log import logger

log = logger(__name__)

BATCH_SIZE = 1000

# Hard-code the deployment time (11:00 ET on Friday April 3, 2020)
# Allow overwriting it for testing
bug_deployment_time = datetime.fromisoformat("2020-04-03T15:00:00")


def find_fee_accounting_entries_for_free_messages(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    dry_run=True, bug_deployment_time=bug_deployment_time
):
    InverseFeeAccountingEntry = aliased(FeeAccountingEntry)
    # Find all entries associated with a message credit having free: true
    entries = (
        db.session.query(FeeAccountingEntry)
        .join(MessageCredit, MessageCredit.message_id == FeeAccountingEntry.message_id)
        .outerjoin(
            InverseFeeAccountingEntry,
            and_(
                InverseFeeAccountingEntry.message_id == FeeAccountingEntry.message_id,
                InverseFeeAccountingEntry.amount == -FeeAccountingEntry.amount,
            ),
        )
        .filter(
            literal_column("message_credit.json").like('%"free": true%'),
            # Grab only entries within 6 hours of deployment time
            FeeAccountingEntry.created_at > bug_deployment_time,
            FeeAccountingEntry.created_at < bug_deployment_time + timedelta(hours=6),
            # Only get fee accounting entries with positive amounts
            FeeAccountingEntry.amount > 0,
            # Only get fees without corresponding inverses
            InverseFeeAccountingEntry.id == None,
        )
    )

    count = entries.count()
    log.info("Got FeeAccountingEntry list to invert", count=count)

    for entry in entries.yield_per(BATCH_SIZE):
        inverse = FeeAccountingEntry(
            message_id=entry.message_id,
            amount=Decimal(-entry.amount),
            type=FeeAccountingEntryTypes.MESSAGE,
        )
        db.session.add(inverse)
        log.info(
            "Creating inverse FeeAccountingEntry",
            entry_id=entry.id,
            message_id=entry.message_id,
            amount=inverse.amount,
        )

    if dry_run:
        log.info("Finishing FeeAccountingEntry inversion dry run", count=count)
        db.session.rollback()
    else:
        log.info("Finishing FeeAccountingEntry inversion", count=count)
        db.session.commit()
    log.info("Finished FeeAccountingEntry inversion", dry_run=dry_run)
