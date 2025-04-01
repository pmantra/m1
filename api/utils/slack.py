"""
We tried to migrate all slack_v1 (using legacy webhooks) notifications to slack_v2 (using slack channels emails) but now there's a new way to use Slack webhooks that is not legacy.
We decided not to move forward migrating everything to v2 because slack_v2 does not support some features that are important for certain notifications.
In particular:
* with slack_v2 we cannot notify channels with an @channel in the message
* with slack_v2 we generate a lot of visual noise in the slack channel, given that each message shows up as an email. In the case of channels that receive a lot of notifications per day (such as #bookings), this means a lot of visual noise with a big cost in user experience.

Hence, not all notifications were migrated from slack.py to slack_v2.py, and that's why slack.py still exists.

slack_v2 is still used and can be used if you prefer your slack notifications to come from email, but slack supports a new version of
webhook integration that can be done in this file. If you want to integrate with slack via webhook you can create a new webhook
for your slack channel under the Mono Notifications Slack app and use that webhook in the functions below
"""

import json
import os

import ddtrace
import requests

from utils.log import logger

log = logger(__name__)

BOOKINGS_WEBOOK_URL = os.environ.get("BOOKINGS_WEBOOK_URL")
BMS_WEBHOOK_URL = os.environ.get("BMS_WEBHOOK_URL")
ENTERPRISE_BOOKINGS_WEBHOOK_URL = os.environ.get("ENTERPRISE_BOOKINGS_WEBHOOK_URL")
FIREFIGHTERS_WEBHOOK_URL = os.environ.get("FIREFIGHTERS_WEBHOOK_URL")


@ddtrace.tracer.wrap()
def _notifiy_slack_channel(name, webhook_url, message):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if webhook_url and webhook_url.startswith("https://"):
        try:
            requests.post(webhook_url, data={"payload": json.dumps({"text": message})})
            log.info(
                "Successfully notified  slack channel with message",
                slack_channel=name,
            )
        except Exception as e:
            log.info(
                "Could not notify slack channel with message",
                slack_channel=name,
                exception=e,
            )
    else:
        log.warning(
            "No slack config for slack channel, could not deliver message",
            slack_channel=name,
            webhook_url=webhook_url,
        )


def notify_bookings_channel(message):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    _notifiy_slack_channel("bookings", BOOKINGS_WEBOOK_URL, message)


def notify_enterprise_bookings_channel(message):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    _notifiy_slack_channel(
        "enterprise-bookings", ENTERPRISE_BOOKINGS_WEBHOOK_URL, message
    )


def notify_bms_channel(message):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    _notifiy_slack_channel("mavenmilkorders", BMS_WEBHOOK_URL, message)


def notify_firefighters_channel(message):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    _notifiy_slack_channel("firefighters", FIREFIGHTERS_WEBHOOK_URL, message)
