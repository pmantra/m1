from airflow.utils import check_if_run_in_airflow, with_app_context
from tasks.zoom import follow_up_with_users_who_participated_in_zoom_webinar
from utils.constants import CronJobName


@check_if_run_in_airflow(
    CronJobName.FOLLOW_UP_WITH_USERS_WHO_PARTICIPATED_IN_ZOOM_WEBINAR
)
@with_app_context(team_ns="content_and_community", service_ns="content_campaigns")
def follow_up_with_users_who_participated_in_zoom_webinar_job() -> None:
    follow_up_with_users_who_participated_in_zoom_webinar()
