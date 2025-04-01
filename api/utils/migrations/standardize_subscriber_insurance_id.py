from re import sub

from storage.connection import db
from utils.log import logger
from wallet.models.reimbursement_wallet import MemberHealthPlan

log = logger(__name__)


def standardize_subscriber_insurance_id(subscriber_id: str) -> str:
    """
    Standardizes the subscriber insurance ID by removing spaces, dashes, and slashes,
    and converting it to uppercase.
    """
    return sub(r"[^a-zA-Z0-9]", "", subscriber_id).upper()


def standardize_subscriber_insurance_id_for_all_member_health_plans(
    is_dry_run: bool = True,
) -> None:
    """
    Standardizes the subscriber insurance ID for all Member Health Plans.
    """
    log.info("Querying all health plans")
    # We currently have fewer than 7500 Member Health Plans,
    # so we can afford to do this in a single query..
    member_health_plans = MemberHealthPlan.query.all()
    session = db.session().using_bind("default")
    log.info("Queried all health plans", num_plans=len(member_health_plans))
    replaced_ids = []
    for member_health_plan in member_health_plans:
        if member_health_plan.subscriber_insurance_id:
            standardized_id = standardize_subscriber_insurance_id(
                member_health_plan.subscriber_insurance_id
            )
            if member_health_plan.subscriber_insurance_id.upper() != standardized_id:
                replaced_ids.append(
                    f"[{member_health_plan.subscriber_insurance_id}, id={member_health_plan.id}]"
                )
            member_health_plan.subscriber_insurance_id = standardized_id
    log.info(
        "Unexpected characters",
        impacted_ids=";".join(replaced_ids),
        num_ids=len(replaced_ids),
    )
    if not is_dry_run:
        for idx in range(0, len(member_health_plans), 100):
            batch = member_health_plans[idx : idx + 100]
            log.info(
                "Saving batch of health plans",
                index=idx,
                is_dry_run=is_dry_run,
                batch_size=len(batch),
            )
            session.add_all(batch)
            session.commit()
            log.info("Saved batch of health plans.", index=idx)


def backfill(dry_run: bool = False) -> None:
    log.info(
        "Executing standardize_subscriber_insurance_id_for_all_member_health_plans.",
        dry_run=dry_run,
    )
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            with db.session.no_autoflush:
                standardize_subscriber_insurance_id_for_all_member_health_plans(
                    is_dry_run=dry_run
                )
        except Exception as e:
            log.error("Got an exception while updating.", error=e)
            return
        log.info("Finished.")


def main(dry_run: bool = True) -> None:
    backfill(dry_run=dry_run)


if __name__ == "__main__":
    main()
