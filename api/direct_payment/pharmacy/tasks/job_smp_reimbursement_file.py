import argparse
import sys

from app import create_app
from direct_payment.pharmacy.tasks.libs.rx_file_processor import process_smp_file
from direct_payment.pharmacy.tasks.libs.smp_reimbursement_file import (
    ReimbursementFileProcessor,
)
from utils.log import logger

log = logger(__name__)


def main() -> None:
    """
    Job to download maven pharmacy partner SMP reimbursement file from SMPs SFTP server and process invoices creating
    Approved Reimbursement Requests.
    """
    args = _generate_args()
    with create_app().app_context():
        status = execute_job(args.dry_run)
    sys.exit(status)


def _generate_args():  # type: ignore[no-untyped-def]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        type=lambda x: {"true": True, "false": False}[x],
        required=True,
        help="True will download from SMP and print number rows of data to be processed,"
        " False will process and save data from file.",
    )
    args = parser.parse_args()
    return args


def execute_job(dry_run: bool) -> bool:
    log.info("Reimbursement Job Started.")
    processor = ReimbursementFileProcessor(dry_run=dry_run)
    success = process_smp_file(processor)
    if success:
        log.info("Reimbursement Job Succeeded.")
    else:
        log.error("Reimbursement Job Failed.")
    return not success


if __name__ == "__main__":
    main()
