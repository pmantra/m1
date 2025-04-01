from airflow.utils import with_app_context
from appointments.tasks.localization import update_appointment_search_localized_strings


@with_app_context(team_ns="care_discovery", service_ns="appointments")
def update_appointment_search_localized_strings_job() -> None:
    update_appointment_search_localized_strings()
