from __future__ import annotations

from flask_restful import abort, request
from maven.feature_flags import bool_variation

from common.services.api import AuthenticatedResource
from direct_payment.billing.http.common import BillResourceMixin
from direct_payment.billing.models import BillStatus
from direct_payment.payments import models
from direct_payment.payments.constants import ALERT_LABEL_TEXT, DetailLabel
from direct_payment.payments.payments_helper import PaymentsHelper
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def enable_refund_refinement_phase_2() -> bool:
    return bool_variation(
        "refund-refinement-phase-2",
        default=False,
    )


class PaymentDetailResource(AuthenticatedResource, BillResourceMixin):
    def get(self, bill_uuid: str) -> dict:
        pay_helper = PaymentsHelper(db.session)
        bill = pay_helper.billing_service.get_bill_by_uuid(bill_uuid)
        if not bill:
            abort(404, message="Bill not found.")
        self._user_has_access_to_bill_or_403(
            accessing_user=self.user,
            bill=bill,  # type: ignore[arg-type] # Argument "bill" to "_user_has_access_to_bill_or_403" of "BillResourceMixin" has incompatible type "Optional[Bill]"; expected "Bill"
            session=db.session,
        )

        procedure = pay_helper.treatment_procedure_repo.read(
            treatment_procedure_id=bill.procedure_id  # type: ignore[union-attr] # Item "None" of "Optional[Bill]" has no attribute "procedure_id"
        )
        (
            cost_breakdown,
            past_cost_breakdown,
        ) = pay_helper.return_relevant_cost_breakdowns(
            procedure_uuid=procedure.uuid,
            expected_cost_breakdown_id=bill.cost_breakdown_id,  # type: ignore[union-attr] # Item "None" of "Optional[Bill]" has no attribute "cost_breakdown_id"
        )
        if not procedure or not cost_breakdown:
            log.error(
                "Missing supporting information for requested bill payment detail",
                procedure_id=bill.procedure_id,  # type: ignore[union-attr] # Item "None" of "Optional[Bill]" has no attribute "procedure_id"
                procedure=procedure,
                cost_breakdown_id=bill.cost_breakdown_id,  # type: ignore[union-attr] # Item "None" of "Optional[Bill]" has no attribute "cost_breakdown_id"
                cost_breakdown=cost_breakdown,
            )
            abort(400, message="Payment detail could not be constructed.")
        clinic_loc_name, clinic_name = pay_helper.return_relevant_clinic_names(
            fertility_clinic_location_id=procedure.fertility_clinic_location_id
        )
        is_credit_based_wallet = pay_helper.return_credit_use_bool_for_procedure(
            procedure
        )
        past_bill_fees = pay_helper.billing_service.calculate_past_bill_fees_for_procedure(
            current_bill=bill  # type: ignore[arg-type] # Argument "current_bill" to "calculate_past_bill_fees_for_procedure" of "BillingService" has incompatible type "Optional[Bill]"; expected "Bill"
        )

        detail = pay_helper.create_payment_detail(
            bill=bill,  # type: ignore[arg-type] # Argument "bill" to "create_payment_detail" of "PaymentsHelper" has incompatible type "Optional[Bill]"; expected "Bill"
            past_bill_fees=past_bill_fees,
            procedure=procedure,
            cost_breakdown=cost_breakdown,  # type: ignore[arg-type] # Argument "cost_breakdown" to "create_payment_detail" of "PaymentsHelper" has incompatible type "Optional[CostBreakdown]"; expected "CostBreakdown"
            past_cost_breakdown=past_cost_breakdown,
            clinic_loc_name=clinic_loc_name,
            clinic_name=clinic_name,
            is_credit_based_wallet=is_credit_based_wallet,
            show_voided_payment_status=pay_helper.show_payment_status_voided(
                request_headers=request.headers,  # type: ignore[arg-type] # Argument "request_header" to "show_payment_status_voided" of "PaymentsHelper" has incompatible type "EnvironHeaders"; expected "dict[Any, Any]"
                use_refunds_refinement=enable_refund_refinement_phase_2(),
            ),
        )
        return self._deserialize(detail)

    def _deserialize(self, detail: models.PaymentDetail) -> dict:
        # "Maven Benefit" and "Medical Plan" are the two current labels
        # Medical Plan is always 0 for now and causes confusion with the
        # users, so we are filtering it out for now.
        non_medical_plan_breakdowns = [
            breakdown
            for breakdown in detail.benefit_breakdown
            if breakdown.label != DetailLabel.MEDICAL_PLAN.value
        ]
        response = {
            "covered_amount_total": sum(
                breakdown.cost for breakdown in non_medical_plan_breakdowns
            ),
            "label": detail.label,
            "treatment_procedure_id": detail.treatment_procedure_id,
            "treatment_procedure_clinic": detail.treatment_procedure_clinic,
            "treatment_procedure_location": detail.treatment_procedure_location,
            "treatment_procedure_started_at": (
                detail.treatment_procedure_started_at.isoformat()
                if detail.treatment_procedure_started_at
                else None
            ),
            "payment_status": detail.payment_status,
            "member_responsibility": detail.member_responsibility,
            "total_cost": detail.total_cost,
            "cost_responsibility_type": detail.cost_responsibility_type,
            "error_type": detail.error_type,
            "responsibility_breakdown": [
                {
                    "label": breakdown.label,
                    "cost": breakdown.cost,
                    "original": breakdown.original,
                }
                for breakdown in detail.responsibility_breakdown
            ],
            "benefit_breakdown": [
                {
                    "label": breakdown.label,
                    "cost": breakdown.cost,
                    "original": breakdown.original,
                }
                for breakdown in non_medical_plan_breakdowns
            ],
            "credits_used": detail.credits_used,
            "created_at": detail.created_at.isoformat(),
            "due_at": detail.due_at.isoformat() if detail.due_at else None,
            "completed_at": (
                detail.completed_at.isoformat() if detail.completed_at else None
            ),
        }
        if enable_refund_refinement_phase_2():
            # Only show the alert label when the procedure is cancelled
            if detail.procedure_status == BillStatus.CANCELLED.value:
                response["alert_label"] = ALERT_LABEL_TEXT
            else:
                response["alert_label"] = None

        return response
