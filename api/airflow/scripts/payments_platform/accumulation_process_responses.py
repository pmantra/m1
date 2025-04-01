from airflow.utils import with_app_context
from payer_accumulator.tasks.rq_payer_accumulation_csv_response_processing import (
    bcbs_ma_process_accumulation_responses,
)
from payer_accumulator.tasks.rq_payer_accumulation_response_processing import (
    anthem_process_accumulation_responses,
    credence_process_accumulation_responses,
    luminare_process_accumulation_responses,
    premera_process_accumulation_responses,
)


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def anthem_accumulation_process_responses_job() -> None:
    anthem_process_accumulation_responses()


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def bcbs_ma_accumulation_process_responses_job() -> None:
    bcbs_ma_process_accumulation_responses()


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def credence_accumulation_process_responses_job() -> None:
    credence_process_accumulation_responses()


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def luminare_accumulation_process_responses_job() -> None:
    luminare_process_accumulation_responses()


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def premera_accumulation_process_responses_job() -> None:
    premera_process_accumulation_responses()
