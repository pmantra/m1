from sqlalchemy import Boolean, Column, DateTime

from appointments.models.appointment_ack import AppointmentAck


class PractitionerAppointmentAck(AppointmentAck):
    __tablename__ = "practitioner_appointment_ack"

    ack_by = Column(DateTime(), nullable=False)
    is_alerted = Column(Boolean, default=False, nullable=False)

    warn_by = Column(DateTime(), nullable=False)
    is_warned = Column(Boolean, default=False, nullable=False)
