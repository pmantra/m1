from __future__ import annotations

import click

from storage.connection import db
from utils.log import logger
from wallet.annual_insurance_questionnaire_constants import (
    ONBOARDED_TO_MMB_IN_2024_ORG_IDS,
)

log = logger(__name__)


def get_updateable_ids(org_ids: set[int]) -> list[int]:
    my_query = """
    SELECT
    id
    FROM reimbursement_organization_settings
    WHERE organization_id IN :org_ids    
    """
    res = db.session.execute(my_query, {"org_ids": org_ids}).fetchall()
    to_return = [r[0] for r in res]
    log.info(f"{len(res)} rows will be updated", ids=to_return)
    return to_return


def _update_roses(ros_ids: list[int]):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    my_query = """
    UPDATE reimbursement_organization_settings
    SET allowed_members = 'SHAREABLE'
    WHERE id IN :ros_ids
    """
    db.session.execute(my_query, {"ros_ids": ros_ids})
    log.info("Update completed", ros_ids=ros_ids)


def _get_affected_count() -> int:  # type: ignore[return] # Missing return statement
    my_query = """ 
    SELECT ROW_COUNT() AS affected_rows 
    """
    cnt = db.session.execute(my_query).scalar()
    log.info(f"{cnt} rows were updated.")


def _confirmation(exp: list[int]) -> list[int]:  # type: ignore[return] # Missing return statement
    my_query = """
    SELECT 
    id  
    FROM reimbursement_organization_settings
    WHERE allowed_members = 'SHAREABLE'   
    """
    rows = db.session.execute(my_query).fetchall()
    res = {r[0] for r in rows}
    assert res == set(exp)


@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
def update_data(dry_run: bool = True):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    try:
        ros_ids: list[int] = get_updateable_ids({ONBOARDED_TO_MMB_IN_2024_ORG_IDS})  # type: ignore[arg-type] # Argument 1 to <set> has incompatible type "Set[int]"; expected "int"
        _update_roses(ros_ids)
        affected_count: int = _get_affected_count()
        _confirmation(ros_ids)
    except Exception as e:
        db.session.rollback()
        log.exception("Got an exception while updating.", error=str(e))
        return

    if dry_run:
        log.info(
            f"Dry run requested. Rolling back changes. {affected_count=}",
            count=affected_count,
        )
        db.session.rollback()
        return

    log.info("Committing changes...", count=affected_count)
    db.session.commit()
    log.info("Finished.")


if __name__ == "__main__":
    from app import create_app

    with create_app(task_instance=True).app_context():
        update_data(False)
