from airflow.utils import check_if_run_in_airflow, with_app_context
from appointments.tasks.appointments import send_appointment_completion_event
from utils.constants import CronJobName


@check_if_run_in_airflow(CronJobName.SEND_APPOINTMENT_COMPLETION_EVENT)
@with_app_context(team_ns="care_management", service_ns="assessments")
def send_appointment_completion_event_job() -> None:
    send_appointment_completion_event()
