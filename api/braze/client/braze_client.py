from __future__ import annotations

import dataclasses
import datetime
import enum
import html
import json
import os
import time
from typing import Any, Collection, Literal, Mapping

import ddtrace
import requests
from dateutil.parser import parse
from maven import feature_flags

from braze.client import constants
from common import stats
from utils.log import logger

log = logger(__name__)


__all__ = (
    "BrazeClient",
    "BrazeEmail",
    "BrazeEmailAttachment",
    "BrazeEvent",
    "BrazeUserAttributes",
    "BrazeSubscriptionState",
    "RawBrazeString",
    "SupportedMethods",
    "BrazeEmailBodyMissingError",
    "format_dt",
    "recursive_html_escape",
    "BrazeExportedUser",
    "BrazeUserAlias",
    "BrazeCustomEventResponse",
)


class SupportedMethods(str, enum.Enum):
    GET = "GET"
    POST = "POST"


def process_in_batches(func):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    def wrapper(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self,
        user_attributes: Collection[BrazeUserAttributes] | None = None,
        events: Collection[BrazeEvent] | None = None,
    ):
        offset = 0
        num_attrs = len(user_attributes) if user_attributes else 0
        num_events = len(events) if events else 0
        while True:
            user_attrs = None
            user_events = None

            if num_attrs and offset < num_attrs:
                user_attrs = user_attributes[  # type: ignore[index] # Value of type "Optional[Collection[BrazeUserAttributes]]" is not indexable
                    offset : offset + constants.TRACK_USER_ENDPOINT_LIMIT
                ]
            if num_events and offset < num_events:
                user_events = events[  # type: ignore[index] # Value of type "Optional[Collection[BrazeEvent]]" is not indexable
                    offset : offset + constants.TRACK_USER_ENDPOINT_LIMIT
                ]

            resp = func(self, user_attributes=user_attrs, events=user_events)

            offset += constants.TRACK_USER_ENDPOINT_LIMIT
            if offset > num_attrs and offset > num_events:
                break

        return resp  # return the last response

    return wrapper


class BrazeClient:
    def __init__(self, api_key: str = constants.BRAZE_API_KEY):  # type: ignore[assignment] # Incompatible default for argument "api_key" (default has type "Optional[str]", argument has type "str")
        self.api_key = api_key

    @ddtrace.tracer.wrap()
    def _make_request(
        self,
        *,
        endpoint: str,
        data: dict | None,
        method: SupportedMethods = SupportedMethods.POST,
        retry_on_failure: bool = True,
        escape_html: bool = True,
    ) -> requests.Response | None:
        """Handles calling the Braze API endpoints using the endpoint
        provided. This function should be called with one of the pre-defined
        endpoints:
            EMAIL_SUBSCRIBE_ENDPOINT
            MESSAGE_SEND_ENDPOINT
            USER_TRACK_ENDPOINT
            USER_DELETE_ENDPOINT

        Any other endpoints that are needed should be added to the list of
        pre-defined endpoints, with care being taken to not use dynamic
        information due to how it is being used for custom metrics tags.

        If such dynamic data is required in the future, the custom metrics
        should be revisited to find a way to ensure that the tags are from
        a static, limited set of values.

        method: currently support GET, POST
        for POST, data will be passed as request body
        for GET, data will be passed as parameters(query string)
        """
        log.info(
            "Making Braze API request.",
            braze_endpoint=endpoint,
            method=method,
            retry_on_failure=retry_on_failure,
        )

        # if the feature flag is disabled, don't process any requests.
        # if we can't connect to LaunchDarkly, and there is a TESTING env var, don't process any requests.
        if not feature_flags.bool_variation(
            flag_key="kill-switch-braze-api-requests",
            default=not bool(os.environ.get("TESTING")),
        ):
            log.warning(
                "Skipping Braze API request in when `kill-switch-braze-api-requests` flag is disabled."
            )
            return None

        if not self.api_key:
            log.warning("Skipping Braze API request in environment without an api key.")
            return None

        endpoint_tag = endpoint[len(constants.API_ENDPOINT) :]
        try:
            # This custom metric, along with those collected from CPS, lets us
            # keep track of calls to the Braze endpoints.
            stats.increment(
                metric_name="braze.api.request",
                pod_name=stats.PodNames.TEST_POD,
                tags=[
                    f"endpoint:{endpoint_tag}",
                    # At this time, Mono is not sending the bulk header, so this is always false
                    "is_bulk:false",
                ],
            )

            if escape_html:
                data = recursive_html_escape(data)

            headers = {
                "Content-type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }

            if method == SupportedMethods.POST:
                resp = requests.post(
                    endpoint,
                    data=json.dumps(data),
                    headers=headers,
                    timeout=constants.REQUEST_TIMEOUT,
                )
            elif method == SupportedMethods.GET:
                resp = requests.get(
                    endpoint,
                    params=data,
                    headers=headers,
                    timeout=constants.REQUEST_TIMEOUT,
                )
            else:
                raise NotImplementedError(f"{method} is not supported")

            # The X-RateLimit-Remaining value in a successful response header indicates
            # how many requests are remaining in the current rate limit window.
            ratelimit_remaining = resp.headers.get("X-RateLimit-Remaining", None)
            if ratelimit_remaining is not None:
                stats.gauge(
                    metric_name="braze.api.response.header.X-RateLimit-Remaining",
                    pod_name=stats.PodNames.TEST_POD,
                    metric_value=ratelimit_remaining,  # type: ignore[arg-type] # Argument "metric_value" to "gauge" has incompatible type "str"; expected "float"
                    tags=[
                        f"endpoint:{endpoint_tag}",
                    ],
                )
            resp.raise_for_status()
            return resp
        except requests.HTTPError as http_e:
            log.error(
                "Braze API request failed.",
                braze_endpoint=endpoint,
                response=http_e.response.text,
                exception=http_e,
                will_retry=retry_on_failure,
            )
            # We track the fatal error returns from Braze based on 400-level &
            # 500-level status error codes.
            stats.increment(
                metric_name="braze.api.fatal_error",
                pod_name=stats.PodNames.TEST_POD,
                tags=[
                    f"endpoint:{endpoint_tag}",
                    f"reason:{http_e.response.status_code}",
                ],
            )

            # We only want to retry requests if the response code was 5xx
            if retry_on_failure and http_e.response.status_code >= 500:
                return self._make_request(
                    endpoint=endpoint,
                    data=data,
                    method=method,
                    retry_on_failure=False,
                )
            return http_e.response
        except requests.Timeout as timeout_e:
            log.error(
                "Braze API request failed.",
                braze_endpoint=endpoint,
                exception_message=str(timeout_e),
                exception=timeout_e,
                will_retry=retry_on_failure,
            )
            stats.increment(
                metric_name="braze.api.fatal_error",
                pod_name=stats.PodNames.TEST_POD,
                tags=[
                    f"endpoint:{endpoint_tag}",
                    "reason:timeout",
                ],
            )

            if retry_on_failure:
                time.sleep(1)
                return self._make_request(
                    endpoint=endpoint,
                    data=data,
                    method=method,
                    retry_on_failure=False,
                )

            response = requests.Response()
            response._content = str(timeout_e).encode("utf-8")
            response.status_code = 408
            return response
        except (ConnectionError, requests.ConnectionError) as cnx_e:
            log.error(
                "Braze API request failed.",
                braze_endpoint=endpoint,
                exception_message=str(cnx_e),
                exception=cnx_e,
                will_retry=retry_on_failure,
            )
            stats.increment(
                metric_name="braze.api.fatal_error",
                pod_name=stats.PodNames.TEST_POD,
                tags=[
                    f"endpoint:{endpoint_tag}",
                    "reason:connection_reset_by_peer",
                ],
            )

            if retry_on_failure:
                time.sleep(1)
                return self._make_request(
                    endpoint=endpoint,
                    data=data,
                    method=method,
                    retry_on_failure=False,
                )

            response = requests.Response()
            response._content = str(cnx_e).encode("utf-8")
            response.status_code = 400
            return response
        except Exception as e:
            log.error(
                "Braze API request failed.",
                braze_endpoint=endpoint,
                exception_message=str(e),
                exception=e,
                will_retry=retry_on_failure,
            )
            # Non-HTTP errors are still tracked, but do not provide the specific reason.
            # Anyone investigating these errors should be checking the logs for more
            # information.
            stats.increment(
                metric_name="braze.api.fatal_error",
                pod_name=stats.PodNames.TEST_POD,
                tags=[
                    f"endpoint:{endpoint_tag}",
                    "reason:unknown",
                ],
            )

            if retry_on_failure:
                time.sleep(1)
                return self._make_request(
                    endpoint=endpoint,
                    data=data,
                    method=method,
                    retry_on_failure=False,
                )

            response = requests.Response()
            response._content = str(e).encode("utf-8")
            response.status_code = 400
            return response

    @ddtrace.tracer.wrap()
    def track_user(
        self,
        user_attributes: BrazeUserAttributes | None = None,
        events: Collection[BrazeEvent] | None = None,
    ) -> requests.Response | None:
        """
        Record custom events and update user profile attributes.

        https://www.braze.com/docs/api/endpoints/user_data/post_user_track/
        """
        return self.track_users(
            user_attributes=[user_attributes] if user_attributes else None,
            events=events,
        )

    @ddtrace.tracer.wrap()
    @process_in_batches
    def track_users(
        self,
        *,
        user_attributes: Collection[BrazeUserAttributes] | None = None,
        events: Collection[BrazeEvent] | None = None,
    ) -> requests.Response | None:
        """
        Record custom events and update user profile attributes for multiple users.

        https://www.braze.com/docs/api/endpoints/user_data/post_user_track/
        """
        if not user_attributes and not events:
            log.warning("No data to send to Braze. Skipping request")
            return None

        payload = {}
        if events:
            payload["events"] = [event.as_dict() for event in events]

        attributes = []
        if user_attributes:
            for braze_user in user_attributes:
                # Make sure there are actually attributes to send.
                if any(val is not None for val in braze_user.attributes.values()):
                    attributes.append(braze_user.as_dict())

            if attributes:
                payload["attributes"] = attributes

        if not events and not attributes:
            log.warning("No data to send to Braze. Skipping request")
            return None

        external_ids = (
            {braze_user.external_id for braze_user in user_attributes}
            if user_attributes
            else set()
        )
        if events:
            external_ids.update({event.external_id for event in events})

        log.info("Calling BrazeClient.track_users", external_ids=external_ids)
        resp = self._make_request(
            endpoint=constants.USER_TRACK_ENDPOINT,
            data=payload,
        )

        if resp and not resp.ok:
            log.error(
                "Failed request to BrazeClient.track_users", external_ids=external_ids
            )

        total_data_points = 0
        if resp and resp.ok and user_attributes:
            total_data_points += sum(
                braze_user.total_data_points() for braze_user in user_attributes
            )

        if events:
            success = "false"
            if resp and resp.ok:
                total_data_points += sum(event.total_data_points() for event in events)
                success = "true"

            tags = [f"success:{success}"]
            tags += [f"event_name:{event.name}" for event in events]
            stats.increment(
                metric_name="braze.api.send_event",
                pod_name=stats.PodNames.TEST_POD,
                tags=tags,
            )

        if total_data_points:
            stats.increment(
                metric_name="braze.api.data_points_used.count",
                pod_name=stats.PodNames.TEST_POD,
                metric_value=total_data_points,
            )

        return resp

    @ddtrace.tracer.wrap()
    def delete_user(self, *, external_id: str) -> requests.Response | None:
        """
        Delete a user profile

        https://www.braze.com/docs/api/endpoints/user_data/post_user_delete/
        """
        return self.delete_users(external_ids=[external_id])

    @ddtrace.tracer.wrap()
    def delete_users(
        self,
        *,
        external_ids: list[str],
    ) -> requests.Response | None:
        """
        Delete user profiles

        https://www.braze.com/docs/api/endpoints/user_data/post_user_delete/
        """
        log.info("Calling BrazeClient.delete_users", external_ids=external_ids)
        resp = self._make_request(
            endpoint=constants.USER_DELETE_ENDPOINT,
            data={"external_ids": external_ids},
        )
        if not resp or not resp.ok:
            log.error(
                "Failed request to BrazeClient.delete_users", external_ids=external_ids
            )
        return resp

    @ddtrace.tracer.wrap()
    def unsubscribe_email(self, *, email: str) -> requests.Response | None:
        """
        Unsubscribe from Braze marketing emails
        """
        return self.update_email_subscription_status(
            email=email,
            subscription_state=BrazeSubscriptionState.UNSUBSCRIBED,
        )

    @ddtrace.tracer.wrap()
    def opt_in_email(self, *, email: str) -> requests.Response | None:
        """
        Opt-in to Braze marketing emails
        """
        return self.update_email_subscription_status(
            email=email,
            subscription_state=BrazeSubscriptionState.OPTED_IN,
        )

    @ddtrace.tracer.wrap()
    def update_email_subscription_status(
        self,
        *,
        email: str,
        subscription_state: BrazeSubscriptionState,
    ) -> requests.Response | None:
        """
        Update the email subscription state for the user.

        https://www.braze.com/docs/api/endpoints/email/post_email_subscription_status/
        """
        return self.update_email_subscription_statuses(
            emails=[email],
            subscription_state=subscription_state,
        )

    @ddtrace.tracer.wrap()
    def update_email_subscription_statuses(
        self,
        *,
        emails: list[str],
        subscription_state: BrazeSubscriptionState,
    ) -> requests.Response | None:
        """
        Update the email subscription state for the users.

        https://www.braze.com/docs/api/endpoints/email/post_email_subscription_status/
        """
        return self._make_request(
            endpoint=constants.EMAIL_SUBSCRIBE_ENDPOINT,
            data={"email": emails, "subscription_state": subscription_state.value},
        )

    @ddtrace.tracer.wrap()
    def get_unsubscribes(
        self,
        *,
        start_date: datetime.date,
        end_date: datetime.date,
        offset: int = 0,
    ) -> list[str]:
        """
        Get the emails that have unsubscribed during the given time period.

        https://www.braze.com/docs/api/endpoints/email/get_query_unsubscribed_email_addresses/

        @param start_date: datetime.date, start date
        @param end_date: datetime.date, end date
        @param offset: int, beginning point in the list to retrieve from
        """
        emails = []
        data = {
            "limit": constants.UNSUBSCRIBES_ENDPOINT_LIMIT,
            "offset": offset,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "sort_direction": "asc",
        }
        resp = self._make_request(
            endpoint=constants.UNSUBSCRIBES_ENDPOINT,
            data=data,
            method=SupportedMethods.GET,
        )
        if not resp or not resp.ok:
            log.warn("Could not retrieve unsubscribes due to a Braze API failure")
            return emails

        json_ = resp.json()
        for unsubscribe in json_["emails"]:
            emails.append(unsubscribe["email"])
        return emails

    @ddtrace.tracer.wrap()
    def send_email(
        self,
        *,
        email: BrazeEmail,
        recipient_subscription_state: Literal[
            "opted_in", "subscribed", "all"
        ] = "subscribed",
    ) -> str | None:
        """
        Immediately send message to designated users.

        https://www.braze.com/docs/api/endpoints/messaging/send_messages/post_send_messages/
        """
        # body is required unless email_template_id is given
        if email.body is None and email.email_template_id is None:
            raise BrazeEmailBodyMissingError(
                "`body` is required when `email_template_id` is not provided."
            )

        email_json = dataclasses.asdict(email)
        # `from` is a reserved keyword in Python,
        # but it's the name of the name of the field Braze requires,
        # so we rename the key here before sending to Braze.
        email_json["from"] = email_json.pop("from_")

        external_ids = email_json.pop("external_ids")

        email_json = {k: v for k, v in email_json.items() if v is not None}

        if recipient_subscription_state not in ["opted_in", "subscribed", "all"]:
            log.warning("Invalid recipient subscription state, will use 'subscribed'")
            recipient_subscription_state = "subscribed"

        resp = self._make_request(
            endpoint=constants.MESSAGE_SEND_ENDPOINT,
            data={
                "external_user_ids": external_ids,
                "messages": {"email": email_json},
                "recipient_subscription_state": recipient_subscription_state,
            },
            # Cannot send escaped HTML in this case, or it will be unrendered in the email
            escape_html=False,
        )

        if resp:
            json_ = resp.json()
            return json_.get("dispatch_id")
        return None

    @ddtrace.tracer.wrap()
    def get_mau_count(
        self,
        *,
        length: int = 1,
        ending_at: datetime.datetime | None = None,
        app_id: str | None = None,
    ) -> int | None:
        """
        Retrieve a daily series of the total number of unique active users over a 30-day rolling window.

        https://www.braze.com/docs/api/endpoints/export/kpi/get_kpi_mau_30_days/

        :param length: Maximum number of days [1-100] before `ending_at` to include in the returned series.
        :param ending_at: Date on which the data series should end. Defaults to current time.
        :param app_id: App API identifier. If null, results for all apps in a workspace will be returned.
        """
        assert (
            1 <= length <= 100
        ), "Invalid length! Length must be between 1 and 100, inclusive"

        if not ending_at:
            ending_at = datetime.datetime.utcnow()

        params = dict(length=length, ending_at=ending_at.isoformat())
        if app_id is not None:
            params.update({"app_id": app_id})

        resp = self._make_request(
            endpoint=constants.MAU_ENDPOINT,
            method=SupportedMethods.GET,
            data=params,
        )

        if resp and resp.ok:
            mau_resp = BrazeMauResponse(**resp.json())
            mau = mau_resp.data[0].mau

            stats.gauge(
                metric_name="braze.api.mau",
                pod_name=stats.PodNames.TEST_POD,
                metric_value=mau,
            )
            return mau

        return None

    @ddtrace.tracer.wrap()
    def get_dau_count(
        self,
        *,
        length: int = 1,
        ending_at: datetime.datetime | None = None,
        app_id: str | None = None,
    ) -> int | None:
        """
        Retrieve a daily series of the total number of unique active users on each date.

        https://www.braze.com/docs/api/endpoints/export/kpi/get_kpi_dau_date/

        :param length: Maximum number of days [1-100] before `ending_at` to include in the returned series.
        :param ending_at: Date on which the data series should end. Defaults to current time.
        :param app_id: App API identifier. If null, results for all apps in a workspace will be returned.
        """
        assert (
            1 <= length <= 100
        ), "Invalid length! Length must be between 1 and 100, inclusive"

        if not ending_at:
            ending_at = datetime.datetime.utcnow()

        params = dict(length=length, ending_at=ending_at.isoformat())
        if app_id is not None:
            params.update({"app_id": app_id})

        resp = self._make_request(
            endpoint=constants.DAU_ENDPOINT,
            method=SupportedMethods.GET,
            data=params,
        )

        if resp and resp.ok:
            dau_resp = BrazeDauResponse(**resp.json())
            dau = dau_resp.data[0].dau

            stats.gauge(
                metric_name="braze.api.dau",
                pod_name=stats.PodNames.TEST_POD,
                metric_value=dau,
            )
            return dau

        return None

    @ddtrace.tracer.wrap()
    def fetch_user(self, *, external_id: str) -> BrazeExportedUser | None:
        """
        Export data from a Braze user profile matching the given external_id.

        https://www.braze.com/docs/api/endpoints/export/user_data/post_users_identifier/
        """
        braze_profiles = self.fetch_users(external_ids=[external_id])
        if braze_profiles:
            return braze_profiles[0]
        return None

    @ddtrace.tracer.wrap()
    def fetch_user_by_email(self, *, email: str) -> BrazeExportedUser | None:
        """
        Export data from a Braze user profile matching the given email.

        https://www.braze.com/docs/api/endpoints/export/user_data/post_users_identifier/
        """
        braze_profiles = self.fetch_users(email=email)
        if braze_profiles:
            return braze_profiles[0]
        return None

    @ddtrace.tracer.wrap()
    def fetch_users(
        self,
        *,
        external_ids: list[str] | None = None,
        email: str | None = None,
    ) -> list[BrazeExportedUser] | None:
        """
        Export data from Braze user profiles matching by the given external_ids or email.

        https://www.braze.com/docs/api/endpoints/export/user_data/post_users_identifier/
        """
        if not external_ids and not email:
            log.warning("No user identifiers specified. Skipping request.")
            return None

        payload = {}
        if external_ids:
            payload["external_ids"] = external_ids

        if email:
            payload["email_address"] = email  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", target has type "List[str]")

        resp = self._make_request(
            endpoint=constants.USER_EXPORT_ENDPOINT,
            method=SupportedMethods.POST,
            data=payload,
        )

        if resp and resp.ok:
            export_resp = BrazeExportUsersResponse(**resp.json())
            exported_users = export_resp.users
            return exported_users

        return None


@dataclasses.dataclass(frozen=True)
class BrazeUserAttributes:
    __slots__ = ("external_id", "attributes")
    external_id: str
    attributes: dict

    def as_dict(self) -> dict:
        attrs = {"external_id": self.external_id}
        for key, value in self.attributes.items():
            if isinstance(value, (datetime.datetime, datetime.date)):
                self.attributes[key] = format_dt(value)
        return {**attrs, **self.attributes}

    def total_data_points(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return _total_data_points(self.attributes)


@dataclasses.dataclass(frozen=True)
class BrazeEmail:
    external_ids: list[str]
    from_: str
    body: str | None = None  # required unless email_template_id is specified
    plaintext_body: str | None = None
    subject: str | None = None
    reply_to: str | None = None
    headers: dict[str, str] | None = None
    email_template_id: str | None = None
    attachments: list[BrazeEmailAttachment] | None = None
    app_id: str = constants.BRAZE_WEB_APP_ID  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Optional[str]", variable has type "str")


@dataclasses.dataclass(frozen=True)
class BrazeEmailAttachment:
    __slots__ = ("file_name", "url")
    file_name: str
    url: str


@dataclasses.dataclass(frozen=True)
class BrazeEvent:
    external_id: str
    name: str
    properties: dict | None = None
    time: datetime.datetime | None = None

    def as_dict(self) -> dict:
        time_ = self.time or datetime.datetime.utcnow()

        if self.properties:
            for key, value in self.properties.items():
                if isinstance(value, (datetime.datetime, datetime.date)):
                    self.properties[key] = format_dt(value)

        return {
            "external_id": self.external_id,
            "name": self.name,
            "time": format_dt(time_),
            "properties": self.properties,
        }

    def total_data_points(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # Braze charges one data point for the event
        total_data_points = 1
        # and then one point per property, including nested objects.
        if self.properties:
            total_data_points += _total_data_points(self.properties)
        return total_data_points


@dataclasses.dataclass()
class BrazeMauResponse:
    message: str
    data: list[BrazeMauDataPoint]

    def __post_init__(self) -> None:
        self.data = [BrazeMauDataPoint(**d) for d in self.data]  # type: ignore[arg-type] # Argument after ** must be a mapping, not "BrazeMauDataPoint"


@dataclasses.dataclass(frozen=True)
class BrazeMauDataPoint:
    time: str
    mau: int


@dataclasses.dataclass()
class BrazeDauResponse:
    message: str
    data: list[BrazeDauDataPoint]

    def __post_init__(self) -> None:
        self.data = [BrazeDauDataPoint(**d) for d in self.data]  # type: ignore[arg-type] # Argument after ** must be a mapping, not "BrazeDauDataPoint"


@dataclasses.dataclass(frozen=True)
class BrazeDauDataPoint:
    time: str
    dau: int


@dataclasses.dataclass()
class BrazeExportUsersResponse:
    message: str
    users: list[BrazeExportedUser] | None
    invalid_user_ids: list[str] | None = None

    def __post_init__(self) -> None:
        self.users = (
            [BrazeExportedUser.from_dict(u) for u in self.users] if self.users else None  # type: ignore[arg-type] # Argument 1 to "from_dict" of "BrazeExportedUser" has incompatible type "BrazeExportedUser"; expected "Dict[str, Any]"
        )


@dataclasses.dataclass()
class BrazeExportedUser:
    """
    This dataclass doesn't capture all the available fields,
    but it captures the ones we are most interested in.

    The full set of available fields can be found in the Braze API docs:
    https://www.braze.com/docs/api/endpoints/export/user_data/post_users_identifier#sample-user-export-file-output
    """

    external_id: str
    created_at: datetime.datetime
    user_aliases: list[BrazeUserAlias]
    braze_id: str
    email_subscribe: str
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    custom_attributes: dict[str, Any] | None = None
    custom_events: list[BrazeCustomEventResponse] | None = None
    country: str | None = None
    language: str | None = None
    time_zone: str | None = None
    email_unsubscribed_at: datetime.datetime | None = None

    def __post_init__(self) -> None:
        self.custom_events = (
            [BrazeCustomEventResponse(**e) for e in self.custom_events]  # type: ignore[arg-type] # Argument after ** must be a mapping, not "BrazeCustomEventResponse"
            if self.custom_events
            else None
        )
        self.user_aliases = [BrazeUserAlias(**a) for a in self.user_aliases]  # type: ignore[arg-type] # Argument after ** must be a mapping, not "BrazeUserAlias"
        self.created_at = (
            parse(self.created_at, ignoretz=True)  # type: ignore[arg-type] # Argument 1 to "parse" has incompatible type "datetime"; expected "Union[bytes, str, IO[str], IO[Any]]"
            if isinstance(self.created_at, str)
            else self.created_at
        )
        self.email_unsubscribed_at = (
            parse(self.email_unsubscribed_at)  # type: ignore[arg-type] # Argument 1 to "parse" has incompatible type "Optional[datetime]"; expected "Union[bytes, str, IO[str], IO[Any]]"
            if self.email_unsubscribed_at
            and isinstance(self.email_unsubscribed_at, str)
            else None
        )

    @classmethod
    def from_dict(cls: BrazeExportedUser, data: dict[str, Any]) -> BrazeExportedUser:
        fields = {f.name for f in dataclasses.fields(cls)}
        return BrazeExportedUser(**{k: v for k, v in data.items() if k in fields})

    def as_dict(self) -> dict:
        data = dataclasses.asdict(self)
        custom_attributes = data.pop("custom_attributes", {})
        data.update(custom_attributes)
        return {k: v for k, v in data.items() if v is not None}


@dataclasses.dataclass()
class BrazeCustomEventResponse:
    name: str
    first: datetime.datetime
    last: datetime.datetime
    count: int

    def __post_init__(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self.first = parse(self.first) if isinstance(self.first, str) else self.first  # type: ignore[arg-type] # Argument 1 to "parse" has incompatible type "datetime"; expected "Union[bytes, str, IO[str], IO[Any]]"
        self.last = parse(self.last) if isinstance(self.last, str) else self.last  # type: ignore[arg-type] # Argument 1 to "parse" has incompatible type "datetime"; expected "Union[bytes, str, IO[str], IO[Any]]"


@dataclasses.dataclass(frozen=True)
class BrazeUserAlias:
    alias_name: str
    alias_label: str


class BrazeSubscriptionState(str, enum.Enum):
    OPTED_IN = "opted_in"
    UNSUBSCRIBED = "unsubscribed"


class BrazeEmailBodyMissingError(Exception):
    pass


class RawBrazeString:
    """RawBrazeString represents a string that should not be html escaped when sent to braze."""

    def __init__(self, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.value = value

    def __eq__(self, other):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return isinstance(other, RawBrazeString) and self.value == other.value


def format_dt(datetime_obj) -> str:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    if isinstance(datetime_obj, datetime.datetime):
        return datetime_obj.isoformat()
    elif isinstance(datetime_obj, datetime.date):
        dt = datetime.datetime(datetime_obj.year, datetime_obj.month, datetime_obj.day)
        return dt.isoformat()
    else:
        return datetime_obj


def recursive_html_escape(data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """Adapted from https://stackoverflow.com/a/48304328"""
    if isinstance(data, RawBrazeString):
        return data.value
    if isinstance(data, str):
        return html.escape(data)
    if isinstance(data, Mapping):
        return type(data)({k: recursive_html_escape(v) for k, v in data.items()})  # type: ignore[call-arg] # Too many arguments for "Mapping"
    if isinstance(data, Collection):
        return type(data)(recursive_html_escape(v) for v in data)  # type: ignore[call-arg] # Too many arguments for "Collection"
    return data


def _total_data_points(obj: dict) -> int:
    # Braze charges one data point per key.
    # If the value of the key is a nested dictionary,
    # we are charged one data point per key in the nested dictionary,
    # but not for the top-level key.
    num_keys = 0
    for _, value in obj.items():
        if isinstance(value, dict):
            num_keys += _total_data_points(value)
        else:
            num_keys += 1
    return num_keys
