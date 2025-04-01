import enum

from sqlalchemy import Column, Enum, ForeignKey, Integer
from sqlalchemy.ext.declarative import declared_attr

REGENERATION_DAYS = 14


class AppointmentMetaDataTypes(enum.Enum):
    PRACTITIONER_NOTE = "PRACTITIONER_NOTE"


class APPOINTMENT_STATES:
    scheduled = "SCHEDULED"
    overdue = "OVERDUE"
    completed = "COMPLETED"
    incomplete = "INCOMPLETE"
    overflowing = "OVERFLOWING"
    cancelled = "CANCELLED"
    occurring = "OCCURRING"
    payment_pending = "PAYMENT_PENDING"
    payment_resolved = "PAYMENT_RESOLVED"
    payment_pending_or_resolved = "PAYMENT_PENDING_OR_RESOLVED"
    disputed = "DISPUTED"


class PRIVACY_CHOICES:
    anonymous = "anonymous"
    basic = "basic"
    full_access = "full_access"


class RX_REASONS(str, enum.Enum):
    IS_ALLOWED = "is_allowed"
    NOT_ALLOWED_BY_ORG = "not_allowed_by_org"
    PHARMACY_INFO_NOT_ADDED = "pharmacy_info_not_added"
    NOT_SET_UP = "not_set_up"
    CANNOT_PRESCRIBE = "cannot_prescribe"
    NOT_LICENSED_IN_STATE = "not_licensed_in_state"
    MEMBER_OUTSIDE_US = "member_outside_us"


class ScheduleStates:
    available = "AVAILABLE"
    unavailable = "UNAVAILABLE"
    contingent = "CONTINGENT"


class ScheduleFrequencies(str, enum.Enum):
    MONTHLY = "MONTHLY"
    WEEKLY = "WEEKLY"
    DAILY = "DAILY"


class ScheduleObject:
    id = Column(Integer, primary_key=True)
    # Unavailable is default unless one of these two is set for a given time
    # on a schedule
    states = [v for k, v in ScheduleStates.__dict__.items() if not k.startswith("_")]

    state = Column(Enum(*states, name="state"), nullable=False, default="AVAILABLE")

    @declared_attr
    def schedule_id(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return Column(Integer, ForeignKey("schedule.id"))


class AppointmentTypes(str, enum.Enum):
    ANONYMOUS = "anonymous"
    EDUCATION_ONLY = "education_only"
    STANDARD = "standard"
