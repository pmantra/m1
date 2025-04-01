from __future__ import annotations

import click

from storage.connection import db
from utils.log import logger
from wallet.annual_insurance_questionnaire_constants import ORGID_TO_HDHP_PLAN_NAME_MAP

log = logger(__name__)


def update_org_ids(org_to_plan_name: dict[int, str], dry_run=True):
    tot_affected_count = 0
    for i, (organization_id, alegeus_plan_id) in enumerate(org_to_plan_name.items()):
        log.info(
            "Update started",
            organization_id=organization_id,
            alegeus_plan_id=alegeus_plan_id,
        )
        my_query = """
            UPDATE reimbursement_plan
            SET organization_id = :organization_id
            WHERE alegeus_plan_id = :alegeus_plan_id
            """
        db.session.execute(
            my_query,
            {"organization_id": organization_id, "alegeus_plan_id": alegeus_plan_id},
        )
        affected_count = _get_affected_count()
        tot_affected_count += affected_count
        if i % 20 == 0:
            log.info(
                "Update completed (not committed)",
                loop_count=i,
                running_affected_count=tot_affected_count,
                payload_size=len(org_to_plan_name),
            )
    log.info(
        "Update completed (not committed)",
        running_count=tot_affected_count,
        payload_size=len(org_to_plan_name),
    )
    if dry_run:
        log.info("Dry run requested. Rolling back changes. ")
        db.session.rollback()
    else:
        log.info("Committing changes...", tot_affected_count=tot_affected_count)
        db.session.commit()
        log.info(
            "Finished",
            tot_affected_count=tot_affected_count,
            payload_size=len(org_to_plan_name),
        )


def _get_affected_count() -> int:
    my_query = """ 
    SELECT ROW_COUNT() AS affected_rows 
    """
    cnt = db.session.execute(my_query).scalar()
    if not cnt:
        log.info(f"{cnt} rows were updated.")
    return cnt


@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
def update_data(dry_run: bool = True):
    log.info("Begun.")
    try:
        update_org_ids(ORGID_TO_HDHP_PLAN_NAME_MAP, dry_run=dry_run)
    except Exception as e:
        db.session.rollback()
        log.exception("Got an exception while updating.", error=str(e))
        return
    log.info("Ended.")


if __name__ == "__main__":
    from app import create_app

    with create_app(task_instance=True).app_context():
        update_data(False)
