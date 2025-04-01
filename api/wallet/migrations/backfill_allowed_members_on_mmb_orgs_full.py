from __future__ import annotations

from collections import defaultdict

import click

from storage.connection import db
from utils.log import logger
from wallet.migrations.config.backfill_allowed_members_on_mmb_orgs_full import (
    ROS_AND_ALLOWED_MEMBERS_TUPLES,
)

log = logger(__name__)


def _create_map() -> dict[str, list[int]]:
    to_return = defaultdict(list[int])
    for (ros_id, allowed_members_value) in ROS_AND_ALLOWED_MEMBERS_TUPLES:
        to_return[allowed_members_value].append(ros_id)
    return to_return


def _update_roses(created_map: dict[str, list[int]], dry_run: bool):
    tot_affected_count = 0
    for allowed_members_value, ros_ids in created_map.items():
        log.info(
            "Update started",
            ros_ids=ros_ids,
            allowed_members_value=allowed_members_value,
        )
        my_query = """
        UPDATE reimbursement_organization_settings
        SET allowed_members = :allowed_members_value
        WHERE id IN :ros_ids
        """
        db.session.execute(
            my_query,
            {"ros_ids": ros_ids, "allowed_members_value": allowed_members_value},
        )
        log.info(
            "Update completed (not committed)",
            ros_ids=ros_ids,
            allowed_members_value=allowed_members_value,
        )
        affected_count = _log_affected_count()
        tot_affected_count += affected_count
        if dry_run:
            log.info(
                f"Dry run requested. Rolling back changes. {affected_count=}",
                ros_ids=ros_ids,
                allowed_members_value=allowed_members_value,
                count=affected_count,
            )
            db.session.rollback()
            return
    log.info("Committing changes...", tot_affected_count=tot_affected_count)
    db.session.commit()
    log.info("Finished", tot_affected_count=tot_affected_count)


def _log_affected_count() -> int:
    my_query = """ 
    SELECT ROW_COUNT() AS affected_rows 
    """
    cnt = db.session.execute(my_query).scalar()
    log.info(f"{cnt} rows were updated.")
    return cnt


def _confirmation(created_map: dict[str, list[int]]):
    for allowed_members_value, ros_ids in created_map.items():

        my_query = """
            SELECT 
            COUNT(*)  
            FROM reimbursement_organization_settings
            WHERE 
                allowed_members = :allowed_members_value AND 
                id IN :ros_ids  
        """
        res = db.session.execute(
            my_query,
            {"ros_ids": ros_ids, "allowed_members_value": allowed_members_value},
        ).fetchall()
        if res != len(ros_ids):
            log.error(
                "Mismatch!",
                allowed_members_value=allowed_members_value,
                result_ct=res,
                exp_cnt=len(ros_ids),
            )


@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
def update_data(dry_run: bool = True):
    log.info("Begun.")
    try:
        created_map: dict[str, list[int]] = _create_map()
        _update_roses(created_map, dry_run)
        _confirmation(created_map)
    except Exception as e:
        db.session.rollback()
        log.exception("Got an exception while updating.", error=str(e))
        return

    log.info("Ended.")


if __name__ == "__main__":
    from app import create_app

    with create_app(task_instance=True).app_context():
        update_data(False)
