"""
Job to upload maven pharmacy direct payment eligibility file to SMP SFTP server.
"""
import argparse
import sys

from app import create_app
from utils.log import logger

log = logger(__name__)


def main():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    args = _generate_args()
    with create_app().app_context():
        status = execute_job(args.dry_run)
    sys.exit(status)


def _generate_args():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        type=lambda x: {"true": True, "false": False}[x],
        required=True,
        help="True will upload to SMP, False will save file locally",
    )
    args = parser.parse_args()
    return args


def execute_job(dry_run: bool) -> bool:
    log.info("Job Started.")
    # Import here because SQLAlchemy.
    from direct_payment.pharmacy.tasks.libs.smp_eligibility_file import (
        ship_eligibility_file_to_smp,
    )

    success = ship_eligibility_file_to_smp(dry_run=dry_run)
    if success:
        log.info("Job Succeeded.")
    else:
        log.error("Job Failed.")
    return not success


if __name__ == "__main__":
    main()
