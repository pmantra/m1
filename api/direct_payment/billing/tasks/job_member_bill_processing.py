"""
Job to process NEW MEMBER bills over a date range. This job is safe to rerun.
"""
import sys

from app import create_app
from utils.log import logger

log = logger(__name__)


def main() -> None:
    with create_app().app_context():
        status = process_member_bills_and_summarize(False)
    sys.exit(status)


def process_member_bills_and_summarize(dry_run: bool) -> bool:
    # Import here because SQLAlchemy.
    from direct_payment.billing.tasks.lib.member_bill_processing_functions import (
        process_member_bills_driver,
    )

    log.info(f"Running with {dry_run=}.")
    results = process_member_bills_driver(dry_run=dry_run)
    failure_count = sum(1 for status in results.values() if not status.success_flag)
    if failure_count:
        log.error(
            "There were non payment-gateway errors. Please check the job logs. Job Failed.",
            failure_count=failure_count,
        )
    else:
        log.info("Job Succeeded.")
    to_return = failure_count > 0
    return to_return


if __name__ == "__main__":
    main()
