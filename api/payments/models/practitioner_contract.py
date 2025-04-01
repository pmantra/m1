import enum
from datetime import MAXYEAR, date

from sqlalchemy import Column, Date, Enum, ForeignKey, Index, Integer, and_, case
from sqlalchemy.dialects.mysql import DOUBLE
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from models import base
from utils.log import logger

log = logger(__name__)

RATE_PER_MESSAGE = 4


class ContractType(str, enum.Enum):
    BY_APPOINTMENT = "By appointment"
    FIXED_HOURLY = "Fixed hourly"
    FIXED_HOURLY_OVERNIGHT = "Fixed hourly overnight"
    HYBRID_1_0 = "Hybrid 1.0"
    HYBRID_2_0 = "Hybrid 2.0"
    NON_STANDARD_BY_APPOINTMENT = "Non standard by appointment"
    W2 = "W2"


class PractitionerContract(base.TimeLoggedModelBase):
    __tablename__ = "practitioner_contract"
    constraints = (Index("prac_id_end_date_idx", "practitioner_id", "end_date"),)

    id = Column(Integer, primary_key=True)

    practitioner_id = Column(
        Integer, ForeignKey("practitioner_profile.user_id"), nullable=False
    )
    created_by_user_id = Column(Integer, nullable=False)
    contract_type = Column(Enum(ContractType), nullable=False)

    practitioner = relationship("PractitionerProfile")
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    weekly_contracted_hours = Column(DOUBLE(precision=5, scale=2), nullable=True)
    fixed_hourly_rate = Column(DOUBLE(precision=5, scale=2), nullable=True)
    rate_per_overnight_appt = Column(DOUBLE(precision=5, scale=2), nullable=True)
    hourly_appointment_rate = Column(DOUBLE(precision=5, scale=2), nullable=True)
    non_standard_by_appointment_message_rate = Column(
        DOUBLE(precision=5, scale=2), nullable=True
    )

    @property
    def end_date_not_none(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # If end_dates doesnt exist, we can replace it by max possible date
        return self.end_date if self.end_date else date(MAXYEAR, 12, 31)

    # We declare active as a hybridy property because we need it to work in the context of SQL statements
    # In particular, we will be using active as a filter in the PractitionerContractView, so we need `.filter(User.active==True)` to work
    # The sql implementation of `active` is defined in `@active.expression`
    @hybrid_property
    def active(self):
        # Contract is active if start_date < now < end_date (if latter exists)
        today = date.today()
        if not self.end_date:
            return self.start_date <= today
        return self.start_date <= today and today <= self.end_date

    @active.expression  # type: ignore[no-redef] # Name "active" already defined on line 62
    def active(cls):
        today = date.today()
        return case(
            [
                (cls.end_date, and_(cls.start_date <= today, today <= cls.end_date)),
            ],
            else_=cls.start_date <= today,
        )

    @property
    def products(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.practitioner.products

    @property
    def rate_per_message(self) -> int:
        return RATE_PER_MESSAGE

    @hybrid_property
    def emits_fees(self) -> bool:
        log.info(
            "Accessing PractitionerContract property 'emits_fees'",
            contract_id=self.id,
            practitioner_id=self.practitioner_id,
        )
        return self.contract_type == ContractType.BY_APPOINTMENT
