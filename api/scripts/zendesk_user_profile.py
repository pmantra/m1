from __future__ import annotations

import time
from datetime import datetime
from typing import List, Optional

from authn.models.user import User
from messaging.services.zendesk import update_zendesk_user, zenpy_client
from messaging.services.zendesk_client import IdentityType
from storage.connection import db
from utils.log import logger

log = logger(__name__)

ZENDESK_RATE_LIMIT = 700


def get_all_active_members_missing_zendesk_user_id(
    limit: int = 0,
    updated_user_ids: Optional[list[int]] = None,
) -> List[User]:
    """
    Return all active members missing a `zendesk_user_id`
    :param updated_user_ids:
    :param limit:
    :return:
    """

    # handle `notin_` expecting an iterable list
    if updated_user_ids is None:
        updated_user_ids = []

    query = (
        db.session.query(User)
        .outerjoin(User.practitioner_profile)
        .outerjoin(User.member_profile)
        .filter(
            User.practitioner_profile == None,
            User.member_profile != None,
            User.zendesk_user_id.is_(None),
            User.id.notin_(updated_user_ids),
            User.created_at > datetime(2023, 1, 1),
        )
    )

    if limit:
        query = query.limit(limit)

    return query.all()


def get_all_active_members_with_zendesk_user_id(
    limit: int = 0,
    updated_user_ids: Optional[list[int]] = None,
) -> List[User]:
    """
    Return all active Users with a Zendesk user id and a phone number
    :param limit:
    :param updated_user_ids:
    :return:
    """

    # handle `notin_` expecting an iterable list
    if updated_user_ids is None:
        updated_user_ids = []

    query = (
        db.session.query(User)
        .outerjoin(User.practitioner_profile)
        .outerjoin(User.member_profile)
        .filter(
            User.practitioner_profile == None,
            User.member_profile != None,
            User.zendesk_user_id.isnot(None),
            User.id.notin_(updated_user_ids),
        )
    )

    if limit:
        query = query.limit(limit)

    return query.all()


def create_missing_zendesk_user_profile(
    batch_size: int = 50,
    max_iteration_limit: int = 30,
    configured_sleep_time: int = 60,
    dry_run: bool = True,
) -> None:
    updated_user_ids = []
    num_requests_made = 0
    total_successes = {}
    total_failures = []
    total_aborts = []

    for i in range(max_iteration_limit):
        # retrieve all Users that do not have a `zendesk_user_id`; we must pass in `updated_user_ids` to update our query filter
        # as we are dynamically updating the return result due to downstream db commits
        users_missing_zendesk_user_id = get_all_active_members_missing_zendesk_user_id(
            limit=batch_size, updated_user_ids=updated_user_ids
        )

        # if we've run out of queried items, exit the loop
        if not users_missing_zendesk_user_id:
            break

        # local successes and failures for the current batch
        batch_successes = {}
        batch_failures = []
        batch_aborts = []

        # iterate through users and call `get_or_create_zenpy_user` to create a Zendesk Profile for them
        for user in users_missing_zendesk_user_id:
            try:
                log.info("Creating Zendesk user for Maven user.", user_id=user.id)
                if not dry_run:
                    zd_user = zenpy_client.create_or_update_user(
                        user,
                    )
                    previous_user = (
                        db.session.query(User)
                        .filter(User.zendesk_user_id == zd_user.id)
                        .first()
                    )
                    if previous_user:
                        log.info(
                            "found duplicate ZD accounts, aborting creation",
                            zd_user_id=zd_user.id,
                            user_id=user.id,
                        )
                        batch_aborts.append(user.id)
                        continue
                    user.zendesk_user_id = zd_user.id
                    db.session.commit()
                num_requests_made += 1
                batch_successes[user.id] = user.zendesk_user_id
            except Exception as e:
                log.error(
                    "Script failed to create a Zendesk User profile for user",
                    user_id=user.id,
                    exception=e,
                )
                batch_failures.append(user.id)
                continue

            # check if the rate limit is about to be exceeded
            if num_requests_made >= ZENDESK_RATE_LIMIT / 2:
                log.info(
                    f"Rate limit reached. Pausing for {configured_sleep_time} seconds."
                )
                time.sleep(
                    configured_sleep_time
                )  # sleep to avoid exceeding the Zendesk rate limit
                num_requests_made = 0  # reset request count to 0

        # update list of processed zendesk ids
        updated_user_ids.extend([user.id for user in users_missing_zendesk_user_id])

        log.info(
            f"Successfully completed batch {i + 1}",
            user_ids_to_zendesk_user_ids=batch_successes,
            user_ids_failed=batch_failures,
        )

        # add local success and failure to total accumulations
        total_successes.update(batch_successes)
        total_failures.extend(batch_failures)
        total_aborts.extend(batch_aborts)

        # exit the loop early if fewer users are returned than the batch size
        if len(users_missing_zendesk_user_id) < batch_size:
            break

    log.info(
        "Retroactively created Zendesk User Profile for users",
        user_ids_to_zendesk_user_ids=total_successes,
        user_ids_failed=total_failures,
        user_ids_aborted=total_aborts,
    )


def update_zendesk_user_profile(
    batch_size: int = 50, max_iteration_limit: int = 30, configured_sleep_time: int = 60
) -> None:
    updated_user_ids = []
    num_requests_made = 0
    total_successes = {}
    total_failures = []

    for i in range(max_iteration_limit):
        # retrieve all Users that have a zendesk user profile; we must pass in `updated_user_ids` to update our query filter
        # as we are dynamically updating the return result due to downstream db commits
        users_required_phone_number_update = (
            get_all_active_members_with_zendesk_user_id(
                limit=batch_size, updated_user_ids=updated_user_ids
            )
        )

        # if we've run out of queried items, exit the loop
        if not users_required_phone_number_update:
            break

        # local successes and failures for the current batch
        batch_successes = {}
        batch_failures = []

        # iterate through users and call `get_or_create_zenpy_user` to create a Zendesk Profile for them
        for user in users_required_phone_number_update:
            try:
                # use TRACK identity to update org
                update_zendesk_user(
                    user_id=str(user.id),
                    update_identity=IdentityType.TRACK,
                )
                num_requests_made += 1
                batch_successes[user.id] = user.zendesk_user_id
            except Exception as e:
                log.error(
                    "Script failed to update Zendesk User profile phone number for user",
                    user_id=user.id,
                    exception=e,
                )
                batch_failures.append(user.id)
                continue

            # check if the rate limit is about to be exceeded
            if num_requests_made >= ZENDESK_RATE_LIMIT / 2:
                log.info(
                    f"Rate limit reached. Pausing for {configured_sleep_time} seconds."
                )
                time.sleep(
                    configured_sleep_time
                )  # sleep to avoid exceeding the Zendesk rate limit
                num_requests_made = 0  # reset request count to 0

        # update list of processed zendesk ids
        updated_user_ids.extend(
            [user.id for user in users_required_phone_number_update]
        )

        log.info(
            f"Successfully completed batch {i + 1}",
            user_ids_to_zendesk_user_ids=batch_successes,
            user_ids_failed=batch_failures,
        )

        # add local success and failure to total accumulations
        total_successes.update(batch_successes)
        total_failures.extend(batch_failures)

        if len(users_required_phone_number_update) < batch_size:
            break

    log.info(
        "Retroactively updated the phone number on the Zendesk User Profile for users",
        user_ids_to_zendesk_user_ids=total_successes,
        user_ids_failed=total_failures,
    )
