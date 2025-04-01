from airflow.utils import check_if_run_in_airflow, with_app_context
from appointments.tasks.appointment_notifications import (
    sms_notify_upcoming_appointments_member,
)
from utils.constants import CronJobName


@check_if_run_in_airflow(CronJobName.SMS_NOTIFY_UPCOMING_APPOINTMENTS_MEMBER_CRON_JOB)
@with_app_context(team_ns="virtual_care", service_ns="appointment_notifications")
def sms_notify_upcoming_appointments_member_job() -> None:
    sms_notify_upcoming_appointments_member()
