from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TypeVar

from authn.domain import service
from authn.util.constants import API_MIGRATION_PREFIX
from common import stats
from common.authn_api.internal_client import AuthnApiInternalClient
from common.constants import current_web_origin
from utils.log import logger

log = logger(__name__)

S = TypeVar("S")
T = TypeVar("T")


class AuthnDataComparer:
    def __init__(
        self,
        sso_service: service.SSOService,
        authn_service: service.AuthenticationService,
        user_service: service.UserService,
        authnapi_client: AuthnApiInternalClient,
    ) -> None:
        self.today12am: datetime = self._get_daily_12am()
        self.yesterday12am: datetime = self._get_daily_12am() - timedelta(days=1)
        self.sso_service: service.SSOService = sso_service or service.SSOService()
        self.authn_service: service.AuthenticationService = (
            authn_service or service.AuthenticationService()
        )
        self.user_service: service.UserService = user_service or service.UserService()
        self.authnapi_client = authnapi_client or AuthnApiInternalClient(
            base_url=f"{current_web_origin()}/api/v1/-/oauth/"
        )

    def check_user_external_identity(self) -> bool:
        log.info("Start checking the user external identity table.")
        table_name = "user_external_identity"
        # Get mono database data
        data_from_mono = self.sso_service.get_identities_by_time_range(
            end=self.today12am, start=self.yesterday12am
        )
        log.info(
            f"Get {len(data_from_mono) if data_from_mono else 0} rows from {table_name} in the mono DB"
        )
        # Call the authn-api endpoint to get the data
        data_from_authnapi = (
            self.authnapi_client.get_user_external_identity_by_time_range(
                start=self.yesterday12am, end=self.today12am
            ).user_external_identities
        )
        if not data_from_authnapi:
            log.error("None returned from the authn-api get data")
            self._send_metrics(table_name=table_name, status="error")
        log.info(
            f"Get {len(data_from_authnapi)} rows from {table_name} in the authnapi DB"
        )
        # Compare the data with the data fetched from the mono DB
        if self.compare_data_diff(data_from_mono, data_from_authnapi):
            log.warning(
                f"The result of daily modification from {table_name} in the authnapi and mono is different"
            )
            self._send_metrics(table_name=table_name, status="error")
            return False
        else:
            self._send_metrics(table_name=table_name, status="success")
            return True

    def check_identity_provider(self) -> bool:
        log.info("Start checking the identity provider table.")
        table_name = "identity_provider"
        # Get mono database data
        data_from_mono = self.sso_service.get_idps_by_time_range(
            end=self.today12am, start=self.yesterday12am
        )
        log.info(
            f"Get {len(data_from_mono) if data_from_mono else 0} rows in {table_name} from the mono DB"
        )
        # Call the authn-api endpoint to get the data
        data_from_authnapi = self.authnapi_client.get_identity_provider_by_time_range(
            start=self.yesterday12am, end=self.today12am
        ).identity_providers
        if not data_from_authnapi:
            log.error("None returned from the authn-api get data")
            self._send_metrics(table_name=table_name, status="error")
        log.info(
            f"Get {len(data_from_authnapi)} rows in {table_name} from the authnapi DB"
        )
        # Compare the data with the data fetched from the mono DB
        if self.compare_data_diff(data_from_mono, data_from_authnapi):
            log.warning(
                f"The result of daily modification from {table_name} in the authnapi and mono is different"
            )
            self._send_metrics(table_name=table_name, status="error")
            return False
        else:
            self._send_metrics(table_name=table_name, status="success")
            return True

    def check_user(self) -> bool:
        log.info("Start checking the user table.")
        table_name = "user"
        # Get mono database data
        data_from_mono = self.user_service.get_all_by_time_range(
            end=self.today12am, start=self.yesterday12am
        )
        log.info(
            f"Get {len(data_from_mono) if data_from_mono else 0} rows in {table_name} from the authnapi DB"
        )
        # Call the authn-api endpoint to get the data
        data_from_authnapi = self.authnapi_client.get_user_by_time_range(
            start=self.yesterday12am, end=self.today12am
        ).users
        if not data_from_authnapi:
            log.error("None returned from the authn-api get data")
            self._send_metrics(table_name=table_name, status="error")
        log.info(
            f"Get {len(data_from_authnapi)} rows in {table_name} from the authnapi DB"
        )
        # Compare the data with the data fetched from the mono DB
        if self.compare_data_diff(data_from_mono, data_from_authnapi):
            log.warning(
                f"The result of daily modification from {table_name} in the authnapi and mono is different"
            )
            self._send_metrics(table_name=table_name, status="error")
            return False
        else:
            self._send_metrics(table_name=table_name, status="success")
            return True

    def check_user_auth(self) -> bool:
        log.info("Start checking the user auth table")
        table_name = "user_auth"
        # Get mono database data
        data_from_mono = self.authn_service.get_user_auth_by_time_range(
            end=self.today12am, start=self.yesterday12am
        )
        log.info(
            f"Get {len(data_from_mono) if data_from_mono else 0} rows in {table_name} from the authnapi DB"
        )
        # Call the authn-api endpoint to get the data
        data_from_authnapi = self.authnapi_client.get_user_auth_by_time_range(
            start=self.yesterday12am, end=self.today12am
        ).user_auths
        if not data_from_authnapi:
            log.error("None returned from the authn-api get data")
            self._send_metrics(table_name=table_name, status="error")
        log.info(
            f"Get {len(data_from_authnapi)} rows in {table_name} from the authnapi DB"
        )
        # Compare the data with the data fetched from the mono DB
        if self.compare_data_diff(data_from_mono, data_from_authnapi):
            log.warning(
                f"The result of daily modification from {table_name} in the authnapi and mono is different"
            )
            self._send_metrics(table_name=table_name, status="error")
            return False
        else:
            self._send_metrics(table_name=table_name, status="success")
            return True

    def check_org_auth(self) -> bool:
        log.info("Start checking the identity provider table.")
        table_name = "organization_auth"
        # Get mono database data
        data_from_mono = self.authn_service.get_org_auth_by_time_range(
            end=self.today12am, start=self.yesterday12am
        )
        log.info(
            f"Get {len(data_from_mono) if data_from_mono else 0} rows in {table_name} from the mono DB"
        )
        # Call the authn-api endpoint to get the data
        data_from_authnapi = self.authnapi_client.get_org_auth_by_time_range(
            start=self.yesterday12am, end=self.today12am
        ).org_auths
        if not data_from_authnapi:
            log.error("None returned from the authn-api get data")
            self._send_metrics(table_name=table_name, status="error")
        log.info(
            f"Get {len(data_from_authnapi)} rows in {table_name} from the authnapi DB"
        )
        # Compare the data with the data fetched from the mono DB
        if self.compare_data_diff(data_from_mono, data_from_authnapi):
            log.warning(
                f"The result of daily modification from {table_name} in the authnapi and mono is different"
            )
            self._send_metrics(table_name=table_name, status="error")
            return False
        else:
            self._send_metrics(table_name=table_name, status="success")
            return True

    def _get_daily_12am(self) -> datetime:
        now = datetime.now(timezone.utc)
        return now.replace(
            hour=0,
            minute=0,
            second=0,
        )

    def _send_metrics(self, table_name: str, status: str) -> None:
        stats.increment(
            metric_name=f"{API_MIGRATION_PREFIX}.{table_name}",
            pod_name=stats.PodNames.CORE_SERVICES,
            tags=[f"status:{status}"],
        )

    def compare_data_diff(self, mono_data: list[S], authnapi_data: list[T]) -> bool:
        mono_data = mono_data or []
        authnapi_data = authnapi_data or []
        if len(mono_data) != len(authnapi_data):
            return True
        else:
            # The data in the list should sort by the modify time
            for i in range(0, len(mono_data)):
                for field in vars(authnapi_data[i]):
                    if getattr(mono_data[i], field, None) != getattr(
                        authnapi_data[i], field
                    ):
                        return True
        return False
