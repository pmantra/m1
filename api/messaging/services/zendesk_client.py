from __future__ import annotations

import contextlib
import re
import time
from datetime import datetime, timedelta
from typing import Any, Generator

import requests
from maven import feature_flags
from redset.locks import LockTimeout
from zenpy import Zenpy
from zenpy.lib.api_objects import Comment as ZDComment
from zenpy.lib.api_objects import Identity as ZDIdentity
from zenpy.lib.api_objects import Organization as ZDOrganization
from zenpy.lib.api_objects import Ticket as ZDTicket
from zenpy.lib.api_objects import User as ZDUser
from zenpy.lib.exception import APIException as ZendeskAPIException

from common import stats
from common.stats import PodNames
from models.failed_external_api_call import Status
from utils.cache import RedisLock
from utils.constants import (
    ZENDESK_API_ERROR_COUNT_METRICS,
    ZENDESK_API_SUCCESS_COUNT_METRICS,
    ZENDESK_MESSAGE_PROCESSING_LOOKBACK_CONFIG,
    ZENDESK_ORG_UPDATE_CREATE_TIMEOUT,
    ZENDESK_TICKET_MISSING_ERROR,
    ZENDESK_USER_UPDATE_CREATE_TIMEOUT,
)
from utils.failed_external_api_call_recorder import FailedVendorAPICallRecorder
from utils.flag_groups import ZENDESK_CLIENT_CONFIGURATION, ZENDESK_V2_RECONCILIATION
from utils.log import LogLevel, generate_user_trace_log, logger

log = logger(__name__)

ZENDESK_VENDOR_NAME: str = "Zendesk"

# The default lookback in seconds for the updated ticket search if no flag value
# is provided.
_FALLBACK_UPDATED_TICKET_SEARCH_LOOKBACK_SECONDS: int = 1 * 60 * 60  # 1 hour
# The number of jobs we spin off (one for each ticket) is increased by making
# the look back window larger. This is a safety net to block an unexpected
# overload of jobs from being created.
_UPDATED_TICKET_LOOKBACK_SECONDS_RUNAWAY_GUARD = 12 * 60 * 60  # 12 hours

# Zendesk has a maximum search result limit of 1000. What that means is that if
# we create a search and their are a total of 2000 results the last 1000 will
# not be reachable even with pagination. to accommodate for this we limit how
# far we page into a search result by MAX_TICKETS_PER_SEARCH_CALL and then walk
# forward given the last ticket we have.
MAX_TICKETS_PER_SEARCH_CALL: int = 1000

# this is used as a safety check to prevent infinite recursion this
# effectively limits us to returning N*MAX_TICKETS_PER_SEARCH_CALL per
# search regardless of the total number of tickets in the search result
# is indicating from Zendesk
TICKET_SEARCH_RECURSION_LIMIT: int = 5

DEFAULT_ZENDESK_RETRY_WAIT_TIME: int = 30
DEFAULT_ZENDESK_RATE_LIMIT_WARNING_THRESHOLD: int = 100
DEFAULT_ZENDESK_API_MAX_RETRY: int = 3
DEFAULT_ZENDESK_PERCENTAGE_THRESHOLD: int = 10

# Ticket class reference
# https://github.com/facetoe/zenpy/blob/78073ff8ebbd66c75c1ddfd73a94d498a06a8fdf/zenpy/lib/api_objects/__init__.py#L3979C9-L3980C21
ZendeskTicketId = int


class IdentityType:
    EMAIL = "email"
    PHONE = "phone_number"
    CARE_ADVOCATE = "care_advocate"
    NAME = "name"
    TRACK = "track"


def get_updated_ticket_search_default_lookback_seconds() -> int:
    """
    Returns the default lookback seconds for the updated ticket search.

    Defines the max age of a ticket update that we will consider when searching
    for recently updated tickets or comments. Making this value higher will
    increase the number of jobs we spin off (one for each tix). There are a high
    number of tickets ~1k updated each day. A look back of 3 days creates ~3k jobs
    per cron period which is too much pressure on the RQ queues and the Zendesk
    API rate limit. Keep this value fairly low and recover any incident caused
    gaps with a 1 off manually triggered backfill job.
    """
    lookback_sec = feature_flags.int_variation(
        ZENDESK_V2_RECONCILIATION.UPDATED_TICKET_SEARCH_LOOKBACK_SECONDS,
        default=_FALLBACK_UPDATED_TICKET_SEARCH_LOOKBACK_SECONDS,
    )
    runaway_guard_sec = feature_flags.int_variation(
        ZENDESK_V2_RECONCILIATION.UPDATED_TICKET_SEARCH_RUNAWAY_GUARD_SECONDS,
        default=_UPDATED_TICKET_LOOKBACK_SECONDS_RUNAWAY_GUARD,
    )
    if lookback_sec > runaway_guard_sec:
        log.warning(
            "The lookback seconds for the updated ticket search is greater than the runaway guard seconds. The runaway guard value will be used.",
            lookback_sec=lookback_sec,
            runaway_guard_sec=runaway_guard_sec,
        )
        stats.increment(
            metric_name=ZENDESK_MESSAGE_PROCESSING_LOOKBACK_CONFIG,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=["error_type:lookback_greater_than_runaway"],
        )

    elif lookback_sec < 0 or runaway_guard_sec < 0:
        log.warning(
            "The lookback or runaway guard seconds value is invalid.",
            lookback_sec=lookback_sec,
            runaway_guard_sec=runaway_guard_sec,
        )
        stats.increment(
            metric_name=ZENDESK_MESSAGE_PROCESSING_LOOKBACK_CONFIG,
            pod_name=stats.PodNames.VIRTUAL_CARE,
            tags=["error_type:invalid_lookback_or_runaway_value"],
        )

    return max(0, min(lookback_sec, runaway_guard_sec))


def exception_related_to_email_already_exists(e: ZendeskAPIException) -> bool:
    """
    Parse the ZendeskAPIException and identify if it is related to a duplicate email error
    :param e:
    :return:
    """
    details = e.response.json().get("details")
    if "email" in details and details["email"][0]["error"] == "DuplicateValue":
        return True
    if (
        "error" in details.get("value", [{}])[0]
        and details["value"][0]["error"] == "DuplicateValue"
    ):
        return True
    return False


class ZendeskAPIEmailAlreadyExistsException(Exception):
    pass


def warn_on_zendesk_rate_limit(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    response,
) -> None:
    """
    Logs warnings when nearing Zendesk's rate limit for both account-wide and endpoint-specific limits.

    :param response:
    :return:
    """

    # https://developer.zendesk.com/documentation/ticketing/using-the-zendesk-api/best-practices-for-avoiding-rate-limiting/#python
    account_limit_remaining = (
        int(response.headers.get("ratelimit-remaining"))
        if response.headers.get("ratelimit-remaining") is not None
        else None
    )

    warning_threshold = feature_flags.int_variation(
        ZENDESK_CLIENT_CONFIGURATION.RATE_LIMIT_WARNING_THRESHOLD,
        default=DEFAULT_ZENDESK_RATE_LIMIT_WARNING_THRESHOLD,
    )

    endpoint_limit_remaining = (
        int(response.headers.get("Zendesk-RateLimit-Endpoint"))
        if response.headers.get("Zendesk-RateLimit-Endpoint") is not None
        else None
    )

    # percentage closeness to threshold
    close_to_threshold_percentage = feature_flags.int_variation(
        ZENDESK_CLIENT_CONFIGURATION.ZENDESK_PERCENTAGE_THRESHOLD,
        default=DEFAULT_ZENDESK_PERCENTAGE_THRESHOLD,
    )

    # calculate percentage thresholds
    warning_threshold_low = warning_threshold
    warning_threshold_high = warning_threshold + (
        warning_threshold * close_to_threshold_percentage / 100
    )

    # check if account limit is close to or below the threshold
    if (
        account_limit_remaining is not None
        and account_limit_remaining <= warning_threshold_high
    ):
        if account_limit_remaining < warning_threshold_low:
            log.warning(
                "Zendesk account rate limit is below the warning threshold!",
                warning_threshold=warning_threshold_low,
            )
        elif account_limit_remaining <= warning_threshold_high:
            log.warning(
                "Approaching Zendesk endpoint rate limit!",
                warning_threshold=warning_threshold_high,
            )

    # check if endpoint limit is close to or below the threshold
    if (
        endpoint_limit_remaining is not None
        and endpoint_limit_remaining <= warning_threshold_high
    ):
        if endpoint_limit_remaining < warning_threshold_low:
            log.warning(
                "Zendesk endpoint rate limit is below the warning threshold!",
                warning_threshold=warning_threshold_low,
            )
        elif endpoint_limit_remaining <= warning_threshold_high:
            log.warning(
                "Approaching Zendesk endpoint rate limit!",
                warning_threshold=warning_threshold_high,
            )

    return None


def handle_zendesk_rate_limit(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    response,
) -> None:

    # The Retry-After header specifies how long after (in seconds) receiving a 429 that you can make another request
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        retry_wait_time = int(retry_after)
    else:
        # Use a default wait time if Retry-After is empty
        retry_wait_time = DEFAULT_ZENDESK_RETRY_WAIT_TIME

    # Edge case - add a 1-second buffer in case we have a non-compliant retry after value
    retry_wait_time = max(retry_wait_time, 1)
    log.info(
        "Zendesk rate limit exceeded. Retrying...", retry_wait_time=retry_wait_time
    )
    time.sleep(retry_wait_time)


class CustomSession(requests.Session):
    """
    Custom session to intercept requests and handle rate limits.
    """

    def __init__(
        self, warning_threshold: int = DEFAULT_ZENDESK_RATE_LIMIT_WARNING_THRESHOLD
    ):
        super().__init__()
        self.warning_threshold = warning_threshold

    def request(self, method, url, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        response = super().request(method, url, *args, **kwargs)

        # Warn about approaching rate limits
        warn_on_zendesk_rate_limit(response=response)

        return response


class ZendeskClient:
    def __init__(self, creds, failed_vendor_api_call_recorder):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        custom_session = CustomSession()
        self.zenpy = Zenpy(**creds, session=custom_session)
        self.zenpy.disable_caching()
        self.failed_vendor_api_call_recorder = failed_vendor_api_call_recorder

    def _record_failed_call(self, user_id, called_by, api_name, payload):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        external_id = FailedVendorAPICallRecorder.generate_external_id(
            user_id,
            called_by,
            ZENDESK_VENDOR_NAME,
            api_name,
        )

        self.failed_vendor_api_call_recorder.create_record(
            external_id=external_id,
            payload=payload,
            called_by=called_by,
            vendor_name=ZENDESK_VENDOR_NAME,
            api_name=api_name,
            status=Status.pending,
        )

    def retrieve_tickets_by_user(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        zd_user,
        user_id,
        called_by="Not set",
        pod_name=stats.PodNames.VIRTUAL_CARE,
    ):
        try:
            response = self.zenpy.users.requested(zd_user)
            stats.increment(
                metric_name=ZENDESK_API_SUCCESS_COUNT_METRICS,
                pod_name=pod_name,
                tags=["api_name:retrieve_tickets_by_user"],
            )
            return response
        except Exception as e:
            exception_type = e.__class__.__name__
            exception_message = str(e)
            generate_user_trace_log(
                log,
                LogLevel.ERROR,
                user_id,
                "Error in retrieving tickets by user",
                exception_type=exception_type,
                exception_message=exception_message,
                zendesk_user_id=zd_user.id,
            )

            stats.increment(
                metric_name=ZENDESK_API_ERROR_COUNT_METRICS,
                pod_name=pod_name,
                tags=[
                    "api_name:retrieve_tickets_by_user",
                    f"exception_type:{exception_type}",
                    # TODO: Add failure_reason
                ],
            )
            self._record_failed_call(
                user_id,
                called_by,
                "zenpy.users.requested",
                {
                    "exception_type": exception_type,
                    "exception_message": exception_message,
                    "zendesk_user_id": zd_user.id,
                    "user_id": user_id,
                },
            )

            raise

    def permanently_delete_user(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        zd_user,
        user_id,
        called_by="Not set",
        pod_name=stats.PodNames.VIRTUAL_CARE,
    ):
        try:
            response = self.zenpy.users.permanently_delete(zd_user)
            stats.increment(
                metric_name=ZENDESK_API_SUCCESS_COUNT_METRICS,
                pod_name=pod_name,
                tags=["api_name:permanently_delete_user"],
            )
            return response
        except Exception as e:
            exception_type = e.__class__.__name__
            exception_message = str(e)
            generate_user_trace_log(
                log,
                LogLevel.ERROR,
                user_id,
                "Error in permanently deleting zendesk user",
                exception_type=exception_type,
                exception_message=exception_message,
                zendesk_user_id=zd_user.id,
            )

            stats.increment(
                metric_name=ZENDESK_API_ERROR_COUNT_METRICS,
                pod_name=pod_name,
                tags=[
                    "api_name:permanently_delete_user",
                    f"exception_type:{exception_type}",
                    # TODO: Add failure_reason
                ],
            )
            self._record_failed_call(
                user_id,
                called_by,
                "zenpy.users.permanently_deleted",
                {
                    "exception_type": exception_type,
                    "exception_message": exception_message,
                    "zendesk_user_id": zd_user.id,
                    "user_id": user_id,
                },
            )

            raise

    def delete_user(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        zd_user,
        user_id,
        called_by="Not set",
        pod_name=stats.PodNames.VIRTUAL_CARE,
    ):
        try:
            response = self.zenpy.users.delete(zd_user)
            stats.increment(
                metric_name=ZENDESK_API_SUCCESS_COUNT_METRICS,
                pod_name=pod_name,
                tags=["api_name:delete_user"],
            )
            return response
        except Exception as e:
            exception_type = e.__class__.__name__
            exception_message = str(e)
            generate_user_trace_log(
                log,
                LogLevel.ERROR,
                user_id,
                "Error in deleting zendesk user",
                exception_type=exception_type,
                exception_message=exception_message,
                zendesk_user_id=zd_user.id,
            )

            stats.increment(
                metric_name=ZENDESK_API_ERROR_COUNT_METRICS,
                pod_name=pod_name,
                tags=[
                    "api_name:delete_user",
                    f"exception_type:{exception_type}",
                ],
            )
            self._record_failed_call(
                user_id,
                called_by,
                "zenpy.users.delete",
                {
                    "exception_type": exception_type,
                    "exception_message": exception_message,
                    "zendesk_user_id": zd_user.id,
                    "user_id": user_id,
                },
            )

            raise

    def tag_zendesk_user(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        zendesk_user,
        tags,
        called_by="Not set",
        pod_name=stats.PodNames.VIRTUAL_CARE,
    ):
        try:
            response = self.zenpy.users.add_tags(zendesk_user.id, tags)
            stats.increment(
                metric_name=ZENDESK_API_SUCCESS_COUNT_METRICS,
                pod_name=pod_name,
                tags=["api_name:tag_zendesk_user"],
            )
            return response
        except Exception as e:
            exception_type = e.__class__.__name__
            exception_message = str(e)
            generate_user_trace_log(
                log,
                LogLevel.ERROR,
                zendesk_user.id,
                "Error in tagging zendesk user",
                exception_type=exception_type,
                exception_message=exception_message,
                zendesk_user_id=zendesk_user.id,
            )

            stats.increment(
                metric_name=ZENDESK_API_ERROR_COUNT_METRICS,
                pod_name=pod_name,
                tags=[
                    "api_name:tag_zendesk_user",
                    f"exception_type:{exception_type}",
                ],
            )
            self._record_failed_call(
                zendesk_user.id,
                called_by,
                "users.add_tags",
                {
                    "exception_type": exception_type,
                    "exception_message": exception_message,
                    "zendesk_user_id": zendesk_user.id,
                },
            )

            raise

    def get_zendesk_user(
        self,
        zendesk_user_id: str = "",
        zendesk_user_email: str = "",
        called_by: str = "Not set",
        pod_name: PodNames = stats.PodNames.VIRTUAL_CARE,
    ) -> ZDUser:
        """
        Get Zendesk User Profile by zendesk_user_id or zendesk_user_email

        :param zendesk_user_id:
        :param zendesk_user_email:
        :param called_by:
        :param pod_name:
        :return:
        """
        try:
            if zendesk_user_id:
                response = self.zenpy.users(id=zendesk_user_id)
            elif zendesk_user_email:
                response = next(
                    self.zenpy.search(type="user", query=zendesk_user_email), None
                )
            if response and not response.active:
                log.info(
                    "ZD user found is inactive",
                    zendesk_user_id_searched_for=zendesk_user_id,
                    zendesk_user_email_searched_for=zendesk_user_email,
                    retrieved_zendesk_user_id=response.id,
                )
                return None

            stats.increment(
                metric_name=ZENDESK_API_SUCCESS_COUNT_METRICS,
                pod_name=pod_name,
                tags=["api_name:get_zendesk_user_by_id"],
            )

            return response
        except Exception as e:
            exception_type = e.__class__.__name__
            exception_message = str(e)
            generate_user_trace_log(
                log,
                LogLevel.ERROR,
                zendesk_user_id,
                "Error getting zendesk user by id or email",
                zendesk_user_id=zendesk_user_id,
                zendesk_user_email=zendesk_user_email,
                exception_type=exception_type,
                exception_message=exception_message,
            )

            stats.increment(
                metric_name=ZENDESK_API_ERROR_COUNT_METRICS,
                pod_name=pod_name,
                tags=[
                    "api_name:get_zendesk_user",
                    f"exception_type:{exception_type}",
                ],
            )
            self._record_failed_call(
                zendesk_user_id,
                called_by,
                "zenpy.users.users",
                {
                    "exception_type": exception_type,
                    "exception_message": exception_message,
                    "user_id": zendesk_user_id,
                },
            )

            return None

    def update_primary_identity_helper(
        self, zendesk_user_id: str, zendesk_user: ZDUser, update_identity: str = ""
    ) -> None:
        # get list of identities
        identities = self.zenpy.users.identities(id=zendesk_user_id)

        # extract identities based on the value of update_identity ("email" or "phone")
        relevant_identities = [
            identity for identity in identities if identity.type == update_identity
        ]

        # iterate through list of identities to get the current primary identity and check if the identity that is to be primary already exists on the profile
        current_primary_identity = next(
            (identity for identity in relevant_identities if identity.primary), None
        )

        # while zendesk returns a `phone_number` field, the ZendeskUser obj has a field called `phone`
        attribute_name = (
            "phone" if update_identity == IdentityType.PHONE else update_identity
        )

        new_primary_identity = next(
            (
                identity
                for identity in relevant_identities
                if identity.value == getattr(zendesk_user, attribute_name)
            ),
            None,
        )

        # create the new identity if it doesn't exist
        if not new_primary_identity:
            log.info(
                "Creating a new primary identity for the user",
                zendesk_user_id=zendesk_user_id,
                updated_entity_type=update_identity,
                num_existing_relevant_identites=len(relevant_identities),
            )

            # create a new Identity object for the `update_identity` value in order to assign it as the primary value
            new_primary_identity = self.zenpy.users.identities.create(
                user=zendesk_user.id,
                identity=ZDIdentity(
                    type=update_identity,
                    value=getattr(zendesk_user, attribute_name),
                    verified=True,
                ),
            )

        if not new_primary_identity.verified:
            log.info(
                "Verifying new primary identity for user",
                zendesk_user_id=zendesk_user_id,
                updated_entity_type=update_identity,
            )
            new_primary_identity.verified = True
            self.zenpy.users.identities.update(
                user=zendesk_user_id, identity=new_primary_identity
            )

        # if there's a current primary identity, make it secondary
        if (
            current_primary_identity
            and current_primary_identity.id != new_primary_identity.id
        ):
            log.info(
                "Demoting the existing primary identity for user",
                zendesk_user_id=zendesk_user_id,
                updated_entity_type=update_identity,
            )
            current_primary_identity.primary = False
            self.zenpy.users.identities.update(
                user=zendesk_user_id, identity=current_primary_identity
            )

        # make the new identity the primary one
        self.zenpy.users.identities.make_primary(
            user=zendesk_user_id, identity=new_primary_identity
        )
        log.info(
            "Updated the primary identity for user",
            zendesk_user_id=zendesk_user_id,
            updated_entity_type=update_identity,
        )

        return None

    def update_primary_identity(
        self, zendesk_user_id: str, zendesk_user: ZDUser, update_identity: str = ""
    ) -> None:
        """
        Update the primary identity for the given Zendesk user
        :param update_identity: The type of identity to be updated as the primary
        :param zendesk_user_id: Zendesk user id
        :param zendesk_user: Zendesk User object that has the updated identity value
        :return:
        """

        max_retries = 1
        retries = 0

        while retries <= max_retries:
            try:
                self.update_primary_identity_helper(
                    zendesk_user_id=zendesk_user_id,
                    zendesk_user=zendesk_user,
                    update_identity=update_identity,
                )
                return
            except ZendeskAPIException as e:
                if exception_related_to_email_already_exists(e):
                    if retries < max_retries:
                        log.error(
                            "Received zendesk API email already exists exception, will retry",
                            zendesk_user_id=zendesk_user_id,
                            updated_entity_type=update_identity,
                        )
                        time.sleep(1)
                        retries += 1
                    else:
                        raise ZendeskAPIEmailAlreadyExistsException
                else:
                    raise

    def merge_zendesk_profiles(
        self,
        user_id: str,
        source_zendesk_user: ZDUser,
        destination_zendesk_user: ZDUser,
        called_by: str = "Not set",
        pod_name: PodNames = stats.PodNames.VIRTUAL_CARE,
    ) -> ZDUser:
        """
        Merge the source zendesk user profile into the destination user profile
        :param user_id:
        :param source_zendesk_user:
        :param destination_zendesk_user:
        :param called_by:
        :param pod_name:
        :return:
        """
        # get the other zendesk_user_profile by email
        try:
            response = self.zenpy.users.merge(
                source_user=source_zendesk_user,
                dest_user=destination_zendesk_user,
            )
            stats.increment(
                metric_name=ZENDESK_API_SUCCESS_COUNT_METRICS,
                pod_name=pod_name,
                tags=["api_name:merge_zendesk_profiles"],
            )

            log.info(
                "Successfully merged duplicate Zendesk User Profiles",
                user_id=user_id,
                merged_zendesk_profile_id=response.id,
            )
            return response
        except Exception as e:
            exception_type = e.__class__.__name__
            exception_message = str(e)
            generate_user_trace_log(
                log,
                LogLevel.ERROR,
                user_id,
                "Error merging zendesk user profiles",
                exception_type=exception_type,
                exception_message=exception_message,
            )

            stats.increment(
                metric_name=ZENDESK_API_ERROR_COUNT_METRICS,
                pod_name=pod_name,
                tags=[
                    "api_name:merge_zendesk_profiles",
                    f"exception_type:{exception_type}",
                ],
            )
            self._record_failed_call(
                user_id,
                called_by,
                "zenpy.users.merge",
                {
                    "exception_type": exception_type,
                    "exception_message": exception_message,
                    "user_id": user_id,
                },
            )

            raise

    def update_user(
        self,
        user_id: str,
        zendesk_user: ZDUser,
        called_by: str = "Not set",
        pod_name: PodNames = stats.PodNames.VIRTUAL_CARE,
    ) -> ZDUser:
        """
        Update Zendesk User Profile

        :param user_id:
        :param zendesk_user:
        :param called_by:
        :param pod_name:
        :return:
        """
        with self.create_or_update_zd_user_lock(user_id):
            try:
                response = self.zenpy.users.update(zendesk_user)

                stats.increment(
                    metric_name=ZENDESK_API_SUCCESS_COUNT_METRICS,
                    pod_name=pod_name,
                    tags=["api_name:update_user"],
                )

                return response
            except ZendeskAPIException as e:
                exception_type = e.__class__.__name__
                exception_message = str(e)

                email_already_exists_exception = (
                    exception_related_to_email_already_exists(e)
                )
                reason_tag = (
                    "email_already_exists"
                    if email_already_exists_exception
                    else "unknown"
                )

                stats.increment(
                    metric_name=ZENDESK_API_ERROR_COUNT_METRICS,
                    pod_name=pod_name,
                    tags=[
                        "api_name:update_user",
                        f"reason:{reason_tag}",
                        f"exception_type:{exception_type}",
                    ],
                )
                self._record_failed_call(
                    user_id,
                    called_by,
                    "zenpy.users.update",
                    {
                        "exception_type": exception_type,
                        "exception_message": exception_message,
                        "user_id": user_id,
                    },
                )
                generate_user_trace_log(
                    log,
                    LogLevel.ERROR,
                    user_id,
                    "Error updating user",
                    exception_type=exception_type,
                    exception_message=exception_message,
                    email_already_exists_exception=email_already_exists_exception,
                )
                if email_already_exists_exception:
                    raise ZendeskAPIEmailAlreadyExistsException
                raise

    def create_or_update_user(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        user,
        called_by="Not set",
        pod_name=stats.PodNames.VIRTUAL_CARE,
    ):
        user_id = user.id
        track_info = (
            ", ".join(
                (
                    f"{track.name} - {[modifier.value for modifier in track.track_modifiers]}"
                    if track.track_modifiers
                    else f"{track.name}"
                )
                for track in user.active_tracks
            )
            if user.active_tracks
            else None
        )

        with self.create_or_update_zd_user_lock(str(user_id)):
            try:
                zendesk_organization = None
                if user.organization_v2:
                    zendesk_organization = self.get_zendesk_organization(
                        user.organization_v2.id,
                    )
                response = self.zenpy.users.create_or_update(
                    users=ZDUser(
                        email=user.email,
                        name=(
                            user.full_name
                            if user.first_name
                            else user.email.split("@")[0]
                        ),
                        phone=(
                            re.sub(r"[^+\d]", "", user.profile.phone_number)
                            if (user.profile and user.profile.phone_number)
                            else None
                        ),
                        external_id=user_id,
                        user_fields={
                            "care_advocate": (
                                user.care_coordinators[0].full_name
                                if user.care_coordinators
                                else None
                            ),
                            "track": track_info,
                        },
                        organization_id=zendesk_organization.id
                        if zendesk_organization
                        else None,
                    ),
                )

                stats.increment(
                    metric_name=ZENDESK_API_SUCCESS_COUNT_METRICS,
                    pod_name=pod_name,
                    tags=["api_name:user_create_or_update"],
                )

                return response
            except Exception as e:
                exception_type = e.__class__.__name__
                exception_message = str(e)
                generate_user_trace_log(
                    log,
                    LogLevel.ERROR,
                    str(user_id),
                    "Error in creating or updating user",
                    exception_type=exception_type,
                    exception_message=exception_message,
                )

                stats.increment(
                    metric_name=ZENDESK_API_ERROR_COUNT_METRICS,
                    pod_name=pod_name,
                    tags=[
                        "api_name:user_create_or_update",
                        f"exception_type:{exception_type}",
                    ],
                )
                self._record_failed_call(
                    user_id,
                    called_by,
                    "zenpy.users.create_or_update",
                    {
                        "exception_type": exception_type,
                        "exception_message": exception_message,
                        "user_id": user_id,
                    },
                )

                raise

    def search(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        type,
        email,
        user_id,
        called_by="Not set",
        pod_name=stats.PodNames.VIRTUAL_CARE,
    ):
        try:
            response = self.zenpy.search(email=email, type=type)
            stats.increment(
                metric_name=ZENDESK_API_SUCCESS_COUNT_METRICS,
                pod_name=pod_name,
                tags=["api_name:search"],
            )

            return response
        except Exception as e:
            exception_type = e.__class__.__name__
            exception_message = str(e)
            generate_user_trace_log(
                log,
                LogLevel.ERROR,
                user_id,
                "Error in searching",
                exception_type=exception_type,
                exception_message=exception_message,
                type=type,
            )

            stats.increment(
                metric_name=ZENDESK_API_ERROR_COUNT_METRICS,
                pod_name=pod_name,
                tags=["api_name:search", f"exception_type:{exception_type}"],
            )
            self._record_failed_call(
                user_id,
                called_by,
                "zenpy.search",
                {
                    "exception_type": exception_type,
                    "exception_message": exception_message,
                    "user_id": user_id,
                    "type": type,
                },
            )

            raise

    def get_ticket(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        ticket_id,
        user_id,
        called_by="Not set",
        message_id="",
        pod_name=stats.PodNames.VIRTUAL_CARE,
    ):
        try:
            response = self.zenpy.tickets(id=ticket_id)

            stats.increment(
                metric_name=ZENDESK_API_SUCCESS_COUNT_METRICS,
                pod_name=pod_name,
                tags=["api_name:get_ticket"],
            )

            return response
        except Exception as e:
            exception_type = e.__class__.__name__
            exception_message = str(e)

            # If we had a ticket ID but couldn't find the corresponding ticket
            # we want to just create a new ticket. Returning none here will
            # ultimately create a new ticket in #update_zendesk
            if "RecordNotFound" in exception_message:
                stats.increment(
                    metric_name=ZENDESK_TICKET_MISSING_ERROR,
                    pod_name=pod_name,
                    tags=["api_name:get_ticket", f"exception_type:{exception_type}"],
                )
                return None

            generate_user_trace_log(
                log,
                LogLevel.ERROR,
                user_id,
                "Error in looking up zendesk ticket",
                exception_type=exception_type,
                exception_message=exception_message,
                zendesk_ticket_id=ticket_id,
            )

            stats.increment(
                metric_name=ZENDESK_API_ERROR_COUNT_METRICS,
                pod_name=pod_name,
                tags=["api_name:get_ticket", f"exception_type:{exception_type}"],
            )
            self._record_failed_call(
                user_id,
                called_by,
                "zenpy.tickets",
                {
                    "exception_type": exception_type,
                    "exception_message": exception_message,
                    "user_id": user_id,
                    "message_id": message_id,
                    "zendesk_ticket_id": ticket_id,
                },
            )

            raise

    def update_ticket(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        updated_ticket,
        user_id,
        called_by="Not set",
        message_id="",
        pod_name=stats.PodNames.VIRTUAL_CARE,
    ):
        try:
            response = self.zenpy.tickets.update(updated_ticket)
            stats.increment(
                metric_name=ZENDESK_API_SUCCESS_COUNT_METRICS,
                pod_name=pod_name,
                tags=["api_name:update_ticket"],
            )

            return response
        except Exception as e:
            exception_type = e.__class__.__name__
            exception_message = str(e)
            generate_user_trace_log(
                log,
                LogLevel.ERROR,
                user_id,
                "Failed to update existing ticket",
                exception_type=exception_type,
                exception_message=exception_message,
                zendesk_ticket_id=updated_ticket.id,
                zendesk_user_id=updated_ticket.comment.author_id,
            )

            stats.increment(
                metric_name=ZENDESK_API_ERROR_COUNT_METRICS,
                pod_name=pod_name,
                tags=[
                    "api_name:update_ticket",
                    f"exception_type:{exception_type}",
                ],
            )
            self._record_failed_call(
                user_id,
                called_by,
                "zenpy.tickets.update",
                {
                    "exception_type": exception_type,
                    "exception_message": exception_message,
                    "user_id": user_id,
                    "zendesk_ticket_id": updated_ticket.id,
                    "zendesk_user_id": updated_ticket.comment.author_id,
                    "message_id": message_id,
                },
            )

            raise

    def create_ticket(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        new_ticket,
        user_id,
        zd_requester_id,
        called_by="Not set",
        message_id="",
        pod_name=stats.PodNames.VIRTUAL_CARE,
    ):
        try:
            response = self.zenpy.tickets.create(new_ticket)

            stats.increment(
                metric_name=ZENDESK_API_SUCCESS_COUNT_METRICS,
                pod_name=pod_name,
                tags=["api_name:create_ticket"],
            )

            return response
        except Exception as e:
            exception_type = e.__class__.__name__
            exception_message = str(e)

            failure_reason = "unknown"
            error_message = "Failed to create new ticket"

            # We want to send suspender_user errors to a different alert channel. Right now those are the only
            # errors that need special routing
            if "is suspended" in exception_message:
                failure_reason = "suspended_user"
                error_message = "Failed to create new ticket, user is suspended"
            elif "cannot be blank" in exception_message:
                failure_reason = "blank_message"
                error_message = "Failed to create new ticket, blank value"

            generate_user_trace_log(
                log,
                LogLevel.ERROR,
                user_id,
                error_message,
                exception_type=exception_type,
                exception_message=exception_message,
                zendesk_user_id=zd_requester_id,
            )

            stats.increment(
                metric_name=ZENDESK_API_ERROR_COUNT_METRICS,
                pod_name=pod_name,
                tags=[
                    "api_name:create_ticket",
                    f"exception_type:{exception_type}",
                    f"failure_reason:{failure_reason}",
                ],
            )
            self._record_failed_call(
                user_id,
                called_by,
                "zenpy.tickets.create",
                {
                    "exception_type": exception_type,
                    "exception_message": exception_message,
                    "user_id": user_id,
                    "zendesk_user_id": zd_requester_id,
                    "message_id": message_id,
                },
            )

            raise

    def delete_ticket(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        deleted_ticket,
        user_id,
        zd_requester_id,
        called_by="Not set",
        pod_name=stats.PodNames.VIRTUAL_CARE,
    ):
        try:
            response = self.zenpy.tickets.delete(deleted_ticket)

            stats.increment(
                metric_name=ZENDESK_API_SUCCESS_COUNT_METRICS,
                pod_name=pod_name,
                tags=["api_name:deleted_ticket"],
            )

            return response
        except Exception as e:
            exception_type = e.__class__.__name__
            exception_message = str(e)
            generate_user_trace_log(
                log,
                LogLevel.ERROR,
                user_id,
                "Failed to delete ticket",
                exception_type=exception_type,
                exception_message=exception_message,
                zendesk_ticket_id=deleted_ticket.id,
                zendesk_user_id=zd_requester_id,
            )

            stats.increment(
                metric_name=ZENDESK_API_ERROR_COUNT_METRICS,
                pod_name=pod_name,
                tags=[
                    "api_name:deleted_ticket",
                    f"exception_type:{exception_type}",
                ],
            )
            self._record_failed_call(
                user_id,
                called_by,
                "zenpy.tickets.delete",
                {
                    "exception_type": exception_type,
                    "exception_message": exception_message,
                    "user_id": user_id,
                    "zendesk_ticket_id": deleted_ticket.id,
                    "zendesk_user_id": zd_requester_id,
                },
            )

            raise

    def default_updated_ticket_search_window(
        self,
    ) -> tuple[datetime, datetime]:
        """
        Returns a tuple of datetime objects representing the default search
        window for recently updated tickets.
        """
        default_lookback_sec = get_updated_ticket_search_default_lookback_seconds()
        default_to_date = datetime.utcnow()
        default_from_date = default_to_date - timedelta(seconds=default_lookback_sec)
        return default_from_date, default_to_date

    def find_updated_ticket_ids(
        self,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[ZendeskTicketId]:
        """
        Returns a list of Zendesk ticket ids that were updated between the
        from_date and to_date. If no dates are provided, the default search
        window will be used.
        """
        (
            default_from_date,
            default_to_date,
        ) = self.default_updated_ticket_search_window()

        search_from_date = from_date or default_from_date
        search_to_date = to_date or default_to_date

        all_tickets = self._ticket_search_helper(
            search_from_date,
            search_to_date,
        )

        ticket_ids = [ticket.id for ticket in all_tickets]
        return ticket_ids

    def datetime_from_zendesk_date_str(self, date_str: str) -> datetime:
        """
        Returns the datetime instance from the Zendesk formatted timestamp string
        Zendesk format  '2024-02-14T17:25:52Z'
        """
        if date_str is None:
            raise ValueError("date_str must not be None")
        return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")

    def _ticket_search_helper(
        self,
        from_date: datetime,
        to_date: datetime,
        accumulator: list[ZDTicket] | None = None,
        # this is used as a safety check to prevent infinite recursion this
        # effectively limits us to returning N*MAX_TICKETS_PER_SEARCH_CALL per
        # search regardless of the total number of tickets in the search result
        # is indicating from Zendesk
        recursion_limiter: int = TICKET_SEARCH_RECURSION_LIMIT,
        pod_name: PodNames = stats.PodNames.VIRTUAL_CARE,
    ) -> list[ZDTicket]:
        """
        zendesk limits the number of results to 1000 but will inform us of the
        total tickets in the search window even if it is more than 1000. we
        can use this value to move our search window forward and accumulate
        all tickets.
        """
        if accumulator is None:
            accumulator = []
        # this is a safety check to prevent infinite recursion if the search
        # results from zendesk do not shift forward as we expect when we step
        # the `from_date` forward.
        if recursion_limiter <= 0:
            return accumulator
        # move the search window forward to most recent ticket we already have
        # only if we have any tickets

        while recursion_limiter > 0:
            try:
                if len(accumulator) > 0:
                    from_date = self.datetime_from_zendesk_date_str(
                        accumulator[-1].updated_at
                    )

                """
                # Zendesk side filters for webhook triggers
                # ✅ ticket tags must include cx_messaging
                # ✅ ticket stats is not closed
                # ticket was not updated via (API), we check how comment was created instead
                # ticket details > current user is (agent)
                # - unsure if this matters... we can de-dupe comment ids later...
                # ✅ ticket comment is public (handled in process_updated_zendesk_ticket_id)
                # ❌ ticket was not created from a bot conversation handoff
                #
                # order the results from oldest to youngest so that we process them in
                # the order they were updated
                """
                found_tickets: list[ZDTicket] = self.zenpy.search(
                    "",
                    type="ticket",
                    updated_between=[from_date, to_date],
                    tags=["cx_messaging"],
                    status_less_than="closed",
                    order_by="updated_at",
                    sort="asc",
                    # omit tickets created through conversation bot interactions
                    minus=["via:sunshine_conversations_api"],
                )
                # found_tickets_count can be higher than MAX_TICKETS_PER_SEARCH_CALL
                # thats the signal that we will need to shift our search window forward
                # and make another call
                found_tickets_count = len(found_tickets)

                # append the next block to our final result. limit the block size.
                end_index = min(found_tickets_count, MAX_TICKETS_PER_SEARCH_CALL)
                accumulator.extend(found_tickets[:end_index])

                # if we found fewer tix than our max return size then we are done
                if found_tickets_count < MAX_TICKETS_PER_SEARCH_CALL:
                    break
            except ZendeskAPIException as e:
                if e.response and e.response.status_code == 429:
                    handle_zendesk_rate_limit(e.response)
                    exception_type = e.__class__.__name__
                    stats.increment(
                        metric_name=ZENDESK_API_ERROR_COUNT_METRICS,
                        pod_name=pod_name,
                        tags=[
                            "api_name:search",
                            f"exception_type:{exception_type}",
                            f"status_code:{e.response.status_code}",
                        ],
                    )
                    recursion_limiter -= 1
                    continue  # Retry after rate limit handling

            recursion_limiter -= 1  # Decrement limiter on every loop iteration

        return accumulator

    def ticket_with_id(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        ticket_id: ZendeskTicketId | None = None,
        pod_name=stats.PodNames.VIRTUAL_CARE,
        max_retries=DEFAULT_ZENDESK_API_MAX_RETRY,
    ) -> ZDTicket | None:
        if ticket_id is None:
            return None

        retries = 0
        while retries < max_retries:
            try:
                response = self.zenpy.tickets(id=ticket_id)
                stats.increment(
                    metric_name=ZENDESK_API_SUCCESS_COUNT_METRICS,
                    pod_name=pod_name,
                    tags=["api_name:tickets"],
                )

                return response
            except ZendeskAPIException as e:
                if e.response and e.response.status_code == 429:
                    handle_zendesk_rate_limit(e.response)
                    exception_type = e.__class__.__name__
                    stats.increment(
                        metric_name=ZENDESK_API_ERROR_COUNT_METRICS,
                        pod_name=pod_name,
                        tags=[
                            "api_name:tickets",
                            f"exception_type:{exception_type}",
                            f"status_code:{e.response.status_code}",
                        ],
                    )
                    retries += 1
                    continue
            except Exception as e:
                exception_type = e.__class__.__name__
                log.error(
                    "Error when attempting to retrieve ticket", ticket_id=ticket_id
                )

                stats.increment(
                    metric_name=ZENDESK_API_ERROR_COUNT_METRICS,
                    pod_name=pod_name,
                    tags=["api_name:tickets", f"exception_type:{exception_type}"],
                )
                raise e

        log.error("Exceeded max retries for ticket retrieval", ticket_id=ticket_id)
        return None

    def get_comments_for_ticket_id(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        ticket_id: ZendeskTicketId | None = None,
        pod_name=stats.PodNames.VIRTUAL_CARE,
        max_retries=DEFAULT_ZENDESK_API_MAX_RETRY,
    ) -> list[ZDComment] | None:
        """
        Returns a list of Zendesk comments for the given ticket_id.
        WARNING: This is not guaranteed to only contain public comments.
        2024-01-29: There does not look to be any way to request only public comments.
        https://developer.zendesk.com/api-reference/ticketing/tickets/ticket-requests/#listing-comments
        """
        if ticket_id is None:
            return []

        retries = 0
        while retries < max_retries:
            try:
                response = self.zenpy.tickets.comments(ticket=ticket_id)
                stats.increment(
                    metric_name=ZENDESK_API_SUCCESS_COUNT_METRICS,
                    pod_name=pod_name,
                    tags=["api_name:tickets.comments"],
                )

                return response
            except ZendeskAPIException as e:
                if e.response and e.response.status_code == 429:
                    handle_zendesk_rate_limit(e.response)
                    exception_type = e.__class__.__name__
                    stats.increment(
                        metric_name=ZENDESK_API_ERROR_COUNT_METRICS,
                        pod_name=pod_name,
                        tags=[
                            "api_name:tickets.comments",
                            f"exception_type:{exception_type}",
                            f"status_code:{e.response.status_code}",
                        ],
                    )
                    retries += 1
                    continue
            except Exception as e:
                exception_type = e.__class__.__name__
                log.error(
                    "Error when attempting to retrieve comments for ticket",
                    ticket_id=ticket_id,
                )

                stats.increment(
                    metric_name=ZENDESK_API_ERROR_COUNT_METRICS,
                    pod_name=pod_name,
                    tags=[
                        "api_name:tickets.comments",
                        f"exception_type:{exception_type}",
                    ],
                )
                raise e

        log.error(
            "Exceeded max retries when attempting to retrieve comments for ticket",
            ticket_id=ticket_id,
        )
        return None

    @contextlib.contextmanager
    def create_or_update_zd_user_lock(
        self,
        # other locks use message/comment/ticket ID, this uses user
        user_id: str | None,
        # sec we wait before giving up. this should be a low number so we can give
        # resources back to the job pool and use the job scheduling and retry system
        # to do the waiting for us
        lock_timeout_sec: int = 5,
    ) -> Generator[None, None, None]:
        if not user_id:
            return None

        cache_key = f"create_or_update_zd_user:lock:{user_id}"
        try:
            # have a short timeout then exit to put the job back into the queue to be retried
            # doesn't block the other jobs too much
            with RedisLock(cache_key, timeout=lock_timeout_sec):
                yield
        except LockTimeout as e:
            # This is not necessarily an error. It is expected that we will have
            # some number of these. Each will be retried with a backoff. We see an
            # increasing number of jobs that fail all retries with the lock timeout
            # error we should investigate the job backoff and retry configuration.
            log.info(
                "Missed creating or updating Zendesk user due to lock timeout",
                user_id=user_id,
                error=e,
            )
            stats.increment(
                metric_name=ZENDESK_USER_UPDATE_CREATE_TIMEOUT,
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=[
                    f"lock_timeout_sec:{int(lock_timeout_sec)}",
                ],
            )
            raise e

    @contextlib.contextmanager
    def create_or_update_zd_org_lock(
        self,
        org_id: str | None,
        lock_timeout_sec: int = 5,
    ) -> Generator[None, None, None]:
        if not org_id:
            return None

        cache_key = f"create_or_update_zd_org:lock:{org_id}"
        try:
            # have a short timeout then exit to not block
            with RedisLock(cache_key, timeout=lock_timeout_sec):
                yield
        except LockTimeout as e:
            log.info(
                "Missed creating or updating Zendesk organization due to lock timeout",
                org_id=org_id,
                error=e,
            )
            stats.increment(
                metric_name=ZENDESK_ORG_UPDATE_CREATE_TIMEOUT,
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=[
                    f"lock_timeout_sec:{int(lock_timeout_sec)}",
                ],
            )
            raise e

    def create_or_update_organization(
        self,
        org_id: int,
        org_name: str,
        tracks: str,
        offshore_restriction: bool,
        pod_name: PodNames = stats.PodNames.VIRTUAL_CARE,
    ) -> Any:
        with self.create_or_update_zd_org_lock(str(org_id)):
            try:
                response = self.zenpy.organizations.create_or_update(
                    organization=ZDOrganization(
                        external_id=org_id,
                        name=org_name,
                        organization_fields={
                            "tracks": tracks,
                            "offshore_restriction": offshore_restriction,
                        },
                    )
                )
                stats.increment(
                    metric_name=ZENDESK_API_SUCCESS_COUNT_METRICS,
                    pod_name=pod_name,
                    tags=["api_name:org_create_or_update"],
                )

                return response
            except Exception as e:
                exception_type = e.__class__.__name__
                exception_message = str(e)
                log.error(
                    "Error creating or updating Zendesk Organization",
                    org_id=org_id,
                    exception_type=exception_type,
                    exception_message=exception_message,
                )

                stats.increment(
                    metric_name=ZENDESK_API_ERROR_COUNT_METRICS,
                    pod_name=pod_name,
                    tags=[
                        "api_name:org_create_or_update",
                        f"exception_type:{exception_type}",
                    ],
                )

    def get_zendesk_organization(
        self,
        org_id: int | None,
    ) -> ZDOrganization | None:
        zendesk_organizations = None
        try:
            # get matching org in ZD
            zendesk_organizations = list(
                self.zenpy.search(type="organization", external_id=org_id)
            )
            if len(zendesk_organizations) > 1:
                log.info(
                    "Multiple organizations found for org id, using first",
                    org_id=org_id,
                    number_organizations=len(zendesk_organizations),
                )
            return zendesk_organizations[0] if zendesk_organizations else None

        except Exception as e:
            exception_type = e.__class__.__name__
            exception_message = str(e)
            log.error(
                "Error getting Zendesk organization",
                org_id=org_id,
                zendesk_org_id=zendesk_organizations[0].id
                if zendesk_organizations
                else None,
                exception_type=exception_type,
                exception_message=exception_message,
            )
            return None
