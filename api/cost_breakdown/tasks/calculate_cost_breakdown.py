import pymysql
import sqlalchemy
from rq import get_current_job

from common import stats
from common.global_procedures.constants import UNAUTHENTICATED_PROCEDURE_SERVICE_URL
from common.global_procedures.procedure import ProcedureService
from cost_breakdown.constants import (
    IS_INTEGRATIONS_K8S_CLUSTER,
    CostBreakdownTriggerSource,
)
from cost_breakdown.cost_breakdown_processor import CostBreakdownProcessor
from cost_breakdown.errors import (
    CostBreakdownDatabaseException,
    PayerDisabledCostBreakdownException,
)
from cost_breakdown.models.cost_breakdown import SystemUser
from cost_breakdown.wallet_balance_reimbursements import deduct_balance
from direct_payment.billing.tasks.rq_job_create_bill import (
    create_member_and_employer_bill,
    create_member_bill,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.utils.procedure_utils import (
    get_currency_balance_from_credit_wallet_balance,
)
from storage.connection import db
from tasks.queues import job
from utils.cache import redis_client
from utils.log import logger
from wallet.models.constants import BenefitTypes
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.utils.alegeus.claims.sync import (
    get_wallet_with_pending_claims,
    sync_pending_claims,
)

log = logger(__name__)

METRIC_NAME = "api.cost_breakdown.tasks.calculate_cost_breakdown"
JOB_NAME = "calculate_cost_breakdown_async"


def incr_metric(method_name, pod_name, tags):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    stats.increment(
        metric_name=f"{METRIC_NAME}.{method_name}",
        pod_name=pod_name,
        tags=tags,
    )


@job("priority", service_ns="cost_breakdown", team_ns="payments_platform")
def calculate_cost_breakdown_async(wallet_id: int, treatment_procedure_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    try:
        calculate_cost_breakdown(
            wallet_id=wallet_id,
            treatment_procedure_id=treatment_procedure_id,
            use_async=True,
        )
    finally:
        current_job = get_current_job()
        redis_cli = redis_client()
        key: str = f"cost_breakdown_rq:{wallet_id}"
        log.info(f"Remove job id {current_job.id} from redis key {key}")
        redis_cli.lrem(key, 0, current_job.id)


def calculate_cost_breakdown(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    wallet_id: int, treatment_procedure_id: int, use_async=True
):
    log.info(
        "Starting job to calculate cost breakdown",
        wallet_id=wallet_id,
        treatment_procedure_id=treatment_procedure_id,
    )
    wallet = ReimbursementWallet.query.get(wallet_id)

    if not wallet:
        log.error("Invalid wallet id", wallet_id=wallet_id)
        incr_metric(
            JOB_NAME,
            stats.PodNames.PAYMENTS_PLATFORM,
            ["success:false", "reason:invalid_wallet_id"],
        )
        return

    treatment_procedure = TreatmentProcedure.query.get(treatment_procedure_id)
    if not treatment_procedure:
        log.error(
            "Invalid treatment procedure id",
            treatment_procedure_id=treatment_procedure_id,
        )
        incr_metric(
            JOB_NAME,
            stats.PodNames.PAYMENTS_PLATFORM,
            ["success:false", "reason:invalid_treatment_procedure_id"],
        )
        return

    # sync claims belonging to the wallet with Alegeus
    try:
        wallet_with_claims = get_wallet_with_pending_claims(wallet=wallet)
        if not wallet_with_claims:
            log.info(
                "No pending claims from wallet",
                wallet_id=str(wallet_id),
                treatment_procedure_id=str(treatment_procedure_id),
            )
        else:
            log.info(
                "Sync pending claims during calculating cost breakdown",
                wallet_id=str(wallet_id),
                treatment_procedure_id=str(treatment_procedure_id),
            )
            sync_pending_claims([wallet_with_claims])
    except Exception as e:
        log.error(
            "error in syncing pending claims",
            wallet_id=str(wallet_id),
            treatment_procedure_id=str(treatment_procedure_id),
            exc_info=True,
            error=str(e),
        )
        incr_metric(
            JOB_NAME,
            stats.PodNames.PAYMENTS_PLATFORM,
            ["success:false", "reason:sync_pending_claims_error"],
        )
        raise e

    benefit_type = wallet.category_benefit_type(
        request_category_id=treatment_procedure.reimbursement_request_category_id
    )

    wallet_balance = None
    if benefit_type == BenefitTypes.CYCLE:
        wallet_balance = get_currency_balance_from_credit_wallet_balance(
            treatment_procedure=treatment_procedure
        )

    processor = CostBreakdownProcessor(
        procedure_service_client=(
            ProcedureService(base_url=UNAUTHENTICATED_PROCEDURE_SERVICE_URL)
            if IS_INTEGRATIONS_K8S_CLUSTER
            else ProcedureService(internal=True)
        ),
        system_user=SystemUser(trigger_source=CostBreakdownTriggerSource.CLINIC.value),
    )
    # note this performs a commit via the param store_to_db: Optional[bool] = True
    try:
        cost_breakdown = processor.get_cost_breakdown_for_treatment_procedure(
            wallet=wallet,
            treatment_procedure=treatment_procedure,
            wallet_balance=wallet_balance,
        )
    except PayerDisabledCostBreakdownException:
        log.info(
            "Payer disabled cost breakdown",
            wallet_id=str(wallet_id),
            treatment_procedure_id=treatment_procedure_id,
            member_id=treatment_procedure.member_id,
        )
        incr_metric(
            JOB_NAME,
            stats.PodNames.PAYMENTS_PLATFORM,
            ["success:false", "reason:payer_disabled_cost_breakdown"],
        )
        return
    except (
        sqlalchemy.exc.OperationalError,
        pymysql.err.InternalError,
        pymysql.err.OperationalError,
    ):
        log.error(
            "error running cost breakdown",
            wallet_id=str(wallet_id),
            treatment_procedure_id=treatment_procedure_id,
            member_id=treatment_procedure.member_id,
        )
        incr_metric(
            JOB_NAME,
            stats.PodNames.PAYMENTS_PLATFORM,
            ["success:false", "reason:cost_breakdown_error"],
        )
        raise CostBreakdownDatabaseException(
            "Database error occurred."
        )  # raise a new exception to prevent PHI from being logged
    except Exception as e:
        log.error(
            "error running cost breakdown",
            wallet_id=str(wallet_id),
            treatment_procedure_id=treatment_procedure_id,
            member_id=treatment_procedure.member_id,
            exc_info=True,
            error=str(e),
        )
        incr_metric(
            JOB_NAME,
            stats.PodNames.PAYMENTS_PLATFORM,
            ["success:false", "reason:cost_breakdown_error"],
        )
        raise e

    treatment_procedure.cost_breakdown_id = cost_breakdown.id
    try:
        db.session.add(treatment_procedure)
        db.session.commit()
        # also trigger bill creation
        _create_bills(
            treatment_procedure, cost_breakdown, wallet.id, use_async=use_async
        )
        deduct_balance(
            treatment_procedure=treatment_procedure,
            cost_breakdown=cost_breakdown,
            wallet=wallet,
            procedure_service_client=processor.procedure_service_client,
        )
        log.info(
            "Finished job to calculate cost breakdown",
            cost_breakdown_id=cost_breakdown.id,
        )
        incr_metric(
            JOB_NAME,
            stats.PodNames.PAYMENTS_PLATFORM,
            ["success:true"],
        )
    except Exception as e:
        log.error(
            "error adding cost breakdown to treatment procedure",
            cost_breakdown_id=cost_breakdown.id,
            treatment_procedure_id=treatment_procedure_id,
            error=str(e),
        )
        incr_metric(
            JOB_NAME,
            stats.PodNames.PAYMENTS_PLATFORM,
            ["success:false", "reason:add_cost_breakdown_to_treatment"],
        )


def _create_bills(treatment_procedure, cost_breakdown, wallet_id, use_async=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if use_async:
        if treatment_procedure.status in [
            TreatmentProcedureStatus.COMPLETED,
            TreatmentProcedureStatus.PARTIALLY_COMPLETED,
        ]:
            create_member_and_employer_bill.delay(
                treatment_procedure_id=treatment_procedure.id,
                cost_breakdown_id=cost_breakdown.id,
                wallet_id=wallet_id,
                treatment_procedure_status=treatment_procedure.status,
            )
        else:
            create_member_bill.delay(
                treatment_procedure_id=treatment_procedure.id,
                cost_breakdown_id=cost_breakdown.id,
                wallet_id=wallet_id,
                treatment_procedure_status=treatment_procedure.status,
            )
    else:
        if treatment_procedure.status in [
            TreatmentProcedureStatus.COMPLETED,
            TreatmentProcedureStatus.PARTIALLY_COMPLETED,
        ]:
            create_member_and_employer_bill(
                treatment_procedure_id=treatment_procedure.id,
                cost_breakdown_id=cost_breakdown.id,
                wallet_id=wallet_id,
                treatment_procedure_status=treatment_procedure.status,
            )
        else:
            create_member_bill(
                treatment_procedure_id=treatment_procedure.id,
                cost_breakdown_id=cost_breakdown.id,
                wallet_id=wallet_id,
                treatment_procedure_status=treatment_procedure.status,
            )
