from airflow.utils import with_app_context
from payer_accumulator.tasks.rq_payer_accumulation_file_ingestion import (
    aetna_accumulation_277_ingestion,
    aetna_accumulation_277ca_ingestion,
)


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def aetna_accumulation_277_ingestion_job() -> None:
    aetna_accumulation_277_ingestion()


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def aetna_accumulation_277ca_ingestion_job() -> None:
    aetna_accumulation_277ca_ingestion()
