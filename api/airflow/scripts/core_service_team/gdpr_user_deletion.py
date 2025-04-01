from airflow.utils import with_app_context
from tasks.gdpr_user_deletion import gdpr_delete_users


@with_app_context(team_ns="core_services", service_ns="gdpr_deletion")
def gdpr_user_deletion_job() -> None:
    gdpr_delete_users()
