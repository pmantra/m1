"""
python3 -- utils/migrations/fix_premera_subscriber_ids.py
"""
"""
fix_premera_subscriber_ids.py

Modify the subscriber_insurance_id for PREMERA health plans with common faulty patterns.

Usage:
  fix_premera_subscriber_ids.py [--dryrun]

Options:
  -h --help     Show this screen.
  --dryrun       Dry run the script. 
"""
from typing import Callable, List

from docopt import docopt
from sqlalchemy import and_, func

import app
from payer_accumulator.models.payer_list import Payer
from storage.connection import db
from utils.log import logger
from wallet.models.reimbursement_organization_settings import EmployerHealthPlan
from wallet.models.reimbursement_wallet import MemberHealthPlan

log = logger(__name__)

pattern_to_fix = {
    "^AQT [0-9]{9} 0[0-9]$": lambda x: x.removeprefix("AQT").replace(" ", ""),
    "^AQT [0-9]{9}0[0-9]$": lambda x: x.removeprefix("AQT").replace(" ", ""),
    "^AQT[0-9]{9}0[0-9]$": lambda x: x.removeprefix("AQT"),
    "^[0-9]{9} 0[0-9]$": lambda x: x.replace(" ", ""),
    "^[0-9]{9}-0[0-9]$": lambda x: x.replace("-", ""),
}


def find_plans(pattern: str) -> List[MemberHealthPlan]:
    return (
        db.session.query(
            MemberHealthPlan
        )  # noqa # allow sqlalchemy query outside of the repo for util scripts
        .join(
            EmployerHealthPlan,
            EmployerHealthPlan.id == MemberHealthPlan.employer_health_plan_id,
        )
        .join(
            Payer,
            Payer.id == EmployerHealthPlan.benefits_payer_id,
        )
        .filter(
            and_(
                Payer.payer_name == "PREMERA",
                func.length(MemberHealthPlan.subscriber_insurance_id) != 11,
                MemberHealthPlan.subscriber_insurance_id.op("REGEXP")(pattern),
            )
        )
        .all()
    )


def fix_plans(pattern: str, fix_fn: Callable) -> List[MemberHealthPlan]:
    log.info(f"Fixing health plans with the following subscriber_id pattern: {pattern}")
    updated_health_plans = []
    plans_with_bad_ids = find_plans(pattern)
    log.info(
        f"{len(plans_with_bad_ids)} health plans with {pattern} subscriber_ids found."
    )
    for plan in plans_with_bad_ids:
        plan.subscriber_insurance_id = fix_fn(plan.subscriber_insurance_id)
        updated_health_plans.append(plan)
    return updated_health_plans


if __name__ == "__main__":
    dryrun = docopt(__doc__)["--dryrun"]
    with app.create_app().app_context():
        for given_pattern, fix_function in pattern_to_fix.items():
            updated_health_plans = fix_plans(given_pattern, fix_function)
            if dryrun:
                log.info(
                    f"DRYRUN: Would update {len(updated_health_plans)} health plans for pattern {given_pattern}."
                )
            else:
                db.session.add_all(updated_health_plans)
                db.session.commit()
                log.info(
                    f"LIVE RUN: Updated {len(updated_health_plans)} health plans for pattern {given_pattern}."
                )
