from __future__ import annotations

from typing import Any

from common.services.api import PermissionedUserResource
from utils.log import logger
from wallet.services.reimbursement_request import ReimbursementRequestService

log = logger(__name__)


class ReimbursementWalletAvailableCurrenciesResource(PermissionedUserResource):
    def get(self) -> tuple[Any, int]:
        try:
            rrs = ReimbursementRequestService()
            available_currencies: list[dict] = rrs.get_available_currencies()
        except Exception as e:
            msg = "Exception encountered while fetching available currencies"
            log.exception(msg, exc=e)
            return msg, 500
        else:
            return available_currencies, 200
