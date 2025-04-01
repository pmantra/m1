from airflow.utils import with_app_context
from direct_payment.invoicing.tasks.generate_invoices_job import generate_invoices


@with_app_context(team_ns="benefits_experience", service_ns="invoice")
def invoice_generation_job() -> None:
    generate_invoices()
