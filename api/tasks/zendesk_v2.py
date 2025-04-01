from __future__ import annotations

import contextlib
import dataclasses
import enum
import json
from datetime import datetime, timedelta
from typing import Generator

import maven.feature_flags as feature_flags
from redset.locks import LockTimeout
from zenpy.lib.api_objects import Comment as ZDComment
from zenpy.lib.api_objects import Ticket as ZDTicket

from authn.models.user import User
from care_advocates.models.assignable_advocates import AssignableAdvocate
from common import stats
from messaging.models.messaging import Channel, Message, MessageCredit
from messaging.schemas.zendesk import (
    ZendeskInboundMessageSchema,
    ZendeskInboundMessageSource,
    ZendeskWebhookSchema,
    ticket_to_zendesk_inbound_message_schema,
    webhook_to_zendesk_inbound_message_schema,
)
from messaging.services.zendesk import (
    ZENDESK_PRACTITIONER_TAGS,
    get_or_create_zenpy_user,
    tag_zendesk_user,
    zenpy_client,
)
from messaging.services.zendesk_client import (
    ZendeskTicketId,
    get_updated_ticket_search_default_lookback_seconds,
)
from models.profiles import PractitionerProfile
from storage.connection import db
from tasks.helpers import get_user
from tasks.notifications import notify_new_message
from tasks.queues import job, retryable_job
from utils import braze
from utils.cache import RedisLock, redis_client
from utils.constants import (
    ZENDESK_MESSAGE_PROCESSING,
    ZENDESK_MESSAGE_PROCESSING_LOCK_TIMEOUT,
    ZENDESK_MESSAGE_PROCESSING_MESSAGE_TYPE,
    ZENDESK_MESSAGE_PROCESSING_OUTCOME,
    ZENDESK_MESSAGE_PROCESSING_UNKNOWN_AUTHOR,
    ZENDESK_TICKET_PROCESSING_ERROR,
)
from utils.flag_groups import CARE_DELIVERY_RELEASE, ZENDESK_CONFIGURATION
from utils.log import LogLevel, generate_user_trace_log, logger
from utils.mail import PRACTITIONER_SUPPORT_EMAIL, alert_admin
from utils.service_owner_mapper import service_ns_team_mapper

log = logger(__name__)

MAVEN_SUPPORT_EMAIL_ADDRESS = "support+consumer@mavenclinic.com"
ZENDESK_TAG_WALLET = "maven_wallet"
ZENDESK_TAG_PREFIX_CHANNEL_ID = "cx_channel_id_"

EXCLUDE_TICKET_IDS_FROM_RECONCILIATION: list[ZendeskTicketId] = [
    # details can be found here https://mavenclinic.slack.com/archives/C06HGG70HKQ/p1707344038987089
    180554,  # inc-126
    559398,  # inc-126
    561274,  # inc-126
]

# This is the number of times we will attempt to process a message through
# reconciliation. This should be fairly low as the reconciliation job will pick
# up a message multiple times as the lookback window moves forward. The number
# is equal to lookback window/reconciliation period
ZENDESK_INBOUND_MESSAGE_RECONCILIATION_JOB_RETRY_LIMIT = 2


class ZendeskMessageType(str, enum.Enum):
    WALLET = "wallet"
    MEMBER = "member"


def should_check_channel_members() -> bool:
    """
    Returns True if we should check what channel tag the zendesk comment author is associated with
    """
    return feature_flags.bool_variation(
        ZENDESK_CONFIGURATION.CHECK_CHANNEL_MEMBERS,
        default=False,
    )


@contextlib.contextmanager
def zendesk_comment_processing_job_lock(
    zendesk_comment_id: int | None,
    # sec we wait before giving up. this should be a low number so we can give
    # resources back to the job pool and use the job scheduling and retry system
    # to do the waiting for us
    lock_timeout_sec: int = 5,
) -> Generator[None, None, None]:
    if not zendesk_comment_id:
        return None

    cache_key = f"zendesk_message_processing:lock:{zendesk_comment_id}"
    try:
        # we are async processing the pool of comments. If we wait for the lock
        # we block the underlying job worker from processing other comments.
        # Instead, we issue a very short time out and then exit. This will kick
        # the job back into the processing queue to be retried with the
        # configured backoff.
        with RedisLock(cache_key, timeout=lock_timeout_sec):
            yield
    except LockTimeout as e:
        # This is not necessarily an error. It is expected that we will have
        # some number of these. Each will be retried with a backoff. We see an
        # increasing number of jobs that fail all retries with the lock timeout
        # error we should investigate the job backoff and retry configuration.
        log.info(
            "Missed comment processing lock due to timeout",
            zendesk_comment_id=zendesk_comment_id,
            error=e,
        )
        stats.increment(
            metric_name=ZENDESK_MESSAGE_PROCESSING_LOCK_TIMEOUT,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=[
                f"lock_timeout_sec:{int(lock_timeout_sec)}",
            ],
        )
        raise e


# Do not retry on the priority queue, we must not clog the queue with retries.
# If the first attempt fails, the reconciliation job will pick it up.
@job("priority")
def process_zendesk_inbound_message_from_webhook(
    inbound_message: ZendeskInboundMessageSchema | None = None,
) -> None:
    return process_zendesk_inbound_message_worker(
        inbound_message=inbound_message,
    )


# It is important that these jobs are not placed on the priority queue.
@retryable_job(
    "default",
    retry_limit=ZENDESK_INBOUND_MESSAGE_RECONCILIATION_JOB_RETRY_LIMIT,
)
def process_zendesk_inbound_message_from_reconciliation(
    inbound_message: ZendeskInboundMessageSchema | None = None,
) -> None:
    return process_zendesk_inbound_message_worker(
        inbound_message=inbound_message,
    )


def process_zendesk_inbound_message_worker(
    inbound_message: ZendeskInboundMessageSchema | None = None,
) -> None:
    """
    For each new message created in Zendesk this job should be called to process
    the message and store it in Mavens system.

    This job is idempotent and may be called multiple times for the same message
    without issue.
    """

    if not inbound_message:
        log.error("Attempting to process null zendesk inbound message")
        return None

    # ensure we hold the lock before evaluating
    # has_zendesk_comment_id_been_processed if we do it after, we introduce
    # processing race conditions
    with zendesk_comment_processing_job_lock(inbound_message.comment_id):
        log_tags = {
            "zendesk_user_id": inbound_message.zendesk_user_id,
            "zendesk_comment_id": inbound_message.comment_id,
            "comment_author_email": inbound_message.comment_author_email,
            "tags": inbound_message.tags,
            "source": inbound_message.source,
        }

        already_processed = has_zendesk_comment_id_been_processed(
            inbound_message.comment_id,
        )
        stats.increment(
            metric_name=ZENDESK_MESSAGE_PROCESSING,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=[
                f"already_processed:{already_processed}",
                f"source:{inbound_message.source}",
            ],
        )

        # if we have already processed this comment, bail out
        if already_processed:
            generate_user_trace_log(
                log,
                LogLevel.INFO,
                f"{inbound_message.zendesk_user_id}",
                "Skipping process_zendesk_inbound_message_worker, message already processed",
                **log_tags,
            )
            return None  # job will not be retried

        member = get_member(
            maven_user_email=inbound_message.maven_user_email,
            zendesk_user_id=inbound_message.zendesk_user_id,
        )
        if not member:
            signal_message_processing_error(
                reason="no_member", source=inbound_message.source
            )
            generate_user_trace_log(
                log,
                LogLevel.WARNING,
                f"{inbound_message.zendesk_user_id}",
                "Unable to find member",
                **log_tags,
            )

            try:
                temp_debug_timeout = timedelta(days=2)
                temporary_debug_zendesk_v2_no_member_key = (
                    f"zendesk_v2:temp:no_member:{inbound_message.comment_id}"
                )
                json_str: str = json.dumps(dataclasses.asdict(inbound_message))
                redis_client().setex(
                    name=temporary_debug_zendesk_v2_no_member_key,
                    value=json_str,
                    time=temp_debug_timeout,
                )
            except Exception as e:
                # sink this error as it has nothing to do with the processing of
                # the message. it is only a helper to facilitate rapid debugging response.
                log.exception(
                    "Failed to store temporary debug data for inbound message processing",
                    exception=e,
                    **log_tags,
                )

            return None  # job will not be retried
        try:
            new_message = route_and_handle_inbound_message(
                inbound_message=inbound_message,
                member=member,
                log_tags=log_tags,
            )
            if new_message:
                # very important to commit our changes.
                # "Anything not saved will be lost.."
                # - Nintendo
                db.session.add(new_message)
                db.session.commit()

        except Exception as e:
            log.exception(
                "Failed to route and handle inbound message",
                exception=e,
                **log_tags,
            )
            # undo any db activity that occurred during the inbound message handling
            db.session.rollback()
            raise e  # job will be retried

        # ensure we commit BEFORE taking any early exits so that any db activity that
        # occurred during the inbound processing is persisted to the db
        if not new_message:
            generate_user_trace_log(
                log,
                LogLevel.WARNING,
                f"{inbound_message.zendesk_user_id}",
                "Inbound zendesk message processing did not result in a new Maven side message",
                **log_tags,
            )
            return None  # job will not be retried

    service_ns_tag = "messaging_system"
    team_ns_tag = service_ns_team_mapper.get(service_ns_tag)

    notify_new_message.delay(
        member.id,
        new_message.id,
        service_ns=service_ns_tag,
        team_ns=team_ns_tag,
    )
    update_message_attrs.delay(
        member.id,
        service_ns=service_ns_tag,
        team_ns=team_ns_tag,
        caller="process_zendesk_webhook",
    )

    return None  # job will not be retried


def should_include_ticket_id_in_reconciliation(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    zendesk_ticket_id: ZendeskTicketId | None = None,
):
    """
    During manual backfills it may become necessary to exclude certain tickets.
    Adding the ticket id to the EXCLUDE_TICKET_IDS_FROM_RECONCILIATION list will
    prevent it from being reconciled.
    """
    if (
        not zendesk_ticket_id
        or zendesk_ticket_id in EXCLUDE_TICKET_IDS_FROM_RECONCILIATION
    ):
        return False

    return feature_flags.bool_variation(
        CARE_DELIVERY_RELEASE.ENABLE_ZENDESK_V2_RECONCILIATION_OF_TICKET,
        context=(
            feature_flags.Context.builder(
                f"reconciliation_include_ticket_id_{zendesk_ticket_id}",
            )
            .kind("reconciliation_inclusion")
            .set("zendesk_ticket_id", zendesk_ticket_id)
            .build()
        ),
        # default to excluding all tickets to prevent any processing until the
        # flag starts rolling out.
        default=False,
    )


def route_and_handle_inbound_message(
    inbound_message: ZendeskInboundMessageSchema | None = None,
    member: User | None = None,
    log_tags: dict | None = None,
) -> Message | None:
    # guard optional log_tags
    if log_tags is None:
        log_tags = {}

    if inbound_message is None:
        log.error(
            "Unable to process null inbound message",
            **log_tags,
        )
        return None

    is_wallet_resp = is_wallet_response(inbound_message.tags)
    message_type = (
        ZendeskMessageType.WALLET if is_wallet_resp else ZendeskMessageType.MEMBER
    )
    stats.increment(
        metric_name=ZENDESK_MESSAGE_PROCESSING_MESSAGE_TYPE,
        pod_name=stats.PodNames.VIRTUAL_CARE,
        tags=[
            f"type:{message_type}",
        ],
    )
    new_message = None
    if is_wallet_resp:
        new_message = process_inbound_wallet_message(inbound_message, member, log_tags)
    else:
        new_message = process_inbound_member_message(inbound_message, member, log_tags)

    return new_message


# This job is unlikely to succeed on retry given the same data and same target.
@job("priority")
def process_zendesk_webhook(data: dict | None = None) -> None:
    """
    This job is triggered when a new webhook is received from Zendesk. Its
    purpose is to transform the payload into the common structure needed for
    process_zendesk_inbound_message and schedule that job. We use a scheduled
    job to split the action of forcing the payload into
    ZendeskInboundMessageSchema and the actions of processing that data.

    In this implementation retries are useless as the data will not have changed
    format. For that reason we capture and sink exceptions. With job failure
    monitors this will split failures due to malformed payloads and errors our
    side.

    Important Note:
    Conditions under which a Zendesk message will be saved in the Maven database:
    - the recipient, identified by zendesk_user_id or maven_user_email, must not be a CA
    - the sender, identified by comment_author_email, must have a PractitionerProfile whose email is one of the following
          comment_author_email@mavenclinic.com
          comment_author_email+prac@mavenclinic.com
      OR
          the comment_author_email must be support+consumer@mavenclinic.com
          (in which case kaitlyn+messaging@mavenclinic.com will be used as author)
    - the sender's PractitionerProfile must be linked to a CA vertical
    """
    if not data:
        log.error("Attempting to process null Zendesk webhook payload")
        return None
    try:
        loaded_schema = ZendeskWebhookSchema().load(data)
        inbound_message = webhook_to_zendesk_inbound_message_schema(loaded_schema)
        service_ns_tag = "messaging_system"
        team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
        process_zendesk_inbound_message_from_webhook.delay(
            inbound_message, service_ns=service_ns_tag, team_ns=team_ns_tag
        )
    except Exception as e:
        log.exception(
            "Failed marshalling Zendesk inbound message schema",
            exception=e,
            # do not log `data`` as it may contain sensitive information
        )
    return None


def ticket_with_id(ticket_id: ZendeskTicketId | None) -> ZDTicket | None:
    """
    Retrieve the ticket with the given Zendesk ticket_id.
    """
    if not ticket_id:
        return None
    ticket = zenpy_client.ticket_with_id(ticket_id=ticket_id)
    return ticket


def public_comments_for_ticket(ticket: ZDTicket | None) -> list[ZDComment]:
    """
    Retrieve the public comments for a given Zendesk ticket.
    """
    if not ticket:
        return []
    return public_comments_for_ticket_id(ticket_id=ticket.id)


def public_comments_for_ticket_id(
    ticket_id: ZendeskTicketId | None,
) -> list[ZDComment]:
    """
    Retrieve the public comments for a given Zendesk ticket_id.
    """
    if not ticket_id:
        return []

    comments = zenpy_client.get_comments_for_ticket_id(ticket_id=ticket_id)
    if comments is None:
        return []

    public_comments = [c for c in comments if c.public]
    return public_comments


def signal_message_processing_skipped(
    reason: str | None = None,
    source: ZendeskInboundMessageSource | None = None,
) -> None:
    stats.increment(
        metric_name=ZENDESK_MESSAGE_PROCESSING_OUTCOME,
        pod_name=stats.PodNames.VIRTUAL_CARE,
        tags=[
            "result:skipped",
            f"reason:{reason}",
            f"source:{source}",
        ],
    )


def signal_message_processing_error(
    reason: str | None = None,
    source: ZendeskInboundMessageSource | None = None,
) -> None:
    stats.increment(
        metric_name=ZENDESK_MESSAGE_PROCESSING_OUTCOME,
        pod_name=stats.PodNames.VIRTUAL_CARE,
        tags=[
            "result:failure",
            f"reason:{reason}",
            f"source:{source}",
        ],
    )
    return None


def process_zendesk_comment(
    ticket: ZDTicket | None,
    comment: ZDComment | None,
) -> None:
    """
    Accepts a Zendesk ticket/comment pair. If the comment is public, this
    schedules a job to record it in Mavens system.
    """
    if not comment:
        signal_message_processing_error(
            reason="null_comment", source=ZendeskInboundMessageSource.TICKET
        )
        return None

    # we must ensure we only process public comments
    # this is a secondary guard against processing private comments
    if not comment.public:
        # private comments should be filtered out prior to this function. ensure
        # use of public_comments_for_ticket or public_comments_for_ticket_id
        signal_message_processing_error(
            reason="private_comment", source=ZendeskInboundMessageSource.TICKET
        )
        return

    # attempt transform into ZendeskInboundMessageSchema from Zendesk comment.
    # this is required to normalize the data across push and pull paths.
    try:
        # will raise if transform is unsuccessful
        inbound_message = ticket_to_zendesk_inbound_message_schema(
            ticket=ticket,
            comment=comment,
        )
        # keep the execution of this in context. a comment should be considered
        # a single unit of work. if later fanout is necessary it should be done
        # at the threshold of ticket / comment.
        process_zendesk_inbound_message_worker(inbound_message)
    except Exception as e:
        signal_message_processing_error(
            reason="inbound_message_transform",
            source=ZendeskInboundMessageSource.TICKET,
        )
        log.exception(
            "Failed to create inbound message from recent Zendesk comment",
            comment_id=comment.id,
            ticket_id=(ticket.id if ticket else None),
            exception=e,
        )
    return None


def signal_ticket_processing_error(reason: str | None = None) -> None:
    stats.increment(
        metric_name=ZENDESK_TICKET_PROCESSING_ERROR,
        pod_name=stats.PodNames.VIRTUAL_CARE,
        tags=[
            f"reason:{reason}",
        ],
    )
    return None


# do not retry ticket processing jobs. There are multiple reconciliation runs
# per lookback window. This will intrinsically be retried.
@job("default")
def process_updated_zendesk_ticket_id(ticket_id: ZendeskTicketId | None) -> None:
    """
    Given a Zendesk ticket_id that is believed to have been updated, pull the
    list of public comments and process each one for reconciliation.

    This process is idempotent and may be called multiple times for the same
    ticket_id.
    """
    if not ticket_id:
        signal_ticket_processing_error(reason="null_ticket_id")
        return None  # job will not be retried

    if not should_include_ticket_id_in_reconciliation(ticket_id):
        signal_ticket_processing_error(reason="ticket_id_exclusion")
        log.info(
            "Excluding Zendesk ticket reconciliation",
            ticket_id=ticket_id,
        )
        return None  # job will not be retried

    ticket = ticket_with_id(ticket_id=ticket_id)
    if not ticket:
        log.error(
            "Failed to retrieve Zendesk ticket for update processing",
            ticket_id=ticket_id,
        )
        signal_ticket_processing_error(reason="no_ticket_with_id")
        raise Exception("Zendesk ticket not found by id")  # job will be retried

    # NOTE: processing of the comment list is done serially instead of spanning
    # a new job. this is done because the comments are not directly accessible
    # by id, instead we must load the parent ticket then access the comments
    # through it. If we spawned a new job per comment we would be doing a large
    # amount of duplicate work.
    comment_list = public_comments_for_ticket(ticket=ticket)
    log.info("Attempting to process comments", number_of_comments=len(comment_list))
    for comment in comment_list:
        try:
            # check each comment to ensure we do as little extra work as possible
            if not should_process_reconciliation_comment(
                comment=comment,
                parent_ticket=ticket,
            ):
                signal_message_processing_skipped(
                    reason="should_not_process_reconciliation_comment",
                    source=ZendeskInboundMessageSource.TICKET,
                )
                continue

            process_zendesk_comment(ticket=ticket, comment=comment)
        except Exception as e:
            # we are not guaranteed that all child paths of
            # process_zendesk_comment are exception safe. we must catch
            # exceptions here to ensure we do not bail before we have processed
            # all comments.
            log.exception(
                "Failed to process Zendesk comment",
                comment_id=comment.id,
                ticket_id=ticket.id,
                exception=e,
            )
            signal_message_processing_error(
                reason="unexpected_exception", source=ZendeskInboundMessageSource.TICKET
            )
            continue


def should_process_reconciliation_comment(
    comment: ZDComment,
    parent_ticket: ZDTicket,
) -> bool:
    """
    Given a Zendesk comment, determine if it should be processed for reconciliation.
    """
    if comment is None or parent_ticket is None:
        return False

    if not should_reconcile_zendesk_messages():
        log.info("feature flag has disabled zendesk v2 reconciliation job")
        return False

    if comment.via is not None and comment.via.channel == "api":
        return False

    ticket_updated_at = zenpy_client.datetime_from_zendesk_date_str(
        parent_ticket.updated_at,
    )
    comment_created_at = zenpy_client.datetime_from_zendesk_date_str(comment.created_at)

    # tickets can have many.... many.... comments. We are only interested in
    # processing the comments that are within lookback window of the time the
    # ticket was updated. This ensures that we can go beyond
    # get_updated_ticket_search_default_lookback_seconds for back fills and only the
    # comments recent to the ticket update timestamp will be processed.
    lookback_sec = get_updated_ticket_search_default_lookback_seconds()
    if comment_created_at < ticket_updated_at - timedelta(
        seconds=lookback_sec,
    ):
        signal_ticket_processing_error(reason="comment_beyond_lookback")
        return False

    # for all comments that fall within the processing window leaverage the
    # feature flag controls to determine if we should do this work.
    return feature_flags.bool_variation(
        CARE_DELIVERY_RELEASE.ENABLE_ZENDESK_V2_RECONCILIATION_OF_COMMENT,
        context=(
            feature_flags.Context.builder(
                f"reconciliation_exclude_comment_id_{comment.id}",
            )
            .kind("reconciliation_exclusion")
            .set("zendesk_ticket_id", parent_ticket.id)
            .set("zendesk_comment_id", comment.id)
            .build()
        ),
        # default to excluding all comments to prevent any processing until the
        # flag starts rolling out.
        default=False,
    )


def should_reconcile_zendesk_messages() -> bool:
    """
    Returns True if we should attempt message reconciliation.
    """
    return feature_flags.bool_variation(
        CARE_DELIVERY_RELEASE.ENABLE_ZENDESK_V2_RECONCILIATION_JOB,
        # default to not processing inbound messages with the v2 pipeline
        default=False,
    )


# This job will be scheduled to run on a cron. Failures are unlikely to be
# resolved by retry. Instead we should press the period as low as possible so we
# recover quickly after releasing a fix.
@job("default")
def reconcile_zendesk_messages() -> None:
    """
    This job runs periodically to reconcile messages that were created in
    Zendesk but that failed to be properly processed through the inbound
    webhook. It searches for tickets that have been updated within the provided
    look back window and schedules a job to process each updated ticket. This
    job, and all children are idempotent and are expected to be called many
    times for the same ticket/comment.
    """
    if not should_reconcile_zendesk_messages():
        log.info("feature flag has disabled zendesk v2 reconciliation job")
        return None  # job will not be retried

    # without passing from/to we will get the default window
    updated_tickets = zenpy_client.find_updated_ticket_ids()
    log.info(
        "Retrieved list of updated tickets",
        number_of_updated_tickets=len(updated_tickets),
    )
    for ticket_id in updated_tickets:
        try:
            process_updated_zendesk_ticket_id.delay(ticket_id, team_ns="virtual_care")
        except Exception as e:
            log.error(
                "Failed to schedule recently updated Zendesk ticket for reconciliation",
                ticket_id=ticket_id,
                error=e,
            )
            signal_ticket_processing_error(reason="job_scheduling_error")
            continue  # being explicit with our intent to continue processing


@job("default")
def update_message_attrs(user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    user = get_user(user_id=user_id)
    if not user:
        log.warning("User id not found", user_id=user_id)

    braze.update_message_attrs(user=user)


@job(traced_parameters=("user_id",))
def tag_practitioner_in_zendesk(user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    user = get_user(user_id)
    if not user.is_practitioner:
        log.error(
            "Attempted to tag a non-practitioner user with the practitioner tags",
            user=user,
        )
        return
    if user.is_care_coordinator:
        log.info(
            "No need to tag care coordinators with zendesk practitioner tags. Skipping tag.",
            user=user,
        )
        return
    zendesk_user = get_or_create_zenpy_user(user)
    tag_zendesk_user(zendesk_user, ZENDESK_PRACTITIONER_TAGS)


def has_zendesk_comment_id_been_processed(
    comment_id: int | None = None,
) -> bool:
    """
    Determines if the given Zendesk comment_id is found in the database.
    """
    if not comment_id:
        return False

    existing_message = Message.query.filter(
        Message.zendesk_comment_id == comment_id,
    ).first()
    if not existing_message:
        return False
    return True


def get_member(
    maven_user_email: str | None = None,
    zendesk_user_id: int | None = None,
) -> User | None:
    """
    The goal of `get_member` is to identify the target user for a given reply
    from a CA. This is done by matching the zendesk_user_id or maven_user_email.
    Historically we only matched on zendesk_user_id which produced message loss
    when this value was not properly set upstream.

    In the event that the provided maven_user_email locates a user without a
    zendesk_user_id we will emit a job to proactively attempt to assign it. If
    we only match on maven_user_email and that user already has a
    zendesk_user_id we cannot automatically assign the zendesk_user_id. In these
    cases manual intervention is required.
    """
    if not maven_user_email and not zendesk_user_id:
        log.error(
            "One of maven_user_email or zendesk_user_id required to identify member for inbound Zendesk message processing",
        )
        return None

    if not maven_user_email or not zendesk_user_id:
        # We expect both of these values to be present. If one is missing it is
        # a strong signal of upstream issues. We will log this as a warning and
        # attempt to match on the available value.
        log.warn(
            "Missing member identifier during inbound Zendesk message processing",
            # provide context in logs without leaking sensitive data
            has_maven_user_email=bool(maven_user_email),
            has_zendesk_user_id=bool(zendesk_user_id),
        )

    if maven_user_email == MAVEN_SUPPORT_EMAIL_ADDRESS:
        log.warn("Ignoring Zendesk webhook for maven_user_email matching support email")
        return None

    # Try to find the user by zendesk_user_id.
    member_user = None
    if (
        zendesk_user_id
    ):  # Need to be sure that one is provided, if not, following query might throw false positive
        user_matching_zendesk_user_id = User.query.filter(
            User.zendesk_user_id == zendesk_user_id
        ).first()
        if user_matching_zendesk_user_id:
            log.info(
                "Identified maven member by zendesk_user_id",
                zendesk_user_id=zendesk_user_id,
                user_matching_zendesk_user_id_user_id=user_matching_zendesk_user_id.id,
            )
            member_user = user_matching_zendesk_user_id

    # If finding by zendesk_user_id failed, try to find using email.
    if not member_user and maven_user_email:
        user_matching_maven_user_email = User.query.filter_by(
            email=maven_user_email
        ).first()

        if user_matching_maven_user_email:
            log.info(
                "Identified maven member by maven_user_email",
                zendesk_user_id=zendesk_user_id,
                user_matching_maven_user_email_user_id=user_matching_maven_user_email.id,
                user_matching_maven_user_email_zendesk_user_id=user_matching_maven_user_email.zendesk_user_id,
            )
            member_user = user_matching_maven_user_email

            # If a user is found by email (and not by zendesk_user_id - notice that came first),
            # try to reconcile the found user zendesk_user_id
            if user_matching_maven_user_email.zendesk_user_id is None:
                # schedule an async job to recover the zendesk_user_id onto the user
                # identified by maven_user_email. this is not required, as we are
                # already falling back to maven_user_email, but it is a proactive
                # step to heal missing data in our DB.
                log.info(
                    "Triggering recover_zendesk_user_id",
                    maven_user_email=maven_user_email,
                    zendesk_user_id=zendesk_user_id,
                )

                service_ns_tag = "messaging_system"
                team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
                recover_zendesk_user_id.delay(
                    maven_user_email=maven_user_email,
                    zendesk_user_id=zendesk_user_id,
                    service_ns=service_ns_tag,
                    team_ns=team_ns_tag,
                )
            else:
                # If there is a zendesk_user_id set on this user and it is different
                # than what we received then manual intervention is required to ensure
                # we are able to source more details and potentially manually fix.
                log.warn(
                    "Member matched by maven_user_email had existing zendesk_user_id that did not match inbound zendesk_user_id.",
                    zendesk_user_id=zendesk_user_id,
                    user_matching_maven_user_email_user_id=user_matching_maven_user_email.id,
                    user_matching_maven_user_email_zendesk_user_id=user_matching_maven_user_email.zendesk_user_id,
                )

    if not member_user:
        log.warn(
            "Ignoring Zendesk webhook for zendesk_user_id and maven_user_email with no matching Maven user."
        )
        return None

    if member_user.is_care_coordinator:
        log.warn(
            "Ignoring Zendesk webhook for maven_user_email matching care coordinator.",
            user_id=member_user.id,
        )
        return None
    # passed all checks
    return member_user


def get_author(comment_author_email) -> User | None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    pp = PractitionerProfile.query.filter_by(zendesk_email=comment_author_email).first()
    if pp:
        return pp.user

    # check for +prac emails
    email_parts = comment_author_email.split("@")
    prac_email = f"{email_parts[0]}+prac@{email_parts[1]}"

    generate_user_trace_log(
        log,
        LogLevel.WARNING,
        "0",
        "Attempting +prac email",
        comment_author_email=comment_author_email,
        prac_email=prac_email,
    )

    pp = PractitionerProfile.query.filter_by(zendesk_email=prac_email).first()
    if pp:
        generate_user_trace_log(
            log,
            LogLevel.WARNING,
            "0",
            "Found practitioner email",
            comment_author_email=comment_author_email,
            prac_email=prac_email,
        )
        return pp.user

    # we hard-code Kaitlyn's account here for backwards compatibility
    if comment_author_email == "support+consumer@mavenclinic.com":
        return AssignableAdvocate.default_care_coordinator()

    log.warn("Cannot establish practitioner for Zendesk webhook.")
    return None


def emit_non_cx_comment_warning(email: str, user: User) -> None:
    error = (
        "Zendesk agent {} "
        "corresponding with Maven practitioner {} "
        "created a comment, but does not have the Care Advocate vertical.\n"
        "Please add the vertical to their account if they truly are a Care Advocate, "
        "or alert engineering otherwise.".format(email, user)
    )
    try:
        alert_admin(
            error,
            [PRACTITIONER_SUPPORT_EMAIL],
            subject="Zendesk Agent Missing CX Vertical",
        )
    except Exception as e:
        log.error("Failed to alert practitioner support: %s\n%s", e, error)

    log.warn(
        "Ignoring Zendesk webhook for non care coordinator comment author %s.",
        user,
    )


def get_channel_and_message_author(member, author, tags):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    tagged_channel = get_corresponding_channel_from_tags(
        tags, author.id, should_check_channel_members()
    )
    if member.is_enterprise:
        if tagged_channel:
            log.info(
                "Routing message for enterprise user to tagged channel as comment author.",
            )
            return tagged_channel, author

        channel = Channel.get_or_create_channel(author, [member])
        log.info(
            "Routing message for enterprise user to new or existing channel with comment author.",
        )
        return channel, author

    if tagged_channel:
        log.info(
            "Routing message for marketplace user to tagged channel as channel practitioner.",
        )
        return tagged_channel, tagged_channel.practitioner

    if member.care_coordinators:
        cc = member.care_coordinators[0]
    else:
        cc = AssignableAdvocate.default_care_coordinator()

    channel = Channel.get_or_create_channel(cc, [member])
    log.info(
        "Routing message for marketplace user to new or existing channel with member care advocate.",
    )
    return channel, cc


def get_corresponding_channel_from_tags(
    tags: list[str],
    author_id: int | None,
    check_members_enabled: bool,
) -> Channel | None:
    """
    Given a list of Zendesk tags, return the first corresponding channel if feature flag is off. If feature flag
    is on then we return the channel associated with the zendesk author. If there's no match, we return the channel
    created most recently. Tickets can have multiple channel tags from CA changes so this ensures that we're
    directing messages to the correct place.
    """
    if not tags:
        return None
    latest_created_channel: Channel | None = None
    latest_created_datetime: datetime | None = None
    for tag in tags:
        if tag.startswith(ZENDESK_TAG_PREFIX_CHANNEL_ID):
            c_id = tag.lstrip(ZENDESK_TAG_PREFIX_CHANNEL_ID)
            c = Channel.query.get(c_id)
            if not c:
                log.warning(
                    "Didn't find channel associated with zendesk tags",
                    tags=tags,
                    channel_id=c_id,
                )
                return None
            # if feature flag off follow old logic and return first channel
            if not check_members_enabled:
                return c
            # return immediately if the author is in the channel
            if c.practitioner.id == author_id:
                log.info(
                    "Found channel with matching author_id",
                    author_id=author_id,
                    channel_id=c_id,
                )
                return c
            if not latest_created_datetime or c.created_at > latest_created_datetime:
                latest_created_channel = c
                latest_created_datetime = c.created_at
    # if we didn't find a channel with the author in it use the newest channel
    log.info(
        "Returning the latest created at channel because we didn't find an author match"
    )
    return latest_created_channel


def is_wallet_response(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    tags: list[str] | None = None,
):
    """
    Returns True if the given list of Zendesk tags contains the wallet tag.
    """
    if not tags:
        return False
    return any(ZENDESK_TAG_WALLET in tag for tag in tags)


def create_wallet_message(
    inbound_message: ZendeskInboundMessageSchema | None = None,
) -> Message | None:
    """
    Creates a new wallet message for the given inbound message.
    """
    if not inbound_message:
        return None

    tagged_channel = get_corresponding_channel_from_tags(
        inbound_message.tags, None, should_check_channel_members()
    )
    if not tagged_channel:
        log.warn(
            "Zendesk webhook did not have a tag indicating origin channel.",
            zendesk_user_id=inbound_message.zendesk_user_id,
            zendesk_comment_id=inbound_message.comment_id,
            tags=inbound_message.tags,
        )
        return None

    # Wallet messages have no author on the backend. See also: add_maven_wallet_channel()
    message = Message(
        user=None,
        channel=tagged_channel,
        body=inbound_message.message_body,
        zendesk_comment_id=inbound_message.comment_id,
    )
    db.session.add(message)
    return message


def record_successful_processing_of_inbound_zendesk_message(
    inbound_message: ZendeskInboundMessageSchema | None = None,
    new_mvn_message: Message | None = None,
    message_type: str = "unknown",
) -> None:
    if not inbound_message or not new_mvn_message:
        return None
    stats.increment(
        metric_name=ZENDESK_MESSAGE_PROCESSING_OUTCOME,
        pod_name=stats.PodNames.VIRTUAL_CARE,
        tags=[
            "result:success",
            f"type:{message_type}",
            f"source:{inbound_message.source}",
        ],
    )
    generate_user_trace_log(
        log,
        LogLevel.INFO,
        f"{inbound_message.zendesk_user_id}",
        "Recorded Zendesk comment from webhook as Maven message.",
        zendesk_user_id=inbound_message.zendesk_user_id,
        zendesk_comment_id=inbound_message.comment_id,
        message_id=new_mvn_message.id,
        source=inbound_message.source,
    )
    return None


def attempt_record_credit_usage(
    originating_msg: Message | None = None,
    response_msg: Message | None = None,
    log_tags: dict | None = None,
) -> MessageCredit | None:
    # guard optional log_tags
    if not log_tags:
        log_tags = {}
    log_tags["originating_message_id"] = originating_msg.id if originating_msg else None
    log_tags["response_msg_id"] = response_msg.id if response_msg else None

    if not originating_msg:
        log.error(
            "Attempting to consume credit for messages with no originating message",
            **log_tags,
        )
        return None
    if not response_msg:
        log.error(
            "Attempting to consume credit for messages that did not have a response message",
            **log_tags,
        )
        return None

    if not originating_msg.user and originating_msg.channel.is_wallet:
        # wallet channels have messages without a user, this is not an error it is expected
        log.info(
            "Skipping attempt to consume messaging credit for wallet channel",
            **log_tags,
        )
        return None

    if not originating_msg.user:
        # if there is no user attached to the originating message we cannot
        # determine the expectation for credit consumption.
        log.error(
            "Originating message had no user, skipping attempt to consume credit",
            **log_tags,
        )
        return None

    # after none check add the user id to the log props
    log_tags["originating_msg_user_id"] = originating_msg.user.id

    # we only want to consume credits for the first reply to a member message.
    # consecutive messages from the same practitioner should not attempt to
    # consume credits.
    if not originating_msg.user.is_member:
        # NOTE: this log message may be removed at a later date. We initially
        # keep it to aide in validation of system operation.
        log.info(
            "Skipping attempt to consume credit from non-member originating message",
            **log_tags,
        )
        return None

    # here we expect the originating message to be from a member and have
    # credit attached. If it does not we are unable to resolve automatically and
    # must log an error for further investigation.
    if not originating_msg.credit:
        log.error(
            "Failed to consume credit from originating member message without credit attached",
            **log_tags,
        )
        return None

    credit = originating_msg.credit
    credit.responded_at = datetime.utcnow()
    credit.response = response_msg
    log.info(
        "Registered response for message from Zendesk",
        **log_tags,
    )
    db.session.add(credit)
    return credit


def get_message_this_in_reply_to(
    reply_message: Message | None = None,
) -> Message | None:
    """
    Given a reply message, return the message that this was in reply to.
    Returns None if no message was found.

    NOTE: This is a mirror of the previous implementation. It does not take into
    account situations where one of the users has sent multiple messages in a
    row. For now this is OK because we only want to deduct credits the first
    time at the time that a practitioner is replying to a member message, not
    for every message they may send in reply.
    """
    if not reply_message:
        raise ValueError(
            "must provide reply_message to determine what it was in reply to",
        )

    # guard broken channel back reference
    message_list = reply_message.channel.messages if reply_message.channel else []

    for i in reversed(range(len(message_list))):
        if reply_message.channel.messages[i].id == reply_message.id and i > 0:
            return reply_message.channel.messages[i - 1]
    return None


def process_credits_after_message_receive(
    inbound_message: ZendeskInboundMessageSchema | None = None,
    member: User | None = None,
    channel: Channel | None = None,
    new_message: Message | None = None,
) -> None:
    # common logging properties
    log_tags = {
        "inbound_message_comment_id": (
            inbound_message.comment_id if inbound_message else None
        ),
        "member_id": (member.id if member else None),
        "channel_id": (channel.id if channel else None),
        "new_message_id": (new_message.id if new_message else None),
    }
    # input validation
    if not member:
        log.error(
            "Attempting to process credits without member",
            **log_tags,
        )
        return None
    if not channel:
        log.error(
            "Attempting to process credits without corresponding channel",
            **log_tags,
        )
        return None
    if not new_message:
        log.error(
            "Attempting to process credits without corresponding new message",
            **log_tags,
        )
        return None

    in_reply_to = get_message_this_in_reply_to(new_message)
    if in_reply_to:
        attempt_record_credit_usage(
            originating_msg=in_reply_to,
            response_msg=new_message,
            log_tags=log_tags,
        )

    return None


def process_inbound_wallet_message(
    inbound_message: ZendeskInboundMessageSchema | None = None,
    member: User | None = None,
    log_tags: dict | None = None,
) -> Message | None:
    # guard optional log_tags
    if log_tags is None:
        log_tags = {}

    # input validation
    if not inbound_message:
        log.error(
            "Attempting to process wallet message without inbound message data",
            member_id=(member.id if member else None),
            **log_tags,
        )
        return None
    if not member:
        log.error(
            "Attempting to process wallet message without member",
            inbound_message_comment_id=inbound_message.comment_id,
            **log_tags,
        )
        return None

    new_message = create_wallet_message(inbound_message)
    if not new_message:
        log.error(
            "Failed to create wallet message",
            inbound_message_comment_id=inbound_message.comment_id,
            member_id=member.id,
            **log_tags,
        )
        return None

    record_successful_processing_of_inbound_zendesk_message(
        inbound_message=inbound_message,
        new_mvn_message=new_message,
        message_type=ZendeskMessageType.WALLET,
    )
    process_credits_after_message_receive(
        inbound_message=inbound_message,
        member=member,
        channel=new_message.channel,
        new_message=new_message,
    )
    return new_message


def signal_on_comment_author_error(
    inbound_message: ZendeskInboundMessageSchema | None = None,
) -> None:
    """
    Creates trackable metrics when the provided comment_author_email is a Maven member.
    See the following ticket for more details: https://mavenclinic.atlassian.net/browse/VIRC-1754
    """
    if not inbound_message:
        return None

    comment_author_email = inbound_message.comment_author_email
    if not comment_author_email:
        return None

    user = (
        db.session.query(User).filter(User.email == comment_author_email).one_or_none()
    )

    group = "unknown"
    if not user:
        # we dont know who this is
        group = "no_user_found"
    elif user.is_practitioner:
        # this is a practitioner but for some reason we did not properly match
        # in the get_author step
        group = "practitioner"
    elif user.is_member:
        # see this ticket for extended description on how we can get into this
        # state
        group = "member"
        # TODO: attempt to find the message by the comment body

    stats.increment(
        metric_name=ZENDESK_MESSAGE_PROCESSING_UNKNOWN_AUTHOR,
        pod_name=stats.PodNames.VIRTUAL_CARE,
        tags=[
            f"group:{group}",
        ],
    )
    return None


def process_inbound_member_message(
    inbound_message: ZendeskInboundMessageSchema | None = None,
    member: User | None = None,
    log_tags: dict | None = None,
) -> Message | None:
    if log_tags is None:
        log_tags = {}
    if not inbound_message:
        log.error(
            "Attempting to process member message without inbound message data",
            **log_tags,
        )
        return None

    comment_author = get_author(inbound_message.comment_author_email)
    if not comment_author:
        signal_message_processing_error(
            reason="invalid_author",
            source=inbound_message.source,
        )

        generate_user_trace_log(
            log,
            LogLevel.WARNING,
            f"{inbound_message.zendesk_user_id}",
            "Unable to find comment author",
            maven_clinic_email="mavenclinic.com" in inbound_message.comment_author_email
            if inbound_message.comment_author_email
            else True,
            **log_tags,
        )
        signal_on_comment_author_error(
            inbound_message=inbound_message,
        )
        return None

    if not comment_author.is_care_coordinator:
        signal_message_processing_error(
            reason="author_is_not_ca",
            source=inbound_message.source,
        )
        emit_non_cx_comment_warning(
            inbound_message.comment_author_email,
            comment_author,
        )
        return None

    channel, message_author = get_channel_and_message_author(
        member,
        comment_author,
        inbound_message.tags,
    )
    if not channel or not message_author:
        signal_message_processing_error(
            reason="invalid_channel_message_author",
            source=inbound_message.source,
        )
        generate_user_trace_log(
            log,
            LogLevel.WARNING,
            f"{inbound_message.zendesk_user_id}",
            "Unable to find channel or message author! Aborting.",
            **log_tags,
        )
        log.warn("Unable to find channel or message author! Aborting.")
        return None

    new_message = Message(
        user=message_author,
        channel=channel,
        body=inbound_message.message_body,
        zendesk_comment_id=inbound_message.comment_id,
    )
    record_successful_processing_of_inbound_zendesk_message(
        inbound_message,
        new_message,
        message_type=ZendeskMessageType.MEMBER,
    )
    process_credits_after_message_receive(
        inbound_message,
        member,
        new_message.channel,
        new_message,
    )
    return new_message


@job("default")
def recover_zendesk_user_id(
    maven_user_email: str,
    zendesk_user_id: int,
) -> None:
    """
    If we identify a user by maven_user_email and they do not have a
    zendesk_user_id we schedule this job to try and recover it.

    This job is not required to succeed because upstream systems gracefully fall
    back to the email match. This job is only to reduce the frequency of
    unexpected fallbacks and increase the accuracy of the data in our DB.
    """
    if not maven_user_email or not zendesk_user_id:
        raise ValueError("maven_user_email and zendesk_user_id are required")

    log.info("Recovering zendesk_user_id for maven_user_email")
    # locate the user by zendesk_user_id or maven_user_email
    target_user = User.query.filter(
        User.email == maven_user_email,
    ).first()

    if not target_user:
        log.error(
            "Unable to locate user by maven_user_email during zendesk_user_id recovery",
        )
        return None

    if target_user.zendesk_user_id:
        if target_user.zendesk_user_id == zendesk_user_id:
            # another recovery job likely beat us to updating the id
            log.info(
                "Target user already has matching zendesk_user_id, no recovery necessary",
            )
        else:
            # we dont know how to resolve this automatically. manual
            # intervention is required.
            log.error(
                "Target user has a different zendesk_user_id, manual intervention required",
            )
        return None

    target_user.zendesk_user_id = zendesk_user_id
    db.session.add(target_user)
    db.session.commit()

    log.info(
        "Recovered zendesk_user_id for user matching provided maven_user_email",
        user_id=target_user.id,
        zendesk_user_id=zendesk_user_id,
    )
    return None
