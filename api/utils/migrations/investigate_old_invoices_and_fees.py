import datetime

from sqlalchemy import and_, exc, or_

from appointments.models.payments import FeeAccountingEntry, Invoice
from storage.connection import db
from tasks.payments import PROVIDER_PAYMENTS_EMAIL
from tasks.queues import job
from utils.log import logger
from utils.mail import send_message
from utils.reporting import fees_csv, invoices_csv

log = logger(__name__)


@job
def report_fees_not_added_to_an_invoice(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    older_than=datetime.datetime(  # noqa  B008  TODO:  Do not perform function calls in argument defaults.  The call is performed only once at function definition time. All calls to your function will reuse the result of that definition-time function call.  If this is intended, assign the function call to a module-level variable and use that variable as a default value.
        2022, 2, 1
    )
):
    fees_not_added_to_an_invoice = (
        db.session.query(FeeAccountingEntry)
        .filter(
            and_(
                FeeAccountingEntry.created_at <= older_than,
                FeeAccountingEntry.invoice_id.is_(None),
            )
        )
        .all()
    )

    if not fees_not_added_to_an_invoice:
        log.debug("No fees not added to an invoice! :D")
        return
    else:
        log.info(
            f"Found {len(fees_not_added_to_an_invoice)} fees older than {str(older_than)} that have no invoice_id"
        )

    fees_csv_text = "".join(fees_csv(fees=fees_not_added_to_an_invoice))

    send_message(
        to_email=PROVIDER_PAYMENTS_EMAIL,
        subject="Fees with no invoices",
        text=f"Fees reported are those older than {str(older_than)} and that have no invoice_id.\nSee attachment for details.",
        csv_attachments=[("fees_with_no_invoices.csv", fees_csv_text)],
        internal_alert=True,
    )


@job
def report_invoices_with_issues(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    older_than=datetime.datetime(  # noqa  B008  TODO:  Do not perform function calls in argument defaults.  The call is performed only once at function definition time. All calls to your function will reuse the result of that definition-time function call.  If this is intended, assign the function call to a module-level variable and use that variable as a default value.
        2022, 2, 1
    ),
    return_results=False,
):
    old_invoices_with_issues = (
        db.session.query(Invoice)
        .filter(
            and_(
                Invoice.created_at <= older_than,
                or_(
                    Invoice.started_at.is_(None),
                    Invoice.completed_at.is_(None),
                    Invoice.id.is_(None),
                ),
            )
        )
        .all()
    )
    if not old_invoices_with_issues:
        log.debug("No old_invoices_with_issues! :D")
        return
    else:
        log.info(
            f"Found {len(old_invoices_with_issues)} invoices older than {str(older_than)} that have issues"
        )

    if return_results:
        return old_invoices_with_issues

    fieldnames = [
        "id",
        "created_at",
        "started_at",
        "completed_at",
        "failed_at",
        "practitioner_id",
        "practitioner",
        "recipient_id",
        "transfer_id",
        "value",
    ]

    invoices_csv_text = "".join(
        invoices_csv(invoices=old_invoices_with_issues, fieldnames=fieldnames)
    )

    send_message(
        to_email=PROVIDER_PAYMENTS_EMAIL,
        subject="Invoices with issues",
        text=f"Invoices reported are those older than {str(older_than)} and that either have no invoice_id, no started_at or no completed_at\nSee attachment for details.",
        csv_attachments=[("invoices_with_issues.csv", invoices_csv_text)],
        internal_alert=True,
    )


def investigate_old_invoices_and_fees():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    report_invoices_with_issues.delay()
    report_fees_not_added_to_an_invoice.delay()


def delete_problem_invoices_zero_value(dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # Get list of problem invoices
    invoices = report_invoices_with_issues(datetime.datetime(2022, 2, 1), True)

    if not invoices:
        return None

    # Loop and delete if invalid value
    for invoice in invoices:
        if (
            invoice.value == 0
            or invoice.value == None
            or invoice.value == ""
            or invoice.value == False
        ):
            log.info(f"Deleting invoice [{invoice.id}]")

            # Start database transaction and exception handling
            try:
                # Delete any records in fee_accounting_entry
                db.session.execute(
                    FeeAccountingEntry.__table__.delete().where(
                        FeeAccountingEntry.invoice_id == invoice.id
                    )
                )
                # Delete the invoice
                db.session.execute(
                    Invoice.__table__.delete().where(Invoice.id == invoice.id)
                )
                # Finish up
                if dry_run:
                    db.session.rollback()
                else:
                    db.session.commit()

            except exc.IntegrityError as exception:
                log.error(f"Database integrity error for invoice [{invoice.id}]")
                log.error(exception)
                db.session.rollback()
                break
            except exc.DatabaseError as exception:
                log.error(f"Datebase error for invoice [{invoice.id}]")
                log.error(exception)
                db.session.rollback()
                break
            except exc.SQLAlchemyError as exception:
                log.error(f"SQLAlchemy error for invoice [{invoice.id}]")
                log.error(exception)
                db.session.rollback()
                break
            except Exception as exception:
                log.error(f"Geneeric error for invoice [{invoice.id}]")
                log.error(exception)
                db.session.rollback()
                break
