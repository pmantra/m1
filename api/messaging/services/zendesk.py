from __future__ import annotations

import contextlib
import os
import re
import time
from abc import ABC, abstractmethod
from typing import Generator

import ddtrace
from flask_babel import lazy_gettext
from maven import feature_flags
from maven.feature_flags import Context
from redset.locks import LockTimeout
from sqlalchemy.exc import SQLAlchemyError
from zenpy.lib.api_objects import Comment, Ticket
from zenpy.lib.api_objects import User as ZDUser
from zenpy.lib.exception import APIException as ZendeskAPIException

import configuration
from authn.models.user import User
from common import stats
from common.constants import ENVIRONMENT, Environment
from messaging.models.messaging import Channel, Message
from messaging.repository.message import MessageRepository
from messaging.services.zendesk_client import (
    IdentityType,
    ZendeskAPIEmailAlreadyExistsException,
    ZendeskClient,
)
from messaging.services.zendesk_models import ZendeskClientTrack, ZendeskTrackName
from messaging.utils.common import get_wallet_by_channel_id, wallet_exists_for_channel
from storage.connection import db
from tasks.helpers import get_user
from tasks.queues import job, retryable_job
from utils.cache import RedisLock, redis_client
from utils.constants import ZENDESK_UPDATE_COUNT_METRIC, UpdateZendeskFailureReason
from utils.exceptions import DeleteUserActionableError
from utils.failed_external_api_call_recorder import FailedVendorAPICallRecorder
from utils.flag_groups import ZENDESK_UPDATE_ORGANIZATION, ZENDESK_USER_PROFILE
from utils.launchdarkly import user_context
from utils.log import LogLevel, generate_user_trace_log, logger
from utils.string_matching import hamming_distance
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers

log = logger(__name__)

creds = {
    "email": os.environ.get("ZENDESK_EMAIL", "support+consumer@mavenclinic.com"),
    "token": os.environ.get("ZENDESK_API_TOKEN", "foobar"),
    "subdomain": os.environ.get("ZENDESK_DOMAIN", "mavenclinic"),
}

zenpy_client = ZendeskClient(creds, FailedVendorAPICallRecorder())

ZENDESK_PRACTITIONER_TAGS = ["mavenpractitioners"]

MAVEN_TO_ZENDESK_RECONCILIATION_LIST_KEY = "maven_to_zendesk_reconciliation_list"

# Max number of characters that can be different between zendesk comment and mono message to consider them a match
MAX_STRING_MATCH_DISTANCE = 5


def ticket_context(ticket: Ticket) -> Context:
    builder = Context.builder(str(ticket.id)).kind("ticket")

    builder.set("ticket_id", ticket.id)
    return builder.build()


def enable_set_user_need_if_solving_ticket(ticket: Ticket) -> bool:

    ff_value = feature_flags.bool_variation(
        "enable-set-user-need-if-solving-ticket",
        context=ticket_context(ticket),
        default=False,
    )
    log.info(
        "enable-set-user-need-if-solving-ticket ff evaluated",
        ticket_id=ticket.id,
        ff_value=ff_value,
    )
    return ff_value


def enable_merge_duplicate_zendesk_profiles() -> bool:
    return feature_flags.bool_variation(
        flag_key=ZENDESK_USER_PROFILE.MERGE_DUPLICATE_ZENDESK_PROFILES,
        default=False,
    )


def should_update_zendesk_user_profile() -> bool:
    return feature_flags.bool_variation(
        flag_key=ZENDESK_USER_PROFILE.UPDATE_ZENDESK_USER_PROFILE,
        default=False,
    )


def get_user_need_custom_field_id() -> int:
    # In ZD, tickets have custom fields. In particular, they have a custom field for user_need,
    # which we update upon solving tickets. We need to reference it by an ID
    USER_NEED_CUSTOM_FIELD_ID_QA2 = 32089765770643
    USER_NEED_CUSTOM_FIELD_ID_PROD = 31873516408723
    if Environment.current() == Environment.PRODUCTION:
        return USER_NEED_CUSTOM_FIELD_ID_PROD
    return USER_NEED_CUSTOM_FIELD_ID_QA2


def should_update_zendesk_org() -> bool:
    return feature_flags.bool_variation(
        flag_key=ZENDESK_UPDATE_ORGANIZATION,
        default=False,
    )


# This exception is raised when we encounter a validation error from Zendesk.
# Do not retry without modification of the data.
class ZendeskInvalidRecordException(Exception):
    def __init__(
        self,
        message: str = "",
        zendesk_api_exception: ZendeskAPIException | None = None,
    ) -> None:
        # the zendesk_api_exception.details field has been shown to contain
        # PII. Do not inject it into the exception where it may be logged.
        if not zendesk_api_exception:
            super().__init__(f"zendesk data validation error: {message}")
            return

        bad_field_names = (zendesk_api_exception.response.get("details") or {}).keys()
        error_type = zendesk_api_exception.response.get("error") or "unknown"
        error_description = (
            zendesk_api_exception.response.get("description") or "unknown"
        )
        super().__init__(
            f"zendesk data validation error: {message} - {error_type} - {error_description} - {bad_field_names}",
        )


def namespace_subject(subject: str) -> str:
    if Environment.current() != Environment.PRODUCTION:
        subject = f"{ENVIRONMENT}: {subject}"

    return subject


def handle_another_user_might_have_reference_to_zd_user(
    zd_user: ZDUser, user_id: int
) -> None:

    # We've seen cases where a ZD user that we want to link to a maven user is already associated to a different user.
    # This is probably the case when members recently had a new maven user created,
    # and the old one is linked to their ZD account.
    # In that case, we need to update their old user, removing its reference to the zendesk user
    # So we can link the new user account to the zd user
    previous_user = (
        db.session.query(User).filter(User.zendesk_user_id == zd_user.id).first()
    )
    if previous_user:
        generate_user_trace_log(
            log,
            LogLevel.ERROR,
            str(user_id),
            "Found another user with assigned zendesk_user_id",
            previous_user_id=previous_user.id,
            current_user_id=user_id,
            zendesk_user_id=zd_user.id,
        )
        previous_user.zendesk_user_id = None
        db.session.commit()


def enable_validate_existing_zendesk_user_id(user: User) -> bool:
    return feature_flags.bool_variation(
        "enable-validate-existing-zendesk-user-id",
        user_context(user),
        default=False,
    )


def get_zenpy_user_from_zendesk(
    zendesk_user_id: str, user_id: int, called_by: str = "Not set"
) -> ZDUser | None:
    log.info(
        "getting zendesk user",
        zendesk_id=zendesk_user_id,
        user_id=user_id,
        called_by=called_by,
    )
    return zenpy_client.get_zendesk_user(zendesk_user_id=zendesk_user_id)


def get_or_create_zenpy_user(user, called_by="Not set", validate_existing_zendesk_user_id=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation

    if user.zendesk_user_id:
        # zendesk_user_id may become invalid. When validate_existing_zendesk_user_id is True,
        # we will validate that a ZD account exists for this id.
        # If that fails, we will alternatively validate if a ZD account exits for user email.
        if (
            not validate_existing_zendesk_user_id
            or not enable_validate_existing_zendesk_user_id(user)
        ):
            log.info(
                "Using stored zendesk_user_id without validating it",
                zendesk_id=user.zendesk_user_id,
                user_id=user.id,
            )
            return ZDUser(id=user.zendesk_user_id)

        # Else, validate that user.zendesk_user_id corresponds to an existing ZD User
        zd_user_account_by_id = zenpy_client.get_zendesk_user(
            zendesk_user_id=str(user.zendesk_user_id)
        )
        if zd_user_account_by_id:
            log.info(
                "Using stored zendesk_user_id after validating it.",
                zendesk_id=user.zendesk_user_id,
                user_id=user.id,
            )
            return ZDUser(id=user.zendesk_user_id)

        log.info(
            "Stored zendesk_user_id does not correspond to any existing ZD account",
            zendesk_id=user.zendesk_user_id,
            user_id=user.id,
        )
        # Else, search a ZD account by user.email
        zd_user_account_by_email = zenpy_client.get_zendesk_user(
            zendesk_user_email=user.email
        )
        if zd_user_account_by_email:
            log.info(
                "Found a ZD account for user searching by email. Will replace that account's zendesk_user_id on the user",
                zd_user_account_by_email_id=zd_user_account_by_email.id,
                user_id=user.id,
                current_user_zendesk_user_id=user.zendesk_user_id,
            )
            handle_another_user_might_have_reference_to_zd_user(
                zd_user_account_by_email, user.id
            )

            user.zendesk_user_id = zd_user_account_by_email.id
            return ZDUser(id=user.zendesk_user_id)

        # Else, move on, which means, create a new zd account
        log.info(
            "Could not find any ZD account by zendesk_user_id nor email. Will proceed to create a new zd account for user",
            user_id=user.id,
        )

    log.info("Creating Zendesk user for Maven user.", user_id=user.id)
    zd_user = zenpy_client.create_or_update_user(
        user,
        called_by=called_by,
    )

    # This call should not be needed here anymore but just in case
    handle_another_user_might_have_reference_to_zd_user(zd_user, user.id)

    user.zendesk_user_id = zd_user.id
    return zd_user


@contextlib.contextmanager
def update_zendesk_user_job_lock(
    user_id: str,
    update_identity: str,
    lock_timeout_sec: int = 10,
) -> Generator[None, None, None]:
    """
    Grab lock on user_id to prevent concurrent updates to one zendesk user
    """
    if user_id is None:
        raise RequiredParameterException

    user_id_cache_key = f"update_zendesk_user:user_id:lock:{user_id}"
    try:
        with RedisLock(user_id_cache_key, timeout=lock_timeout_sec):
            yield True
    except LockTimeout as e:
        log.info(
            "Missed update zendesk user lock due to timeout, will requeue the job",
            user_id=user_id,
            update_identity=update_identity,
            error=e,
        )
        update_zendesk_user.delay(
            user_id=user_id,
            update_identity=update_identity,
            team_ns="virtual_care",
            caller="update_zendesk_user_job_lock",
        )
        yield False


@ddtrace.tracer.wrap()
@job
def update_zendesk_user(user_id: str, update_identity: str = "") -> None:
    with update_zendesk_user_job_lock(user_id, update_identity) as lock_acquired:
        if lock_acquired:
            user = get_user(user_id)
            if not user:
                log.warning(
                    "Could not updated Zendesk User Profile. Could not find user.",
                    user_id=user_id,
                )
                return None

            if not user.zendesk_user_id:
                log.warning(
                    "Could not updated Zendesk User Profile. Missing `zendesk_user_id` on the User model.",
                    user_id=user.id,
                )
                return None

            existing_zd_user = zenpy_client.get_zendesk_user(
                zendesk_user_id=str(user.zendesk_user_id)
            )
            if not existing_zd_user:
                log.warning(
                    "Zendesk User Profile not found for User model's `zendesk_user_id` field",
                    user_id=user.id,
                    zendesk_user_id=user.zendesk_user_id,
                )
                return None
            # if we're updating track, update user org
            if update_identity == IdentityType.TRACK:
                org_id = user.organization_v2.id if user.organization_v2 else None
                zendesk_organization = zenpy_client.get_zendesk_organization(
                    org_id,
                )
                if not zendesk_organization:
                    # don't create org because we don't want to call back to the org table
                    # to get the info we need, zd should be given the info we need. manual
                    # remediation required to reduce code complexity
                    log.error(
                        "Missing organization when trying update Zendesk organization",
                        org_id=org_id,
                        user_id=user_id,
                    )
                else:
                    existing_zd_user.organization_id = zendesk_organization.id

            # if the Zendesk profile exists, update the zd user attributes
            existing_zd_user.external_id = user.id
            existing_zd_user.email = user.email.lower() if user.email else user.email
            existing_zd_user.phone = (
                re.sub(r"[^+\d]", "", user.profile.phone_number)
                if (user.profile and user.profile.phone_number)
                else None
            )
            existing_zd_user.name = (
                user.full_name if user.first_name else user.email.split("@")[0]
            )
            if existing_zd_user.user_fields is None:
                existing_zd_user.user_fields = {}
            existing_zd_user.user_fields["care_advocate"] = (
                user.care_coordinators[0].full_name if user.care_coordinators else None
            )

            existing_zd_user.user_fields["track"] = ", ".join(
                f"{track.name} - {[modifier.value for modifier in track.track_modifiers]}"
                if track.track_modifiers
                else f"{track.name}"
                for track in user.active_tracks
            )

            try:
                # In the case of updating email, we need to update primary identity too
                if update_identity == IdentityType.EMAIL:
                    # make the new identity field the primary value
                    zenpy_client.update_primary_identity(
                        zendesk_user_id=str(user.zendesk_user_id),
                        zendesk_user=existing_zd_user,
                        update_identity=update_identity,
                    )

                # apply final Zendesk User Profile update
                zenpy_client.update_user(
                    user_id=str(user.id), zendesk_user=existing_zd_user
                )

                log.info(
                    "Zendesk Profile updated for user",
                    user_id=user.id,
                    zendesk_user_id=user.zendesk_user_id,
                    update_identity=update_identity,
                )

                return None
            except ZendeskAPIEmailAlreadyExistsException as e:

                # We were not able to make the update because another ZD account already exists with the given email
                # We will attempt to merge that account into the user's existing account.

                # Get the other Zendesk account that has the user email
                source_zendesk_user = zenpy_client.get_zendesk_user(
                    zendesk_user_email=user.email
                )
                if not source_zendesk_user:
                    log.info(
                        "Got exception due to email already being used, but failed to find another ZD profile by email",
                        user_id=user.id,
                        zendesk_user_id=user.zendesk_user_id,
                        exception=e,
                    )
                    return None

                if not enable_merge_duplicate_zendesk_profiles():
                    log.info(
                        "Duplicate Zendesk profiles found, but flag to merge duplicate profiles is disabled.",
                        user_id=user.id,
                        zendesk_user_id=user.zendesk_user_id,
                        duplicate_zd_profile_zendesk_user_id=source_zendesk_user.id,
                        exception=e,
                    )
                    return None

                log.info(
                    "Found existing Zendesk Profile with duplicate email. Will attempt to merge duplicate profiles for user.",
                    user_id=user.id,
                    zendesk_user_id=user.zendesk_user_id,
                    duplicate_zd_profile_zendesk_user_id=source_zendesk_user.id,
                    exception=e,
                )

                merged_zendesk_profile = merge_zendesk_profiles(
                    user_id=user_id,
                    source_zendesk_user=source_zendesk_user,
                    destination_zendesk_user=existing_zd_user,
                )

                # after merging the profiles we need to set the email as the primary identity
                try:
                    merged_zendesk_profile.email = (
                        user.email.lower() if user.email else user.email
                    )

                    zenpy_client.update_primary_identity(
                        zendesk_user_id=str(user.zendesk_user_id),
                        zendesk_user=existing_zd_user,
                        update_identity=IdentityType.EMAIL,
                    )
                    zenpy_client.update_user(
                        user_id=str(user.id), zendesk_user=existing_zd_user
                    )
                except Exception as e:
                    log.info(
                        "Could not update primary email after merging profiles",
                        user_id=user_id,
                        zendesk_user_id=merged_zendesk_profile.id,
                        duplicate_zd_profile_zendesk_user_id=source_zendesk_user.id,
                        exception=e,
                    )
                    raise e

            except Exception as e:
                log.error(
                    "Could not update the zendesk profile for the user",
                    exception=e,
                    user_id=user.id,
                )
                return None


def merge_zendesk_profiles(
    user_id: str, source_zendesk_user: ZDUser, destination_zendesk_user: ZDUser
) -> ZDUser:
    """
    Call Zendesk Client's `merge_zendesk_profiles` to trigger the merge and log the output
    :param user_id:
    :param source_zendesk_user:
    :param destination_zendesk_user:
    :return:
    """
    try:
        merged_profile = zenpy_client.merge_zendesk_profiles(
            user_id=user_id,
            source_zendesk_user=source_zendesk_user,
            destination_zendesk_user=destination_zendesk_user,
        )

        # delay the update to ensure we don't run into any conflicts after merging the duplicate profiles
        # TODO: will followup with a better solution to avoid brute force
        time.sleep(1)

        log.info(
            "The source zendesk user profile has been merged into the destination zendesk profile",
            source_zendesk_user_id=source_zendesk_user.id,
            destination_zendesk_user_id=destination_zendesk_user.id,
            merged_profile_id=merged_profile.id,
        )

        return merged_profile
    except Exception as e:
        log.info(
            "Could not merge Zendesk profiles for user", user_id=user_id, exception=e
        )


def get_zenpy_user(user, called_by="Not Set"):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """Attempts to retrieve a zendesk user, but does not create one if missing."""
    try:
        if user.zendesk_user_id:
            log.debug(
                "Using stored Zendesk user id for Maven user.",
                zendesk_id=user.zendesk_user_id,
                user=user,
            )
            return ZDUser(id=user.zendesk_user_id)
        search_results = zenpy_client.search(
            "user",
            f'"{user.email.lower()}"',
            user.id,
            called_by=called_by,
        )
        zd_user = next(
            result for result in search_results if result.email == user.email.lower()
        )
        if zd_user:
            return zd_user
        else:
            log.info("Failed to retrieve Zendesk user for Maven user", user_id=user.id)
    except Exception as e:
        log.error("Could not establish Zendesk user.", exception=e, user_id=user.id)
        raise


def tag_zendesk_user(zendesk_user, tags: list, called_by="Not set") -> list:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    try:
        return zenpy_client.tag_zendesk_user(zendesk_user, tags, called_by=called_by)
    except ZendeskAPIException as e:
        stats.increment(
            metric_name="api.zendesk.error",
            pod_name=stats.PodNames.MPRACTICE_CORE,
            tags=[
                "domain:zendesk",
                "error:true",
            ],
        )
        log.error(
            "Failed to tag Zendesk user",
            exception=e,
            zendesk_user=zendesk_user,
            tags=tags,
        )
        raise


def permanently_delete_user(user, called_by="Not set"):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.debug(f"Permanently deleting ZenDesk data for user ({user.id})")

    try:
        uu = list(
            zenpy_client.search(
                "user",
                f'"{user.email.lower()}"',
                user.id,
                called_by=called_by,
            ),
        )
    except Exception as e:
        log.exception(e)
        return

    if not uu:
        log.debug(f"No ZenDesk user found for user ({user.id})")
        return

    if len(uu) > 1:
        raise DeleteUserActionableError(
            "ZenDesk requires manual cleanup. Multiple ZenDesk users matched email.",
        )

    zd_user = uu[0]
    for zd_ticket in list(
        zenpy_client.retrieve_tickets_by_user(zd_user, user.id, called_by=called_by),
    ):
        if zd_ticket.status != "closed":
            zd_ticket.status = "closed"
            zenpy_client.update_ticket(zd_ticket, user.id, called_by=called_by)
        zenpy_client.delete_ticket(zd_ticket, user.id, zd_user.id, called_by=called_by)
    zenpy_client.delete_user(zd_user, user.id, called_by=called_by)
    zenpy_client.permanently_delete_user(zd_user, user.id, called_by=called_by)

    log.debug(f"Permanently deleted ZenDesk data for user ({user.id})")


def send_general_ticket_to_zendesk(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    user: User,
    ticket_subject: str,
    content: str,
    called_by="Not set",
    tags: list[str] | None = None,
    status: str = "open",
    via_followup_source_id=None,
    user_need_when_solving_ticket: str = "",
):
    """
    Sends an abstract ticket to zendesk. Must be followed by a commit to persist
    user's zendesk id.
    """
    if tags is None:
        tags = []
    try:
        # Side effect here
        requester_id = get_or_create_zenpy_user(user, called_by=called_by).id

        new_ticket = Ticket(
            requester_id=requester_id,
            status=status,
            subject=namespace_subject(ticket_subject),
            comment=Comment(body=content, author_id=requester_id, public=False),
            tags=tags,
        )
        if (
            status == "solved"
            and user_need_when_solving_ticket
            and enable_set_user_need_if_solving_ticket(new_ticket)
        ):
            new_ticket.custom_fields = [
                {
                    "id": get_user_need_custom_field_id(),
                    "value": user_need_when_solving_ticket,
                }
            ]

        if via_followup_source_id:
            new_ticket.via_followup_source_id = via_followup_source_id

        ticket_audit = zenpy_client.create_ticket(
            new_ticket,
            user.id,
            requester_id,
            called_by=called_by,
        )
        log.debug(
            f"All set adding ticket for {user} to ZenDesk ({ticket_audit.ticket})",
        )
        if (ticket_audit.ticket and ticket_audit.ticket.id) is None:
            log.error(
                "Failed to create a Zendesk ticket for a user",
                user_id=str(user.id),
                ticket_subject=ticket_subject,
            )
        return ticket_audit.ticket and ticket_audit.ticket.id
    except Exception as e:
        log.info(
            "Cannot add Zendesk ticket.",
            user_id=str(user.id),
            ticket_subject=ticket_subject,
        )
        log.exception(e)


def get_cx_tags(
    member: User | None,
    channel: Channel | None,
    message: Message | None,
    existing_tags: list | None = None,
) -> list:
    """
    Generates applicable tags that are used within Zendesk.
    """
    if member is None or channel is None or message is None:
        raise AttributeError("member, channel, and message are required to get_cx_tags")

    tags = set(existing_tags) if existing_tags else set()

    tags.update(
        [
            SynchronizedZendeskTicket.CX_MESSAGING,
            _generate_cx_channel_id_tag(channel.id),
        ]
    )

    if wallet_exists_for_channel(channel.id):
        tags.add(SynchronizedZendeskTicket.MAVEN_WALLET)

    if message.is_automated_message:
        tags.add(SynchronizedZendeskTicket.NEW_AUTOMATED_MESSAGE)
    else:
        tags.discard(SynchronizedZendeskTicket.NEW_AUTOMATED_MESSAGE)

    if channel.has_automated_ca_message:
        tags.add(SynchronizedZendeskTicket.AUTOMATED_MESSAGE_IN_THREAD)

    if member.is_enterprise:
        if not member.organization_v2:
            raise AttributeError(
                "member.organization is required to get organization.name for tags",
            )

        tags.add(SynchronizedZendeskTicket.ENTERPRISE)
        tags.add(_generate_org_name_tag(member.organization_v2.name))

    return list(tags)


def _generate_org_name_tag(org_name: str) -> str:
    if not org_name:
        return ""
    return org_name.lower().replace("-", "_").replace(" ", "_")


def _generate_cx_channel_id_tag(channel_id: int) -> str:
    if not channel_id:
        return ""
    return f"cx_channel_id_{channel_id}"


def _generate_tags_for_update_zendesk_count_metric(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    is_internal_channel: bool,
    is_wallet_channel: bool,
    source: str,
    exception_type: str,
    failure_reason: UpdateZendeskFailureReason,
):
    return [
        f"is_internal_channel:{is_internal_channel}",
        f"is_wallet_channel:{is_wallet_channel}",
        f"source:{source}",
        f"exception_type:{exception_type}",
        f"failure_reason:{failure_reason.name}",
    ]


def _increment_update_zendesk_count_metric(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    is_internal_channel: bool,
    is_wallet_channel: bool,
    source: str,
    failure_reason: UpdateZendeskFailureReason = UpdateZendeskFailureReason.NONE,
    exception_type: str = "N/A",
    pod_name: stats.PodNames = stats.PodNames.VIRTUAL_CARE,
):
    stats.increment(
        metric_name=ZENDESK_UPDATE_COUNT_METRIC,
        pod_name=pod_name,
        tags=_generate_tags_for_update_zendesk_count_metric(
            is_internal_channel,
            is_wallet_channel,
            source,
            exception_type,
            failure_reason,
        ),
    )


def find_zendesk_comment_that_matches_message(
    zendesk_comments_list: list[Comment],
    message: Message,
) -> Comment | None:
    """
    Find best string match between zendesk comments' body and a mono message's body
    """
    if not message or not message.body:
        log.info(
            "Cant find match for None message or message with no body",
            message_id=message.id if message else None,
        )
        return None

    best_comment_match = None
    lowest_comment_distance = MAX_STRING_MATCH_DISTANCE
    for zendesk_comment in zendesk_comments_list:
        if not zendesk_comment.body:
            log.info("No body in zendesk comment", zd_comment_id=zendesk_comment.id)
            continue
        comment_distance = hamming_distance(
            str1=zendesk_comment.body, str2=message.body
        )
        if comment_distance < lowest_comment_distance:
            lowest_comment_distance = comment_distance
            best_comment_match = zendesk_comment

    return best_comment_match


class RequiredParameterException(Exception):
    """
    Raised when we require a parameter that was not provided
    """

    pass


@contextlib.contextmanager
def reconcile_zendesk_comment_id_job_locks(
    ticket_id: int,
    message_id: int,
    lock_timeout_sec: int = 5,
) -> Generator[None, None, None]:
    """
    We will grab two locks, one for ticket_id and one for message_id
    """
    if ticket_id is None or message_id is None:
        raise RequiredParameterException

    ticket_cache_key = f"reconcile_zendesk_comment:ticket_id:lock:{ticket_id}"
    message_cache_key = f"reconcile_zendesk_comment:message_id:lock:{message_id}"
    try:
        with RedisLock(ticket_cache_key, timeout=lock_timeout_sec), RedisLock(
            message_cache_key, timeout=lock_timeout_sec
        ):
            yield
    except LockTimeout as e:
        log.info(
            "Missed comment processing lock due to timeout",
            ticket_id=ticket_id,
            message_id=message_id,
            error=e,
        )
        raise e


@retryable_job("default", retry_limit=3)
def reconcile_zendesk_comment_id(
    ticket_id: int,
    message_id: int,
) -> None:
    """
    The goal of this function is to learn and record the zendesk_comment_id for a message that did make it to zendesk
    but for which we were unable to collect the zendesk id when the message was sent.
    To do so, we grab all zendesk comments for the given ticket, check the comments ids, identify which one is not
    present in our db, and check if that comment's body matches with the message with no zendesk_comment_id.
    """

    # Avoiding circular dependency
    from tasks.zendesk_v2 import (
        has_zendesk_comment_id_been_processed,
        public_comments_for_ticket_id,
        zendesk_comment_processing_job_lock,
    )

    # ensure we hold locks before evaluating to prevent race conditions
    # in particular, we don't want two processes reconciling the same message_id
    # and we don't want two processes using the same ticket id
    # (if not more than one can use the ticket's comments for reconciliation)
    with reconcile_zendesk_comment_id_job_locks(ticket_id, message_id):
        log.info(
            "Starting to reconcile zendesk_comment_id",
            ticket_id=ticket_id,
            message_id=message_id,
        )

        message = MessageRepository().get(id=message_id)
        if not message:
            log.info(
                "Could not find message, aborting zendesk_comment_id reconciliation",
                message_id=message_id,
                ticket_id=ticket_id,
            )
            return

        # Sanity check, check that message indeed has no zendesk_comment_id
        if message.zendesk_comment_id:
            # This should never happen, because we only call reconcile_zendesk_comment_id when the id is missing
            log.info(
                "Message already has a zendesk_comment_id, no need to reconcile it",
                message_id=message_id,
            )
            return

        zd_comment_list = public_comments_for_ticket_id(ticket_id=ticket_id)
        zd_comments_with_id_not_found_in_mono_db = []
        for zd_comment in zd_comment_list:
            # ensure we hold a lock by zd_comment.id
            # in particular we need to protect against race conditions with process_zendesk_inbound_message_worker,
            # so we will use the same lock
            with zendesk_comment_processing_job_lock(zd_comment.id):
                already_processed = has_zendesk_comment_id_been_processed(
                    comment_id=zd_comment.id
                )
                if not already_processed:
                    zd_comments_with_id_not_found_in_mono_db.append(zd_comment)

        if not zd_comments_with_id_not_found_in_mono_db:
            log.info(
                "ZD Ticket has no comments with ids not found in mono db. It seems like the message did not make it to ZD.",
                ticket_id=ticket_id,
                message_id=message_id,
                zd_comments_ids=[c.id for c in zd_comment_list],
            )
            return

        zd_comment_that_matched = find_zendesk_comment_that_matches_message(
            zendesk_comments_list=zd_comments_with_id_not_found_in_mono_db,
            message=message,
        )
        if not zd_comment_that_matched:
            log.info(
                "Could not find a zd comment that matches the mono message",
                ticket_id=ticket_id,
                message_id=message_id,
                zd_comments_ids=[
                    c.id for c in zd_comments_with_id_not_found_in_mono_db
                ],
            )
            return None
        # Else, at this point we have found a zendesk comment that
        # a) its id is not present in mono db as the zendesk_comment_id of any Message, and
        # b) its body matches the body of our message that has no zendesk_comment_id
        # hence, we are in a good place to reconcile the zendesk_comment_id on this message
        message.zendesk_comment_id = zd_comment_that_matched.id
        db.session.add(message)
        db.session.commit()
        log.info(
            "zendesk_comment_id reconciled for message",
            zendesk_comment_id=zd_comment_that_matched.id,
            message_id=message_id,
            ticket_id=ticket_id,
        )
        return None


@job(team_ns="virtual_care")
def update_zendesk_org(
    org_id: int,
    org_name: str,
    tracks: list[ZendeskClientTrack],
    offshore_restriction: bool,
    track_name: str = "",
) -> None:
    if should_update_zendesk_org():
        if track_name:
            log.info(
                "Updating zendesk organization for track change",
                org_id=org_id,
                track_name=track_name,
            )
        else:
            log.info(
                "Updating zendesk organization",
                org_id=org_id,
            )
        filtered_tracks = filter_client_tracks(tracks)
        zenpy_client.create_or_update_organization(
            org_id, org_name, filtered_tracks, offshore_restriction
        )


def filter_client_tracks(tracks: list[ZendeskClientTrack]) -> str:
    # we don't include these tracks in ZD orgs because
    # they're not user facing tracks
    filtered_tracks = [
        track
        for track in tracks
        if track.active is True
        and track.name
        not in (
            ZendeskTrackName.GENERIC,
            ZendeskTrackName.SPONSORED,
            ZendeskTrackName.PREGNANCY_OPTIONS,
        )
    ]
    if filtered_tracks and "_" in filtered_tracks[0].display_name:
        return "\n".join(str(lazy_gettext(t.display_name)) for t in filtered_tracks)
    return "\n".join(str(t.display_name) for t in filtered_tracks)


class SynchronizedZendeskTicket(ABC):
    member: User | None
    NEW_AUTOMATED_MESSAGE = "ca_automated_message_new"
    AUTOMATED_MESSAGE_IN_THREAD = "ca_automated_message_in_thread"
    CX_MESSAGING = "cx_messaging"
    MAVEN_WALLET = "maven_wallet"
    ENTERPRISE = "enterprise"

    def __init__(self) -> None:
        self.previous_tags = None

    @property
    @abstractmethod
    def recorded_ticket_id(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        pass

    @recorded_ticket_id.setter
    @abstractmethod
    def recorded_ticket_id(self, ticket_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        pass

    @abstractmethod
    def record_comment_id(self, comment_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        pass

    @property
    @abstractmethod
    def desired_ticket_requester(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        pass

    @property
    @abstractmethod
    def desired_ticket_status(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        pass

    @property
    @abstractmethod
    def desired_ticket_subject(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        pass

    @property
    @abstractmethod
    def desired_ticket_tags(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        pass

    @property
    @abstractmethod
    def comment_public(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        pass

    @property
    @abstractmethod
    def comment_author(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        pass

    @property
    @abstractmethod
    def comment_body(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        pass

    @property
    @abstractmethod
    def is_internal(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        pass

    @property
    @abstractmethod
    def is_wallet(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        pass

    @property
    @abstractmethod
    def user_id(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        pass

    @property
    @abstractmethod
    def user_need_when_solving_ticket(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        pass

    def update_zendesk(self, message_id: str = ""):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        log.info("Updating Zendesk with message.", message_id=message_id)
        redis_cli = redis_client()

        # Pushing message_id to reconciliation_list if message_id exists
        # This list is used to retry messages that fail to get sent to Zendesk
        # Retries happen in maven_to_zendesk_message_reconciliation job.
        if message_id:
            redis_cli.sadd(MAVEN_TO_ZENDESK_RECONCILIATION_LIST_KEY, message_id)
            log.info(
                f"Added message to {MAVEN_TO_ZENDESK_RECONCILIATION_LIST_KEY} redis list",
                message_id=message_id,
            )

        try:
            ticket = self._get_existing_ticket(message_id)
            if ticket and ticket.status != "closed":
                log.info(
                    "Found unclosed ticket for message",
                    message_id=message_id,
                    ticket_id=ticket.id,
                    ticket_status=ticket.status,
                )
                self.previous_tags = ticket.tags
                ticket_audit = self._comment_on_existing_ticket(ticket, message_id)
            else:
                log.info(
                    "Message ticket is closed or does not exist. Will create new one",
                    message_id=message_id,
                    ticket_id=ticket.id if ticket else None,
                )
                ticket_audit = self._create_new_ticket(ticket, message_id)
        except ZendeskInvalidRecordException as e:
            # we did not successfully deliver the message and retrying wont help
            # we must address the data validation errors and retry
            generate_user_trace_log(
                log,
                LogLevel.ERROR,
                self.user_id,
                "Unable to deliver message to Zendesk due to data validation error",
                message_id=message_id,
                exception=str(e),
            )
            _increment_update_zendesk_count_metric(
                self.is_internal,
                self.is_wallet,
                self.__class__.__name__,
                UpdateZendeskFailureReason.ERROR_IN_DATA_VALIDATING_IN_ZENDESK,
                e.__class__.__name__,
            )
            if message_id:
                # Remove message_id from maven_to_zendesk_reconciliation_list, because retry won't do it
                redis_cli.srem(MAVEN_TO_ZENDESK_RECONCILIATION_LIST_KEY, message_id)
                log.info(
                    f"Removed message from {MAVEN_TO_ZENDESK_RECONCILIATION_LIST_KEY} redis list",
                    message_id=message_id,
                )
            raise

        try:
            ticket_id = ticket_audit.ticket.id
            self.recorded_ticket_id = ticket_id
            comment_id = self._parse_comment_id(ticket_audit, self.user_id)
            # If we successfully parse comment_id from ZD response, save zendesk_comment_id in the message
            if comment_id:
                self.record_comment_id(comment_id)
                if message_id:
                    # Remove message_id from maven_to_zendesk_reconciliation_list
                    # now that we know message was correctly sent to Zendek
                    redis_cli.srem(MAVEN_TO_ZENDESK_RECONCILIATION_LIST_KEY, message_id)
                    log.info(
                        f"Removed message from {MAVEN_TO_ZENDESK_RECONCILIATION_LIST_KEY} redis list",
                        message_id=message_id,
                    )
            elif message_id:
                # If we fail to parse comment_id from ZD response, in particular for the case of sending a message,
                # we know that in most cases the message did make it to ZD, its only that the response doesn't come with
                # zendesk_comment_id. In this case, we want to try to reconcile the zendesk_comment_id for the message
                # because if a message doesn't have a zendesk_comment_id, our system will think that the message did
                # not make it to zendesk and we might re-try sending it.
                log.info(
                    "Could not get zendesk_comment_id. Will try to reconcile it",
                    ticket_id=ticket_id,
                    user_id=self.user_id,
                    message_id=message_id,
                )
                reconcile_zendesk_comment_id.delay(
                    ticket_id=ticket_id,
                    message_id=message_id,
                    team_ns="virtual_care",
                )
                # Even though we have a mechanism in place to reconcile this message, we might fail to do so,
                # so we will keep the message in the reconciliation list just in case.
            # If we fail to parse comment_id from ZD response, in particular for the case when we are NOT sending a
            # message (this is the case when we do ticket creation), we want to log. It is unclear if the operation
            # could have succeeded or not, it could be the case that we just failed to parse, but in any case,
            # logging can help for further debugging.
            else:
                log.info(
                    "Failed to parse zendesk_comment_id during ticket creation",
                    ticket_id=ticket_id,
                    user_id=self.user_id,
                )

        except SQLAlchemyError as e:
            _increment_update_zendesk_count_metric(
                self.is_internal,
                self.is_wallet,
                self.__class__.__name__,
                UpdateZendeskFailureReason.ERROR_IN_UPDATING_DATA_FROM_ZENDESK,
                e.__class__.__name__,
            )
            generate_user_trace_log(
                log,
                LogLevel.ERROR,
                self.user_id,
                "Error updating maven's data from Zendesk",
                exception_type=e.__class__.__name__,
                excetpion_message=str(e),
                zendesk_ticket_id=ticket_audit.ticket.id,
            )
            raise

    def _get_or_create_zenpy_user(self, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            return get_or_create_zenpy_user(user, called_by=self.__class__.__name__)
        except SQLAlchemyError as e:
            generate_user_trace_log(
                log,
                LogLevel.ERROR,
                user.id,
                "DB operation error at get_or_create_zenpy_user",
                exception_type=e.__class__.__name__,
                exception_message=str(e),
            )
            _increment_update_zendesk_count_metric(
                self.is_internal,
                self.is_wallet,
                self.__class__.__name__,
                UpdateZendeskFailureReason.ERROR_IN_UPDATING_DATA_FROM_ZENDESK,
                e.__class__.__name__,
            )
            raise
        except Exception as e:
            generate_user_trace_log(
                log,
                LogLevel.ERROR,
                user.id,
                "Could not establish Zendesk user",
                exception_type=e.__class__.__name__,
                exception_message=str(e),
            )
            _increment_update_zendesk_count_metric(
                self.is_internal,
                self.is_wallet,
                self.__class__.__name__,
                UpdateZendeskFailureReason.ERROR_IN_UPDATE_OR_CREATE_USER_IN_ZENDESK,
                e.__class__.__name__,
            )
            raise

    def _get_existing_ticket(self, message_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        ticket_id = self.recorded_ticket_id
        log.info(
            "Searching for ticket based on recorded_ticket_id",
            message_id=message_id,
            ticket_id=ticket_id,
        )
        if ticket_id is not None:
            try:
                ticket = zenpy_client.get_ticket(
                    ticket_id,
                    self.user_id,
                    called_by=self.__class__.__name__,
                    message_id=message_id,
                )

                log_message = (
                    "Successfully get the ticket"
                    if ticket is not None
                    else "Error trying to find an "
                    "existing zendesk ticket, "
                    "will create new ticket "
                )
                generate_user_trace_log(
                    log,
                    LogLevel.INFO,
                    self.user_id,
                    log_message,
                    zendesk_ticket_id=ticket_id,
                    message_id=message_id,
                )

                return ticket
            except Exception as e:
                generate_user_trace_log(
                    log,
                    LogLevel.ERROR,
                    self.user_id,
                    "Error in getting the existing ticket",
                    exception_type=e.__class__.__name__,
                    exception_message=str(e),
                    zendesk_ticket_id=ticket_id,
                    message_id=message_id,
                )

                _increment_update_zendesk_count_metric(
                    self.is_internal,
                    self.is_wallet,
                    self.__class__.__name__,
                    UpdateZendeskFailureReason.ERROR_IN_GETTING_TICKET_IN_ZENDESK,
                    e.__class__.__name__,
                )
                raise

    def _set_user_need_if_solving_ticket(self, ticket: Ticket) -> None:
        if not enable_set_user_need_if_solving_ticket(ticket):
            return

        if ticket.status != "solved":
            return

        user_need = self.user_need_when_solving_ticket
        if not user_need:
            log.warning(
                "Unknown user_need when solving ticket, will use a default user_need",
                ticket_id=ticket.id,
            )
            user_need = "customer-need-member-proactive-outreach-other"

        # The custom_fields attribute on a Ticket corresponds to list of dictionaries, where each
        # dictionary has keys 'id' and 'value', 'id' to identify each custom_field, 'value' to indicate the value
        # present in that custom field.

        # For new tickets, the custom_field attribute will be empty
        # For existing tickets, the custom_field attribute is already formed, with all the existing custom_fields
        # already populated in the attribute, with a value of None for custom fields that are empty.
        # So, we need to identify if the custom_field is already present or not, to properly populate the
        # user_need custom field
        user_need_custom_field_id = get_user_need_custom_field_id()
        if not ticket.custom_fields:
            ticket.custom_fields = [
                {
                    "id": user_need_custom_field_id,
                    "value": user_need,
                }
            ]
            return

        # Else, ticket.custom_fields already exists.
        # We need to loop over list of custom_fields to find the user_need one
        for custom_field_dict in ticket.custom_fields:
            if custom_field_dict["id"] == user_need_custom_field_id:
                custom_field_dict["value"] = user_need
                return

        # If we are still here, ticket.custom_fields existed, but it did not have user_need_custom_field_id, which is unexpected
        # But in any case, we will manually add it
        ticket.custom_fields.append(
            {
                "id": user_need_custom_field_id,
                "value": user_need,
            }
        )
        log.warning(
            "user_need_custom_field_id not found in ticket.custom_fields. added, but unclear if it will persist",
            ticket_id=ticket.id,
            user_need_custom_field_id=user_need_custom_field_id,
        )

    def _comment_on_existing_ticket(self, ticket: Ticket, message_id: str):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        new_status = self.desired_ticket_status
        log.info(
            "Adding comment to ticket that has not been closed.",
            ticket_id=ticket.id,
            ticket_status=ticket.status,
            new_ticket_status=new_status,
        )
        ticket.status = new_status
        ticket.comment = self._compose_comment()
        ticket.tags = self.desired_ticket_tags

        self._set_user_need_if_solving_ticket(ticket)

        try:
            updated_ticket = zenpy_client.update_ticket(
                ticket,
                self.user_id,
                called_by=self.__class__.__name__,
                message_id=message_id,
            )
            generate_user_trace_log(
                log,
                LogLevel.INFO,
                self.user_id,
                "Successfully comment on an existing ticket",
                zendesk_ticket_id=ticket.id,
                zendesk_user_id=ticket.comment.author_id,
                message_id=message_id,
            )
            return updated_ticket
        except Exception as e:
            generate_user_trace_log(
                log,
                LogLevel.ERROR,
                self.user_id,
                "Error in adding a comment in an existing ticket",
                exception_type=e.__class__.__name__,
                exception_message=str(e),
                zendesk_ticket_id=ticket.id,
                zendesk_user_id=ticket.comment.author_id,
                message_id=message_id,
            )

            _increment_update_zendesk_count_metric(
                self.is_internal,
                self.is_wallet,
                self.__class__.__name__,
                UpdateZendeskFailureReason.ERROR_IN_UPDATING_TICKET_COMMENT_IN_ZENDESK,
                e.__class__.__name__,
            )
            raise

    def _create_new_ticket(self, existing_ticket, message_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        requester = self.desired_ticket_requester
        zd_requester = self._get_or_create_zenpy_user(requester)

        new_ticket = Ticket(
            requester_id=zd_requester.id,
            status=self.desired_ticket_status,
            subject=namespace_subject(self.desired_ticket_subject),
            comment=self._compose_comment(),
            tags=self.desired_ticket_tags,
        )

        self._set_user_need_if_solving_ticket(new_ticket)

        if existing_ticket:
            log.info(
                "Opening follow up ticket to closed ticket.",
                existing_ticket_id=existing_ticket.id,
            )
            new_ticket.via_followup_source_id = existing_ticket.id
        else:
            log.info("Opening new ticket.")

        try:
            ticket_audit = zenpy_client.create_ticket(
                new_ticket,
                self.user_id,
                zd_requester.id,
                called_by=self.__class__.__name__,
                message_id=message_id,
            )

            generate_user_trace_log(
                log,
                LogLevel.INFO,
                self.user_id,
                "Successfully creating a new ticket",
                zendesk_ticket_id=ticket_audit.ticket.id,
                zendesk_user_id=zd_requester.id,
                message_id=message_id,
            )
            return ticket_audit
        except ZendeskAPIException as e:
            if e.response.json().get("error") == "RecordInvalid":
                # the data passed to Zendesk was invalid. retries will not resolve this.
                # emit a failure metric and
                raise ZendeskInvalidRecordException(e)
            raise
        except Exception as e:
            generate_user_trace_log(
                log,
                LogLevel.ERROR,
                self.user_id,
                "Error in creating a new ticket",
                zendesk_ticket_id=new_ticket.id,
                zendesk_user_id=zd_requester.id,
                message_id=message_id,
            )

            _increment_update_zendesk_count_metric(
                self.is_internal,
                self.is_wallet,
                self.__class__.__name__,
                UpdateZendeskFailureReason.ERROR_IN_CREATING_TICKET_IN_ZENDESK,
                e.__class__.__name__,
            )
            raise

    def _compose_comment(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        public = self.comment_public
        body = self.comment_body
        author = self.comment_author
        zd_author = self._get_or_create_zenpy_user(author)
        return Comment(body=body, author_id=zd_author.id, public=public)

    @staticmethod
    def _parse_comment_id(ticket_audit, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        comment_ids = [
            e["id"] for e in ticket_audit.audit.events if e.get("type") == "Comment"
        ]
        if len(comment_ids) == 1:
            return comment_ids[0]
        elif len(comment_ids) > 1:
            generate_user_trace_log(
                log,
                LogLevel.ERROR,
                user_id,
                "Cannot determine Zendesk comment ID from audit",
                comment_ids=comment_ids,
                zendesk_ticket_id=ticket_audit.ticket.id,
            )
        else:
            generate_user_trace_log(
                log,
                LogLevel.ERROR,
                user_id,
                "Cannot get Zendesk comment ID from audit",
                zendesk_ticket_id=ticket_audit.ticket.id,
            )


class MessagingZendeskTicket(SynchronizedZendeskTicket):
    """MessagingZendeskTicket maintains a ticket for receiving and sending Maven messages on Zendesk."""

    def __init__(
        self,
        message: Message,
        initial_cx_message: bool,
        user_need_when_solving_ticket: str = "",
    ):
        super().__init__()
        self.message = message
        self.initial_cx_message = initial_cx_message
        self._user_need_when_solving_ticket = user_need_when_solving_ticket

    @property
    def recorded_ticket_id(self) -> int | None:
        user_id = self.message.user_id
        zendesk_ticket_id_row = (
            db.session.query(ReimbursementWalletUsers.zendesk_ticket_id)
            .filter(
                ReimbursementWalletUsers.user_id == user_id,
                ReimbursementWalletUsers.channel_id == self.channel.id,
            )
            .one_or_none()
        )
        if zendesk_ticket_id_row is None:
            # If you cannot find a zendesk_ticket_id attached to
            # the reimbursement_wallet_user, then default to the
            # zendesk_ticket_id for the member's profile
            if self.member is None or self.member.member_profile is None:
                raise AttributeError(
                    f"member or member_profile not found when retrieving zendesk_ticket_id for channel {self.channel.id} and user {user_id}",
                )
            zendesk_ticket_id = self.member.member_profile.zendesk_ticket_id
            log.info(
                "Retrieved ticket id from member profile",
                zendesk_ticket_id=zendesk_ticket_id,
            )
            return zendesk_ticket_id

        zendesk_ticket_id = zendesk_ticket_id_row[0]
        log.info(
            "Retrieving ticket id from reimbursement_wallet_user",
            zendesk_ticket_id=zendesk_ticket_id,
        )
        return zendesk_ticket_id

    @recorded_ticket_id.setter
    def recorded_ticket_id(self, ticket_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        This method sets a user's zendesk_ticket_id to ticket_id.
        It updates the user's MemberProfile.zendesk_ticket_id if there is
        no reimbursement_wallet_users entry for the user. Otherwise, it updates
        the reimbursement_wallet_users entry.
        """
        user_id = self.message.user_id
        reimbursement_wallet_user = (
            db.session.query(ReimbursementWalletUsers)
            .filter(
                ReimbursementWalletUsers.user_id == user_id,
                ReimbursementWalletUsers.channel_id == self.channel.id,
            )
            .one_or_none()
        )
        if reimbursement_wallet_user is None:
            if self.member is None or self.member.member_profile is None:
                raise AttributeError(
                    "member or member_profile not found when retrieving zendesk_ticket_id",
                )
            self.member.member_profile.zendesk_ticket_id = ticket_id
        else:
            log.info(
                "updating reimbursement wallet user's zendesk ticket",
                prev_zendesk_ticket_id=reimbursement_wallet_user.zendesk_ticket_id,
                new_zendesk_ticket_id=ticket_id,
                user_id=user_id,
            )
            reimbursement_wallet_user.zendesk_ticket_id = ticket_id
        db.session.commit()

    def record_comment_id(self, comment_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.message.zendesk_comment_id = comment_id

    @property
    def desired_ticket_requester(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.initial_cx_message and self.comment_author != self.member:
            return self.member
        return self.comment_author

    @property
    def desired_ticket_status(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.initial_cx_message:
            return "solved"
        return "open"

    @property
    def desired_ticket_subject(self) -> str:
        if not wallet_exists_for_channel(self.channel.id):
            return f"CX Message with {self.desired_ticket_requester.full_name}"
        else:
            return (
                f"Maven Wallet message with {self.desired_ticket_requester.full_name}"
            )

    @property
    def desired_ticket_tags(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return get_cx_tags(
            self.member,
            self.channel,
            self.message,
            self.previous_tags,
        )

    @property
    def comment_public(self) -> bool:
        return True

    @property
    def comment_author(self) -> User:
        return self.message.user

    @property
    def user_id(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (
            str(self.message.user_id)
            if self.message is not None and self.message.user_id is not None
            else ""
        )

    @property
    def comment_body(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        config = configuration.get_api_config()
        lines = []
        wallet = get_wallet_by_channel_id(self.channel.id)
        if self.message.body:
            lines.append(self.message.body)
        else:
            lines.append("(no message)")
        if self.message.attachments:
            lines.append("")
            lines.append("Attachments:")
        for n, a in enumerate(self.message.attachments, start=1):
            lines.append(
                f"{n}. {config.common.base_url}/ajax/api/v1/assets/{a.id}/download?disposition=inline",
            )
            if wallet is not None:
                # TODO: improve url detection for admin urls separate from main site urls
                lines.append(
                    f"  - Create Reimbursement Request from Attachment {n}: "
                    f"https://admin.mvnapp.net/admin/reimbursementrequestsource/?flt1_wallet_reimbursement_wallet_id_equals={wallet.id}",
                )

        return "\n".join(lines)

    @property
    def channel(self) -> Channel:
        return self.message.channel

    @property
    def member(self) -> User | None:
        return self.channel.member

    # To address the following analysis error caused by overriding the base
    # classes r/w member property with a ro version, but maintain the prior
    # behavior of raising `AttributeError: can't set attribute` when attempting
    # to set a value for member, we will explicitly raise with a more
    # descriptive error.
    #
    # error: Cannot override writeable attribute with read-only property [override]
    #
    @member.setter
    def member(self, member: User) -> None:
        raise AttributeError("member is read only")

    @property
    def is_internal(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.channel.internal

    @property
    def is_wallet(self) -> bool:
        return self.channel.is_wallet

    @property
    def user_need_when_solving_ticket(self) -> str:
        return self._user_need_when_solving_ticket

    def update_zendesk(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.comment_author.is_care_coordinator and not self.initial_cx_message:
            generate_user_trace_log(
                log,
                LogLevel.INFO,
                self.user_id,
                "Not updating Zendesk with message from Care Advocate",
                message_id=self.message.id,
            )
            return

        if not self.member:
            raise AttributeError("member not found on MessagingZendeskTicket")
        if not self.member.is_member:
            generate_user_trace_log(
                log,
                LogLevel.INFO,
                self.user_id,
                "Not updating Zendesk with message from practitioner-only channel",
                message_id=self.message.id,
            )
            return

        super().update_zendesk(str(self.message.id))

        generate_user_trace_log(
            log,
            LogLevel.INFO,
            self.user_id,
            "Updated Zendesk with message",
            message_id=self.message.id,
            ticket_id=self.recorded_ticket_id,
        )
        _increment_update_zendesk_count_metric(
            self.is_internal,
            self.is_wallet,
            self.__class__.__name__,
        )


class ReconciliationZendeskTicket(MessagingZendeskTicket):
    """ReconciliationZendeskTicket maintains a ticket for retrying sending Maven messages on Zendesk."""

    def __init__(self, message: Message):
        super().__init__(message=message, initial_cx_message=False)

    @property
    def user_need_when_solving_ticket(self) -> str:
        return ""

    def update_zendesk(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation

        # Notice that ReconciliationZendeskTicket inherits from MessagingZendeskTicket,
        # which allows us to reuse all its properties
        # Nonetheless, we do not want to reuse its implementation of `update_zendesk`,
        # Instead, we want to use the implementation of the parent class, SynchronizedZendeskTicket,
        # so we invoke it directly
        SynchronizedZendeskTicket.update_zendesk(self, message_id=str(self.message.id))
        generate_user_trace_log(
            log,
            LogLevel.INFO,
            self.user_id,
            "Updated Zendesk with message during reconciliation",
            message_id=self.message.id,
        )
        _increment_update_zendesk_count_metric(
            self.is_internal,
            self.is_wallet,
            self.__class__.__name__,
        )


class EnterpriseValidationZendeskTicket(SynchronizedZendeskTicket):
    """EnterpriseValidationZendeskTicket maintains a ticket tracking the enterprise onboarding status of a user."""

    @classmethod
    def comment(cls, user, comment_body, comment_public: bool = False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        ticket = cls(user, "open", comment_body)
        ticket.comment_public = comment_public
        ticket.update_zendesk()
        return ticket

    @classmethod
    def solve(cls, user, comment_body):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        ticket = cls(
            user,
            "solved",
            comment_body,
            "customer-need-member-enrollments_-renewals_-and-transitions-account-creation-_failed-enterprise-verification_",
        )  # Account creation (failed enterprise verification)
        # Only solve the ticket if this user has had an issue.
        if ticket.recorded_ticket_id:
            ticket.update_zendesk()
        else:
            log.info(
                "User signed up for enterprise without additional help. No need to solve ticket.",
            )

    def __init__(self, user, status, comment, user_need_when_solving_ticket: str = ""):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().__init__()
        self.user = user
        self._comment_public = False
        self._desired_ticket_status = status
        self._comment_body = comment
        self._user_need_when_solving_ticket = user_need_when_solving_ticket

    @property
    def recorded_ticket_id(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.user.member_profile.zendesk_verification_ticket_id

    @recorded_ticket_id.setter
    def recorded_ticket_id(self, ticket_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.user.member_profile.zendesk_verification_ticket_id = ticket_id

    def record_comment_id(self, _comment_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        pass  # Nothing

    @property
    def desired_ticket_requester(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.user

    @property
    def desired_ticket_status(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self._desired_ticket_status

    @property
    def desired_ticket_subject(self) -> str:
        return f"Enterprise Verification for {self.user.full_name}"

    @property
    def desired_ticket_tags(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return ["enterprise_verification_needed", "enterprise"]

    @property
    def comment_public(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self._comment_public

    @comment_public.setter
    def comment_public(self, comm_pub):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._comment_public = comm_pub

    @property
    def comment_author(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.user

    @property
    def user_id(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.user.id if self.user is not None else ""

    @property
    def comment_body(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self._comment_body

    @property
    def is_internal(self) -> bool:
        return False

    @property
    def is_wallet(self) -> bool:
        return False

    @property
    def user_need_when_solving_ticket(self) -> str:
        return self._user_need_when_solving_ticket

    def update_zendesk(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        log.info(
            "Updating Zendesk with EnterpriseValidationZendeskTicket message.",
            user_id=self.user.id,
            recorded_ticket_id=self.recorded_ticket_id,
        )

        super().update_zendesk()

        _increment_update_zendesk_count_metric(
            self.is_internal, self.is_wallet, self.__class__.__name__
        )


class PostSessionZendeskTicket(SynchronizedZendeskTicket):
    @property
    def recorded_ticket_id(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.member.member_profile.zendesk_ticket_id

    @recorded_ticket_id.setter
    def recorded_ticket_id(self, ticket_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.member.member_profile.zendesk_ticket_id = ticket_id
        db.session.commit()

    def record_comment_id(self, comment_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.message.zendesk_comment_id = comment_id
        db.session.commit()

    @property
    def desired_ticket_requester(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.member

    @property
    def desired_ticket_status(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return "solved"

    @property
    def desired_ticket_subject(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return f"CX Message with {self.desired_ticket_requester.full_name}"

    @property
    def desired_ticket_tags(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return get_cx_tags(self.member, self.channel, self.message, self.previous_tags)

    @property
    def comment_public(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return True

    @property
    def comment_author(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.user

    @property
    def user_id(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.user.id if self.user is not None else ""

    @property
    def comment_body(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.message.body

    @property
    def channel(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.message.channel

    @property
    def member(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.channel.member

    @property
    def is_internal(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.channel.internal

    @property
    def is_wallet(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.channel.is_wallet

    @property
    def user_need_when_solving_ticket(self) -> str:
        return self._user_need_when_solving_ticket

    def __init__(self, user, message, user_need_when_solving_ticket: str = ""):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().__init__()
        self.user = user
        self.message = message
        self._user_need_when_solving_ticket = user_need_when_solving_ticket

    def update_zendesk(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not self.user.is_care_coordinator:
            return

        if not self.member.is_member:
            return

        super().update_zendesk(str(self.message.id))

        log.info(
            "Updated Zendesk with Post Session message.",
            message_id=self.message.id,
            ticket_id=self.recorded_ticket_id,
        )

        _increment_update_zendesk_count_metric(
            self.is_internal, self.is_wallet, self.__class__.__name__
        )
