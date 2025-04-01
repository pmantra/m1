from __future__ import annotations

import traceback

from flask_restful import abort
from werkzeug.exceptions import HTTPException

from common.services.api import AuthenticatedResource
from direct_payment.payments import models
from direct_payment.payments.estimates_helper import EstimatesHelper
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class EstimateDetailResource(AuthenticatedResource):
    def get(self, bill_uuid: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        estimates_helper = EstimatesHelper(db.session)
        try:
            estimate = estimates_helper.get_estimate_detail_by_uuid(bill_uuid=bill_uuid)
            if not estimate:
                log.error("Estimate not found.")
                abort(404, message="Estimate not found.")
            return self.deserialize(estimate)
        except HTTPException:
            abort(404, message="Estimate not found.")
        except Exception as e:
            log.error(
                "Exception constructing estimate detail",
                exception=traceback.format_exception_only(type(e), e),
            )
            abort(400, message="Estimate detail could not be constructed.")

    @staticmethod
    def deserialize(detail: models.EstimateDetail) -> dict:
        items_bd = [
            {"label": rb.label, "cost": rb.cost}
            for rb in detail.responsibility_breakdown.items
        ]
        return {
            "procedure_id": detail.procedure_id,
            "bill_uuid": detail.bill_uuid,
            "procedure_title": detail.procedure_title,
            "clinic": detail.clinic,
            "clinic_location": detail.clinic_location,
            "estimate_creation_date": detail.estimate_creation_date,
            "estimate_creation_date_raw": detail.estimate_creation_date_raw.isoformat(),
            "estimated_member_responsibility": detail.estimated_member_responsibility,
            "estimated_total_cost": detail.estimated_total_cost,
            "estimated_boilerplate": detail.estimated_boilerplate,
            "credits_used": detail.credits_used,
            "responsibility_breakdown": {
                "title": detail.responsibility_breakdown.title,
                "total_cost": detail.responsibility_breakdown.total_cost,
                "items": items_bd,
            },
            "covered_breakdown": {
                "title": detail.covered_breakdown.title,
                "total_cost": detail.covered_breakdown.total_cost,
                "items": [
                    {
                        "label": detail.covered_breakdown.items[0].label,
                        "cost": detail.covered_breakdown.items[0].cost,
                    },
                ],
            },
        }
