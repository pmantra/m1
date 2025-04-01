from __future__ import annotations

import json
import urllib.parse
from typing import Any, Literal, Mapping

import flask
from requests import Response
from structlog import BoundLoggerBase

from common.base_http_client import BaseHttpClient
from utils.log import logger

# Headers
CONTENT_TYPE = "application/json"


class BaseTriforceClient(BaseHttpClient):
    """
    Base class for interacting with TriForce services.

    Adds support for internal routing and authentication.

    See [BaseHttpClient] for additional features.

    Headers passed to the constructor will be sent on all requests. When calling
    make_service_request() the client will automatically include headers from the
    current request, plus any headers passed as a parameter to the call, but only
    if they match the include_headers list. This list only includes
    authentication-related headers.
    """

    def __init__(
        self,
        *,
        base_url: str,
        service_name: str,
        headers: Mapping[str, str] | None,
        content_type: str = CONTENT_TYPE,
        internal: bool = False,
        log: BoundLoggerBase | None = None,
    ) -> None:
        """
        :param base_url: fully-qualified URL representing the API's root
        :param service_name: used for logging
        :param headers: data to be sent as HTTP headers on all requests
        :param content_type: default content type for all requests
        :param internal: flag to enable internal routing
        :param log: logger instance
        """
        log = log or logger(__name__)

        if internal:
            log.warning(
                f"Client indicated internal routing be used for {service_name!r}"
            )
            split = urllib.parse.urlsplit(base_url)
            if split.scheme != "http":
                split = split._replace(scheme="http", netloc=split.hostname)  # type: ignore[arg-type] # Argument "netloc" to "_replace" of "_SplitResultBase" has incompatible type "Optional[str]"; expected "str"
                base_url = urllib.parse.urlunsplit(split)

        super().__init__(
            base_url=base_url,
            service_name=service_name,
            headers=headers,
            content_type=content_type,
            log=log,
        )

    def _fetch_headers_from_request(self) -> dict[str, str]:
        try:
            return dict(flask.request.headers)
        except RuntimeError as e:
            self.log.debug(f"Failed to fetch headers from current request: {e}")
            return {}

    def _incorporate_request_headers(self, **headers: str) -> Mapping[str, str]:
        base_headers = {**self._fetch_headers_from_request(), **headers}
        filtered = {
            h: base_headers[h] for h in base_headers.keys() & self.include_headers
        }
        return filtered

    include_headers = frozenset(
        (  # note: flask.request.headers converts header keys to camel-case
            "Cookie",
            "Referer",
            "Authorization",
            "X-Maven-User-Id",
            "X-Maven-User-Identities",
        )
    )

    def make_service_request(
        self,
        url: str,
        data: Any = None,
        params: dict[str, Any] | None = None,
        extra_headers: Mapping[str, str] | None = None,
        method: Literal["GET", "PUT", "POST", "DELETE", "PATCH"] = "GET",
        timeout: int = 10,
    ) -> Response:
        """
        Make an HTTP request to the service

        :param url: path to be appended to the API root for the request
        :param data: data to be sent as a JSON object in the body of the request
        :param params: data to be sent as URL parameters in the query string of the request
        :param extra_headers: data to be sent as HTTP headers on the request (subject to filtering)
        :param method: HTTP method for the request
        :param timeout: timeout in seconds for the request
        """

        extra_headers = extra_headers or {}
        extra_headers = self._incorporate_request_headers(**extra_headers)
        data = json.dumps(data) if data else None

        return self.make_request(
            url=url,
            data=data,
            params=params,
            extra_headers=extra_headers,
            method=method,
            timeout=timeout,
            verify=False,
        )
