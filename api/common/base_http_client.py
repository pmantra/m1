from __future__ import annotations

import time
from typing import Any, Literal, Mapping, Optional

import ddtrace
import requests
from ddtrace.propagation import http
from requests import HTTPError, Response, Timeout
from requests.exceptions import SSLError
from structlog import BoundLoggerBase

from common import stats
from common.stats import PodNames
from utils.log import logger


class BaseHttpClient:
    """
    Base class for interacting with HTTP-based services.

    While it is possible to instantiate and use this class directly, most if not
    all users will want to extend the class to support default customization
    and custom logic for their use case.

    Calling make_request() on the instance will execute the HTTP request with
    standard logging and return a standardized Response object:
    >> client = MyService()
    >> response = client.make_request("/status")

    *Optional Features*

    **Metrics**
    To configure the class for logging, pass the `metric_prefix` and `metric_pod_name`
    to the constructor. When configured, calls to make_request() that pass a `metric_suffix`
    will record metrics for all calls, success or failure. Extended classes may call
    _increment_metric() to record custom metrics.

    **Retry**
    When make_request() is called with `retry_on_error=True`, extended classes should
    override `_should_retry_on_error()` to determine if a specific request should be retried,
    and may override `_retry_make_request()` if custom retry behavior is needed.

    **Tokens**
    See [AccessTokenMixin] for token support.

    **Triforce**
    See [BaseTriforceClient] for a class with Triforce-specific features.
    """

    def __init__(
        self,
        *,
        base_url: str = "",
        service_name: str,
        content_type: str,
        headers: Mapping[str, str] | None = None,
        log: BoundLoggerBase | None = None,
        metric_prefix: str | None = None,
        metric_pod_name: PodNames | None = None,
    ) -> None:
        """
        :param base_url: base URL of the service to be prepended to the URL for all requests (Optional)
        :param service_name: used for logging
        :param content_type: default content type for all requests
        :param headers: data to be sent as HTTP headers on all requests
        :param log: logger instance
        :param metric_prefix: base name for metrics
        :param metric_pod_name: Pod name tag for metrics
        """
        self.base_url = base_url
        self.headers = headers or {}
        self.headers.setdefault("Content-Type", content_type)  # type: ignore[attr-defined] # "Mapping[str, str]" has no attribute "setdefault"
        self.service_name = service_name
        self.log = log or logger(__name__)
        self.metric_prefix = metric_prefix
        self.metric_pod_name = metric_pod_name

        if self.metric_prefix and not self.metric_pod_name:
            raise RuntimeError("Pod Name must be set when metric prefix is present.")

    def _prepare_headers(self, **extra_headers: str) -> Mapping[str, str]:
        merged = {**self.headers, **extra_headers}
        context = ddtrace.tracer.current_trace_context()
        if context:
            http.HTTPPropagator.inject(context, merged)
        return merged

    @staticmethod
    def _get_response_json_or_text(response: requests.Response) -> Any:
        try:
            return response.json()
        except requests.JSONDecodeError:
            return response.text

    def make_request(
        self,
        url: str,
        data: Any = None,
        params: dict[str, Any] | None = None,
        extra_headers: Mapping[str, str] | None = None,
        method: Literal["GET", "PUT", "POST", "DELETE", "PATCH"] = "GET",
        timeout: int | None = None,
        retry_on_error: bool = False,
        metric_suffix: str | None = None,
        **kwargs: Any,
    ) -> Response:
        """
        Make an HTTP request

        :param url: Complete URL for the request
        :param data: data to be sent as the body of the request
        :param params: data to be sent as URL parameters in the query string of the request
        :param extra_headers: data to be sent as HTTP headers on the request
        :param method: HTTP method for the request
        :param timeout: Request timeout in seconds
        :param retry_on_error: If the request should be retried on error
        :param metric_suffix: Appended to metric_prefix to create metric name
        :param kwargs: Additional arguments passed directly to Requests.request()
        :return: Response object
        """

        full_url = f"{self.base_url}{url}"
        extra_headers = extra_headers or {}
        headers = self._prepare_headers(**extra_headers)

        request_exception: Exception | None = None
        successful: bool = False
        metric_reason: str | None = None

        try:
            response = requests.request(
                method=method,
                url=full_url,
                data=data,
                params=params,
                headers=headers,
                timeout=timeout,
                **kwargs,
            )
            response.raise_for_status()
            result = response
            successful = True
        except HTTPError as e:
            self.log.error(
                f"{self.service_name} request failed with an HTTP status message.",
                url=full_url,
                params=params,
                exception_message=str(e),
                exeption_type=type(e),
                response=self._get_response_json_or_text(e.response),
            )
            request_exception = e
            result = e.response
            metric_reason = "request_http_error"
        except Timeout as e:
            self.log.error(
                f"{self.service_name} request failed due to a connection timeout.",
                url=full_url,
                params=params,
                exception_message=str(e),
                exeption_type=type(e),
            )
            request_exception = e
            result = Response()
            result._content = str(e).encode("utf-8")
            result.status_code = 408
            metric_reason = "request_timeout"
        except SSLError as e:
            self.log.error(
                f"{self.service_name} request failed due to an SSL error.",
                url=full_url,
                params=params,
                exception_message=str(e),
                exeption_type=type(e),
            )
            request_exception = e
            result = Response()
            result._content = str(e).encode("utf-8")
            result.status_code = 500
            metric_reason = "request_ssl_error"
        except Exception as e:
            self.log.error(
                f"{self.service_name} request failed.",
                url=full_url,
                params=params,
                exception_message=str(e),
                exeption_type=type(e),
            )
            request_exception = e
            result = Response()
            result._content = str(e).encode("utf-8")
            result.status_code = 400
            metric_reason = "request_exception"

        if metric_suffix:
            self._increment_metric(
                metric_suffix=metric_suffix,
                successful=successful,
                http_error_code=result.status_code if not successful else None,
                reason=metric_reason,
            )

        if (
            retry_on_error
            and request_exception
            and self._should_retry_on_error(request_exception)
        ):
            return self._retry_make_request(
                url=url,
                data=data,
                params=params,
                extra_headers=extra_headers,
                method=method,
                timeout=timeout,
                retry_on_error=False,
                metric_suffix=metric_suffix,
                **kwargs,
            )

        return result

    def _should_retry_on_error(self, error: Exception) -> bool:
        """
        In case of an error, should the request be retried?

        If make_request() is called with retry_on_error=True, this method should
        be overridden to determine which error responses get retried.
        """
        return False

    def _retry_make_request(self, **kwargs: Any) -> Response:
        """
        Handle retry request.

        If the extending class needs custom retry logic (like updating a header) it
        should override this method, calling this method via super().
        """
        self.log.info(f"{self.service_name} retry sending request", url=kwargs["url"])
        retry_args = kwargs
        retry_args["retry_on_error"] = False
        return self.make_request(
            **retry_args,
        )

    def _increment_metric(
        self,
        metric_suffix: str,
        successful: bool = False,
        http_error_code: int | None = None,
        reason: str | None = None,
    ) -> None:
        if self.metric_prefix is None:
            return

        metric_name = f"{self.metric_prefix}.{metric_suffix}"
        tags = []

        if successful:
            tags.append("success:true")
        else:
            tags.append("success:false")
            if http_error_code is not None:
                tags.append(f"http_error_code:{http_error_code}")
            if reason is not None:
                tags.append(f"reason:{reason}")

        stats.increment(
            metric_name=metric_name,
            pod_name=self.metric_pod_name,  # type: ignore[arg-type] # Argument "pod_name" to "increment" has incompatible type "PodNames | None"; expected "PodNames"
            tags=tags,
        )


class AccessTokenMixin:
    """
    Adds support to BaseHttpClient for retrieving and using an access token.

    Including class must implement _create_access_token()

    This is very generic support and if you need true OAuth 1/2 spec compatability
    (for example, storing and refreshing credentials on behalf of a user) you
    probably want to extend the base class instead.
    """

    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def] #
        super().__init__(*args, **kwargs)
        self.access_token: str | None = None
        self.access_token_expiration: int | None = None

    def get_access_token(self) -> Optional[str]:
        """
        Get an access token, if available.

        If there is no currently-stored token or the token is expired, attempt
        to retrieve a new one.

        :return: access token
        """
        if self.access_token is None or self.access_token_expiration is None:
            self.log.debug(f"{self.service_name} Refresh empty access token")  # type: ignore[attr-defined] #
            self.create_access_token()

        elif self.access_token_expiration < time.time():
            self.log.debug(f"{self.service_name} Refresh expired access token")  # type: ignore[attr-defined] #
            self.create_access_token()

        return self.access_token

    def create_access_token(self) -> None:
        """
        Request and store an access token.
        """
        self.access_token, self.access_token_expiration = self._create_access_token()

    def _create_access_token(self) -> tuple[str | None, int | None]:
        """
        Internal method to request an access token.

        :return: Tuple of access token and access token expiration timestamp
        """
        raise NotImplementedError(
            "Users of AccessTokenMixin must implement a method _create_access_token."
        )
