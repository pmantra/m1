import json
import os
from typing import Any, Dict, Optional, Union

import requests
from maven import feature_flags
from requests.adapters import HTTPAdapter, Retry

from utils.log import logger

log = logger(__name__)


class CarePlanServiceRequest:
    @staticmethod
    def base_url() -> str:
        return os.environ.get("CPS_BASE_URL")  # type: ignore[return-value] # Incompatible return value type (got "Optional[str]", expected "str")

    _default_retry = Retry(total=3, backoff_factor=1)

    @staticmethod
    def session(retry: Union[Retry, int, None] = _default_retry) -> requests.Session:
        ses = requests.Session()
        ses.mount("https://", HTTPAdapter(max_retries=retry))
        return ses

    @staticmethod
    def member_headers(member_id: int) -> Dict[str, Any]:
        """
        adds member specific headers to CPS request
        """
        headers = {
            "Content-type": "application/json",
            "X-Maven-User-ID": str(member_id),
            "X-Maven-User-Identities": '["member"]',
        }
        return headers

    @staticmethod
    def internal_api_headers() -> Dict[str, Any]:
        headers = {
            "Content-type": "application/json",
            "X-Maven-User-Identities": '["maven_service"]',
        }
        return headers

    @staticmethod
    def post(
        member_id: Optional[int],
        route: str,
        body: Any,
        timeout_in_sec: Optional[int] = None,
    ) -> requests.Response:
        sess = CarePlanServiceRequest.session()
        if member_id is not None:
            headers = CarePlanServiceRequest.member_headers(member_id)
        else:
            headers = CarePlanServiceRequest.internal_api_headers()

        if CarePlanServiceRequest._should_use_internal_gateway():
            internal_gateway_url = os.environ.get("INTERNAL_GATEWAY_URL", None)
            if internal_gateway_url is None:
                log.warn(
                    "Cannot find internal gateway URL when using internal gateway in CarePlanServiceRequest.post. Fall back to the old url."
                )
                url = f"{CarePlanServiceRequest.base_url()}{route}"
            else:
                url = f"{internal_gateway_url}/api/cps/{route}"
            log.info(
                "Complete URL in CarePlanServiceRequest.post when using internal gateway",
                url=url,
            )
        else:
            url = f"{CarePlanServiceRequest.base_url()}{route}"
            log.info(
                "Complete URL in CarePlanServiceRequest.post when not using internal gateway",
                url=url,
            )

        body = json.dumps(body) or {}
        response = sess.request(
            headers=headers,
            method="POST",
            url=url,
            data=body,
            timeout=timeout_in_sec,
        )
        response.raise_for_status()
        return response

    @staticmethod
    def _should_use_internal_gateway() -> bool:
        try:
            return feature_flags.bool_variation(
                "use-internal-gateway-for-cps",
                default=False,
            )
        except Exception:
            feature_flags.initialize()
            return feature_flags.bool_variation(
                "use-internal-gateway-for-cps",
                default=False,
            )
