from airflow.utils import with_app_context
from health.tasks.backfill_chronic_diabetes import backfill_chronic_diabetes


@with_app_context(team_ns="mpractice_core", service_ns="health")
def backfill_chronic_diabetes_job() -> None:
    backfill_chronic_diabetes()
