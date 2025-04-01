import csv
import time

from app import create_app
from storage.connection import db
from utils.log import logger
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet

log = logger(__name__)


def populate_reimburse_org_setting():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # Populate reimbursement org settings table with tax status value from csv file
    start_time = time.time()
    with open("./utils/migrations/csvs/org_tax_status.csv", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            reimburse_org = ReimbursementOrganizationSettings.query.filter_by(
                organization_id=int(row["org_id"])
            ).one_or_none()
            if reimburse_org:
                reimburse_org.taxation_status = (
                    row["taxation"].upper().replace("-", "_")
                )
                db.session.add(reimburse_org)
            else:
                print(
                    f"There is no reimburse org setting related to this org id {row['org_id']}, {row['org_name']}"
                )
    db.session.commit()
    elapsed = time.time() - start_time
    log.info(f"Total execution time in seconds: {elapsed}")


def populate_reimbursement_wallet():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # Populate reimbursement wallet table with tax status value from csv file
    start_time = time.time()
    with open(
        "./utils/migrations/csvs/member_id_tax_status.csv", newline=""
    ) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            wallets = ReimbursementWallet.query.filter_by(
                user_id=row["member_id"]
            ).all()
            if wallets:
                if len(wallets) > 1:
                    print(f"User id {row['member_id']} has several wallets: {wallets}")
                else:
                    assert len(wallets) == 1
                    wallet = wallets[0]
                    wallet.taxation_status = row["taxation"].upper().replace("-", "_")
                    db.session.add(wallet)
            else:
                print(
                    f"There is no wallet associated with member id {row['member_id']}"
                )
    db.session.commit()
    elapsed = time.time() - start_time
    log.info(f"Total execution time in seconds: {elapsed}")


def populate_reimbursement_request():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # Populate reimbursement request able with tax status value from csv file
    start_time = time.time()
    with open(
        "./utils/migrations/csvs/reimburse_request_tax_status.csv", newline=""
    ) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            request = ReimbursementRequest.query.filter_by(
                id=row["request_id"]
            ).one_or_none()
            if request:
                request.taxation_status = row["taxation"].upper().replace("-", "_")
                db.session.add(request)
            else:
                print(
                    f"There is no reimbursement request with this id: {row['request_id']}"
                )
    db.session.commit()
    elapsed = time.time() - start_time
    log.info(f"Total execution time in seconds: {elapsed}")


if __name__ == "__main__":
    print(
        "Adding real prod values to tax status col of 3 tables: reimbursement org setting, reimbursement wallet, "
        "and reimbursement request"
    )
    with create_app().app_context():
        populate_reimburse_org_setting()
        populate_reimbursement_wallet()
        populate_reimbursement_request()
