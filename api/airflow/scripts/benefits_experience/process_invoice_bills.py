from airflow.utils import with_app_context
from direct_payment.invoicing.tasks.generate_invoices_job import process_invoice_bills


@with_app_context(team_ns="benefits_experience", service_ns="invoice")
def process_invoice_bills_job() -> None:
    process_invoice_bills()
