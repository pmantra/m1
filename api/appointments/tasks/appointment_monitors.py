from datetime import datetime, timedelta

from sqlalchemy.orm import joinedload
from sqlalchemy.sql.expression import and_, or_

from appointments.models.appointment import Appointment
from models.products import Product
from storage.connection import db
from tasks.queues import job
from utils.log import logger

log = logger(__name__)


@job
def find_overlapping_appointments(search_timedelta_hours: int = 2) -> None:
    """
    This task finds two overlapping appointments and logs them out. There is a corresponding
    Datadog monitor to alert on these logs.

    NOTE: this task must be moved over to the Appointments service

    @param search_timedelta_hours: the amount of previous hours from now that we should search
    """
    log.info("Starting task 'find_overlapping_appointments'")

    now = datetime.utcnow()

    # Get all appointments updated
    appointments: list[Appointment] = (
        db.session.query(Appointment)
        .join(Product)
        .filter(
            Appointment.modified_at <= now,
            Appointment.modified_at >= (now - timedelta(hours=search_timedelta_hours)),
            Appointment.cancelled_at.is_(None),
        )
        .options(joinedload(Appointment.product))
        .all()
    )
    len_appointments = len(appointments)
    log.info(
        f"Found {len_appointments} appointments",
        num_appts_found=len_appointments,
    )
    if len_appointments == 0:
        return

    # For each appointment found above, find overlapping appointments with the same practitioner
    overlapping_appointments = []
    for appt in appointments:
        # WARNING: db call in a loop here. The other options are as follows:
        #     - Batch these into one query, but this makes getting the other matching appointment hard
        #     - Joining on the appointment table again. With the joins needed to match by
        #         practitioner id, I don't believe this option is performant
        #
        # appt.practitioner_id may also be making
        matching_appts = (
            db.session.query(Appointment.id)
            .join(Product)
            .filter(
                appt.product.user_id == Product.user_id,
                Appointment.cancelled_at.is_(None),
                or_(
                    and_(
                        Appointment.scheduled_start > appt.scheduled_start,
                        Appointment.scheduled_start < appt.scheduled_end,
                    ),
                    and_(
                        Appointment.scheduled_end > appt.scheduled_start,
                        Appointment.scheduled_end < appt.scheduled_end,
                    ),
                    and_(
                        appt.scheduled_start > Appointment.scheduled_start,
                        appt.scheduled_end < Appointment.scheduled_end,
                    ),
                    appt.scheduled_start == Appointment.scheduled_start,
                    appt.scheduled_end == Appointment.scheduled_end,
                ),
            )
            .all()
        )
        matching_appt_ids = [a[0] for a in matching_appts]

        # matching_appts query will return itself so we are looking for "> 1"
        if len(matching_appts) > 1:
            overlapping_appointments.append(set(matching_appt_ids))

    if len(overlapping_appointments) > 0:
        log.error(
            "Found overlapping appointments",
            overlapping_appointments=str(overlapping_appointments),
        )
