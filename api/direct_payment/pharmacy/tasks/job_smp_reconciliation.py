"""
Job to upload maven pharmacy direct payment reconciliation file to SMP SFTP server.
"""

import argparse
import sys
from datetime import datetime, timedelta
from typing import Optional

from app import create_app
from utils.log import logger

log = logger(__name__)


def main():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    args = _generate_args()
    with create_app().app_context():
        status = execute_job(args.dry_run, args.start_time, args.end_time)
    sys.exit(status)


def _generate_args():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry_run",
        type=lambda x: {"true": True, "false": False}[x],
        required=True,
        help="Valid value: true or false (all lower case). true will upload to SMP. false will print file content locally",
    )
    parser.add_argument(
        "--start_time",
        type=int,
        required=False,
        help="Start unix epoch time in seconds in UTC to generate reconciliation file",
    )
    parser.add_argument(
        "--end_time",
        type=int,
        required=False,
        help="End unix epoch time in seconds in UTC to generate reconciliation file",
    )
    args = parser.parse_args()
    return args


def execute_job(
    dry_run: bool, start_time: Optional[int] = None, end_time: Optional[int] = None
) -> bool:
    log.info("SMP Reconciliation Job Started.")
    # Import here because SQLAlchemy.
    from direct_payment.pharmacy.tasks.libs.smp_reconciliation_file import (
        generate_reconciliation_report,
    )

    # fmt: off
    # mypy ignore is moved by black causing failure. remove this when
    # no-redef is addressed
    end_time: int = (  # type: ignore[no-redef] # Name "end_time" already defined on line 47
        end_time
        or int(
            datetime.utcnow()
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .timestamp()
        )
    )
    # fmt: on
    start_time: int = start_time or int(end_time - timedelta(days=1).total_seconds())  # type: ignore[no-redef] # Name "start_time" already defined on line 47

    # Note: Use end_time as start since end_time is in the past 1 day
    success = generate_reconciliation_report(
        dry_run=dry_run, start_time=start_time, end_time=end_time
    )
    if success:
        log.info("SMP Reconciliation Job Succeeded.")
    else:
        log.error("SMP Reconciliation Job Failed.")
    return not success


if __name__ == "__main__":
    main()
