from airflow.utils import with_app_context
from tasks.gdpr_backup_data_deletion import gdpr_delete_backup


@with_app_context(team_ns="core_services", service_ns="gdpr_deletion")
def gdpr_backup_deletion_job() -> None:
    gdpr_delete_backup()
