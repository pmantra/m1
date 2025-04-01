from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import ddtrace
from dateutil.relativedelta import relativedelta
from rq.timeouts import JobTimeoutException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload, load_only
from sqlalchemy.orm.exc import NoResultFound

from appointments.models.appointment import Appointment
from appointments.models.payments import FeeAccountingEntry, FeeAccountingEntryTypes
from appointments.models.schedule import Schedule
from authn.models.user import User
from care_advocates.models.assignable_advocates import AssignableAdvocate
from common import stats
from common.services.api import even_chunks
from messaging.models.messaging import (
    Channel,
    ChannelUsers,
    Message,
    MessageCredit,
    MessageSourceEnum,
)
from messaging.services.zendesk import (
    MAVEN_TO_ZENDESK_RECONCILIATION_LIST_KEY,
    MessagingZendeskTicket,
    ZendeskInvalidRecordException,
    send_general_ticket_to_zendesk,
)
from models.actions import ACTIONS, audit
from models.enterprise import OrganizationEmployee  # noqa: F401
from models.marketing import TextCopy
from models.products import Product  # noqa: F401
from models.profiles import Device, PractitionerProfile, practitioner_verticals

# DO NOT REMOVE BELOW 2 LINES. NEEDED FOR MAPPER INSTANTIATION
from models.referrals import ReferralCodeUse  # noqa: F401
from models.tracks import MemberTrack, TrackName
from models.verticals_and_specialties import Vertical, is_cx_vertical_name
from payments.models.practitioner_contract import RATE_PER_MESSAGE
from storage.connection import db
from tasks.queues import get_task_service_name, job, retryable_job
from utils import braze, braze_events
from utils.apns import apns_send_bulk_message
from utils.cache import redis_client
from utils.constants import (
    SEND_TO_ZENDESK_ERROR_COUNT_METRICS,
    TWILIO_SMS_DELIVERY_SUCCESS_COUNT_METRICS,
)
from utils.exceptions import log_exception
from utils.log import LogLevel, generate_user_trace_log, logger
from utils.slack_v2 import notify_mpractice_core_alerts_channel
from utils.sms import send_sms

log = logger(__name__)

TRACKS_WITH_CA_MESSAGE_OFF = [
    TrackName.SURROGACY,
    TrackName.EGG_FREEZING,
    TrackName.ADOPTION,
]


@job
def refund_message_credits(
    chunk_size: int = 500,
    max_per_job_run: int = 1500,
) -> None:
    """
    Refund message credits to members for eligible messages, which satisfy:
    - messages didn't get responded within the guaranteed window.
    - messages have not been refunded before

    - job timeout is 10 min (default)
    - operational review shows ability to process ~2.3k per min (2023-11-13)
    - total credits to processed per job run should not exceed 15k to remain
      within default timeout
    - 15k leaves some headroom for flex in the future

    chunk_size:
        defines the number of credits to process before committing as a checkpoint
    max_per_job_run:
        max number of credits to process per run of this job.
    """
    # define query to find rows to process
    eligible_credits = db.session.query(MessageCredit).filter(
        MessageCredit.refunded_at.is_(None),
        MessageCredit.respond_by < datetime.utcnow(),
        MessageCredit.responded_at.is_(None),
    )

    # emit metric of total number of rows to process
    total_rows_to_process = eligible_credits.count()
    stats.gauge(
        metric_name="mono.messaging.message_credits.pending_refund",
        metric_value=total_rows_to_process or 0,
        pod_name=stats.PodNames.VIRTUAL_CARE,
    )

    if total_rows_to_process == 0:
        log.info("No message credits found to refund")
        return None

    # keeps track of the number of rows we have processed
    records_processed = 0
    while records_processed < max_per_job_run:
        # get the next chunk of rows to process
        chunk = eligible_credits.offset(records_processed).limit(chunk_size).all()
        if not chunk:
            # no records left to process
            break
        for message_credit in chunk:
            try:
                if not message_credit.is_eligible_for_refund():
                    log.debug(
                        "Message credit is not eligible for refund.",
                        message_credit=message_credit,
                    )
                    continue

                log.debug(
                    "Message credit is due for a refund.",
                    message_credit=message_credit,
                )
                message_credit.refund()
                audit(
                    ACTIONS.message_credit_refunded,
                    user_id=message_credit.user_id,
                    message_credit_id=message_credit.id,
                )
            except Exception as e:
                log.warn(
                    "Encountered exception while processing message credit",
                    message_credit=message_credit,
                    exception=e,
                )
                pass
            finally:
                records_processed += 1
        # delay commit until the end of the chunk to soften the number of
        # commits the DB has to deal with
        db.session.commit()

    log.info(
        "Completed refunding message credits.",
        records_processed=records_processed,
    )

    # emit metric of the remaining number of rows to process.
    # monitor this value to ensure it is trending down to 0
    total_rows_to_process = eligible_credits.count()
    stats.gauge(
        metric_name="mono.messaging.message_credits.pending_refund",
        metric_value=total_rows_to_process or 0,
        pod_name=stats.PodNames.VIRTUAL_CARE,
    )
    return None


@job
@db.from_replica
def collect_fees_for_messaging_purchases() -> None:
    """
    Create fees for eligible messages, which satisfy
    - messages that not refunded
    - messages that were responded within respond_by time frame
    - messages that haven't had fees created yet.
    - messages less than one month old
    """
    log.info("Starting collect_fees_for_messaging_purchases")
    one_month_ago = datetime.utcnow() - relativedelta(months=1)
    credit_ids_to_process = [
        c.id
        for c in db.session.query(MessageCredit)
        .options(load_only("id", "json"))
        .filter(
            MessageCredit.message_id.isnot(None),  # message credit has been used
            MessageCredit.refunded_at.is_(None),  # message credit has not been refunded
            MessageCredit.response_id.isnot(None),  # message has been responded
            MessageCredit.responded_at <= MessageCredit.respond_by,  # responded in time
            Message.created_at >= one_month_ago,  # less than one month old
        )
        .outerjoin(Message, MessageCredit.message_id == Message.id)
        .outerjoin(FeeAccountingEntry)
        .filter(FeeAccountingEntry.message_id.is_(None))  # no fee created yet
        if not c.json.get("free", False)
    ]
    chunks = list(even_chunks(credit_ids_to_process, 1000))
    log.info(
        "Collecting fees for messaging in chunks.",
        total_credits_to_process=len(credit_ids_to_process),
        chunk_count=len(chunks),
    )
    for chunk in chunks:
        collect_fees_for_messaging_purchase_chunk.delay(
            chunk, service_ns="provider_payments", team_ns="virtual_care"
        )
    return None


@job
def collect_fees_for_messaging_purchase_chunk(
    message_credit_ids: list[int],
) -> None:
    credits_to_process = (
        MessageCredit.query.options(
            joinedload(MessageCredit.message).options(
                joinedload(Message.channel).options(joinedload(Channel.participants))
            )
        )
        .filter(MessageCredit.id.in_(message_credit_ids))
        .all()
    )
    credits_to_process_count = len(credits_to_process)
    log.info(
        "Collecting fees for messaging.",
        credits_to_process_count=credits_to_process_count,
    )

    no_practitioner_count = 0
    none_message_billing_count = 0
    staff_cost_already_set_count = 0
    staff_cost_just_set_count = 0
    fee_collected_count = 0

    def report_outcome() -> None:
        counts = dict(
            no_practitioner_count=no_practitioner_count,
            none_message_billing_count=none_message_billing_count,
            staff_cost_already_set_count=staff_cost_already_set_count,
            staff_cost_just_set_count=staff_cost_just_set_count,
            fee_collected_count=fee_collected_count,
        )
        credits_processed_count = sum(counts.values())

        if credits_to_process_count == credits_processed_count:
            log.info("All done collecting fees for messaging.", **counts)
        else:
            log.error(
                "All done collecting fees, but not all credits were processed.",
                **counts,
                credits_to_process_count=credits_to_process_count,
                credits_processed_count=credits_processed_count,
            )
        return None

    for message_credit in credits_to_process:
        try:
            practitioner: User = message_credit.message.channel.practitioner
            if not practitioner:
                log.info(
                    "Not collecting fee for message credit in channel without practitioner.",
                    message_credit_id=message_credit.id,
                )
                no_practitioner_count += 1
                continue

            if not practitioner.active:
                log.info(
                    "Not collecting fee for message credit in channel with inactive practitioner.",
                    message_credit_id=message_credit.id,
                    practitioner_id=practitioner.id,
                )
                no_practitioner_count += 1
                continue

            profile = practitioner.practitioner_profile
            if not message_credit.message.requires_fee:
                # TODO: what do these cases represent?
                if message_credit.message_billing is None:
                    none_message_billing_count += 1
                    continue

                # TODO: extract staff_cost from json property to its own
                #       column so that these cases can be filtered above
                if message_credit.message_billing.staff_cost:
                    staff_cost_already_set_count += 1
                    continue

                message_credit.message_billing.staff_cost = profile.loaded_cost(
                    minutes=profile.minutes_per_message
                )
                db.session.add(message_credit.message_billing)
                db.session.commit()
                staff_cost_just_set_count += 1
            else:
                entry = FeeAccountingEntry(
                    message_id=message_credit.message_id,
                    amount=Decimal(RATE_PER_MESSAGE),
                    practitioner_id=profile.user_id,
                    type=FeeAccountingEntryTypes.MESSAGE,
                )
                db.session.add(entry)
                db.session.commit()
                audit(
                    ACTIONS.message_fee_collected,
                    user_id=message_credit.user_id,
                    fee_accounting_entry_id=entry.id,
                )
                fee_collected_count += 1

                log.info(
                    "Fee created for message",
                    message_credit_id=message_credit.id,
                    amount=str(Decimal(RATE_PER_MESSAGE)),
                    practitioner_id=profile.user_id,
                )
        except JobTimeoutException:
            report_outcome()
            raise
        except Exception as e:
            log_exception(
                e, get_task_service_name(collect_fees_for_messaging_purchases)
            )
            continue
    report_outcome()
    return None


@job("priority")
def create_zd_ticket_for_unresponded_promoted_messages() -> None:
    top_of_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    yesterday = top_of_hour - timedelta(hours=24)
    unresponded_messages = (
        db.session.query(Message)
        .join(MessageCredit, Message.id == MessageCredit.message_id)
        .filter(
            MessageCredit.id.isnot(None),
            MessageCredit.refunded_at.is_(None),
            MessageCredit.responded_at.is_(None),
            Message.created_at.between(yesterday - timedelta(hours=1), yesterday),
            Message.source == MessageSourceEnum.PROMOTE_MESSAGING.value,
        )
        .options(
            joinedload(Message.channel),
        )
        .all()
    )
    log.info(
        "Finished searching for unresponded promotoed message(s)",
        len_unresponded=len(unresponded_messages),
    )

    for message in unresponded_messages:
        provider = message.channel.practitioner
        member = message.channel.member

        zd_ticket_body = (
            "A message to a provider has not been responded to in 24 hours. Please "
            "recommend a provider in the same vertical who has availability in the next 24 hours.\n"
            f"Provider: {provider.full_name}\n"
            f"Provider Vertical: {provider.practitioner_profile.vertical}\n"
            f"Member ID: {member.id}\n"
            f"Message date: {message.created_at}"
        )
        send_general_ticket_to_zendesk(
            user=member,
            ticket_subject="A message has not been responded to in 24 hrs",
            content=zd_ticket_body,
            tags=["promote_messaging"],
        )

    # Needed for send_general_ticket_to_zendesk to persist zendesk user
    # also commits zendesk_user_id if created
    db.session.commit()
    return None


@job("priority")
def push_notify_practitioners_to_respond() -> None:
    """
    Prompt practitioners to respond to messages via push notification
    when there is 1 hour left to reply before 24hours response
    guarantee window has expired.
    """
    sms_copy = (
        "Quick! You only have 1 hour left to reply to a message on "
        "Maven. Open MPractice to view the message and reply now. (No need to "
        "respond to this SMS)"
    )
    push_copy = "You only have 1 hour left to reply to a message on Maven"

    now = datetime.utcnow()
    eligible_messages = (
        db.session.query(Message)
        .outerjoin(MessageCredit, Message.id == MessageCredit.message_id)
        .filter(
            MessageCredit.id.isnot(None),
            MessageCredit.refunded_at.is_(None),
            MessageCredit.respond_by.between(now, now + timedelta(hours=1)),
            MessageCredit.responded_at.is_(None),
        )
        .all()
    )
    log.debug(
        "%s message(s) have one hour or less to reply "
        "before 24-hour response guarantee expires",
        len(eligible_messages),
    )

    for message in eligible_messages:
        practitioners = [
            p.user
            for p in message.channel.participants
            if p.user != message.user and p.user.is_practitioner
        ]
        practitioner: User
        for practitioner in practitioners:
            profile = practitioner.practitioner_profile
            alert_setting = profile.notification_setting.get(
                "1hr_left_practitioner_respond_alert", True
            )
            if not alert_setting:
                log.debug("%s has notification turned off. Skipping...", practitioner)
                continue

            credit = message.credit

            # push notification
            if credit.json.get("1hr_left_push_notified_at"):
                log.debug("%s was already push notified for 1hr left alert", message)
            else:
                if alert_setting != "push":
                    log.debug(
                        "%s has push notification turned off. Skipping.", practitioner
                    )
                    continue

                log.debug("Push notify %s to respond to %s", practitioner, message)
                practitioner_devices = Device.for_user(practitioner, profile.role.name)
                result = apns_send_bulk_message(
                    [d.device_id for d in practitioner_devices],
                    push_copy,
                    application_name=profile.role.name,
                )

                if result and not result.errors and not result.failed:
                    credit.json["1hr_left_push_notified_at"] = now.isoformat()
                    db.session.add(credit)
                    db.session.commit()

            # sms notification
            if credit.json.get("1hr_left_sms_notified_at"):
                log.debug("%s was already SMS notified for 1hr left alert", message)
            else:
                if alert_setting != "sms":
                    log.debug(
                        "%s has SMS notification turned off. Skipping.", practitioner
                    )
                    continue

                log.debug("SMS notify %s to respond to %s", practitioner, message)
                practitioner_profile = practitioner.practitioner_profile
                result = send_sms(
                    message=sms_copy,
                    to_phone_number=practitioner_profile.phone_number,
                    user_id=practitioner_profile.user_id,
                    notification_type="messaging",
                )

                if result.is_ok:
                    log.info(
                        "Sent an SMS notification to prompt practitioner to respond to message",
                        user_id=practitioner_profile.user_id,
                        message_id=message.id,
                    )
                    credit.json["1hr_left_sms_notified_at"] = now.isoformat()
                    db.session.add(credit)
                    db.session.commit()
                    stats.increment(
                        metric_name=TWILIO_SMS_DELIVERY_SUCCESS_COUNT_METRICS,
                        pod_name=stats.PodNames.VIRTUAL_CARE,
                        tags=["result:success", "notification_type:messaging"],
                    )
                elif result.is_blocked:
                    log.debug(
                        f"{practitioner_profile.phone_number} is sms blocked: {result.error_message}"
                    )
                    db.session.add(practitioner_profile)
                    practitioner_profile.mark_as_sms_blocked(result.error_code)
                    db.session.commit()
    return None


@ddtrace.tracer.wrap()
@retryable_job(
    "priority",
    retry_limit=3,
    traced_parameters=("message_id", "initial_cx_message, user_id"),
    team_ns="virtual_care",
)
def send_to_zendesk(
    message_id: int,
    initial_cx_message: bool = False,
    user_id: str = "",
    user_need_when_solving_ticket: str = "",
) -> None:
    try:
        message = Message.query.filter_by(id=message_id).one()
    except SQLAlchemyError as e:
        generate_user_trace_log(
            log,
            LogLevel.ERROR,
            user_id,
            "DB operation error at getting message in send_to_zendesk",
            message_id=message_id,
            exception_type=e.__class__.__name__,
            exception_message=str(e),
        )
        stats.increment(
            metric_name=SEND_TO_ZENDESK_ERROR_COUNT_METRICS,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=["reason:db_operation_error"],
        )
        raise
    try:
        mzt = MessagingZendeskTicket(
            message,
            initial_cx_message,
            user_need_when_solving_ticket=user_need_when_solving_ticket,
        )
        mzt.update_zendesk()
    except ZendeskInvalidRecordException:
        stats.increment(
            metric_name=SEND_TO_ZENDESK_ERROR_COUNT_METRICS,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=["reason:zendesk_data_validation_error"],
        )
        return
    # this commit also persists zendesk_comment_id set downstream by record_comment_id
    db.session.commit()
    try:
        braze.update_message_attrs(message.channel.member)
    except Exception as e:
        generate_user_trace_log(
            log,
            LogLevel.ERROR,
            user_id,
            "Error in braze.update_message_attrs",
            message_id=message_id,
            exception=e,
        )
        stats.increment(
            metric_name=SEND_TO_ZENDESK_ERROR_COUNT_METRICS,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=["reason:braze_update_message_attrs_error"],
        )
        # Do not raise the exception from braze.update_message_attrs as it is not a part of the critical path
        # of the job
    return None


@retryable_job(retry_limit=3)
def audit_cx_responses() -> None:
    care_coordinators = (
        db.session.query(PractitionerProfile)
        .join(practitioner_verticals)
        .join(Vertical)
        .filter(is_cx_vertical_name(Vertical.name))
        .all()
    )
    cc_ids = [p.user_id for p in care_coordinators]
    log.debug("Got %d care coordinators", len(cc_ids))

    recent_internal_messages_base = (
        db.session.query(Message)
        .join(Channel)
        .filter(
            Channel.internal.is_(True),
            Message.created_at > datetime.utcnow() - timedelta(hours=24),
        )
    )

    member_msgs = recent_internal_messages_base.filter(
        Message.user_id.notin_(cc_ids)
    ).all()
    active_channel_ids = list({m.channel_id for m in member_msgs})
    member_count = len(member_msgs)
    log.debug(
        "Got %d recent member messages in %d internal channels",
        member_count,
        len(active_channel_ids),
    )

    practitioner_count = recent_internal_messages_base.filter(
        Message.channel_id.in_(active_channel_ids), Message.user_id.in_(cc_ids)
    ).count()
    log.debug(
        "Got %d recent care coordinator messages in internal channels",
        practitioner_count,
    )

    if member_count == 0:
        log.debug("Response rate OK: no recent member messages")
        return None

    # The response rate does not take into account a member sending multiple messages
    # at once and then receiving a single reply. For example if a member sends a CA 3
    # messages and the CA replies with 1 that counts as a 33% reply rate.
    response_rate = practitioner_count / member_count
    if response_rate >= 0.5:
        log.debug("Response rate OK: %s", response_rate)
        return

    log.info("BAD response rate: %s", response_rate)
    try:
        notify_mpractice_core_alerts_channel(
            notification_title="ZenDesk Response Rate Alert!",
            notification_body=f"ZD response rate alarm! Rate is {round(response_rate * 100)}%",
        )
    except Exception as e:
        log.warning("Could not alert admin! Error: %s", e)
    return None


def create_cx_message(
    member: User,
    copy_name: str | None = "cx-initiated-message",
    practitioner_id: int | None = None,
    only_first: bool = True,
    message: str | None = None,
) -> Message | None:
    if practitioner_id:
        practitioner = User.query.get(practitioner_id)
    elif member.care_coordinators:
        practitioner = member.care_coordinators[0]
    else:
        practitioner = AssignableAdvocate.default_care_coordinator()

    if not practitioner:
        log.warning(
            f"Either practitioner_id={practitioner_id} is invalid or default CX practitioner not found in create_cx_message"
        )
        return None

    if copy_name and (message is None):
        try:
            message = (
                db.session.query(TextCopy)
                .filter(TextCopy.name == copy_name)
                .one()
                .content
            )
        except NoResultFound:
            log.warning(f"No TextCopy named: {copy_name} in create_cx_message")
            return None
    elif copy_name:
        log.debug(
            f"Not using TextCopy {copy_name} because we have a message in create_cx_message"
        )

    if not message:
        log.warning(
            "No message for send_cx_message in create_cx_message", user_id=member.id
        )
        return None

    channel = Channel.get_or_create_channel(practitioner, [member])
    if only_first and (len(channel.messages) > 0):
        log.info(
            "CX conversation has already started for %s in create_cx_message", channel
        )
        return None

    m = Message(user=practitioner, channel=channel, body=message)
    db.session.add(m)
    log.debug("CX Message created in %s: %s", channel, m)
    return m


@job
def send_cx_intro_message_for_enterprise_users(hours_ago: int) -> None:
    now = datetime.utcnow()
    x_hours_ago_top = now - timedelta(hours=hours_ago)
    x_hours_ago_bottom = now - timedelta(hours=(hours_ago + 1))

    recent_ent_users = (
        db.session.query(User)
        .join(MemberTrack, User.id == MemberTrack.user_id)
        .filter(User.created_at.between(x_hours_ago_bottom, x_hours_ago_top))
        .all()
    )
    log.debug(
        "Got %s signed up enterprise users during (%s, %s).",
        len(recent_ent_users),
        x_hours_ago_bottom,
        x_hours_ago_top,
    )

    for user in recent_ent_users:
        # check appointments
        cc_ids = [cc.id for cc in user.care_coordinators]
        appts = (
            db.session.query(Appointment)
            .join(Schedule)
            .join(User, aliased=True)
            .filter(
                User.id == user.id,
                Appointment.purpose.contains("introduction")
                | Appointment.purpose.contains("birth_needs_assessment"),
            )
            .join(Product, Appointment.product_id == Product.id)
            .join(User, aliased=True)
            .filter(User.id.in_(cc_ids))
            .count()
        )
        if appts > 0:
            continue

        # check cc messages
        cc_channels = [
            ChannelUsers.find_existing_channel([user.id, cid]) for cid in cc_ids
        ]
        initiated_messages = [
            c.first_message and c.first_message.user == user for c in cc_channels if c
        ]
        if any(initiated_messages):
            continue

        intro_message = None
        # TODO: [multitrack] What to do here if user signed up for multiple tracks?
        #  Perhaps we should just assume one and send the intro message for the first
        member_track: MemberTrack = user.current_member_track
        if member_track and (
            member_track.client_track.name not in TRACKS_WITH_CA_MESSAGE_OFF
        ):
            if member_track and member_track.intro_message:
                intro_message = member_track.intro_message

            cx_message = create_cx_message(user, copy_name=None, message=intro_message)
            if cx_message:
                log.info(
                    f"Saved {cx_message} for user, sending email.", user_id=user.id
                )
                db.session.commit()
                braze_events.member_new_message(user, cx_message)
    return None


@job
def check_message_comment_id() -> None:
    check_message_comment_id_impl(
        start_time=datetime.utcnow() - timedelta(days=1), end_time=datetime.utcnow()
    )
    return None


def check_message_comment_id_impl(
    start_time: datetime,
    end_time: datetime,
) -> tuple[int, int]:
    recent_messages = (
        db.session.query(Message)
        .filter(Message.modified_at.between(start_time, end_time))
        .all()
    )

    num_of_qualified_messages_without_comment_id = 0
    num_of_qualified_message_with_comment_id = 0
    for message in recent_messages:
        if message.user and message.channel:
            is_care_coordinator = message.user.is_care_coordinator
            channel = message.channel
            is_member = channel.member and channel.member.is_member

            if channel.internal and not is_care_coordinator and is_member:
                if message.zendesk_comment_id:
                    num_of_qualified_message_with_comment_id = (
                        num_of_qualified_message_with_comment_id + 1
                    )
                else:
                    log.warn(
                        "Find a qualified message without comment id",
                        message_id=message.id,
                    )
                    num_of_qualified_messages_without_comment_id = (
                        num_of_qualified_messages_without_comment_id + 1
                    )

                    # Pushing message_id to reconciliation_list
                    # This list is used to retry messages that fail to get sent to Zendesk
                    # Retries happen in maven_to_zendesk_message_reconciliation job.
                    log.info(
                        "Adding message to maven-to-zendesk reconciliation set",
                        message_id=message.id,
                    )
                    # this setting should be the same as api/messaging/services/zendesk.py
                    redis_cli = redis_client()
                    redis_cli.sadd(MAVEN_TO_ZENDESK_RECONCILIATION_LIST_KEY, message.id)

    stats.increment(
        metric_name="qualified_messages_with_comment_id.count",
        pod_name=stats.PodNames.VIRTUAL_CARE,
        metric_value=num_of_qualified_message_with_comment_id,
    )

    stats.increment(
        metric_name="qualified_messages_withOUT_comment_id.count",
        pod_name=stats.PodNames.VIRTUAL_CARE,
        metric_value=num_of_qualified_messages_without_comment_id,
    )

    return (
        num_of_qualified_message_with_comment_id,
        num_of_qualified_messages_without_comment_id,
    )
