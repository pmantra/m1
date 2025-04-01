from common import stats
from tasks.queues import job
from utils import braze_events

NOTIFICATIONS_METRIC_PREFIX = "api.wallet.tasks.notifications"


@job
def debit_card_lost_stolen(debit_card):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    stats.increment(
        metric_name=f"{NOTIFICATIONS_METRIC_PREFIX}.debit_card_lost_stolen",
        pod_name=stats.PodNames.PAYMENTS_POD,
        tags=["success:true"],
    )
    braze_events.debit_card_lost_stolen(debit_card)


@job
def debit_card_temp_inactive(debit_card):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    stats.increment(
        metric_name=f"{NOTIFICATIONS_METRIC_PREFIX}.debit_card_temp_inactive",
        pod_name=stats.PodNames.PAYMENTS_POD,
        tags=["success:true"],
    )
    braze_events.debit_card_temp_inactive(debit_card)


@job
def debit_card_mailed(debit_card):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    stats.increment(
        metric_name=f"{NOTIFICATIONS_METRIC_PREFIX}.debit_card_mailed",
        pod_name=stats.PodNames.PAYMENTS_POD,
        tags=["success:true"],
    )
    braze_events.debit_card_mailed(debit_card)


@job
def debit_card_transaction_denied(reimbursement_request):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    stats.increment(
        metric_name=f"{NOTIFICATIONS_METRIC_PREFIX}.debit_card_transaction_denied",
        pod_name=stats.PodNames.PAYMENTS_POD,
        tags=["success:true"],
    )
    braze_events.debit_card_transaction_denied(reimbursement_request)


@job
def debit_card_transaction_needs_receipt(reimbursement_request):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    stats.increment(
        metric_name=f"{NOTIFICATIONS_METRIC_PREFIX}.debit_card_transaction_needs_receipt",
        pod_name=stats.PodNames.PAYMENTS_POD,
        tags=["success:true"],
    )
    braze_events.debit_card_transaction_needs_receipt(reimbursement_request)  # type: ignore[call-arg] # Missing positional arguments "amount", "date" in call to "debit_card_transaction_needs_receipt"


@job
def debit_card_transaction_approved(reimbursement_request):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    stats.increment(
        metric_name=f"{NOTIFICATIONS_METRIC_PREFIX}.debit_card_transaction_approved",
        pod_name=stats.PodNames.PAYMENTS_POD,
        tags=["success:true"],
    )
    braze_events.debit_card_transaction_approved(reimbursement_request)  # type: ignore[call-arg] # Missing positional arguments "amount", "date" in call to "debit_card_transaction_approved"


@job
def debit_card_transaction_insufficient_docs(reimbursement_request):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    stats.increment(
        metric_name=f"{NOTIFICATIONS_METRIC_PREFIX}.debit_card_transaction_insufficient_docs",
        pod_name=stats.PodNames.PAYMENTS_POD,
        tags=["success:true"],
    )
    braze_events.debit_card_transaction_insufficient_docs(reimbursement_request)  # type: ignore[call-arg] # Missing positional arguments "amount", "date" in call to "debit_card_transaction_insufficient_docs"
