import datetime
from decimal import Decimal
from typing import Dict, List

import ddtrace
from flask import current_app
from sqlalchemy.orm.exc import NoResultFound

import emails
from appointments.models.appointment import Appointment
from authn.models.user import User
from authz.models.roles import ROLES
from common import stats
from l10n.utils import message_with_enforced_locale
from messaging.models.messaging import Message, MessageBilling
from models.forum import Post

# DO NOT REMOVE THE BELOW LINE. SQLALCHEMY NEEDS IT FOR MAPPER INSTANTIATION
from models.images import Image  # noqa: F401
from models.profiles import Device, MemberProfile
from models.referrals import ReferralCodeUse  # noqa: F401
from storage.connection import db
from tasks.queues import job, retryable_job
from utils import braze_events
from utils.apns import apns_fetch_inactive_ids, apns_send_bulk_message
from utils.constants import (
    MAVEN_SMS_DELIVERY_ERROR,
    SMS_MISSING_PROFILE,
    SMS_MISSING_PROFILE_NUMBER,
    TWILIO_SMS_DELIVERY_SUCCESS_COUNT_METRICS,
)
from utils.log import logger
from utils.slack import notify_bookings_channel
from utils.sms import country_accepts_url_in_sms, parse_phone_number, send_sms

log = logger(__name__)


@job(traced_parameters=("post_id",))
def notify_about_new_post(post_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.debug("Trying to notify for new post: %s", post_id)

    try:
        post = db.session.query(Post).filter(Post.id == post_id).one()
    except NoResultFound:
        log.warning("No post for ID %s - cannot send notis.", post_id)
        return

    _notify_parent_author(post)
    _notify_followers(post)


def _notify_followers(post):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.debug("Notifying followers for %s", post)
    for bookmarker in post.bookmarks:
        application_name, device_ids = _devices_for_forum_user(bookmarker)

        if device_ids:
            try:
                apns_send_bulk_message(
                    device_ids,
                    "There is a new reply to a post you follow!",
                    sound="default",
                    extra={"link": forum_deeplink(post.parent.id)},
                    application_name=application_name,
                )
                log.debug("All set - sent notification!")
            except Exception as e:
                log.warning(
                    "Problem sending notification via APNS to %s. Error: %s",
                    device_ids,
                    e,
                )
        else:
            log.debug("No devices to notify for %s following: %s", bookmarker, post)
    log.debug("Notified all followers for %s", post)


def _notify_parent_author(post):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if post.parent:
        application_name, device_ids = _devices_for_forum_user(post.parent.author)

        if device_ids:
            try:
                apns_send_bulk_message(
                    device_ids,
                    "There is a new reply to your post!",
                    sound="default",
                    extra={"link": forum_deeplink(post.parent.id)},
                    application_name=application_name,
                )
                log.debug("All set - sent notification!")
            except Exception as e:
                log.warning(
                    "Problem sending notification via APNS to %s. Error: %s",
                    device_ids,
                    e,
                )
        else:
            log.debug("No devices to notify for new post parent author: %s", post)
    else:
        log.debug("%s is top-level, no notification!", post)


def forum_deeplink(post_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return f"{current_app.config['BASE_URL']}/forum/posts/{post_id}"


def _devices_for_forum_user(user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.debug("Getting devices for %s", user)
    practitioner_devices = Device.for_user(user, "practitioner")
    member_devices = Device.for_user(user, "member")
    forum_devices = Device.for_user(user, "forum")

    if practitioner_devices:
        devices = practitioner_devices
        application_name = "practitioner"
    elif member_devices:
        devices = member_devices
        application_name = "member"
    else:
        devices = forum_devices
        application_name = "forum"

    device_ids = []
    for device in devices:
        device_ids.append(device.device_id)

    log.debug("Got devices %s for forum for user %s", device_ids, user)
    return application_name, device_ids


@job
def prune_devices(application_name="forum"):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    try:
        inactive_devices = apns_fetch_inactive_ids(application_name)
    except Exception as e:
        log.warning("PROBLEM with prune_devices! Error: %s", e)
        return

    for _id in inactive_devices:
        log.debug("Going to deactivate %s", _id)

        try:
            device = db.session.query(Device).filter(Device.device_id == _id).one()
        except NoResultFound:
            log.warning("No device for %s", _id)
        else:
            device.is_active = False

            log.debug("Deactivating %s", device)
            db.session.add(device)
            db.session.commit()
            log.debug("Deactivated %s", device)

    log.debug("No inactive devices at this time! (%s)", inactive_devices)


@job
def daily_messaging_summary():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    num_purchased = 0
    maven_credit_used = Decimal("0.00")
    stripe_charge_amount = Decimal("0.00")

    now = datetime.datetime.utcnow()
    a_day_ago = now - datetime.timedelta(days=1)
    purchases = (
        db.session.query(MessageBilling)
        .filter(MessageBilling.created_at.between(a_day_ago, now))
        .all()
    )

    for purchase in purchases:
        if purchase.message_product:
            num_purchased += purchase.message_product.number_of_messages
        else:
            num_purchased += 1  # this is either enterprise or subscription purchase
        maven_credit_used += Decimal(purchase.json.get("maven_credit_used", "0.00"))
        stripe_charge_amount += Decimal(
            purchase.json.get("stripe_charge_amount", "0.00")
        )

    num_sent_member = 0
    num_first = 0
    num_additional = 0
    num_practitioner = 0
    num_missing_users = 0

    all_messages_sent_last_24hrs = (
        db.session.query(Message)
        .filter(Message.created_at.between(a_day_ago, now))
        .all()
    )

    for message in all_messages_sent_last_24hrs:
        if not message.user:
            num_missing_users += 1
        elif message.user.is_practitioner and not message.user.is_care_coordinator:
            num_practitioner += 1
        elif message.user.is_member:
            num_sent_member += 1
            if message.is_first_message_in_channel:
                num_first += 1
            else:
                num_additional += 1

    report = (
        "Last 24 hours message report\n"
        f"Count of messages purchased: {num_purchased} "
        f"(credit used: {maven_credit_used}, cc charged: {stripe_charge_amount})\n"
        f"Count of consumer messages: {num_sent_member} "
        f"({num_first} first, {num_additional} additional) \n"
        f"Count of practitioner replies sent: {num_practitioner}\n"
        f"Count of messages not associated with users: {num_missing_users}"
    )

    log.debug(report)
    notify_bookings_channel(report)


@retryable_job("priority", retry_limit=3)
@ddtrace.tracer.wrap()
def notify_new_message(user_id, message_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """Send user an email to notify them they have a private message."""
    log_props = {"user_id": user_id, "message_id": message_id}
    # validate user
    user = User.query.get(user_id)
    if not user:
        log.warning(
            "User id not found",
            **log_props,
        )
        return

    # validate message
    message = Message.query.get(message_id)
    if not message:
        log.warning(
            "Message id not found",
            **log_props,
        )
        return

    # gather list of devices to send message to
    devices = Device.for_user(user, user.role_name)

    # send the notification
    send_new_message_notification(user=user, devices=devices, message=message)


def send_new_message_notification(user: User, devices: List[Device], message: Message):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Given a user, determine the appropriate notification message to send then
    send it.
    """
    log_props = {"user_id": user.id, "message_id": message.id}

    try:
        if user.is_practitioner:
            send_practitioner_notification_message(
                user=user, devices=devices, message=message
            )
        elif user.is_member:
            send_member_notification_message(
                user=user, devices=devices, message=message
            )
    except Exception as e:
        log.error(
            "Unable to send notification",
            is_practitioner=user.is_practitioner,
            is_member=user.is_member,
            error=e,
            **log_props,
        )


def send_practitioner_notification_message(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    user: User,
    devices: List[Device],
    message: Message,
):
    """Send a notification message to a practitioner."""
    # shared log properties
    log_props = {"user_id": user.id, "message_id": message.id}
    if not user.is_practitioner:
        log.warning(
            "User was expected to be a practitioner",
            **log_props,
        )
        return

    pp = user.practitioner_profile
    if not pp:
        log.warning(
            "Unable to send SMS for new message - profile unavailable",
            message_id=message.id,
            user_id=user.id,
            user_role=ROLES.practitioner,
        )

        stats.increment(
            metric_name=SMS_MISSING_PROFILE,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=[
                "result:failure",
                "notification_type:messaging",
                f"user_role:{ROLES.practitioner}",
                "source:send_practitioner_notification_message",
            ],
        )
        return None

    # DO NOT send SMS or Push notifications to CAs
    if pp.is_cx:
        return

    # build the message body
    message_body = construct_practitioner_notification_message_body(user)

    if pp.phone_number:
        try:
            _deliver_sms(
                user_profile=pp, message_body=message_body, log_props=log_props
            )
        except Exception as e:
            log.exception(
                "Exception found when attempting to send SMS notification for new message",
                message_id=message.id,
                user_id=user.id,
                exception=e,
            )

            stats.increment(
                metric_name=MAVEN_SMS_DELIVERY_ERROR,
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=[
                    "result:failure",
                    "notification_type:messaging",
                    "reason:maven_server_exception",
                    "source:send_practitioner_notification_message",
                ],
            )
    else:
        log.warning(
            "Unable to send SMS for new message - profile number unavailable",
            message_id=message.id,
            user_id=user.id,
            user_role=ROLES.practitioner,
        )

        stats.increment(
            metric_name=SMS_MISSING_PROFILE_NUMBER,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=[
                "result:failure",
                "notification_type:messaging",
                f"user_role:{ROLES.practitioner}",
                "source:send_practitioner_notification_message",
            ],
        )
        _push_notify_new_message(devices, user.role_name, message_body)


def send_member_notification_message(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    user: User,
    devices: List[Device],
    message: Message,
):
    """Send a notification message to a member."""
    # shared log properties
    log_props = {"user_id": user.id, "message_id": message.id}

    # build message body
    message_body = construct_member_notification_message_body(user, message)

    mp = user.member_profile
    if not mp:
        log.warning(
            "Unable to send SMS for new message - profile unavailable",
            message_id=message.id,
            user_id=user.id,
            user_role=ROLES.member,
        )

        stats.increment(
            metric_name=SMS_MISSING_PROFILE,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=[
                "result:failure",
                "notification_type:messaging",
                f"user_role:{ROLES.member}",
                "source:send_member_notification_message",
            ],
        )

    if mp.phone_number:
        try:
            _deliver_sms(
                user_profile=mp, message_body=message_body, log_props=log_props
            )
        except Exception as e:
            log.exception(
                "Exception found when attempting to send SMS notification for new message",
                message_id=message.id,
                user_id=user.id,
                exception=e,
            )

            stats.increment(
                metric_name=MAVEN_SMS_DELIVERY_ERROR,
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=[
                    "result:failure",
                    "notification_type:messaging",
                    "reason:maven_server_exception",
                    "source:send_member_notification_message",
                ],
            )
    elif devices:
        log.warning(
            "Unable to send SMS for new message - profile number unavailable",
            message_id=message.id,
            user_id=user.id,
            user_role=ROLES.member,
        )

        stats.increment(
            metric_name=SMS_MISSING_PROFILE_NUMBER,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=[
                "result:failure",
                "notification_type:messaging",
                f"user_role:{ROLES.member}",
                "source:send_member_notification_message",
            ],
        )
        _push_notify_new_message(devices, user.role_name, message_body)
    else:
        if message.channel.is_wallet:
            braze_events.member_new_wallet_message(user, message)
            log.info(
                "Wallet notification message sent to member",
                **log_props,
            )
        else:
            braze_events.member_new_message(user, message)
            log.info(
                "Message notification sent to member",
                **log_props,
            )


def _deliver_sms(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    user_profile,
    message_body: str,
    log_props: Dict,
) -> None:
    """
    Send an SMS notification to the phone number attached to the user_profile.
    Handles marking the user_profile as sms_blocked if the send result indicates.
    """
    phone_number = user_profile.phone_number
    result = send_sms(
        message=message_body,
        to_phone_number=phone_number,
        user_id=user_profile.user_id,
        notification_type="messaging",
    )

    if result.is_ok:
        log.info(
            "Sent an SMS notification to the user about a new message in the Maven app",
            user_id=user_profile.user_id,
        )
        stats.increment(
            metric_name=TWILIO_SMS_DELIVERY_SUCCESS_COUNT_METRICS,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=["result:success", "notification_type:messaging"],
        )
    if result.is_blocked:
        log.warning(
            "Phone number is sms blocked",
            error_message=result.error_message,
            user_id=user_profile.user_id,
        )
        db.session.add(user_profile)
        user_profile.mark_as_sms_blocked(result.error_code)
        db.session.commit()


def construct_practitioner_notification_message_body(user: User) -> str:
    """
    Construct a notification message body for a practitioner.
    NOTE: The user must be externally validated with `user.is_practitioner`.
    """
    if not user.is_practitioner:
        raise ValueError("User must be a practitioner")

    # standard message notification for all activity
    return "You have a new message on Maven"


def construct_member_notification_message_body(
    user: User,
    message: Message,
) -> str:
    """
    Construct a notification message body for members.
    Throws if user is not a member.
    """
    if not user.is_member:
        raise ValueError("User must be a member")

    # use a specific message for wallet activity notifications
    if message.channel.is_wallet:
        message_body = message_with_enforced_locale(
            user=user, text_key="wallet_message_body"
        )
    else:
        # Fall through for all other cases. This matches the previous behavior
        message_body = message_with_enforced_locale(
            user=user, text_key="generic_message_body"
        )
    parsed_phone_number = parse_phone_number(user.member_profile.phone_number)
    # if we were unable to parse the phone number we adhere to the default condition of including the url
    if not parsed_phone_number or country_accepts_url_in_sms(parsed_phone_number):
        cta_link = message_with_enforced_locale(
            user=user, text_key="cta_message_link"
        ).format(link=current_app.config["BASE_URL"])
        message_body = f"{message_body} {cta_link}"

    return message_body


def _push_notify_new_message(devices, app_name, notification_message):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if devices:
        device_ids = [d.device_id for d in devices]
        log.info(
            "Sending devices %s push notification %s", device_ids, notification_message
        )
        apns_send_bulk_message(
            device_ids, alert=notification_message, application_name=app_name
        )
    else:
        log.warning("No device found to push notify new message.")


@retryable_job(retry_limit=3, traced_parameters=("appointment_id",))
def notify_birth_plan_pdf_availability(appointment_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    appointment = Appointment.query.get(appointment_id)
    log.debug("Sending birth plan available notification for %s", appointment)

    braze_events.birth_plan_posted(appointment)


@job(team_ns="enrollments")
def send_member_profile_follow_up_emails():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for profile in db.session.query(MemberProfile).filter(
        MemberProfile.follow_up_reminder_send_time <= datetime.datetime.utcnow()
    ):
        send_member_profile_follow_up_email.delay(
            profile.user_id, team_ns="enrollments"
        )


@job(team_ns="enrollments")
def send_member_profile_follow_up_email(user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    profile = MemberProfile.query.get(user_id)
    emails.follow_up_reminder_email(profile)

    profile.follow_up_reminder_send_time = None
    db.session.commit()
