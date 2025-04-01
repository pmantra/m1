import csv

import click

from storage.connection import db
from utils.log import logger
from wallet.models.constants import (
    WalletReportConfigCadenceTypes,
    WalletReportConfigColumnTypes,
)
from wallet.models.reimbursement_wallet_report import (
    WalletClientReportConfiguration,
    WalletClientReportConfigurationReportTypes,
)

log = logger(__name__)


def populate_wallet_client_report_configuration_table():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    count = 0
    all_report_columns = WalletClientReportConfigurationReportTypes.query.all()
    mapped_columns = {
        report_column.column_type: report_column for report_column in all_report_columns
    }

    with open(
        "./utils/migrations/csvs/wallet_report_configurations_2023.csv", newline=""
    ) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # parse
            org_id = row["org_id"]
            cadence_raw = row["cadence"]
            column_preset = row["column_preset"]

            # process
            if cadence_raw == "MONTHLY":
                cadence = WalletReportConfigCadenceTypes.MONTHLY
            elif cadence_raw == "BIWEEKLY":
                cadence = WalletReportConfigCadenceTypes.BIWEEKLY
            else:
                cadence = WalletReportConfigCadenceTypes.WEEKLY

            if column_preset == "DEBIT_US":
                columns = [
                    mapped_columns[WalletReportConfigColumnTypes.VALUE_TO_APPROVE_USD],
                    mapped_columns[
                        WalletReportConfigColumnTypes.DEBIT_CARD_FUND_USAGE_USD
                    ],
                    mapped_columns[
                        WalletReportConfigColumnTypes.DEBIT_CARD_FUND_AWAITING_SUBSTANTIATION
                    ],
                    mapped_columns[WalletReportConfigColumnTypes.TOTAL_PROGRAM_TO_DATE],
                    mapped_columns[WalletReportConfigColumnTypes.TAXATION],
                ]
            elif column_preset == "GLOBAL":
                columns = [
                    mapped_columns[WalletReportConfigColumnTypes.VALUE_TO_APPROVE],
                    mapped_columns[WalletReportConfigColumnTypes.FX_RATE],
                    mapped_columns[WalletReportConfigColumnTypes.VALUE_TO_APPROVE_USD],
                    mapped_columns[WalletReportConfigColumnTypes.REIMBURSEMENT_TYPE],
                    mapped_columns[WalletReportConfigColumnTypes.COUNTRY],
                    mapped_columns[WalletReportConfigColumnTypes.PRIOR_PROGRAM_TO_DATE],
                    mapped_columns[WalletReportConfigColumnTypes.TOTAL_PROGRAM_TO_DATE],
                    mapped_columns[WalletReportConfigColumnTypes.TAXATION],
                ]
            elif column_preset == "DEBIT_GLOBAL":
                columns = [
                    mapped_columns[WalletReportConfigColumnTypes.VALUE_TO_APPROVE],
                    mapped_columns[WalletReportConfigColumnTypes.FX_RATE],
                    mapped_columns[WalletReportConfigColumnTypes.VALUE_TO_APPROVE_USD],
                    mapped_columns[
                        WalletReportConfigColumnTypes.DEBIT_CARD_FUND_USAGE_USD
                    ],
                    mapped_columns[WalletReportConfigColumnTypes.REIMBURSEMENT_TYPE],
                    mapped_columns[WalletReportConfigColumnTypes.COUNTRY],
                    mapped_columns[
                        WalletReportConfigColumnTypes.DEBIT_CARD_FUND_AWAITING_SUBSTANTIATION
                    ],
                    mapped_columns[WalletReportConfigColumnTypes.TOTAL_PROGRAM_TO_DATE],
                    mapped_columns[WalletReportConfigColumnTypes.TAXATION],
                ]
            else:
                columns = [
                    mapped_columns[WalletReportConfigColumnTypes.VALUE_TO_APPROVE_USD],
                    mapped_columns[WalletReportConfigColumnTypes.PRIOR_PROGRAM_TO_DATE],
                    mapped_columns[WalletReportConfigColumnTypes.TOTAL_PROGRAM_TO_DATE],
                    mapped_columns[WalletReportConfigColumnTypes.TAXATION],
                ]

            # save
            config = WalletClientReportConfiguration(
                organization_id=org_id,
                cadence=cadence,
            )
            config.columns = columns
            db.session.add(config)
            count += 1

    print(f"Adding {count} rows to the WalletClientReportConfiguration table.")


@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
def populate(dry_run: bool = False):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            populate_wallet_client_report_configuration_table()
        except Exception as e:
            db.session.rollback()
            log.exception("Got an exception while backfilling.", exception=e)
            return

        if dry_run:
            log.info("Dry run requested. Rolling back changes.")
            db.session.rollback()
            return

        log.debug("Committing changes...")
        db.session.commit()
        log.debug("Finished.")


if __name__ == "__main__":
    populate()
