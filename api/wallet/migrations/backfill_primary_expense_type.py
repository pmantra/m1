import argparse

from utils.log import logger

log = logger(__name__)


def _generate_args():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry_run",
        type=lambda x: {"True": True, "False": False}[x],
        required=True,
        help="True to run in dry run mode. False otherwise. -  ",
    )
    args = parser.parse_args()
    return args


def _backfill_primary_expense_type(is_dry_run: bool = True):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from storage.connection import db
    from wallet.migrations.config.backfill_primary_expense_type import (
        WALLET_TO_EXPENSE_TYPE,
    )
    from wallet.models.reimbursement_wallet import ReimbursementWallet

    chunk_size = 200
    updates = []
    total_updates = 0
    len_input = len(WALLET_TO_EXPENSE_TYPE)
    for index, (wallet_id, expense_type) in enumerate(WALLET_TO_EXPENSE_TYPE):
        wallet = (
            db.session.query(ReimbursementWallet)
            .filter(ReimbursementWallet.id == wallet_id)
            .one_or_none()
        )
        if wallet:
            if (
                not wallet.primary_expense_type
                or wallet.primary_expense_type.value != expense_type
            ):
                log.info(
                    f"wallet {wallet_id}, original expense type: {wallet.primary_expense_type}, "
                    f"new expense type:{expense_type}"
                )
                wallet.primary_expense_type = expense_type
                updates.append(wallet)
            else:
                log.info(
                    f"wallet {wallet_id}, no change in expense type: {expense_type}"
                )
        else:
            log.warn(f"wallet {wallet_id} does not match a wallet.")

        len_updates = len(updates)
        if len_updates and (
            (len_updates % chunk_size == 0) or (index == len_input - 1)
        ):
            log.info(f"Processed through index: {index} of {len_input} records")
            total_updates += len_updates
            if not is_dry_run:
                db.session.bulk_save_objects(updates)
                db.session.commit()
                log.info(
                    f"Committed {len_updates} to DB. Total update count {total_updates}"
                )
            else:
                log.info(
                    f"DRY RUN: Processed {len_updates}. Total update-eligible count {total_updates}"
                )
            updates = []


def main():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    args = _generate_args()
    dry_run = args.dry_run
    from traceback import format_exc

    from storage.connection import db

    try:
        log.info(f"Dry run is {dry_run}.")
        _backfill_primary_expense_type(dry_run)
    except Exception as e:
        db.session.rollback()
        log.error(
            f"Got an exception while backfilling, expception = {e} reason = {format_exc()}"
        )
        return


if __name__ == "__main__":
    from app import create_app

    with create_app().app_context():
        main()
