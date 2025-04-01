from airflow.utils import check_if_run_in_airflow, with_app_context
from cost_breakdown.tasks.monitoring import (
    find_treatment_procedures_without_cost_breakdown_ids,
)
from utils.constants import CronJobName


@check_if_run_in_airflow(
    CronJobName.FIND_TREATMENT_PROCEDURES_WITHOUT_COST_BREAKDOWN_IDS
)
@with_app_context(team_ns="payments_platform", service_ns="cost_breakdown")
def find_treatment_procedures_without_cost_breakdown_ids_job() -> None:
    find_treatment_procedures_without_cost_breakdown_ids()
