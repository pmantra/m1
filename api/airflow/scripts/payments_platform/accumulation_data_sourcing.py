from airflow.utils import check_if_run_in_airflow, with_app_context
from payer_accumulator.common import PayerName
from payer_accumulator.tasks.rq_payer_accumulation_data_sourcing import (
    anthem_data_sourcing,
    cigna_data_sourcing,
    esi_data_sourcing,
    luminare_data_sourcing,
    premera_data_sourcing,
    run_data_sourcing,
    uhc_data_sourcing,
)
from storage.connection import db
from utils.constants import CronJobName


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def aetna_accumulation_data_sourcing_job() -> None:
    run_data_sourcing(PayerName.AETNA, db.session)


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def anthem_accumulation_data_sourcing_job() -> None:
    anthem_data_sourcing()


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def bcbs_ma_accumulation_data_sourcing_job() -> None:
    run_data_sourcing(PayerName.BCBS_MA, db.session)


@check_if_run_in_airflow(CronJobName.CIGNA_ACCUMULATION_DATA_SOURCING)
@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def cigna_accumulation_data_sourcing_job() -> None:
    cigna_data_sourcing()


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def cigna_track_1_amazon_accumulation_data_sourcing_job() -> None:
    run_data_sourcing(PayerName.CIGNA_TRACK_1, db.session)


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def cigna_track_1_goldman_sachs_accumulation_data_sourcing_job() -> None:
    run_data_sourcing(PayerName.CIGNA_TRACK_1, db.session)


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def credence_accumulation_data_sourcing_job() -> None:
    run_data_sourcing(PayerName.CREDENCE, db.session)


@check_if_run_in_airflow(CronJobName.ESI_ACCUMULATION_DATA_SOURCING)
@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def esi_accumulation_data_sourcing_job() -> None:
    esi_data_sourcing()


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def luminare_accumulation_data_sourcing_job() -> None:
    luminare_data_sourcing()


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def premera_accumulation_data_sourcing_job() -> None:
    premera_data_sourcing()


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def surest_accumulation_data_sourcing_job() -> None:
    run_data_sourcing(PayerName.SUREST, db.session)


@check_if_run_in_airflow(CronJobName.UHC_ACCUMULATION_DATA_SOURCING)
@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def uhc_accumulation_data_sourcing_job() -> None:
    uhc_data_sourcing()
