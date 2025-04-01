from airflow.utils import check_if_run_in_airflow, with_app_context
from tasks.messaging import create_zd_ticket_for_unresponded_promoted_messages
from utils.constants import CronJobName


@check_if_run_in_airflow(CronJobName.CREATE_ZD_TICKET_FOR_UNRESPONDED_PROMOTED_MESSAGE)
@with_app_context(team_ns="care_discovery", service_ns="incentive")
def create_zd_ticket_for_unresponded_promoted_messages_job() -> None:
    create_zd_ticket_for_unresponded_promoted_messages()
