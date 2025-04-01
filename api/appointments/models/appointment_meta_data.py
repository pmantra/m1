from dataclasses import dataclass

from sqlalchemy import Boolean, Column, Enum, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from appointments.models.constants import AppointmentMetaDataTypes
from models import base
from utils.foreign_key_metric import increment_metric
from utils.log import logger

log = logger(__name__)


class AppointmentMetaData(base.TimeLoggedModelBase):
    __tablename__ = "appointment_metadata"

    id = Column(Integer, primary_key=True)
    type = Column(Enum(AppointmentMetaDataTypes), nullable=False)
    content = Column(Text, nullable=False)
    draft = Column(Boolean, default=False)

    message_id = Column(Integer, ForeignKey("message.id"), nullable=True)
    message = relationship("Message", lazy="joined")

    appointment_id = Column(Integer, nullable=False)

    def __repr__(self) -> str:
        return f"<AppointmentMetaData[{self.id}] type={self.type}>"

    @property
    def appointment(self):  # type: ignore[no-untyped-def]
        from appointments.utils.appointment_utils import get_appointments_by_ids

        model = f"{self.__tablename__}.appointment"
        try:
            appointments = get_appointments_by_ids([self.appointment_id])
            increment_metric(True, model)
            return appointments[0] if len(appointments) > 0 else None
        except Exception as e:
            error_message = "Error in getting appointment in AppointmentMetaData"
            increment_metric(True, model, error_message)
            raise e

    @appointment.setter
    def appointment(self, appointment):  # type: ignore[no-untyped-def]
        from appointments.utils.appointment_utils import upsert_appointment

        model = f"{self.__tablename__}.appointment"
        log.warn(
            "This approach of upserting appointment is not allowed. Use a different way to do so",
            model=model,
        )
        try:
            upsert_appointment(appointment)
            increment_metric(False, model)
        except Exception as e:
            error_message = "Error in upserting appointment in AppointmentMetaData"
            increment_metric(False, model, error_message)
            raise e

    __str__ = __repr__


@dataclass
class PostAppointmentNoteUpdate:
    __slots__ = ("should_send", "post_session")
    should_send: bool
    post_session: AppointmentMetaData
