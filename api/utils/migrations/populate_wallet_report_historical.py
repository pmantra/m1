import csv
from datetime import datetime, timedelta

import click

from storage.connection import db
from utils.log import logger
from wallet.models.reimbursement_wallet_report import (
    WalletClientReportReimbursements,
    WalletClientReports,
)

log = logger(__name__)


def populate_wallet_client_report_reimbursements_table(resume_from_date=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    count = 0
    notes = "Historical Reimbursement report back fill"
    try:
        resume_from_date = datetime.strptime(resume_from_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        resume_from_date = None

    # Cache last report, since data is grouped by org/date.
    # ensure we're always checking that this is the right report by comparing org_ids and date.
    last_report = None
    with open(
        "./utils/migrations/csvs/wallet_report_historical_2023.csv", newline=""
    ) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            count += 1
            # parse
            date_sent_to_client = datetime.strptime(
                row["date_sent_to_client"], "%Y-%m-%d"
            ).date()

            # Use resume parameter to continue backfill if it fails
            if resume_from_date:
                if resume_from_date >= date_sent_to_client:
                    continue

            org_id = row["organization_id"]
            reimbursement_request_id = row["reimbursement_id"]

            try:
                date_of_client_approval = datetime.strptime(
                    row["date_of_client_approval"], "%Y-%m-%d"
                ).date()
            except (ValueError, TypeError):
                date_of_client_approval = None

            try:
                date_of_send_to_peakone = datetime.strptime(
                    row["date_of_send_to_peakone"], "%Y-%m-%d"
                ).date()
            except (ValueError, TypeError):
                date_of_send_to_peakone = None

            # process
            # Check if we already have a row for this reimbursement
            report_reimbursement = WalletClientReportReimbursements.query.get(
                reimbursement_request_id
            )
            if report_reimbursement:
                continue

            report = None
            # Check to see if last_report is correct for this row:
            if (
                last_report
                and last_report.organization_id == org_id
                and last_report.end_date == date_sent_to_client
            ):
                report = last_report

            # otherwise try to query for the latest report and check, or create a new report
            else:
                latest_report = (
                    WalletClientReports.query.filter_by(organization_id=org_id)
                    .order_by(WalletClientReports.end_date.desc())
                    .first()
                )
                if (
                    latest_report
                    and latest_report.organization_id == org_id
                    and latest_report.end_date == date_sent_to_client
                ):
                    report = latest_report

                if not report:
                    # Create new report and add to db
                    if latest_report:
                        start_date = latest_report.end_date
                    else:
                        start_date = date_sent_to_client - timedelta(days=14)

                    report = WalletClientReports(
                        organization_id=org_id,
                        start_date=start_date,
                        end_date=date_sent_to_client,
                        client_submission_date=date_sent_to_client,
                        client_approval_date=date_of_client_approval,
                        peakone_sent_date=date_of_send_to_peakone,
                        notes=notes,
                    )
                    db.session.add(report)
                    db.session.commit()
                    last_report = report

            new_report_reimbursement = WalletClientReportReimbursements(
                wallet_client_report_id=report.id,
                reimbursement_request_id=reimbursement_request_id,
            )
            db.session.add(new_report_reimbursement)
            # save reports

            if count % 50 == 0:
                db.session.commit()
        db.session.commit()

    print(f"Adding {count} rows to the WalletClientReportReimbursementRequest table.")


def populate_wallet_client_report_reimbursements_table_peakone_sent_column(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    resume_from_date=None,
):
    count = 0
    try:
        resume_from_date = datetime.strptime(resume_from_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        resume_from_date = None

    with open(
        "./utils/migrations/csvs/wallet_report_historical_2023.csv", newline=""
    ) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            count += 1
            # parse
            date_sent_to_client = datetime.strptime(
                row["date_sent_to_client"], "%Y-%m-%d"
            ).date()
            date_of_send_to_peakone = datetime.strptime(
                row["date_of_send_to_peakone"], "%Y-%m-%d"
            ).date()
            reimbursement_request_id = row["reimbursement_id"]

            # Use resume parameter to continue backfill if it fails
            if resume_from_date:
                if resume_from_date >= date_sent_to_client:
                    continue
            report_reimbursement = WalletClientReportReimbursements.query.filter_by(
                reimbursement_request_id=reimbursement_request_id
            ).first()
            report_reimbursement.peakone_sent_date = date_of_send_to_peakone

            if count % 200 == 0:
                db.session.commit()
        db.session.commit()
    print(f"Fixed {count} rows to the WalletClientReportReimbursementRequest table.")


@click.command()
@click.argument("start_date", nargs=1, default=None)
def populate(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    start_date,
):
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            populate_wallet_client_report_reimbursements_table(start_date)
        except Exception as e:
            db.session.rollback()
            log.exception("Got an exception while backfilling.", exception=e)
            return

        log.debug("Committing changes...")
        db.session.commit()
        log.debug("Finished.")


if __name__ == "__main__":
    populate()
