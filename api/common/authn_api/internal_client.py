from __future__ import annotations

import traceback
from datetime import datetime
from typing import Optional

from common.authn_api.models import (
    GetIdentityProviderAllResponse,
    GetOrgAuthAllResponse,
    GetUserAllResponse,
    GetUserAuthAllResponse,
    GetUserExternalIdentityAllResponse,
)
from common.base_triforce_client import BaseTriforceClient
from common.constants import current_web_origin
from utils.log import logger

log = logger(__name__)

# Headers
CONTENT_TYPE = "application/json"

SERVICE_NAME = "authn-api"


class AuthnApiInternalClient(BaseTriforceClient):
    def __init__(
        self,
        *,
        base_url: str,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        if not base_url:
            base_url = f"{current_web_origin()}/api/v1/-/oauth/"

        # For internal request, it should not need the maven user id in the headers because they are in the private vpc
        super().__init__(
            base_url=base_url,
            headers=headers,
            service_name=SERVICE_NAME,
            internal=True,
        )

    def get_user_by_time_range(
        self, start: datetime, end: datetime
    ) -> GetUserAllResponse:
        route = "/api/v1/-/oauth/users/get_users_by_time"
        data = {"start_time": start, "end_time": end}
        try:
            response = self.make_service_request(route, method="GET", data=data)
            log.info(
                "Mono to Authn-api GET",
                context={
                    "base_url": self.base_url,
                    "route": route,
                    "response": response.text,
                    "status_code": response.status_code,
                },
            )
            response.raise_for_status()
            return GetUserAllResponse.from_dict(response.json())
        except Exception as e:
            log.error(
                "Exception occurred in Health Profile Service API call",
                error=str(e),
                exc=traceback.format_exc(),
                context={
                    "base_url": self.base_url,
                    "route": route,
                },
            )
            raise e

    def get_user_auth_by_time_range(
        self, start: datetime, end: datetime
    ) -> GetUserAuthAllResponse:
        route = "/api/v1/-/oauth/users/get_user_auth_by_time"
        data = {"start_time": start, "end_time": end}
        try:
            response = self.make_service_request(route, method="GET", data=data)
            log.info(
                "Mono to Authn-api GET",
                context={
                    "base_url": self.base_url,
                    "route": route,
                    "response": response.text,
                    "status_code": response.status_code,
                },
            )
            response.raise_for_status()
            return GetUserAuthAllResponse.from_dict(response.json())
        except Exception as e:
            log.error(
                "Exception occurred in Health Profile Service API call",
                error=str(e),
                exc=traceback.format_exc(),
                context={
                    "base_url": self.base_url,
                    "route": route,
                },
            )
            raise e

    def get_org_auth_by_time_range(
        self, start: datetime, end: datetime
    ) -> GetOrgAuthAllResponse:
        route = "/api/v1/-/oauth/orgs/get_org_auth_by_time"
        data = {"start_time": start, "end_time": end}
        try:
            response = self.make_service_request(route, method="GET", data=data)
            log.info(
                "Mono to Authn-api GET",
                context={
                    "base_url": self.base_url,
                    "route": route,
                    "response": response.text,
                    "status_code": response.status_code,
                },
            )
            response.raise_for_status()
            return GetOrgAuthAllResponse.from_dict(response.json())
        except Exception as e:
            log.error(
                "Exception occurred in Health Profile Service API call",
                error=str(e),
                exc=traceback.format_exc(),
                context={
                    "base_url": self.base_url,
                    "route": route,
                },
            )
            raise e

    def get_identity_provider_by_time_range(
        self, start: datetime, end: datetime
    ) -> GetIdentityProviderAllResponse:
        route = "/api/v1/-/oauth/saml/get_identity_provider_by_time"
        data = {"start_time": start, "end_time": end}
        try:
            response = self.make_service_request(route, method="GET", data=data)
            log.info(
                "Mono to Authn-api GET",
                context={
                    "base_url": self.base_url,
                    "route": route,
                    "response": response.text,
                    "status_code": response.status_code,
                },
            )
            response.raise_for_status()
            return GetIdentityProviderAllResponse.from_dict(response.json())
        except Exception as e:
            log.error(
                "Exception occurred in Health Profile Service API call",
                error=str(e),
                exc=traceback.format_exc(),
                context={
                    "base_url": self.base_url,
                    "route": route,
                },
            )
            raise e

    def get_user_external_identity_by_time_range(
        self, start: datetime, end: datetime
    ) -> GetUserExternalIdentityAllResponse:
        route = "/api/v1/-/oauth/users/get_user_external_identity_by_time"
        data = {"start_time": start, "end_time": end}
        try:
            response = self.make_service_request(route, method="GET", data=data)
            log.info(
                "Mono to Authn-api GET",
                context={
                    "base_url": self.base_url,
                    "route": route,
                    "response": response.text,
                    "status_code": response.status_code,
                },
            )
            response.raise_for_status()
            return GetUserExternalIdentityAllResponse.from_dict(response.json())
        except Exception as e:
            log.error(
                "Exception occurred in Health Profile Service API call",
                error=str(e),
                exc=traceback.format_exc(),
                context={
                    "base_url": self.base_url,
                    "route": route,
                },
            )
            raise e

    def trigger_data_sync(self, table_name: str, dryrun: bool = True) -> None:
        route = "/v1/-/authn-api/data/sync-data"
        data = {"name": table_name, "dryrun": dryrun}
        try:
            response = self.make_service_request(route, method="POST", data=data)
            log.info(
                "Mono to Authn-api GET",
                context={
                    "base_url": self.base_url,
                    "route": route,
                    "response": response.text,
                    "status_code": response.status_code,
                },
            )
            if response.status_code != 204:
                log.error("Trigger data sync failed")
            response.raise_for_status()
        except Exception as e:
            log.error(
                "Exception occurred in Health Profile Service API call",
                error=str(e),
                exc=traceback.format_exc(),
                context={
                    "base_url": self.base_url,
                    "route": route,
                },
            )
            raise e
