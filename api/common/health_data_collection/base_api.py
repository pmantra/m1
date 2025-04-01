import json
import os

import requests
from flask import Response
from requests import HTTPError, Timeout

from common.health_data_collection.constants import HDCconfig
from utils.log import logger

log = logger(__name__)

# Headers
CONTENT_TYPE = "application/json"


def make_hdc_request(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    url,
    data=None,
    params=None,
    extra_headers=None,
    method="GET",
    timeout_in_sec=30,
    user_internal_gateway=False,
) -> Response:
    if user_internal_gateway:
        prefix = os.environ.get("INTERNAL_GATEWAY_URL", None)
        if prefix is None:
            log.error(
                "Cannot find internal gateway URL when using internal gateway in make_hdc_request. Fall back to the old url."
            )
            complete_url = f"{HDCconfig.HDC_API_URL}{url}"
        else:
            complete_url = f"{prefix}/api/hdc/v1{url}"
        log.info(
            f"Complete URL in make_hdc_request when using internal gateway is {complete_url}"
        )
    else:
        complete_url = f"{HDCconfig.HDC_API_URL}{url}"

    headers = {"Content-type": CONTENT_TYPE}

    if extra_headers:
        headers.update(extra_headers)

    try:
        response = requests.request(
            method=method,
            url=complete_url,
            data=json.dumps(data) or {},
            params=params or {},
            headers=headers,
            timeout=timeout_in_sec,
        )
        response.raise_for_status()
        return response  # type: ignore[return-value] # Incompatible return value type (got "requests.models.Response", expected "Optional[flask.wrappers.Response]")
    except HTTPError as e:
        log.error(
            "HDC API request failed with an HTTP status message.",
            url=complete_url,
            params=params,
            exception=e,
            response=e.response.json(),
        )
        return Response(str(e), status=e.response.status_code)
    except Timeout as e:
        log.error(
            "HDC API request failed due to a connection timeout.",
            url=complete_url,
            params=params,
            exception=e,
        )
        return Response(str(e), status=499)
    except Exception as e:
        log.error("HDC request failed", url=complete_url, params=params, exception=e)
        return Response(str(e), status=400)
