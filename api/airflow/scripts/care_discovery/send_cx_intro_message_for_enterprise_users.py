from airflow.utils import check_if_run_in_airflow, with_app_context
from tasks.messaging import send_cx_intro_message_for_enterprise_users
from utils.constants import CronJobName


@check_if_run_in_airflow(CronJobName.SEND_CX_INTRO_MESSAGE_FOR_ENTERPRISE_USERS)
@with_app_context(team_ns="care_discovery", service_ns="care_team")
def send_cx_intro_message_for_enterprise_users_job() -> None:
    send_cx_intro_message_for_enterprise_users(hours_ago=1)
