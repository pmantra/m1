from sqlalchemy.orm import load_only

from appointments.models.payments import FeeAccountingEntry, FeeAccountingEntryTypes
from storage.connection import db
from tasks.payments import PROVIDER_PAYMENTS_EMAIL
from tasks.queues import job
from utils.log import logger
from utils.mail import send_message
from utils.reporting import fees_csv

log = logger(__name__)


def update_rows(ids, type_value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    db.session.query(FeeAccountingEntry).filter(FeeAccountingEntry.id.in_(ids)).update(
        {FeeAccountingEntry.type: type_value}, synchronize_session="fetch"
    )
    db.session.commit()


def populate_fae_type_values():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info("Fetching appointment fees to update...")
    # if appointment id -> appointment
    results_left = True
    while results_left:
        appointment_fee_ids = [
            f.id
            for f in db.session.query(FeeAccountingEntry)
            .options(load_only("id"))
            .filter(
                FeeAccountingEntry.appointment_id != None,
                FeeAccountingEntry.type == FeeAccountingEntryTypes.UNKNOWN,
            )
            .limit(5000)
        ]
        if appointment_fee_ids:
            update_rows(appointment_fee_ids, FeeAccountingEntryTypes.APPOINTMENT)
        else:
            results_left = False

    log.info("Fetching message fees to update...")
    # if message id -> message
    results_left = True
    while results_left:
        message_fee_ids = [
            f.id
            for f in db.session.query(FeeAccountingEntry)
            .options(load_only("id"))
            .filter(
                FeeAccountingEntry.message_id != None,
                FeeAccountingEntry.type == FeeAccountingEntryTypes.UNKNOWN,
            )
            .limit(5000)
        ]
        if message_fee_ids:
            update_rows(message_fee_ids, FeeAccountingEntryTypes.MESSAGE)
        else:
            results_left = False

    log.info("Fetching one-off fees to update...")
    # If only prac id and positive value -> one off
    results_left = True
    while results_left:
        message_fee_ids = [
            f.id
            for f in db.session.query(FeeAccountingEntry)
            .options(load_only("id"))
            .filter(
                FeeAccountingEntry.message_id == None,
                FeeAccountingEntry.practitioner_id != None,
                FeeAccountingEntry.amount > 0,
                FeeAccountingEntry.type == FeeAccountingEntryTypes.UNKNOWN,
            )
            .limit(5000)
        ]
        if message_fee_ids:
            update_rows(message_fee_ids, FeeAccountingEntryTypes.ONE_OFF)
        else:
            results_left = False

    log.info("Fetching malpractice fees to update...")
    # if value -10 -> malpractice
    results_left = True
    while results_left:
        appointment_fee_ids = [
            f.id
            for f in db.session.query(FeeAccountingEntry)
            .options(load_only("id"))
            .filter(
                FeeAccountingEntry.message_id == None,
                FeeAccountingEntry.practitioner_id != None,
                FeeAccountingEntry.amount == -10.00,
                FeeAccountingEntry.type == FeeAccountingEntryTypes.UNKNOWN,
            )
            .limit(5000)
        ]
        if appointment_fee_ids:
            update_rows(appointment_fee_ids, FeeAccountingEntryTypes.MALPRACTICE)
        else:
            results_left = False


@job
def report_fees_not_updated():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # for fees that don't fall into these categories
    # create an output from the script that tells us what they are.
    fees_not_updated = (
        db.session.query(FeeAccountingEntry)
        .filter(
            FeeAccountingEntry.type
            == FeeAccountingEntryTypes.UNKNOWN,  # anything that still has a default type
        )
        .all()
    )

    if not fees_not_updated:
        print("All fees have been upated with a type! :D")
        return
    else:
        print(f"Found {len(fees_not_updated)} fees that were not updated with a type")
        fae_no_type_text = "".join(fees_csv(fees=fees_not_updated))

    send_message(
        to_email=PROVIDER_PAYMENTS_EMAIL,
        subject="Fee accounting entries with no type",
        text="These fee accounting type didn't match criteria to categorize them with a type ",
        csv_attachments=[("fae_with_no_type.csv", fae_no_type_text)],
        internal_alert=True,
    )
