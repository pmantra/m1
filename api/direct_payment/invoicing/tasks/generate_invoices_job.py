import os
from datetime import datetime
from typing import Optional

import croniter  # type: ignore[import-untyped]

from direct_payment.invoicing.direct_payment_invoicing_client import (
    DirectPaymentInvoicingClient,
)
from direct_payment.invoicing.models import OrganizationInvoicingSettings, Process
from utils.log import logger

log = logger(__name__)


def generate_invoices() -> None:
    log.info("Start the generate_invoices job")

    internal_gateway_url = os.environ.get("INTERNAL_GATEWAY_URL")
    if internal_gateway_url is None:
        # The payment service is not used for generating invoices, so just create a
        # warning log without stopping the job
        log.warn("Internal gateway url is unavailable.")

    payment_gateway_base_url = f"{internal_gateway_url}/api/v1/payments/"
    client = DirectPaymentInvoicingClient(
        payment_gateway_base_url=payment_gateway_base_url
    )

    invoice_settings: list[
        OrganizationInvoicingSettings
    ] = client.get_all_invoice_settings()

    log.info(
        f"Start generating invoices for {len(invoice_settings)} organizations in generate_invoices"
    )

    for invoice_setting in invoice_settings:
        if should_generate_invoice(
            invoice_setting.invoice_cadence, invoice_setting.organization_id
        ):
            try:
                client.create_invoices_and_allocate(
                    organization_id=invoice_setting.organization_id,
                    created_by_process=Process.INVOICE_GENERATOR,
                    created_by_user_id=None,
                )

                log.info(
                    "Successful create invoices and allocating bills in generate_invoices",
                    organization_id=invoice_setting.organization_id,
                )
            except Exception as e:
                log.error(
                    "Error during creating invoices and allocating bills in generate_invoices",
                    organization_id=invoice_setting.organization_id,
                    error_msg=str(e),
                )
        else:
            log.info(
                "Not the time to generate invoice in generate_invoices",
                organization_id=invoice_setting.organization_id,
                invoice_cadence=invoice_setting.invoice_cadence,
            )


def should_generate_invoice(
    invoice_cadence: Optional[str], organization_id: int
) -> bool:
    if invoice_cadence is not None:

        try:
            # croniter will raise ValueError if expression is invalid
            croniter.croniter(invoice_cadence)
        except ValueError:
            log.error(
                "The cron expression of the invoice cadence is invalid",
                organization_id=organization_id,
                invoice_cadence=invoice_cadence,
            )
            return False

        # Split the cron expression into parts (ignoring minute and hour)
        parts = invoice_cadence.split()

        # Since we check if the cron expression is valid or not before, we don't need to check if len(parts) == 5 here

        # Extract the relevant parts (day of month, month, day of week)
        day_of_month_expr: str = parts[2]
        month_expr: str = parts[3]
        day_of_week_expr: str = parts[4]

        # Get the current date
        now = datetime.utcnow()
        current_day_of_month: int = now.day
        current_month: int = now.month
        current_day_of_week: int = now.weekday()  # Monday is 0, Sunday is 6
        current_day_of_week = 0 if current_day_of_week == 6 else current_day_of_week + 1

        day_of_month_matches = (
            day_of_month_expr == "*" or int(day_of_month_expr) == current_day_of_month
        )
        month_matches = month_expr == "*" or int(month_expr) == current_month
        day_of_week_matches = (
            day_of_week_expr == "*" or int(day_of_week_expr) == current_day_of_week
        )

        return day_of_month_matches and month_matches and day_of_week_matches

    return False


def process_invoice_bills() -> None:
    log.info("Start the process_invoice_bills job")

    internal_gateway_url = os.environ.get("INTERNAL_GATEWAY_URL")
    if internal_gateway_url is None:
        # The payment service is not used for generating invoices, so just create a
        # warning log without stopping the job
        log.warn("Internal gateway url is unavailable.")

    payment_gateway_base_url = f"{internal_gateway_url}/api/v1/payments/"

    client = DirectPaymentInvoicingClient(
        payment_gateway_base_url=payment_gateway_base_url
    )
    client.process_invoice_bills()
