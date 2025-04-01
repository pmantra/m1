from __future__ import annotations

import datetime
import enum
from decimal import ROUND_HALF_UP, Decimal, getcontext

from sqlalchemy import Column, Integer, String

from appointments.models.appointment import Appointment
from models import base
from utils.log import logger

getcontext().prec = 10

log = logger(__name__)


class CancellationPolicyName(str, enum.Enum):
    """
    The cancellation policy names.

    Reference api/schemas/io/cancellation_policies.py or the database to view the values associated with these policies.
    """

    STRICT = "strict"
    MODERATE = "moderate"
    FLEXIBLE = "flexible"
    CONSERVATIVE = "conservative"

    def __repr__(self) -> str:
        return self.value

    __str__ = __repr__

    @classmethod
    def default(cls) -> CancellationPolicyName:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Default CancellationPolicyName to use when setting on Providers
        """
        return cls.CONSERVATIVE


class CancellationPolicy(base.TimeLoggedModelBase):
    __tablename__ = "cancellation_policy"

    id = Column(Integer, primary_key=True)
    name = Column(String(140), nullable=False)
    slug = Column(String(128), unique=True)

    refund_0_hours = Column(Integer)
    refund_2_hours = Column(Integer)
    refund_6_hours = Column(Integer)
    refund_12_hours = Column(Integer)
    refund_24_hours = Column(Integer)
    refund_48_hours = Column(Integer)

    def __repr__(self) -> str:
        return f"<CancellationPolicy {self.id} [{self.name}]>"

    __str__ = __repr__

    def payment_required_for_appointment(
        self, appointment: Appointment, cancellation_datetime: datetime.datetime = None  # type: ignore[assignment] # Incompatible default for argument "cancellation_datetime" (default has type "None", argument has type "datetime")
    ) -> Decimal:
        """
        Determines the cancellation payment amount for the appointment.
        Cancellation payment is computed based on cancellation time. If not provided through
        the cancellation_datetime arg, the default value is utcnow()
        This function ONLY applies to member cancellations. If the provider has cancelled, the member should not be paying for the appointment
        """
        if not cancellation_datetime:
            cancellation_datetime = datetime.datetime.utcnow()

        log.info(
            "Determining cancellation payment amount for appointment",
            appointment_id=appointment.id,
            cancellation_policy_name=self.name,
            cancellation_datetime=str(cancellation_datetime),
        )

        refund_percent: int = 0

        if appointment.scheduled_start < cancellation_datetime:
            log.info(
                "No refund - appointment already started",
                appointment_id=appointment.id,
            )
        else:
            # determine the amount of the refund
            # note the values in the database have been used as the floor
            # (e.g. 6 < hrs <= 12 will use the refund_6_hours value to determine the refund)
            appointment_in = appointment.scheduled_start - cancellation_datetime

            seconds = 0
            if appointment_in.days:
                seconds = (60 * 60 * 24) * appointment_in.days
            seconds += appointment_in.seconds

            hours = seconds / (60 * 60)

            if 0 < hours <= 2:
                refund_percent = self.refund_0_hours or 0
            elif 2 < hours <= 6:
                refund_percent = self.refund_2_hours or 0
            elif 6 < hours <= 12:
                refund_percent = self.refund_6_hours or 0
            elif 12 < hours <= 24:
                refund_percent = self.refund_12_hours or 0
            elif 24 < hours <= 48:
                refund_percent = self.refund_24_hours or 0
            elif 48 < hours:
                refund_percent = self.refund_48_hours or 0

        pay_percent = abs(100 - refund_percent)
        pay_amount = appointment.product.price * Decimal(pay_percent) / 100
        pay_amount = pay_amount.quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        log.info(
            "Original amount and refund amount",
            appointment_id=appointment.id,
            original_amount=appointment.product.price,
            refund_pay_amount=pay_amount,
        )
        return pay_amount
