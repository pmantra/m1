from typing import Optional

import flask_login as login
from flask import flash

from authn.resources.admin import BaseClassicalMappedView
from direct_payment.invoicing.direct_payment_invoicing_client import (
    DirectPaymentInvoicingClient,
)
from direct_payment.invoicing.models import DirectPaymentInvoice, Process
from direct_payment.invoicing.repository.direct_payment_invoice import (
    DirectPaymentInvoiceRepository,
)
from utils.log import logger

log = logger(__name__)


class DirectPaymentInvoiceView(BaseClassicalMappedView):
    def __init__(self, model, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().__init__(model, *args, **kwargs)

        self.direct_payment_invoicing_client = DirectPaymentInvoicingClient()

    read_permission = "read:direct-payment-invoices"
    create_permission = "create:direct-payment-invoices"
    delete_permission = "delete:direct-payment-invoices"

    list_template = "list.html"

    repo = DirectPaymentInvoiceRepository  # type: ignore[assignment] # Incompatible types in assignment (expression has type "type[DirectPaymentInvoiceRepository]", base class "BaseClassicalMappedView" defined the type as "BaseRepository[Any]")

    can_view_details = True
    column_default_sort = ("created_at", True)
    column_list = [
        "id",
        "uuid",
        "created_by_process",
        "created_by_user_id",
        "created_at",
        "reimbursement_organization_settings_id",
        "bill_creation_cutoff_start_at",
        "bill_creation_cutoff_end_at",
        "bills_allocated_at",
        "bills_allocated_by_process",
        "voided_at",
        "voided_by_user_id",
        "bill_allocated_by_user_id",
    ]

    column_filters = [
        "id",
        "uuid",
        "created_by_user_id",
        "reimbursement_organization_settings_id",
        "bill_allocated_by_user_id",
    ]

    column_details_list = (
        "id",
        "uuid",
        "created_by_process",
        "created_by_user_id",
        "created_at",
        "reimbursement_organization_settings_id",
        "bill_creation_cutoff_start_at",
        "bill_creation_cutoff_end_at",
        "bills_allocated_at",
        "bills_allocated_by_process",
        "voided_at",
        "voided_by_user_id",
        "report_generated_at",
        "report_generated_json",
        "bill_allocated_by_user_id",
    )

    column_sortable_list = (
        "id",
        "uuid",
        "created_by_user_id",
        "created_at",
        "bill_creation_cutoff_start_at",
        "bill_creation_cutoff_end_at",
    )

    form_create_rules = ("reimbursement_organization_settings_id",)

    def create_model(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        ros_id = 0
        try:
            ros_id = form.data["reimbursement_organization_settings_id"]
        except Exception as e:
            flash(f"Failed to get ros_id: {str(e)}", "error")
            return None

        user_id = 0
        try:
            user_id = login.current_user.id
        except Exception as e:
            flash(f"Failed to get login user_id: {str(e)}", "error")
            return None

        try:
            result = self.direct_payment_invoicing_client.create_invoice_and_allocate(
                ros_id=ros_id,
                created_by_process=Process.ADMIN,
                created_by_user_id=user_id,
            )

            if not result:
                flash(
                    "Failed to create direct payment invoice in admin. Check logs for reasons",
                    "error",
                )
                return None
            return self.direct_payment_invoicing_client.get_invoice_by_id(
                invoice_id=list(result.keys())[0]
            )
        except Exception as e:
            flash(
                f"Failed to create direct payment invoice in admin: {str(e)}", "error"
            )
            return None

    def delete_model(self, model: DirectPaymentInvoice):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # The default impl of delete_model is sufficient for deleting the invoice and the associated bills, but
        # we want to implement it by ourselves for org-level report data
        user_id = 0
        try:
            user_id = login.current_user.id
        except Exception as e:
            flash(f"Failed to get login user_id: {str(e)}", "error")

        if model.id is not None:
            error_message: Optional[
                str
            ] = self.direct_payment_invoicing_client.delete_invoice(
                invoice_id=model.id, deleted_by_user_id=user_id
            )

            if error_message is not None:
                flash(
                    f"Failed to delete the direct payment invoice (id={model.id} in admin: {error_message}",
                    "error",
                )
        else:
            flash("Missing invoice id", "error")
