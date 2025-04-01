from appointments.models.appointment import Appointment
from appointments.models.appointment_meta_data import AppointmentMetaData
from appointments.models.constants import AppointmentMetaDataTypes
from storage.connection import db
from utils.log import logger

log = logger(__name__)


def migrate_existing_post_session_notes():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    appts_with_notes = (
        db.session.query(Appointment)
        .filter(
            Appointment.practitioner_notes.isnot(None),
            Appointment.practitioner_notes != "",
        )
        .all()
    )
    log.debug("Got %s appointments to be migrated.", len(appts_with_notes))

    for appt in appts_with_notes:
        new_note = AppointmentMetaData(
            type=AppointmentMetaDataTypes.PRACTITIONER_NOTE,
            appointment_id=appt.id,
            content=appt.practitioner_notes,
            created_at=appt.scheduled_end,
            modified_at=appt.scheduled_end,
        )
        db.session.add(new_note)
        db.session.commit()
        log.debug("Migrated <Appointment[%s]>'s practitioner notes.", appt.id)
