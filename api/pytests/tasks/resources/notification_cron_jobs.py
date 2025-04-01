# notification_cron_jobs.py
from appointments.tasks.appointment_notifications import (
    sms_notify_upcoming_appointments_member,
    sms_notify_upcoming_appointments_practitioner,
)
from utils.constants import CronJobName


def run_sms_notify_upcoming_appointments_member_cron_job():
    sms_notify_upcoming_appointments_member.delay(
        team_ns="virtual_care",
        cron_job_name=CronJobName.SMS_NOTIFY_UPCOMING_APPOINTMENTS_MEMBER_CRON_JOB,
    )


def run_sms_notify_upcoming_appointments_practitioner_cron_job():
    sms_notify_upcoming_appointments_practitioner.delay(
        team_ns="virtual_care",
        cron_job_name=CronJobName.SMS_NOTIFY_UPCOMING_APPOINTMENTS_PRACTITIONER_CRON_JOB,
    )
