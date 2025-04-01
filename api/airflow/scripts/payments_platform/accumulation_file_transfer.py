from airflow.utils import check_if_run_in_airflow, with_app_context
from payer_accumulator.tasks.rq_payer_accumulation_file_transfer import (
    transfer_payer_accumulation_files_to_aetna,
    transfer_payer_accumulation_files_to_amazon_cigna_track_1,
    transfer_payer_accumulation_files_to_anthem,
    transfer_payer_accumulation_files_to_bcbs_ma,
    transfer_payer_accumulation_files_to_cigna_data_sender,
    transfer_payer_accumulation_files_to_credence,
    transfer_payer_accumulation_files_to_esi_data_sender,
    transfer_payer_accumulation_files_to_goldman_sachs_cigna_track_1,
    transfer_payer_accumulation_files_to_luminare,
    transfer_payer_accumulation_files_to_premera,
    transfer_payer_accumulation_files_to_surest,
    transfer_payer_accumulation_files_to_uhc_data_sender,
)
from utils.constants import CronJobName


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def aetna_accumulation_file_transfer_job() -> None:
    transfer_payer_accumulation_files_to_aetna()


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def anthem_accumulation_file_transfer_job() -> None:
    transfer_payer_accumulation_files_to_anthem()


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def bcbs_ma_accumulation_file_transfer_job() -> None:
    transfer_payer_accumulation_files_to_bcbs_ma()


@check_if_run_in_airflow(
    CronJobName.TRANSFER_PAYER_ACCUMULATION_FILE_TO_CIGNA_DATA_SENDER
)
@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def cigna_accumulation_file_transfer_job() -> None:
    transfer_payer_accumulation_files_to_cigna_data_sender()


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def cigna_track_1_amazon_accumulation_file_transfer_job() -> None:
    transfer_payer_accumulation_files_to_amazon_cigna_track_1()


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def cigna_track_1_goldman_sachs_accumulation_file_transfer_job() -> None:
    transfer_payer_accumulation_files_to_goldman_sachs_cigna_track_1()


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def credence_accumulation_file_transfer_job() -> None:
    transfer_payer_accumulation_files_to_credence()


@check_if_run_in_airflow(
    CronJobName.TRANSFER_PAYER_ACCUMULATION_FILE_TO_ESI_DATA_SENDER
)
@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def esi_accumulation_file_transfer_job() -> None:
    transfer_payer_accumulation_files_to_esi_data_sender()


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def luminare_accumulation_file_transfer_job() -> None:
    transfer_payer_accumulation_files_to_luminare()


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def premera_accumulation_file_transfer_job() -> None:
    transfer_payer_accumulation_files_to_premera()


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def surest_accumulation_file_transfer_job() -> None:
    transfer_payer_accumulation_files_to_surest()


@check_if_run_in_airflow(
    CronJobName.TRANSFER_PAYER_ACCUMULATION_FILE_TO_UHC_DATA_SENDER
)
@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def uhc_accumulation_file_transfer_job() -> None:
    transfer_payer_accumulation_files_to_uhc_data_sender()
