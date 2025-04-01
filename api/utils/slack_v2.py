import enum
from typing import Optional

from common import stats
from utils.mail import send_message


class SlackEmails(str, enum.Enum):
    CARE_OPS = "care_ops_alerts-aaaaeqrl6izulzcwnw4aopfauq@mavenclinic.slack.com"
    MPRACTICE_CORE = (
        "mpractice-core-pod-al-aaaais2g5meagds2vqdsrj56xq@mavenclinic.slack.com"
    )
    PROVIDER_OPS = (
        "provider-ops-alerts-aaaaf63dj4x5jcmoj2lmvzksae@mavenclinic.slack.com"
    )
    PROGRAM_OPS = (
        "wallet-survey-respons-aaaabrqaqazkl7ooqcmfqjjlju@mavenclinic.slack.com"
    )
    ENTERPRISE_BOOKINGS_VIP = (
        "enterprisebookings-vi-aaaabrbcyjkjkyztnx3zonwo2i@mavenclinic.slack.com"
    )

    MEMBER_CARE_ALERTS = "v3q6c1r1o3t9q9q1@mavenclinic.slack.com"

    BMS_ALERTS = (
        "team-maven-milk-order-aaaaazm5ajj4ekyjffa4nlywuq@mavenclinic.slack.com"
    )

    GDPR_DELETE_REQUESTS = (
        "gdpr-request-alerts-aaaahdvg56mod4wnvv2rm6t7nm@mavenclinic.slack.com"
    )
    PAYMENT_OPS_NOTIFICATIONS = "y4w8y7k2u9o5s9l2@mavenclinic.slack.com"


def _notify_slack_channel(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    slack_channel_email,
    notification_title,
    notification_body,
    notification_html,
    production_only=True,
):
    send_message(
        to_email=slack_channel_email,
        subject=notification_title,
        text=notification_body,
        production_only=production_only,
        internal_alert=True,
        html=notification_html,
    )

    try:
        slack_name = SlackEmails(slack_channel_email).name
    except ValueError:
        slack_name = "UNKNOWN"

    stats.increment(
        metric_name="api.utils.slack_v2.notify_slack_channel",
        pod_name=stats.PodNames.CORE_SERVICES,
        tags=[f"slack_channel:{slack_name}"],
    )


def notify_mpractice_core_alerts_channel(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    notification_title, notification_body, notification_html=None, production_only=True
):
    _notify_slack_channel(
        slack_channel_email=SlackEmails.MPRACTICE_CORE,
        notification_title=notification_title,
        notification_body=notification_body,
        notification_html=notification_html,
        production_only=production_only,
    )


def notify_care_ops_alerts_channel(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    notification_title, notification_body, notification_html=None, production_only=True
):
    _notify_slack_channel(
        slack_channel_email=SlackEmails.CARE_OPS,
        notification_title=notification_title,
        notification_body=notification_body,
        notification_html=notification_html,
        production_only=production_only,
    )


def notify_provider_ops_alerts_channel(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    notification_title, notification_body, notification_html=None, production_only=True
):
    _notify_slack_channel(
        slack_channel_email=SlackEmails.PROVIDER_OPS,
        notification_title=notification_title,
        notification_body=notification_body,
        notification_html=notification_html,
        production_only=production_only,
    )


def notify_wallet_ops_alerts_channel(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    notification_title,
    notification_body,
    notification_html=None,
    production_only=True,
):
    _notify_slack_channel(
        slack_channel_email=SlackEmails.PROGRAM_OPS,
        notification_title=notification_title,
        notification_body=notification_body,
        production_only=production_only,
        notification_html=notification_html,
    )


def notify_bms_alerts_channel(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    notification_title,
    notification_body,
    notification_html=None,
    production_only=True,
):
    _notify_slack_channel(
        slack_channel_email=SlackEmails.BMS_ALERTS,
        notification_title=notification_title,
        notification_body=notification_body,
        production_only=production_only,
        notification_html=notification_html,
    )


def notify_member_care_alerts_channel(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    notification_title,
    notification_body,
    notification_html=None,
    production_only=True,
):
    _notify_slack_channel(
        slack_channel_email=SlackEmails.MEMBER_CARE_ALERTS,
        notification_title=notification_title,
        notification_body=notification_body,
        production_only=production_only,
        notification_html=notification_html,
    )


def notify_vip_bookings_channel(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    notification_title, notification_body, production_only=True, notification_html=None
):
    _notify_slack_channel(
        slack_channel_email=SlackEmails.ENTERPRISE_BOOKINGS_VIP.value,
        notification_title=notification_title,
        notification_body=notification_body,
        production_only=production_only,
        notification_html=notification_html,
    )


def notify_gdpr_delete_user_request_channel(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    notification_title, notification_body, production_only=True, notification_html=None
):
    _notify_slack_channel(
        slack_channel_email=SlackEmails.GDPR_DELETE_REQUESTS.value,
        notification_title=notification_title,
        notification_body=notification_body,
        production_only=production_only,
        notification_html=notification_html,
    )


def notify_payment_ops_channel(
    notification_title: str,
    notification_body: str,
    production_only: bool = True,
    notification_html: Optional[str] = None,
) -> None:
    _notify_slack_channel(
        slack_channel_email=SlackEmails.PAYMENT_OPS_NOTIFICATIONS.value,
        notification_title=notification_title,
        notification_body=notification_body,
        production_only=production_only,
        notification_html=notification_html,
    )
