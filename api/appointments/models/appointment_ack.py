from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship, validates

from models import base
from utils.data import PHONE_NUMBER_LENGTH, normalize_phone_number


class AppointmentAck(base.TimeLoggedModelBase):
    __abstract__ = True

    id = Column(Integer, primary_key=True)

    phone_number = Column(String(PHONE_NUMBER_LENGTH), nullable=False)

    is_acked = Column(Boolean, default=False, nullable=False)

    @declared_attr
    def appointment_id(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return Column(Integer, ForeignKey("appointment.id"), nullable=False)

    @declared_attr
    def appointment(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return relationship("Appointment", uselist=False)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} ({self.id}) for {self.appointment} [{self.is_acked}]>"

    __str__ = __repr__

    @validates("phone_number")
    def validate_phone_no(self, key, phone_number):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if phone_number:
            phone_number, _ = normalize_phone_number(phone_number, None)
        return phone_number
