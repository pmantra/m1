from airflow.utils import check_if_run_in_airflow, with_app_context
from health.tasks.member_risk_flag_update import (
    update_member_risk_flags,
    update_member_risk_flags_even,
    update_member_risk_flags_odd,
)
from utils.constants import CronJobName


@check_if_run_in_airflow(CronJobName.MEMBER_RISK_FLAGS_EVEN)
@with_app_context(team_ns="mpractice_core", service_ns="health")
def update_member_risk_flags_even_job() -> None:
    update_member_risk_flags_even()


@check_if_run_in_airflow(CronJobName.MEMBER_RISK_FLAGS_ODD)
@with_app_context(team_ns="mpractice_core", service_ns="health")
def update_member_risk_flags_odd_job() -> None:
    update_member_risk_flags_odd()


@check_if_run_in_airflow(CronJobName.MEMBER_RISK_FLAGS)
@with_app_context(team_ns="mpractice_core", service_ns="health")
def update_member_risk_flags_job() -> None:
    update_member_risk_flags()
