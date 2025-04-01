from __future__ import annotations

from typing import Optional

import flask_login as login
from flask import flash
from wtforms import IntegerField, SelectField
from wtforms.validators import DataRequired, ValidationError

from authn.resources.admin import BaseClassicalMappedView
from direct_payment.invoicing.direct_payment_invoicing_client import (
    DirectPaymentInvoicingClient,
)
from direct_payment.invoicing.models import OrganizationInvoicingSettings
from direct_payment.invoicing.repository.organization_invoicing_settings import (
    OrganizationInvoicingSettingsRepository,
)
from direct_payment.invoicing.utils import (
    generate_user_friendly_report_cadence,
    validate_cron_expression,
)
from utils.log import logger

log = logger(__name__)


def _validate_day_based_on_frequency(form, field) -> None:  # type: ignore[no-untyped-def]
    frequency = form.frequency.data  # Get the value of the frequency field
    day = field.data  # Get the value of the day field

    if frequency == "WEEKLY" and not (0 <= day <= 6):
        raise ValidationError(
            "For weekly frequency, day must be between 0 and 6 (representing Sunday to Saturday)."
        )
    elif frequency == "MONTHLY" and not (1 <= day <= 28):
        raise ValidationError("For monthly frequency, day must be between 1 and 28.")


def _generate_cron_expression(frequency: str, day: int) -> str:
    if frequency == "WEEKLY":
        return f"0 0 * * {day}"
    elif frequency == "MONTHLY":
        return f"0 0 {day} * *"
    else:
        raise Exception(f"Unexpected frequency: {frequency}")


class DirectPaymentInvoicingSettingView(BaseClassicalMappedView):
    def __init__(self, model, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().__init__(model, *args, **kwargs)

        self.direct_payment_invoicing_client = DirectPaymentInvoicingClient()

    read_permission = "read:direct-payment-invoicing-setting"
    edit_permission = "edit:direct-payment-invoicing-setting"
    create_permission = "create:direct-payment-invoicing-setting"
    delete_permission = "delete:direct-payment-invoicing-setting"

    list_template = "list.html"

    repo = OrganizationInvoicingSettingsRepository  # type: ignore[assignment] # Incompatible types in assignment (expression has type "type[OrganizationInvoicingSettingsRepository]", base class "BaseClassicalMappedView" defined the type as "BaseRepository[Any]")

    can_view_details = True
    column_default_sort = ("created_at", True)
    column_list = [
        "id",
        "uuid",
        "created_at",
        "updated_at",
        "organization_id",
        "created_by_user_id",
        "updated_by_user_id",
        "invoicing_active_at",
        "invoice_cadence",
        "bill_processing_delay_days",
        "bill_cutoff_at_buffer_days",
    ]

    column_formatters = {
        "invoice_cadence": lambda view, context, model, name: generate_user_friendly_report_cadence(
            model.organization_id, model.invoice_cadence
        ),
    }

    column_filters = [
        "id",
        "uuid",
        "organization_id",
    ]

    column_details_list = (
        "id",
        "uuid",
        "created_at",
        "updated_at",
        "organization_id",
        "created_by_user_id",
        "updated_by_user_id",
        "invoicing_active_at",
        "bills_allocated_by_process",
        "invoice_cadence",
        "bill_processing_delay_days",
        "bill_cutoff_at_buffer_days",
    )

    column_labels = {
        "invoicing_active_at": "Invoicing Active At (The date at which the employer activated invoice based billing)",
        "invoice_cadence": "Invoice generation cadence",
        "bill_processing_delay_days": "Bill Processing Delay Days (how many days bills will be processed after creation)",
        "bill_cutoff_at_buffer_days": "Bill Cutoff At Buffer Days (The cutoff offset in days from the current date for the latest bill creation date)",
    }

    form_create_rules = (
        "organization_id",
        "invoicing_active_at",
        "frequency",
        "day",
        "bill_processing_delay_days",
        "bill_cutoff_at_buffer_days",
    )

    form_edit_rules = (
        "invoicing_active_at",
        "frequency",
        "day",
        "bill_processing_delay_days",
        "bill_cutoff_at_buffer_days",
    )

    form_extra_fields = {
        "frequency": SelectField(
            "Invoice generation frequency",
            choices=[("WEEKLY", "Weekly"), ("MONTHLY", "Monthly")],
            validators=[DataRequired()],
        ),
        "day": IntegerField(
            "Invoice generation day (When frequency is WEEKLY, 0-6 represents Sunday to Saturday. When frequency is MONTHLY, it represents the day of the month)",
            validators=[DataRequired(), _validate_day_based_on_frequency],
        ),
    }

    column_sortable_list = (
        "id",
        "uuid",
        "created_at",
        "updated_at",
        "organization_id",
    )

    def on_form_prefill(self, form, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """Prefill the form with parsed values from the cron expression."""
        invoice_setting = self.get_one(id)
        if invoice_setting and invoice_setting.invoice_cadence:
            validate_cron_expression(invoice_setting.invoice_cadence)
            parts = invoice_setting.invoice_cadence.split()

            # Extract the parts we're interested in (ignoring minute and hour)
            day_of_month = parts[2]
            day_of_week = parts[4]

            if day_of_week != "*":
                form.frequency.data = "WEEKLY"
                form.day.data = day_of_week
            elif day_of_month != "*":
                form.frequency.data = "MONTHLY"
                form.day.data = day_of_month

    def create_model(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user_id = 0
        try:
            user_id = self._get_user_id()
        except Exception as e:
            flash(f"Failed to get login user_id: {str(e)}", "error")
            return None

        invoice_cadence = _generate_cron_expression(
            form.data["frequency"], form.data["day"]
        )

        try:
            result: OrganizationInvoicingSettings | str = (
                self.direct_payment_invoicing_client.create_invoice_setting(
                    organization_id=form.data["organization_id"],
                    created_by_user_id=user_id,
                    invoicing_active_at=form.data["invoicing_active_at"],
                    invoice_cadence=invoice_cadence,
                    bill_processing_delay_days=form.data["bill_processing_delay_days"],
                    bill_cutoff_at_buffer_days=form.data["bill_cutoff_at_buffer_days"],
                )
            )

            if isinstance(result, str):
                flash(
                    f"Failed to update direct payment invoicing setting in admin: {result}",
                    "error",
                )
                return None

            return result
        except Exception as e:
            flash(
                f"Failed to create direct payment invoicing setting in admin: {str(e)}",
                "error",
            )
            return None

    def update_model(self, form, model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user_id = 0
        try:
            user_id = self._get_user_id()
        except Exception as e:
            flash(f"Failed to get login user_id: {str(e)}", "error")
            return None

        invoice_cadence = _generate_cron_expression(
            form.data["frequency"], form.data["day"]
        )

        try:
            result: OrganizationInvoicingSettings | str = (
                self.direct_payment_invoicing_client.update_invoicing_setting(
                    existing_invoicing_setting=model,
                    updated_by_user_id=user_id,
                    invoicing_active_at=form.data["invoicing_active_at"],
                    invoice_cadence=invoice_cadence,
                    bill_processing_delay_days=form.data["bill_processing_delay_days"],
                    bill_cutoff_at_buffer_days=form.data["bill_cutoff_at_buffer_days"],
                )
            )

            if isinstance(result, str):
                flash(
                    f"Failed to update direct payment invoicing setting in admin: {result}",
                    "error",
                )
                return None

            return result

        except Exception as e:
            flash(
                f"Failed to update direct payment invoicing setting in admin: {str(e)}",
                "error",
            )
            return model

    def delete_model(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self, model: OrganizationInvoicingSettings
    ):
        try:
            user_id = self._get_user_id()
        except Exception as e:
            flash(f"Failed to get login user_id: {str(e)}", "error")

        if model.id is not None:
            error_message: Optional[
                str
            ] = self.direct_payment_invoicing_client.delete_invoicing_setting(
                invoicing_setting_id=model.id, deleted_by_user_id=user_id
            )

            if error_message is not None:
                flash(
                    f"Failed to delete the direct payment invoicing setting (id={model.id} in admin: {error_message}",
                    "error",
                )
        else:
            flash("Missing invoicing setting id", "error")

    @staticmethod
    def _get_user_id() -> int:
        try:
            user_id = login.current_user.id
            return user_id
        except Exception as e:
            raise e
