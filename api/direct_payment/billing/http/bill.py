import flask
from flask import request
from flask_restful import abort

from common.payments_gateway import PaymentsGatewayException
from common.services.api import AuthenticatedResource
from direct_payment.billing import errors, models
from direct_payment.billing.billing_service import BillingService
from direct_payment.billing.http.common import BillResourceMixin
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class BillEntityResource(AuthenticatedResource, BillResourceMixin):
    @staticmethod
    def _serialize(bill: models.Bill):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        def format_date_if_not_none(value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            return value.isoformat() if value else None

        return {
            "uuid": str(bill.uuid),
            "amount": bill.amount,
            "last_calculated_fee": bill.last_calculated_fee,
            "label": bill.label,
            "payor_id": bill.payor_id,
            "payor_type": bill.payor_type.value,
            "treatment_procedure_id": bill.procedure_id,
            "cost_breakdown_id": bill.cost_breakdown_id,
            "status": bill.status.value,
            "error_type": bill.error_type,
            "reimbursement_request_created_at": format_date_if_not_none(
                bill.reimbursement_request_created_at
            ),
            "created_at": format_date_if_not_none(bill.created_at),
            "modified_at": format_date_if_not_none(bill.modified_at),
            "processing_at": format_date_if_not_none(bill.processing_at),
            "paid_at": format_date_if_not_none(bill.paid_at),
            "refunded_at": format_date_if_not_none(bill.refunded_at),
            "failed_at": format_date_if_not_none(bill.failed_at),
            "cancelled_at": format_date_if_not_none(bill.cancelled_at),
        }

    def put(self, bill_uuid: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        billing_service = BillingService(session=db.session)
        bill = billing_service.get_bill_by_uuid(bill_uuid)
        if not bill:
            abort(404, message="Bill not found.")
        self._user_has_access_to_bill_or_403(
            accessing_user=self.user,
            bill=bill,  # type: ignore[arg-type] # Argument "bill" to "_user_has_access_to_bill_or_403" of "BillResourceMixin" has incompatible type "Optional[Bill]"; expected "Bill"
            session=billing_service.bill_repo.session,
        )

        # TODO: replace with OpenAPI Core validation
        # Spec should enforce that the new status will always be PROCESSING.
        # Logic will need to change if we use this for anything other than retries.
        request_json = flask.request.get_json(force=True)
        if request_json != {"status": models.BillStatus.PROCESSING.value}:
            abort(422, message="Invalid status change requested.")

        try:
            updated_bill = billing_service.retry_bill(
                bill=bill, initiated_by=__name__, headers=request.headers  # type: ignore[arg-type] # Argument "bill" to "retry_bill" of "BillingService" has incompatible type "Optional[Bill]"; expected "Bill" #type: ignore[arg-type] # Argument "headers" to "retry_bill" of "BillingService" has incompatible type "EnvironHeaders"; expected "Optional[Mapping[str, str]]"
            )
            return flask.jsonify(self._serialize(bill=updated_bill))
        except errors.MissingPaymentGatewayInformation:
            abort(400, message="User not configured for direct payments.")
        except errors.InvalidBillStatusChange as e:
            log.error(
                "Invalid bill status change requested.",
                exception=e,
                initial_status=bill.status,  # type: ignore[union-attr] # Item "None" of "Optional[Bill]" has no attribute "status"
            )
            abort(422, message="Invalid status change requested.")
        except PaymentsGatewayException as e:
            log.error("Payment Gateway Exception raised to the user.", exception=e)
            abort(e.code, message=e.message)
