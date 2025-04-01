from appointments.models.reschedule_history import RescheduleHistory
from common import stats
from storage.connection import db
from views.schemas.common import MavenDateTime


def get_rescheduled_from_previous_appointment_time(obj, context, dd_metric_name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    show_reschedule = False
    user = context.get("user")
    if user:
        # Only populate the field for practitioner users since only MPractice UI
        # needs this information.
        if user == obj.practitioner and not obj.is_anonymous:
            show_reschedule = True
    # Populate this field to the admin request
    elif context.get("admin"):
        show_reschedule = context.get("admin")
    else:
        return None

    if show_reschedule:
        stats.increment(
            metric_name=dd_metric_name,
            tags=["variant:practitioner_query"],
            pod_name=stats.PodNames.VIRTUAL_CARE,
        )

        last_reschedule_record_scheduled_start = (
            db.session.query(RescheduleHistory.scheduled_start)
            .filter(RescheduleHistory.appointment_id == obj.id)
            .order_by(RescheduleHistory.id.desc())
            .first()
        )
        last_reschedule_record_scheduled_start = (
            last_reschedule_record_scheduled_start[0]
            if last_reschedule_record_scheduled_start
            else None
        )

        if last_reschedule_record_scheduled_start:
            previous_reschedule_time = MavenDateTime()._serialize(
                last_reschedule_record_scheduled_start, None, None
            )
            stats.increment(
                metric_name=dd_metric_name,
                tags=["variant:practitioner_query_has_last_reschedule_history"],
                pod_name=stats.PodNames.VIRTUAL_CARE,
            )
        else:
            stats.increment(
                metric_name=dd_metric_name,
                tags=["variant:practitioner_query_no_reschedule_history"],
                pod_name=stats.PodNames.VIRTUAL_CARE,
            )
            # If there is no reschedule history found, return empty
            return None
        return previous_reschedule_time
    else:
        return None
