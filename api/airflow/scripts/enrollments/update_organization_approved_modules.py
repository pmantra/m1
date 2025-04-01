from airflow.utils import check_if_run_in_airflow, with_app_context
from tasks.programs import update_organization_approved_modules
from utils.constants import CronJobName


@check_if_run_in_airflow(CronJobName.UPDATE_ORGANIZATION_APPROVED_MODULES)
@with_app_context(team_ns="enrollments", service_ns="tracks")
def update_organization_approved_modules_job() -> None:
    update_organization_approved_modules()
