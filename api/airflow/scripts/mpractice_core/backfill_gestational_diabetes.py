from airflow.utils import with_app_context
from health.tasks.backfill_gestational_diabetes import backfill_gestational_diabetes


@with_app_context(team_ns="mpractice_core", service_ns="health")
def backfill_gestational_diabetes_job() -> None:
    backfill_gestational_diabetes()
