from airflow.utils import with_app_context
from payer_accumulator.tasks.edi_276_claim_status_request_job import (
    aetna_claim_status_request_generation,
)


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def aetna_claim_status_request_generation_job() -> None:
    aetna_claim_status_request_generation()
