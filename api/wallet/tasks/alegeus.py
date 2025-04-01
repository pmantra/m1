import datetime
from typing import List

from common import stats
from models.profiles import Address
from storage import connection
from tasks.helpers import get_user
from tasks.queues import job
from utils.log import logger
from wallet import alegeus_api
from wallet.config import use_alegeus_for_reimbursements
from wallet.models.organization_employee_dependent import OrganizationEmployeeDependent
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.services.reimbursement_wallet_debit_card import remove_mobile_number
from wallet.utils.alegeus.claims.sync import get_wallets_with_pending_claims
from wallet.utils.alegeus.claims.sync import sync_pending_claims as sync
from wallet.utils.alegeus.common import get_all_alegeus_sync_claims_user_wallets
from wallet.utils.alegeus.connection import test_wca_connection, test_wcp_connection
from wallet.utils.alegeus.debit_cards.terminate_employees import (
    handle_terminated_employees,
)
from wallet.utils.alegeus.enrollments.enroll_wallet import (
    configure_wallet_allowed_category,
    create_dependent_demographic,
    update_dependent_demographic,
    update_employee_demographic,
    update_member_accounts,
)

log = logger(__name__)

metric_name = "api.wallet.tasks.alegeus.sync_pending_claims"


@job("priority", team_ns="payments_platform")
def process_sync_pending_claims_batch(
    wallet_ids: List[int],
) -> None:
    """
    This job syncs Statuses for PENDING ReimbursementRequest and ReimbursementClaim objects
    that have already been submitted to Alegeus.

    The ReimbursementWallet that they link to has been Qualified and configured in the Alegeus portal.

    In addition, this job is the child job of `sync_pending_claims` where it is spawned from.

    This child job will be limited to half the total size of the wallets that have pending claims.
    """

    log.info(
        "Starting a job batch to sync pending claims from alegeus.",
        wallets_to_claim_count=len(wallet_ids),
    )

    wallets = ReimbursementWallet.query.filter(
        ReimbursementWallet.id.in_(wallet_ids),
    ).all()
    wallets_to_claims = get_wallets_with_pending_claims(wallets)
    sync(wallets_to_claims, timeout=3)


@job("priority", team_ns="payments_platform")
def sync_pending_claims() -> None:
    """
    This job kicks off the sync of pending claims.
    The actual syncing occurs in batches in the child job called `process_sync_pending_claims_batch()`.

    In addition, this job will enqueue the actual sync with Alegeus in a batched approach. This means that
    this will spawn two child jobs when this main job kicks off.

    Overall this job grabs all the wallets w/ pending claims and then passes it to a new smaller job.
    """
    if use_alegeus_for_reimbursements():
        from app import create_app

        app = create_app()

        with app.app_context():
            job_start_time = datetime.datetime.utcnow()

            wallets = get_all_alegeus_sync_claims_user_wallets()
            wallets_to_pending_claims = get_wallets_with_pending_claims(wallets)
            wallet_ids = [wallet.wallet.id for wallet in wallets_to_pending_claims]

            child_half_count = (len(wallet_ids) + 1) // 2
            child_job_one_batch = wallet_ids[:child_half_count]
            child_job_two_batch = wallet_ids[child_half_count:]

            claim_ids = [
                claim.id
                for wallet_and_claims in wallets_to_pending_claims
                for claim in wallet_and_claims.claims
            ]
            log.info(
                "Coordinating creation of process_sync_pending_claims_batch jobs.",
                total_wallet_count=len(wallet_ids),
                total_pending_claims_count=len(claim_ids),
            )

            for wallet_batch in [child_job_one_batch, child_job_two_batch]:
                if wallet_batch:
                    process_sync_pending_claims_batch.delay(
                        wallet_ids=wallet_batch, job_timeout=1800
                    )

            time_to_complete_job = datetime.datetime.utcnow() - job_start_time

            stats.histogram(
                metric_name,
                pod_name=stats.PodNames.PAYMENTS_POD,
                metric_value=time_to_complete_job.total_seconds(),
            )


@job
def update_member_demographics(wallet_id: int, user_id: int) -> None:
    """
    This job uses the convenience function for calling the Alegeus API
    to add a member and populate demographic information in Alegeus.
    """
    if use_alegeus_for_reimbursements():
        wallet = ReimbursementWallet.query.filter(
            ReimbursementWallet.id == wallet_id
        ).one_or_none()

        if wallet:
            address = Address.query.filter(Address.user_id == user_id).one_or_none()
            job_start_time = datetime.datetime.utcnow()

            log.info("Starting job to update member demographics in Alegeus.")

            api = alegeus_api.AlegeusApi()
            success = update_employee_demographic(api, wallet, address)

            time_to_complete_job = datetime.datetime.utcnow() - job_start_time

            stats.histogram(
                metric_name="api.wallet.tasks.alegeus.update_member_demographics",
                pod_name=stats.PodNames.PAYMENTS_POD,
                metric_value=time_to_complete_job.total_seconds(),
            )

            if not success:
                log.warning(
                    "Alegeus update_member_demographics job failed.",
                    wallet_id=wallet.id,
                    user_id=user_id,
                )
        else:
            log.warning(
                "Alegeus update_member_demographics job failed.",
                wallet_id=wallet_id,
                user_id=user_id,
            )


@job
def update_or_create_dependent_demographics(
    wallet_id: int,
    dependent_id: int,
    is_created: bool,
) -> None:
    """
    This job uses the convenience function for calling the Alegeus API to update a
    member's dependents' demographic information in Alegeus.
    """
    if use_alegeus_for_reimbursements():
        wallet = ReimbursementWallet.query.filter(
            ReimbursementWallet.id == wallet_id
        ).one_or_none()

        if wallet:
            dependent = OrganizationEmployeeDependent.query.filter_by(
                id=dependent_id,
                reimbursement_wallet_id=wallet_id,
            ).one_or_none()

            if dependent:
                job_start_time = datetime.datetime.utcnow()

                log.info("Starting job to update dependent demographics in Alegeus.")

                api = alegeus_api.AlegeusApi()
                first_name = dependent.first_name or ""
                last_name = dependent.last_name or ""
                if is_created:
                    success, _ = create_dependent_demographic(
                        api,
                        wallet,
                        dependent.alegeus_dependent_id,
                        first_name,
                        last_name,
                    )
                else:
                    success = update_dependent_demographic(
                        api,
                        wallet,
                        dependent.alegeus_dependent_id,
                        first_name,
                        last_name,
                    )

                time_to_complete_job = datetime.datetime.utcnow() - job_start_time

                stats.histogram(
                    metric_name="api.wallet.tasks.alegeus.update_dependent_demographics",
                    pod_name=stats.PodNames.PAYMENTS_POD,
                    metric_value=time_to_complete_job.total_seconds(),
                )
                if not success:
                    log.warning(
                        f"Alegeus update_or_create_dependent_demographics job failed. wallet_id: {wallet.id}"
                        f" dependent_id: {dependent.id} is_created: {is_created}"
                    )
            else:
                log.warning(
                    f"Alegeus update_or_create_dependent_demographics job failed. Missing dependent: {dependent_id}"
                )
        else:
            log.warning(
                f"Alegeus update_or_create_dependent_demographics job failed. Missing wallet: {wallet_id}"
            )


@job
def remove_member_number(user_id: int, old_phone_number: str) -> None:
    """
    This job removes a member's phone number in Alegeus
    """
    if use_alegeus_for_reimbursements():
        user = get_user(user_id)
        if not user:
            log.error(
                f"Alegeus remove_member_number job failed. Missing User: {user_id}"
            )
            return

        job_start_time = datetime.datetime.utcnow()
        success = remove_mobile_number(user, old_phone_number)
        time_to_complete_job = datetime.datetime.utcnow() - job_start_time

        stats.histogram(
            metric_name="api.wallet.tasks.alegeus.remove_member_number",
            pod_name=stats.PodNames.PAYMENTS_POD,
            metric_value=time_to_complete_job.total_seconds(),
        )

        if not success:
            log.warning(f"Alegeus remove_member_number job failed. user_id: {user_id}")


@job
def handle_debit_card_terminated_employees() -> None:
    """
    This job audits all members with debit cards and checks against the Eligibility Service for
    employment status.  Terminated employees will have their cards set to temp inactive.
    """
    if use_alegeus_for_reimbursements():
        job_start_time = datetime.datetime.utcnow()
        success = handle_terminated_employees()
        time_to_complete_job = datetime.datetime.utcnow() - job_start_time

        stats.histogram(
            metric_name="api.wallet.tasks.alegeus.handle_debit_card_terminated_employees",
            pod_name=stats.PodNames.PAYMENTS_POD,
            metric_value=time_to_complete_job.total_seconds(),
        )

        if not success:
            log.warning("Alegeus handle_debit_card_terminated_employees job failed.")


@job
def test_api_connection() -> None:
    """
    This task executes GET requests to both Alegeus APIs to verify operational status.
    Neither request depends on any specific employer or user data.
    """
    wca_result = test_wca_connection()
    wcp_result = test_wcp_connection()

    if wca_result and wcp_result:
        tags = ["success:true"]
        log.info("Success testing Alegeus API connection.")
    else:
        tags = ["success:false"]
        log.error(
            "Error testing Alegeus API connection!", wca=wca_result, wcp=wcp_result
        )

    stats.increment(
        metric_name="api.wallet.alegeus.test_api_connection",
        pod_name=stats.PodNames.PAYMENTS_POD,
        tags=tags,
    )


@job
def add_new_member_accounts(start_date: datetime.date, organization_ids: list) -> None:
    """
    This job checks all the allowed plans for an organization, enrolls all qualified wallets into member accounts
    and creates associated reimbursement accounts.

    @param start_date The date object to filter plan start date by
    @param organization_ids A list of organizations
    """
    if use_alegeus_for_reimbursements():
        from app import create_app

        app = create_app()

        with app.app_context():
            job_start_time = datetime.datetime.utcnow()

            log.info("Starting job to update accounts in Alegeus.")

            tag = update_member_accounts(start_date, organization_ids)

            time_to_complete_job = datetime.datetime.utcnow() - job_start_time

            stats.histogram(
                metric_name="api.wallet.tasks.alegeus.add_new_member_accounts",
                pod_name=stats.PodNames.PAYMENTS_POD,
                metric_value=time_to_complete_job.total_seconds(),
            )

            tags = [f"success:{tag}"]
            stats.increment(
                metric_name="api.wallet.tasks.alegeus.add_new_member_accounts",
                pod_name=stats.PodNames.PAYMENTS_POD,
                tags=tags,
            )


@job(traced_parameters=("wallet_id", "allowed_category_id"))
def enroll_member_account(wallet_id: int, allowed_category_id: int) -> None:
    """
    This task configures an allowed categories plan in Alegeus for the wallet.
    """
    log.info(
        "starting enroll_member_account",
        wallet_id=str(wallet_id),
        allowed_category_id=str(allowed_category_id),
    )
    wallet = (
        connection.db.session.query(ReimbursementWallet)
        .filter(ReimbursementWallet.id == wallet_id)
        .one_or_none()
    )
    if not wallet:
        log.error(
            "Failed to configure wallet allowed category account in Alegeus.",
            wallet_id=str(wallet_id),
            allowed_category_id=str(allowed_category_id),
            error="Wallet or allowed category not found.",
        )
    else:
        try:
            configure_wallet_allowed_category(
                wallet=wallet, allowed_category_id=allowed_category_id
            )
        except Exception as e:
            log.error(
                "Failed to configure wallet allowed category account in Alegeus.",
                wallet_id=str(wallet_id),
                allowed_category_id=str(allowed_category_id),
                error=str(e),
            )
