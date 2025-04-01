from airflow.utils import check_if_run_in_airflow, with_app_context
from appointments.tasks.availability_requests import (
    find_stale_request_availability_messages,
)
from utils.constants import CronJobName


# This script is used to find stale request availability messages in the system.
@check_if_run_in_airflow(CronJobName.FIND_STALE_REQUEST_AVAILABILITY_MESSAGES_JOB)
@with_app_context(team_ns="care_discovery", service_ns="care_team")
def find_stale_request_availability_messages_job() -> None:
    find_stale_request_availability_messages()
