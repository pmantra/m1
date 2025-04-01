from airflow.utils import with_app_context
from appointments.tasks.state import resolve_appointment_pending_payments


@with_app_context(team_ns="care_discovery", service_ns="appointments")
def resolve_appointment_pending_payments_job() -> None:
    resolve_appointment_pending_payments()
