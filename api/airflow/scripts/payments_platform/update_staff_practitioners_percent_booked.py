from airflow.utils import check_if_run_in_airflow, with_app_context
from appointments.tasks.availability import update_staff_practitioners_percent_booked
from utils.constants import CronJobName


@check_if_run_in_airflow(CronJobName.UPDATE_STAFF_PRACTITIONERS_PERCENT_BOOKED)
@with_app_context(team_ns="payments_platform", service_ns="provider_payments")
def update_staff_practitioners_percent_booked_job() -> None:
    update_staff_practitioners_percent_booked()
