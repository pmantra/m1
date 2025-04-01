from airflow.utils import check_if_run_in_airflow, with_app_context
from utils.bad_data_checkers import half_hourly
from utils.constants import CronJobName


@check_if_run_in_airflow(CronJobName.DATA_CHECKER_HALF_HOURLY)
@with_app_context(team_ns="care_discovery", service_ns="care_team")
def data_checker_half_hourly_job() -> None:
    half_hourly()
