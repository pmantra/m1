import traceback
from typing import List

from cost_breakdown.models.cost_breakdown import CostBreakdown
from direct_payment.billing import models
from direct_payment.billing.billing_service import BillingService
from direct_payment.billing.lib import legacy_mono
from direct_payment.billing.models import BillStatus, PayorType
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
)
from utils.log import logger
from wallet.models.reimbursement_wallet import ReimbursementWallet

log = logger(__name__)


class ClinicReverseTransferCreationException(Exception):
    pass


class ClinicReverseTransferProcessingException(Exception):
    pass


class BillValidationException(Exception):
    pass


class BillingAdminService:
    """Flask-admin specific code around validation of form data and related. Supports BillView."""

    @staticmethod
    def process_bill_in_admin(svc: BillingService, bill: models.Bill):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if bill.status == models.BillStatus.NEW:
            svc.set_new_bill_to_processing(input_bill=bill)
        elif bill.status == models.BillStatus.FAILED:
            svc.retry_bill(bill=bill, initiated_by=__name__)
        else:
            raise BillValidationException(
                "Bill must be in a NEW or FAILED status to perform this action."
            )

    @staticmethod
    def cancel_bill_in_admin(svc: BillingService, bill: models.Bill) -> models.Bill:
        if (
            bill.status == models.BillStatus.NEW
            or bill.status == models.BillStatus.FAILED
        ):
            return svc.cancel_bill_with_offsetting_refund(
                bill=bill, record_type="admin_billing_workflow", initiated_by="admin"
            )
        else:
            raise BillValidationException(
                "Bill must be in a NEW or FAILED status to cancel."
            )

    @staticmethod
    def create_refund_from_paid_bill(
        svc: BillingService, bill: models.Bill
    ) -> models.Bill:
        if bill.status == models.BillStatus.PAID:
            return svc.create_full_refund_bill_from_potentially_partially_refunded_paid_bill(
                bill=bill, record_type="admin_billing_workflow"
            )
        else:
            raise BillValidationException("Bill must be in a PAID status to cancel.")

    @staticmethod
    def create_clinic_reverse_transfer_bills_for_procedure(
        svc: BillingService, procedure_id: int
    ) -> List[models.Bill]:
        payer_type_to_bills = {}
        for payor_type in list(PayorType):
            bills = svc.get_money_movement_bills_by_procedure_id_payor_type(
                procedure_id=procedure_id, payor_type=payor_type
            )
            for bill in bills:
                if bill.status not in {BillStatus.PAID, BillStatus.REFUNDED}:
                    raise ClinicReverseTransferCreationException(
                        f"Bill {bill.id} is still not paid yet"
                    )
            payer_type_to_bills[payor_type] = bills

        refund_bills = svc.create_full_refund_bills_for_payor(
            procedure_id=procedure_id, payor_type=PayorType.CLINIC
        )
        if not refund_bills:
            raise ClinicReverseTransferCreationException(
                "No clinic reverse transfer bill created, check previous bills"
            )
        svc.session.commit()
        try:
            for bill in refund_bills:
                svc.set_new_bill_to_processing(bill)
                log.info(
                    "Processed reverse transfer bill",
                    treatment_procedure_id=str(procedure_id),
                    bill_id=bill.id,
                )
        except Exception as e:
            raise ClinicReverseTransferProcessingException(
                f"Unable to process clinic reverse transfer bill, exception: {e}, traceback: {traceback.format_exc()}"
            )
        return refund_bills

    @staticmethod
    def update_payment_method_on_bill(svc: BillingService, bill: models.Bill) -> str:
        return svc.update_payment_method_on_bill(
            bill=bill, record_type="admin_billing_workflow"
        )

    def validate_bill_view_form_data(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        payor_type,
        payor_id,
        procedure_id,
        cost_breakdown_id,
        payment_method,
        requested_status,
    ):
        payor = self._validate_bill_payor(payor_type, payor_id)
        procedure = self._validate_procedure_and_payor(payor_type, payor, procedure_id)
        self._validate_cost_breakdown_and_procedure(cost_breakdown_id, procedure)
        self._validate_bill_status(payment_method, requested_status)

    @staticmethod
    def _validate_bill_payor(payor_type, payor_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """validate the payor_id is correct for a given payor_type"""
        payor = legacy_mono.get_payor(payor_type=payor_type, payor_id=payor_id)
        if payor is None:
            raise BillValidationException(
                f"Could not find payor from payor type {payor_type} and id {payor_id}. Is this a valid bill target?"
            )
        if (
            "payments_customer_id" in payor.__table__.columns
            and payor.payments_customer_id is None
        ) or (
            "payments_recipient_id" in payor.__table__.columns
            and payor.payments_recipient_id is None
        ):
            raise BillValidationException(
                f"Could not match payor type {payor_type} and id {payor_id} to a payments_id. Does the payor have payments configured?"
            )
        return payor

    @staticmethod
    def _validate_procedure_and_payor(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        payor_type, payor, procedure_id
    ) -> TreatmentProcedure:
        """validate the procedure id is associated with the payor"""
        procedure = TreatmentProcedure.query.get(procedure_id)
        if procedure is None:
            raise BillValidationException(
                f"Could not find the requested Treatment Procedure {procedure_id}"
            )
        if (
            payor_type == models.PayorType.MEMBER
            and procedure.reimbursement_wallet_id != payor.id
        ) or (
            payor_type == models.PayorType.CLINIC
            and procedure.fertility_clinic_id != payor.id
        ):
            raise BillValidationException(
                f"This Treatment Procedure is not associated with the given payor type {payor_type} and id {payor.id}."
            )
        elif payor_type == models.PayorType.EMPLOYER:
            member_wallet = ReimbursementWallet.query.get(
                procedure.reimbursement_wallet_id
            )
            if member_wallet.reimbursement_organization_settings_id != payor.id:
                raise BillValidationException(
                    f"This Treatment Procedure is not associated with the given payor type {payor_type} and id {payor.id}."
                )
        return procedure

    @staticmethod
    def _validate_cost_breakdown_and_procedure(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cost_breakdown_id, procedure: TreatmentProcedure
    ) -> CostBreakdown:
        """validate the cost breakdown is associated with the procedure"""
        cost_breakdown = CostBreakdown.query.get(cost_breakdown_id)
        if cost_breakdown is None:
            raise BillValidationException(
                f"Could not find the requested Cost Breakdown {cost_breakdown_id}."
            )
        if cost_breakdown.treatment_procedure_uuid != procedure.uuid:
            raise BillValidationException(
                "The given Cost Breakdown is not associated with the given Treatment Procedure."
            )
        return cost_breakdown

    @staticmethod
    def _validate_bill_status(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        payment_method: models.PaymentMethod, requested_status: models.BillStatus
    ):
        """initial status when creating a bill must be new, no matter what. (Respect the state machine.)
        if payment method = gateway, the requested status must also be new.
        if payment method != gateway, any status is allowed."""
        if (
            payment_method == models.PaymentMethod.PAYMENT_GATEWAY
            and requested_status != models.BillStatus.NEW
        ):
            raise BillValidationException(
                "Payment Gateway payment method bills must be created with the NEW status."
            )

        # Avoiding needing the error_type field in the create form.
        if requested_status.value == "FAILED":
            raise BillValidationException(
                "Cannot create FAILED bills via admin. This status can only be applied by the payment gateway."
            )
