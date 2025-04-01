from airflow.utils import check_if_run_in_airflow, with_app_context
from appointments.tasks.appointment_notifications import (
    sms_notify_upcoming_appointments_practitioner,
)
from utils.constants import CronJobName


@check_if_run_in_airflow(
    CronJobName.SMS_NOTIFY_UPCOMING_APPOINTMENTS_PRACTITIONER_CRON_JOB
)
@with_app_context(team_ns="virtual_care", service_ns="appointment_notifications")
def sms_notify_upcoming_appointments_practitioner_job() -> None:
    sms_notify_upcoming_appointments_practitioner()
