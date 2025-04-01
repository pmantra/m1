import argparse
import sys
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from app import create_app
from direct_payment.reconciliation.tasks.libs.generate_clinic_reconciliation_report import (
    ClinicReconciliationReportGenerator,
)
from utils.log import logger

log = logger(__name__)


def generate_reconciliation_report(
    dry_run: bool,
    group_name: str,
    clinic_names: List[str],
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
) -> Tuple[List, bool]:
    end_time = end_time or int(
        datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    )
    start_time = start_time or int(end_time - timedelta(days=1).total_seconds())

    log.info(
        "Job for generating CCRM reconciliation report starts",
        clinic_group_name=group_name,
        clinic_names=clinic_names,
        start_time=start_time,
        end_time=end_time,
    )

    report_generator = ClinicReconciliationReportGenerator(
        dry_run, group_name, clinic_names, start_time, end_time
    )

    records, success = report_generator.generate_clinic_reconciliation_report()
    if success:
        log.info(
            "Job for generating CCRM reconciliation report ends successfully",
            clinic_group_name=group_name,
            start_time=start_time,
            end_time=end_time,
            num_of_record_returned=len(records),
        )
    else:
        log.error(
            "Job for generating CCRM reconciliation report fails",
            clinic_group_name=group_name,
            start_time=start_time,
            end_time=end_time,
        )
    return records, success


def _generate_args():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry_run",
        type=lambda x: {"true": True, "false": False}[x],
        required=True,
        help="Valid value: true or false (all lower case). true will generate report. false will print file content locally",
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


def main() -> None:
    args = _generate_args()
    with create_app().app_context():
        _, success = generate_reconciliation_report(
            args.dry_run, args.start_time, args.end_time
        )
    sys.exit(not success)


if __name__ == "__main__":
    main()
