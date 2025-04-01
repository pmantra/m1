import datetime

from common import stats
from tasks.queues import job
from utils.log import logger
from wallet.config import use_alegeus_for_reimbursements
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.utils.alegeus.edi_processing.edi_record_imports import (
    upload_ib_file_to_alegeus,
    upload_il_file_to_alegeus,
)
from wallet.utils.alegeus.edi_processing.process_edi_new_employer_configurations import (
    upload_new_employer_configurations,
)
from wallet.utils.alegeus.edi_processing.process_edi_transactions import (
    download_and_process_alegeus_transactions_export,
)

log = logger(__name__)


@job
def upload_employee_demographics_ib_file_to_alegeus(wallet_id, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    This job uploads an IB file to Alegeus EDI in order to update a users address
    This is done because their API doesn't take international addresses, and we'll use
    EDI to update shipping address to Canadian Addresses for debit card as a workaround.
    """
    if use_alegeus_for_reimbursements():
        from app import create_app

        app = create_app()

        with app.app_context():
            job_start_time = datetime.datetime.utcnow()

            log.info(
                "Starting job to upload employee demographic EDI info file to alegeus."
            )
            wallet = ReimbursementWallet.query.get(wallet_id)
            tag = upload_ib_file_to_alegeus(wallet, user_id)

            time_to_complete_job = datetime.datetime.utcnow() - job_start_time

            stats.histogram(
                metric_name="api.wallet.tasks.alegeus.upload_ib_file_to_alegeus",
                pod_name=stats.PodNames.PAYMENTS_POD,
                metric_value=time_to_complete_job.total_seconds(),
            )

            tags = [f"success:{tag}"]
            stats.increment(
                metric_name="api.wallet.tasks.alegeus.upload_employee_demographics_ib_file_to_alegeus",
                pod_name=stats.PodNames.PAYMENTS_POD,
                tags=tags,
            )


@job
def upload_transactions_request_to_alegeus() -> None:
    """
    This job creates a CSV to upload to Alegeus requesting transaction history for all debit card enabled orgs.
    """
    if use_alegeus_for_reimbursements():
        from app import create_app

        app = create_app()

        with app.app_context():
            job_start_time = datetime.datetime.utcnow()

            log.info("Starting job to upload transaction request csv to alegeus.")

            tag = upload_il_file_to_alegeus()

            time_to_complete_job = datetime.datetime.utcnow() - job_start_time

            stats.histogram(
                metric_name="api.wallet.tasks.alegeus.upload_il_file_to_alegeus",
                pod_name=stats.PodNames.PAYMENTS_POD,
                metric_value=time_to_complete_job.total_seconds(),
            )

            tags = [f"success:{tag}"]
            stats.increment(
                metric_name="api.wallet.tasks.alegeus.upload_transactions_request_to_alegeus",
                pod_name=stats.PodNames.PAYMENTS_POD,
                tags=tags,
            )


@job
def download_transactions_alegeus(is_retry=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    This job downloads Alegeus requesting transaction history for all debit card enabled orgs.
    """
    if use_alegeus_for_reimbursements():
        from app import create_app

        app = create_app()

        with app.app_context():
            job_start_time = datetime.datetime.utcnow()

            log.info("Starting job to download transaction export from alegeus.")

            tag = download_and_process_alegeus_transactions_export(is_retry=is_retry)

            time_to_complete_job = datetime.datetime.utcnow() - job_start_time

            stats.histogram(
                metric_name="api.wallet.tasks.alegeus.process_alegeus_transactions",
                pod_name=stats.PodNames.PAYMENTS_POD,
                metric_value=time_to_complete_job.total_seconds(),
            )

            tags = [f"success:{tag}"]
            stats.increment(
                metric_name="api.wallet.tasks.alegeus.process_alegeus_transactions",
                pod_name=stats.PodNames.PAYMENTS_POD,
                tags=tags,
            )


@job()
def upload_and_process_new_employer_configs_to_alegeus(data, org_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if use_alegeus_for_reimbursements():
        from app import create_app

        app = create_app()

        with app.app_context():
            job_start_time = datetime.datetime.utcnow()

            log.info("Starting job to upload employer configuration files to alegeus.")

            tag = upload_new_employer_configurations(data, org_id)

            time_to_complete_job = datetime.datetime.utcnow() - job_start_time

            stats.histogram(
                metric_name="api.wallet.tasks.alegeus_edi.upload_and_process_new_employer_configs_to_alegeus",
                pod_name=stats.PodNames.PAYMENTS_POD,
                metric_value=time_to_complete_job.total_seconds(),
            )

            tags = [f"success:{tag}"]
            stats.increment(
                metric_name="api.wallet.tasks.alegeus_edi.upload_and_process_new_employer_configs_to_alegeus",
                pod_name=stats.PodNames.PAYMENTS_POD,
                tags=tags,
            )
