from __future__ import annotations

from typing import Mapping, Optional

from requests import Response

from common.base_triforce_client import BaseTriforceClient
from common.wallet_historical_spend import models
from utils.log import logger
from wallet.constants import WHS_LEDGER_SEARCH_TIMEOUT_SECONDS

log = logger(__name__)

SERVICE_NAME = "wallet-historical-spend"


class WalletHistoricalSpendClient(BaseTriforceClient):
    def __init__(
        self,
        *,
        base_url: str,
        headers: Optional[dict[str, str]] = None,
        internal: bool = False,
    ) -> None:
        super().__init__(
            base_url=base_url,
            headers=headers,
            service_name=SERVICE_NAME,
            internal=internal,
            log=log,
        )

    def get_historic_spend_records(
        self,
        request_body: dict,
        headers: Optional[Mapping[str, str]] = None,
        request_limit: Optional[int] = 1000,
    ) -> list[models.LedgerEntry]:
        all_ledger_entries = []
        limit = request_limit
        while True:
            response = self.make_service_request(
                "ledgers/search",
                data=request_body,
                method="POST",
                extra_headers=headers,
                timeout=WHS_LEDGER_SEARCH_TIMEOUT_SECONDS,
            )
            if response.status_code != 200:
                log.error("Failed to retrieve LedgerEntry object", response=response)
                raise WalletHistoricalSpendClientException(
                    message=response.text, code=response.status_code, response=response
                )
            page = response.json()
            ledgers_page = page["ledgers"]
            all_ledger_entries.extend(
                models.LedgerEntry.create_ledger_entries_from_dict(ledgers_page)
            )
            request_body = page["next"]
            if len(ledgers_page) != limit:
                break

        return all_ledger_entries


class WalletHistoricalSpendClientException(Exception):
    __slots__ = ("code", "response", "message")

    def __init__(self, message: str, code: int, response: Optional[Response]):
        super().__init__(message)
        self.message = message
        self.code = code
        self.response = response
