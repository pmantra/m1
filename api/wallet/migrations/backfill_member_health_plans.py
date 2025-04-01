"""
Job to backfill Member Health Plans with employer health plan dates.
This will only backfill plans with no dates attached, so it should be safe to rerun.

usage:
    python3 wallet/migrations/backfill_member_health_plans.py               Dry run of the script
    python3 wallet/migrations/backfill_member_health_plans.py live_run      Live run of the script
"""
import sys
from datetime import datetime
from typing import List

from app import create_app
from storage.connection import db
from utils.log import logger
from wallet.models.reimbursement import ReimbursementRequestCategory  # noqa
from wallet.models.reimbursement_organization_settings import EmployerHealthPlan
from wallet.models.reimbursement_wallet import MemberHealthPlan

log = logger(__name__)


LIMIT = 100


def output(msg):
    log.info(f"{msg}")


def check_plans_to_migrate() -> List[int]:
    # How much migration is there to do?
    plans = (
        db.session.query(MemberHealthPlan.id)
        .filter(
            MemberHealthPlan.plan_start_at.is_(None),
            MemberHealthPlan.plan_end_at.is_(None),
            MemberHealthPlan.employer_health_plan_id is not None,
        )
        .all()
    )
    output(f"Member Health Plans missing dates: {len(plans)}")
    return [plan[0] for plan in plans]


def check_migrated_plans_match_employer_health_plans():
    # check all plans match their employer health plan dates
    total_plans = MemberHealthPlan.query.count()
    number_of_matched_plans = (
        MemberHealthPlan.query.join(
            EmployerHealthPlan,
            MemberHealthPlan.employer_health_plan_id == EmployerHealthPlan.id,
        )
        .filter(
            MemberHealthPlan.plan_start_at == EmployerHealthPlan.start_date,
            MemberHealthPlan.plan_end_at == EmployerHealthPlan.end_date,
        )
        .count()
    )
    difference = total_plans - number_of_matched_plans
    output(
        f"Number of Member Health Plans that don't match their associated Employer Health Plans: {difference}"
    )


def backfill(id, dry_run=True):
    output(f"Attempting to update member health plan {id}")
    errors = []
    try:
        mhp, ehp = (
            db.session.query(MemberHealthPlan, EmployerHealthPlan)
            .filter(
                MemberHealthPlan.id == id,
                MemberHealthPlan.plan_start_at.is_(None),
                MemberHealthPlan.plan_end_at.is_(None),
                MemberHealthPlan.employer_health_plan_id is not None,
            )
            .join(
                EmployerHealthPlan,
                EmployerHealthPlan.id == MemberHealthPlan.employer_health_plan_id,
            )
            .first()
        )

        if not mhp:
            errors.append(id)
            output(f"ERROR: No valid Member Health Plan found for id {id}")

        if not ehp:
            errors.append(id)
            output(f"ERROR: No Employer Health Plan found for {mhp}")
            return None

        mhp.plan_start_at = datetime.fromordinal(ehp.start_date.toordinal())
        mhp.plan_end_at = datetime.fromordinal(ehp.end_date.toordinal())
        output(
            f"Updated {mhp} for wallet {mhp.reimbursement_wallet_id} and employer health plan {ehp}."
        )

        if dry_run is False:
            output("Applying changes.")
            db.session.add(mhp)
            db.session.commit()
        else:
            output("Dry Run, changes not applied.")
    except Exception as e:
        db.session.rollback()
        errors.append(id)
        output(f"ERROR: Error {e} for Member Health Plan {id}")
    return errors


def main(dry_run):
    output(f"Dry Run: {dry_run}")
    check_migrated_plans_match_employer_health_plans()
    plans_to_migrate = check_plans_to_migrate()
    all_errors = []
    for id in plans_to_migrate:
        errors = backfill(id, dry_run)
        all_errors += errors
    if all_errors:
        output(f"Failed to update the following plans: {all_errors}")


if __name__ == "__main__":
    with create_app().app_context():
        input_dry_run = True
        if len(sys.argv) > 1:
            input_dry_run = False if sys.argv[1] == "live_run" else True
        main(input_dry_run)
    sys.exit()
