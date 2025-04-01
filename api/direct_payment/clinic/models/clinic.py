import uuid

from sqlalchemy import BigInteger, Column, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import backref, relationship

from direct_payment.clinic.models.fee_schedule import FeeSchedule
from models.base import TimeLoggedExternalUuidModelBase, TimeLoggedModelBase


class FertilityClinic(TimeLoggedExternalUuidModelBase):
    __tablename__ = "fertility_clinic"

    name = Column(String(191), nullable=False, index=True)
    affiliated_network = Column(String(50), nullable=True)
    fee_schedule_id = Column(BigInteger, nullable=False)
    payments_recipient_id = Column(String(36), nullable=True)

    fee_schedule = relationship(
        FeeSchedule,
        primaryjoin="FertilityClinic.fee_schedule_id == FeeSchedule.id",
        foreign_keys=fee_schedule_id,
        backref=backref("schedules"),
    )

    notes = Column(Text)
    self_pay_discount_rate = Column(Numeric(precision=5, scale=2), nullable=True)
    """
    Some clinics offer discount rates to Maven patients who are paying out of pocket.
    If the clinic offers such a discount, it will be a nonnull decimal 
    (NN.NN%, and theoretically NNN.NN%). If the clinic does not offer a discount, then
    this value will be NULL.
    """

    def __repr__(self) -> str:
        return f"Fertility Clinic {self.id}, name: {self.name}, network: {self.affiliated_network}"


class FertilityClinicLocation(TimeLoggedExternalUuidModelBase):
    __tablename__ = "fertility_clinic_location"

    name = Column(String(191), nullable=False, index=True)
    tin = Column(String(11), nullable=True)
    npi = Column(String(10), nullable=True)
    address_1 = Column(String(200), nullable=False)
    address_2 = Column(String(200), nullable=True)
    city = Column(String(40), nullable=False)
    subdivision_code = Column(String(6), nullable=False)
    postal_code = Column(String(20), nullable=False)
    country_code = Column(String(3), nullable=True, default="US")
    phone_number = Column(String(50), nullable=True)
    email = Column(String(120), nullable=True)

    fertility_clinic_id = Column(
        BigInteger,
        nullable=False,
    )
    fertility_clinic = relationship(
        "FertilityClinic",
        primaryjoin="FertilityClinicLocation.fertility_clinic_id == FertilityClinic.id",
        foreign_keys=fertility_clinic_id,
        backref=backref("locations", cascade="all, delete-orphan"),
    )
    contacts = relationship(
        "FertilityClinicLocationContact",
        back_populates="location",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"Fertility Clinic Location {self.name} for Fertility Clinic {self.fertility_clinic.name}"


class FertilityClinicLocationContact(TimeLoggedModelBase):
    __tablename__ = "fertility_clinic_location_contact"

    id = Column(Integer, autoincrement=True, primary_key=True)
    uuid = Column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))

    fertility_clinic_location_id = Column(
        BigInteger,
        ForeignKey("fertility_clinic_location.id"),
        nullable=False,
        doc="Id of the fertility_clinic_location that this person is a contact for.",
    )
    name = Column(String(120), nullable=True, default="")
    phone_number = Column(String(50), nullable=True, default="")
    email = Column(String(120), nullable=True, default="")
    location = relationship(
        "FertilityClinicLocation",
        back_populates="contacts",
    )

    def __repr__(self) -> str:
        return f"Fertility Clinic Contact {self.email} for {self.location.name}"


class FertilityClinicAllowedDomain(TimeLoggedExternalUuidModelBase):
    __tablename__ = "fertility_clinic_allowed_domain"

    domain = Column(String(120), nullable=False)
    fertility_clinic_id = Column(
        BigInteger,
        nullable=False,
    )
    fertility_clinic = relationship(
        "FertilityClinic",
        primaryjoin="FertilityClinicAllowedDomain.fertility_clinic_id == FertilityClinic.id",
        foreign_keys=fertility_clinic_id,
        backref=backref("allowed_domains", cascade="all, delete-orphan"),
    )

    def __repr__(self) -> str:
        return (
            f"Allowed Domain {self.id} for Fertility Clinic {self.fertility_clinic_id}"
        )
