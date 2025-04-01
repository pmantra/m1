from airflow.utils import check_if_run_in_airflow, with_app_context
from utils.constants import CronJobName
from wallet.tasks.survey_monkey import add_survey_ids_to_webhook


@check_if_run_in_airflow(CronJobName.ADD_SURVEY_IDS_TO_WEBHOOK)
@with_app_context(team_ns="benefits_experience", service_ns="clinic_management")
def add_survey_ids_to_webhook_job() -> None:
    add_survey_ids_to_webhook()
