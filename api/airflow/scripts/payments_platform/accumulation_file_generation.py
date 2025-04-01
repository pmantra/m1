from airflow.utils import check_if_run_in_airflow, with_app_context
from payer_accumulator.tasks.rq_payer_accumulation_file_generation import (
    aetna_accumulation_file_generation,
    anthem_accumulation_file_generation,
    bcbs_ma_accumulation_file_generation,
    cigna_accumulation_file_generation,
    cigna_track_1_amazon_accumulation_file_generation,
    cigna_track_1_goldman_sachs_accumulation_file_generation,
    credence_accumulation_file_generation,
    esi_accumulation_file_generation,
    luminare_accumulation_file_generation,
    premera_accumulation_file_generation,
    surest_accumulation_file_generation,
    uhc_accumulation_file_generation,
)
from utils.constants import CronJobName


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def aetna_accumulation_file_generation_job() -> None:
    aetna_accumulation_file_generation()


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def anthem_accumulation_file_generation_job() -> None:
    anthem_accumulation_file_generation()


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def bcbs_ma_accumulation_file_generation_job() -> None:
    bcbs_ma_accumulation_file_generation()


@check_if_run_in_airflow(CronJobName.CIGNA_ACCUMULATION_FILE_GENERATION)
@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def cigna_accumulation_file_generation_job() -> None:
    cigna_accumulation_file_generation()


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def cigna_track_1_amazon_accumulation_file_generation_job() -> None:
    cigna_track_1_amazon_accumulation_file_generation()


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def cigna_track_1_goldman_sachs_accumulation_file_generation_job() -> None:
    cigna_track_1_goldman_sachs_accumulation_file_generation()


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def credence_accumulation_file_generation_job() -> None:
    credence_accumulation_file_generation()


@check_if_run_in_airflow(CronJobName.ESI_ACCUMULATION_FILE_GENERATION)
@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def esi_accumulation_file_generation_job() -> None:
    esi_accumulation_file_generation()


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def luminare_accumulation_file_generation_job() -> None:
    luminare_accumulation_file_generation()


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def premera_accumulation_file_generation_job() -> None:
    premera_accumulation_file_generation()


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def surest_accumulation_file_generation_job() -> None:
    surest_accumulation_file_generation()


@check_if_run_in_airflow(CronJobName.UHC_ACCUMULATION_FILE_GENERATION)
@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def uhc_accumulation_file_generation_job() -> None:
    uhc_accumulation_file_generation()
