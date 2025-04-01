from __future__ import annotations

import csv
from typing import Dict, List

import click

from storage.connection import db
from utils.log import logger
from wallet.models.constants import WalletState
from wallet.models.reimbursement_wallet import ReimbursementWallet

log = logger(__name__)

SOURCE_CSV = "./utils/migrations/csvs/update_wallet_expiration.csv"


def is_none_or_empty(string):
    return not bool(string)


def build_expired_wallet_dictionary() -> Dict[str, str]:
    expired_wallets_list = {}

    with open(SOURCE_CSV, newline="") as f:
        reader = csv.DictReader(f)
        line_number = 2

        for row in reader:
            user_id = row["user_id"]
            wallet_id = row["wallet_id"]

            if is_none_or_empty(user_id) or is_none_or_empty(wallet_id):
                raise ValueError(
                    f"❗️Found missing user_id or wallet_id on line {line_number} in source file."
                )

            expired_wallets_list[user_id] = wallet_id
            line_number += 1
    return expired_wallets_list


def update_wallet_expiration() -> None:
    """
    Clean up and close out old wallets for members that have lost coverage
    """
    total_num_of_updated_records = 0
    mapping = build_expired_wallet_dictionary()
    len_of_mapping = len(mapping)

    reimbursement_wallet_list: List[ReimbursementWallet] = db.session.query(
        ReimbursementWallet
    ).filter(ReimbursementWallet.user_id.in_(list(mapping)))

    for reimbursement_wallet in reimbursement_wallet_list:
        reimbursement_wallet_id = mapping.get(str(reimbursement_wallet.user_id))

        if (
            reimbursement_wallet.user_id
            and reimbursement_wallet_id == str(reimbursement_wallet.id)
            and reimbursement_wallet.state != WalletState.EXPIRED
        ):
            reimbursement_wallet.state = WalletState.EXPIRED
            total_num_of_updated_records += 1

    print(  # noqa
        f"📣 The script has processed {len_of_mapping} records, {total_num_of_updated_records} updated."
    )


@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
def run(dry_run: bool = False) -> None:
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            update_wallet_expiration()
        except Exception as e:
            db.session.rollback()
            log.exception("Got an exception while updating.", exception=e)
            return

        if dry_run:
            log.info("Dry run requested. Rolling back changes.")
            db.session.rollback()
            return

        log.debug("Committing changes...")
        db.session.commit()
        log.debug("Finished.")


if __name__ == "__main__":
    run()
