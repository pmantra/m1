from __future__ import annotations

import os
from datetime import datetime
from typing import List, Optional

import requests
from maven import feature_flags

from authn.models.user import User
from braze.client.braze_client import (
    BrazeClient,
    BrazeEvent,
    BrazeExportedUser,
    BrazeUserAttributes,
)
from utils.braze import build_user_attrs
from utils.log import logger

log = logger(__name__)


def compare_possible_datetimes(braze_str: str, mono_str: str) -> bool:
    """
    Braze uses a different format date times, so this normalizes the date
    time strings before comparison
    """
    try:
        return datetime.strptime(
            braze_str, "%Y-%m-%dT%H:%M:%S.%fZ"
        ) == datetime.strptime(mono_str, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return False


def compare_to_braze_profile(
    *,
    user_attributes: BrazeUserAttributes,
    braze_profile: BrazeExportedUser,
    omitted_attributes: Optional[List[str]] = None,
) -> BrazeUserAttributes | None:
    """
    This function will compare the user's data to the data in the exported braze profile,
    and return a new BrazeUserAttributes object with the difference.

    The data in user_attributes is treated as the truth.
    If the same key exists in both data sets and the values differ, use the data in user_attributes.
    """
    if user_attributes.external_id != braze_profile.external_id:
        log.warn(
            "Cannot compare data: External IDs do not match",
            user_attributes_external_id=user_attributes.external_id,
            braze_profile_external_id=braze_profile.external_id,
        )
        return None

    omitted_attributes = omitted_attributes or []
    truth_attrs = user_attributes.attributes
    braze_attrs = braze_profile.as_dict()

    attributes_to_update = {}
    for key, value in truth_attrs.items():
        if (
            key not in omitted_attributes
            and key in braze_attrs
            and braze_attrs[key] != value
            and not compare_possible_datetimes(braze_attrs[key], value)
        ):
            log.info("mismatch", key=key, braze_attrs_key=braze_attrs[key], value=value)
            attributes_to_update[key] = value

    if attributes_to_update:
        return BrazeUserAttributes(
            external_id=user_attributes.external_id, attributes=attributes_to_update
        )
    return None


def rq_delay_with_feature_flag(func, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
    if not feature_flags.bool_variation(
        flag_key="kill-switch-braze-api-requests",
        default=not bool(os.environ.get("TESTING")),
    ):
        func_name = func.__name__ if hasattr(func, "__name__") else str(func)
        log.warning(
            f"Skipping {func_name} request in when `kill-switch-braze-api-requests` flag is disabled."
        )
    else:
        func.delay(*args, **kwargs)


def recover_braze_user(*, external_id: str) -> requests.Response | None:
    """
    This function will identify gaps between the user's current data in our system,
    and the data that is currently in their Braze profile.

    If any gaps are identified, this will call Braze to update the user's profile.
    """
    return recover_braze_users(external_ids=[external_id])


def get_mismatched_braze_users(
    *,
    users: list[User],
    omitted_attributes: Optional[List[str]] = None,
) -> list[BrazeUserAttributes]:
    braze_client = BrazeClient()

    users_to_update = []
    for user in users:
        try:
            user_attributes: BrazeUserAttributes = build_user_attrs(user=user)
            braze_profile: BrazeExportedUser | None = braze_client.fetch_user(
                external_id=user.esp_id
            )

            attributes_to_update: BrazeUserAttributes | None
            if braze_profile is None:
                log.info(
                    "Braze profile not found. Including all user attributes.",
                    external_id=user.esp_id,
                )
                attributes_to_update = user_attributes
            else:
                attributes_to_update = compare_to_braze_profile(
                    user_attributes=user_attributes,
                    braze_profile=braze_profile,
                    omitted_attributes=omitted_attributes,
                )

            if attributes_to_update:
                users_to_update.append(attributes_to_update)
        except Exception as e:
            log.error(
                "Error while fetching user attributes: {}".format(e),
                external_id=user.esp_id,
            )

    return users_to_update


def recover_braze_users(*, external_ids: list[str]) -> requests.Response | None:
    """
    This function will identify gaps between the users' current data in our system,
    and the data that is currently in their Braze profile.

    If any gaps are identified, this will call Braze to update the users' profiles.
    """
    users = User.query.filter(User.esp_id.in_(external_ids)).all()

    users_to_update = get_mismatched_braze_users(users=users)

    if users_to_update:
        braze_client = BrazeClient()
        return braze_client.track_users(user_attributes=users_to_update)
    return None


def send_braze_event(
    *, external_id: str, event_name: str, properties: dict[str, str]
) -> None:
    """
    This function will send a Braze event to the user's profile.
    """
    braze_client = BrazeClient()
    resp = braze_client.track_user(
        events=[
            BrazeEvent(external_id=external_id, name=event_name, properties=properties)
        ]
    )
    if resp and resp.ok:
        log.info(
            "Successfully sent event to Braze",
            external_id=external_id,
            event_name=event_name,
            properties=properties,
        )
    else:
        log.error(
            "Failed to send event to Braze",
            external_id=external_id,
            event_name=event_name,
            properties=properties,
        )
