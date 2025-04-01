"""
python3 -- utils/migrations/hours_for_health_plan_dates.py
"""
import datetime

from sqlalchemy import func

import app
from storage.connection import db
from utils.log import logger
from wallet.models.reimbursement_wallet import MemberHealthPlan

log = logger(__name__)


def update_plans():
    # get all health plans with bad end times
    plan_count = MemberHealthPlan.query.filter(  # noqa
        func.date_format(MemberHealthPlan.plan_end_at, "%H:%i:%s") != "23:59:59",
        MemberHealthPlan.plan_end_at is not None,
    ).count()
    log.info(
        f"Initial Count of Member Health Plans with Invalid End Times: {plan_count}"
    )
    # 2306 in prod, 1/7/2025

    plans_updated = 0
    plans_failed = 0
    plans = MemberHealthPlan.query.filter(  # noqa
        func.date_format(MemberHealthPlan.plan_end_at, "%H:%i:%s") != "23:59:59",
        MemberHealthPlan.plan_end_at is not None,
    ).all()
    if len(plans) == 0:
        log.info("Retrieved no new plans to update.")
        return
    for plan in plans:
        plan.plan_end_at = datetime.datetime.combine(
            plan.plan_end_at, datetime.time(23, 59, 59)
        )
        try:
            db.session.add(plan)
            db.session.commit()
            plans_updated += 1
        except Exception as e:
            db.session.rollback()
            log.error(f"Failed to update {plan}. Error: {e}")
            plans_failed += 1
            continue
    log.info(f"Number of Health Plans Updated: {plans_updated}")
    log.info(f"Errors: {plans_failed}")
    log.info(f"Total: {plans_updated+plans_failed} out of {plan_count}")


if __name__ == "__main__":
    with app.create_app().app_context():
        update_plans()
