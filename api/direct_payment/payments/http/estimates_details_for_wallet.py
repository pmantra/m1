from __future__ import annotations

import traceback

from flask_restful import abort

from common.services.api import AuthenticatedResource
from direct_payment.payments import models
from direct_payment.payments.estimates_helper import EstimatesHelper
from direct_payment.payments.http.estimates_detail import EstimateDetailResource
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class EstimateDetailsForWalletResource(AuthenticatedResource):
    def get(self, wallet_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        estimates_helper = EstimatesHelper(db.session)
        estimates = []
        try:
            estimates = estimates_helper.get_estimates_by_wallet(wallet_id=wallet_id)
            if not estimates:
                return {"estimates_details": []}
        except Exception as e:
            log.error(
                "Exception constructing estimate details",
                exception=traceback.format_exception_only(type(e), e),
            )
            abort(400, message="Estimate details could not be constructed.")
        return self._deserialize(estimates)

    @staticmethod
    def _deserialize(details: list[models.EstimateDetail]) -> dict:
        return {
            "estimates_details": [
                EstimateDetailResource.deserialize(detail=detail) for detail in details
            ]
        }
