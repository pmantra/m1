import click

from storage.connection import db
from utils.log import logger
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_request_source import (
    ReimbursementRequestSource,
    ReimbursementRequestSourceRequests,
)

log = logger(__name__)


def _find_reimbursement_row_id_that_stays(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    all_ids, user_asset_id, reimbursement_wallet_id
):
    for row in all_ids:
        if row[1] == user_asset_id and row[2] == reimbursement_wallet_id:
            return row[0]


def _find_reim_req_src_req(reimbursement_request_id, final_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    reimbursement_req = ReimbursementRequest.query.filter_by(
        id=reimbursement_request_id
    ).one_or_none()
    reim_req_src_req_exists = ReimbursementRequestSourceRequests.query.filter_by(
        reimbursement_request_id=reimbursement_req.id,
        reimbursement_request_source_id=final_id,
    ).one_or_none()
    return reim_req_src_req_exists


def backfill_remove_dupes():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    reimbursement_req_src_rows_to_keep = db.session.execute(
        """
            SELECT MIN(id), user_asset_id, reimbursement_wallet_id FROM reimbursement_request_source GROUP BY user_asset_id, reimbursement_wallet_id;
        """
    ).fetchall()

    reimbursement_req_src_rows_to_delete = db.session.execute(
        """
            SELECT id, user_asset_id, reimbursement_wallet_id FROM reimbursement_request_source WHERE id NOT in ( SELECT MIN(id) FROM reimbursement_request_source GROUP BY user_asset_id, reimbursement_wallet_id);
        """
    ).fetchall()

    update_reim_req_src_reqs_count = 0
    delete_reim_req_src_reqs_count = 0
    for row in reimbursement_req_src_rows_to_delete:
        final_id = _find_reimbursement_row_id_that_stays(
            reimbursement_req_src_rows_to_keep, row[1], row[2]
        )
        reim_req_src_req_query = ReimbursementRequestSourceRequests.query.filter_by(
            reimbursement_request_source_id=row[0]
        )
        all_rows = reim_req_src_req_query.all()
        if len(all_rows) > 1:
            for row_src_req in all_rows:
                reim_req_src_req_exists = _find_reim_req_src_req(
                    row_src_req.reimbursement_request_id, final_id
                )

                if reim_req_src_req_exists:
                    delete_reim_req_src_reqs_count += 1
                    ReimbursementRequestSourceRequests.query.filter_by(
                        reimbursement_request_source_id=row[0]
                    ).delete()
                else:
                    reim_req_src_req_query.update(
                        {"reimbursement_request_source_id": final_id}
                    )
                    update_reim_req_src_reqs_count += 1
        elif len(all_rows) == 1:
            reim_req_src_req_exists = _find_reim_req_src_req(
                reim_req_src_req_query.one().reimbursement_request_id,
                final_id,
            )
            if reim_req_src_req_exists:
                delete_reim_req_src_reqs_count += 1
                ReimbursementRequestSourceRequests.query.filter_by(
                    reimbursement_request_source_id=row[0]
                ).delete()
            else:
                reim_req_src_req_query.update(
                    {"reimbursement_request_source_id": final_id}
                )
                update_reim_req_src_reqs_count += 1

        ReimbursementRequestSource.query.filter_by(id=row[0]).delete()

    return (
        len(reimbursement_req_src_rows_to_delete),
        update_reim_req_src_reqs_count,
        delete_reim_req_src_reqs_count,
    )


def backfill(dry_run: bool = False):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info(
        "Running backfill...",
        dry_run=dry_run,
    )

    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            result = backfill_remove_dupes()
        except Exception as e:
            db.session.rollback()
            log.exception("Got an exception while backfilling.", exception=e)
            return

        if dry_run:
            log.info("Dry run requested. Rolling back changes.")
            print(
                f"Found {result[0]} duplicate row(s) to be deleted from ReimbursementRequestSource table"
            )
            print(
                f"Found {result[1]} row(s) to update in ReimbursementRequestSourceRequests table"
            )
            print(
                f"Found {result[2]} row(s) to delete in ReimbursementRequestSourceRequests table"
            )
            db.session.rollback()
            return
        log.info(
            f"Removed {result[0]} duplicate row(s) from ReimbursementRequestSource table"
        )
        log.info(
            f"Updated {result[1]} row(s) in ReimbursementRequestSourceRequests table"
        )
        log.info(
            f"Removed {result[2]} duplicate row(s) in ReimbursementRequestSourceRequests table"
        )
        log.debug("Committing changes...")
        db.session.commit()
        log.debug("Finished.")


@click.command()
@click.option(
    "--dry_run",
    "-d",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
def main(dry_run: bool = False):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    backfill(dry_run=dry_run)


if __name__ == "__main__":
    main()
