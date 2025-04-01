from __future__ import annotations

import csv

import click

from storage.connection import db
from utils.log import logger

log = logger(__name__)

SOURCE_CSV = "./utils/migrations/csvs/org_id_reimbursement_request_category_id.csv"


def backfill_historical_reimbursement_request_category(file_path):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    with open(file_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            old_reimbursement_category_request_id = row[
                "old_reimbursement_request_category_id"
            ]
            new_reimbursement_request_category_id = row[
                "new_reimbursement_request_category_id"
            ]
            organization_id = row["org_id"]
            sql = """
                UPDATE reimbursement_request 
                JOIN reimbursement_wallet ON reimbursement_wallet.id = reimbursement_request.reimbursement_wallet_id
                JOIN reimbursement_organization_settings ON reimbursement_organization_settings.id = reimbursement_wallet.reimbursement_organization_settings_id
                JOIN organization ON organization.id = reimbursement_organization_settings.organization_id
                SET reimbursement_request.reimbursement_request_category_id = :new_reimbursement_request_category_id
                WHERE organization.id = :org_id AND reimbursement_request.reimbursement_request_category_id = :old_reimbursement_request_category_id;
                """
            try:
                results = db.session.execute(sql, row)
            except Exception as e:
                log.error(
                    "Exception processing records.",
                    organization_id=organization_id,
                    old_reimbursement_category_request_id=old_reimbursement_category_request_id,
                    new_reimbursement_request_category_id=new_reimbursement_request_category_id,
                    error=e,
                )
                continue
            else:
                log.info(
                    f"{results.rowcount} Reimbursement Request updated for Organization ID: {organization_id}",
                    old_reimbursement_category_request_id=old_reimbursement_category_request_id,
                    new_reimbursement_request_category_id=new_reimbursement_request_category_id,
                )


@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
@click.option(
    "--file_path",
    default=SOURCE_CSV,
    help="File path to run if different than default.",
)
def backfill(dry_run: bool = False, file_path: str = SOURCE_CSV):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from app import create_app

    with create_app(task_instance=True).app_context():
        backfill_historical_reimbursement_request_category(file_path=file_path)
        if dry_run:
            log.info("Dry run requested. Rolling back changes.")
            db.session.rollback()
            return

        log.debug("Committing changes...")
        db.session.commit()
        log.debug("Finished.")


if __name__ == "__main__":
    backfill()
