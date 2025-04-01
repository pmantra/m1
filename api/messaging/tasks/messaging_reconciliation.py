from datetime import datetime, timedelta

import ddtrace
from maven import feature_flags

from common import stats
from messaging.repository.message import MessageRepository
from messaging.services.zendesk import (
    MAVEN_TO_ZENDESK_RECONCILIATION_LIST_KEY,
    ReconciliationZendeskTicket,
    ZendeskInvalidRecordException,
)
from storage.connection import db
from tasks.queues import job
from utils import braze
from utils.cache import redis_client
from utils.constants import ZENDESK_RECONCILIATION_ERROR_COUNT_METRICS
from utils.flag_groups import CARE_DELIVERY_RELEASE
from utils.log import logger

log = logger(__name__)


# Number of max chunks of messages to get from db
# Given that each chunk is size 100, with 10 iterations should be more than enough
# given that we dont expect over 1000 messages to reconcile per day.
N_MAX_MESSAGES_CHUNKS = 10


def maven_to_zendesk_reconciliation_on() -> bool:
    return feature_flags.bool_variation(
        CARE_DELIVERY_RELEASE.ENABLE_MAVEN_TO_ZENDESK_RECONCILIATION_JOB,
        default=False,
    )


@job
@ddtrace.tracer.wrap()
def maven_to_zendesk_message_reconciliation(
    max_per_job_run: int = 50, dry_run: bool = False
) -> None:
    """
    Retry sending to zendesk messages that exist in the maven-to-zendesk redis reconciliation list.
    We will only process messages that are at least 5 min old because we don't want to try to
    reconcile messages that have been just created, as their send_to_zendesk jobs might be already scheduled to run.
    """
    # Check if ff is ON
    should_run = maven_to_zendesk_reconciliation_on()
    log.info(
        "maven_to_zendesk_message_reconciliation triggered",
        will_run=should_run,
    )
    if not should_run:
        return

    # this setting should be the same as api/messaging/services/zendesk.py
    # Get messages from reconciliation list
    redis_cli = redis_client()
    messages_to_reconcile = redis_cli.smembers(MAVEN_TO_ZENDESK_RECONCILIATION_LIST_KEY)
    total_n_messages_to_reconcile = len(messages_to_reconcile)

    # Metric to keep track of messages that need reconciliation
    stats.gauge(
        metric_name="mono.messaging.messaging_reconciliation.maven_to_zendesk.pending_to_reconcile",
        metric_value=total_n_messages_to_reconcile,
        pod_name=stats.PodNames.VIRTUAL_CARE,
    )

    # Messages must be at least 5 min old
    created_at_before = datetime.utcnow() - timedelta(minutes=5)
    # Messages must be at most 1 day old (we don't want to infinitely try to reconcile messages)
    created_at_after = datetime.utcnow() - timedelta(days=1)
    if total_n_messages_to_reconcile == 0:
        log.info(
            "maven_to_zendesk_message_reconciliation job picked up no messages to reconcile",
            created_at_before=created_at_before,
            created_at_after=created_at_after,
        )
        return

    log.info(
        "Running maven_to_zendesk_message_reconciliation job",
        max_per_job_run=max_per_job_run,
        total_n_messages_to_reconcile=total_n_messages_to_reconcile,
        messages_to_reconcile=messages_to_reconcile,
        created_at_before=created_at_before,
        created_at_after=created_at_after,
    )

    n_messages_reconciled = 0
    for message_id in messages_to_reconcile:

        if n_messages_reconciled >= max_per_job_run:
            log.info(
                "Reached max number of messages to reconcile per run. Breaking reconciliation",
            )
            break
        log.info(
            "Processing message as part of maven_to_zendesk_message_reconciliation",
            message_id=message_id,
        )

        # Check that message is old enough
        m = MessageRepository().get(id=message_id)
        if not m:
            log.warning(
                "Could not find message as part of maven_to_zendesk_message_reconciliation.",
                message_id=message_id,
            )
            # For now we wont remove it from the reconciliation list but we might want in the future
            continue

        if m.created_at > created_at_before:
            log.info(
                "Skipping message for reconciliation given that it is not old enough",
                message_id=message_id,
                message_created_at=m.created_at,
                created_at_before=created_at_before,
            )
            continue
        if m.created_at < created_at_after:
            log.info(
                "Removing message from reconciliation list as it is too old",
                message_id=message_id,
                message_created_at=m.created_at,
                created_at_after=created_at_after,
            )
            redis_cli.srem(MAVEN_TO_ZENDESK_RECONCILIATION_LIST_KEY, message_id)
            continue

        # Check that message has no zendesk_comment_id
        # It should never be the case that a message has a zendesk_comment_id and is still in the reconciliation list
        # but this is just a safe check
        if m.zendesk_comment_id:
            log.info(
                "Removing message from reconciliation list as it already has a zendesk_comment_id",
                message_id=message_id,
            )
            redis_cli.srem(MAVEN_TO_ZENDESK_RECONCILIATION_LIST_KEY, message_id)
            continue

        if dry_run:
            log.info(
                "DRY RUN - Not scheduling send_to_zendesk job for message",
                message_id=message_id,
            )
            continue

        # Try to reconcile
        try:
            ReconciliationZendeskTicket(m).update_zendesk()
            db.session.commit()
            log.info(
                "Called ReconciliationZendeskTicket.update_zendesk for message",
                message_id=message_id,
            )
            n_messages_reconciled += 1
        except ZendeskInvalidRecordException:
            stats.increment(
                metric_name=ZENDESK_RECONCILIATION_ERROR_COUNT_METRICS,
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=["reason:zendesk_data_validation_error"],
            )
            continue

        except Exception as e:
            log.warning(
                "Error calling ReconciliationZendeskTicket.update_zendesk",
                message_id=message_id,
                exception=e,
            )
            stats.increment(
                metric_name=ZENDESK_RECONCILIATION_ERROR_COUNT_METRICS,
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=["reason:zendesk_unknown"],
            )
            continue

        # Update braze if reconciliation succeeded
        try:
            braze.update_message_attrs(m.channel.member)
        except Exception as e:
            log.warning(
                "Error in braze.update_message_attrs during message reconciliation",
                message_id=message_id,
                exception=e,
            )
            stats.increment(
                metric_name=ZENDESK_RECONCILIATION_ERROR_COUNT_METRICS,
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=["reason:braze_update_message_attrs_error"],
            )

    stats.increment(
        metric_name="mono.messaging.messaging_reconciliation.maven_to_zendesk.messages_reconciled",
        metric_value=n_messages_reconciled,
        pod_name=stats.PodNames.VIRTUAL_CARE,
    )
