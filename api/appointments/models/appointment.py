from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import Decimal, getcontext
from typing import List, Optional

from ddtrace import tracer
from pytz import UTC, BaseTzInfo
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    and_,
    case,
    desc,
    func,
    or_,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Query, load_only, relationship

from appointments.models.appointment_meta_data import AppointmentMetaData
from appointments.models.constants import (
    APPOINTMENT_STATES,
    PRIVACY_CHOICES,
    RX_REASONS,
    AppointmentMetaDataTypes,
    AppointmentTypes,
)
from appointments.models.payments import (
    AppointmentFeeCreator,
    Credit,
    FeeAccountingEntry,
    FeeAccountingEntryTypes,
    PaymentAccountingEntry,
)
from authn.models.user import User
from common import stats
from common.services.stripe import StripeCustomerClient, stripe
from common.services.stripe_constants import PAYMENTS_STRIPE_API_KEY
from dosespot.constants import (
    DOSESPOT_GLOBAL_CLINIC_ID_V2,
    DOSESPOT_GLOBAL_CLINIC_KEY_V2,
)
from dosespot.resources.dosespot_api import DoseSpotAPI
from models import base
from models.common import PrivilegeType
from models.products import Product
from models.profiles import MemberProfile
from models.questionnaires import RecordedAnswer, RecordedAnswerSet
from payments.models.constants import PROVIDER_CONTRACTS_EMAIL
from provider_matching.models.constants import StateMatchType
from storage.connection import db
from utils.data import JSONAlchemy
from utils.foreign_key_metric import increment_metric
from utils.log import logger
from utils.mail import send_message
from utils.service_owner_mapper import service_ns_team_mapper

getcontext().prec = 10

MAX_MEMBER_CANCELLATIONS = 3
# How many days ahead should we generate events from elements by default?
REGENERATION_DAYS = 14
_SESSION_ID = "session_id"
_MEMBER_TOKEN = "member_token"
_PRACTITIONER_TOKEN = "practitioner_token"
_VIDEO_PROPERTIES = (_SESSION_ID, _MEMBER_TOKEN, _PRACTITIONER_TOKEN)


log = logger(__name__)


@dataclass
class PostSessionNoteUpdate:
    __slots__ = ("should_send", "post_session")
    should_send: bool
    post_session: AppointmentMetaData


class Appointment(base.TimeLoggedModelBase):
    __tablename__ = "appointment"
    __restricted_columns__ = frozenset(["video"])
    __calculated_columns__ = frozenset(["state", "api_id"])
    constraints = (Index("idx_privacy", "privacy"),)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Tuple[Index]", base class "ModelBase" defined the type as "Tuple[()]")

    MEMBER_ALLOWED_TIMESTAMPS = ("member_started_at", "member_ended_at")
    PRACTITIONER_ALLOWED_TIMESTAMPS = (
        "practitioner_started_at",
        "practitioner_ended_at",
        "member_ended_at",
    )

    states = APPOINTMENT_STATES
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("product.id"), nullable=False)
    product = relationship("Product", backref="appointments")
    member_schedule_id = Column(Integer, ForeignKey("schedule.id"), nullable=False)
    member_schedule = relationship("Schedule", backref="appointments")
    privacy = Column(String(20))
    purpose = Column(String(50))
    schedule_event_id = Column(Integer, ForeignKey("schedule_event.id"), nullable=True)
    schedule_event = relationship("ScheduleEvent", backref="appointments")
    """DEPRECATED: PlanSegment is deprecated"""
    plan_segment_id = 0
    scheduled_start = Column(DateTime(), nullable=False)
    scheduled_end = Column(DateTime(), nullable=False)
    member_started_at = Column(DateTime(), nullable=True)
    member_ended_at = Column(DateTime(), nullable=True)
    practitioner_started_at = Column(DateTime(), nullable=True)
    practitioner_ended_at = Column(DateTime(), nullable=True)
    phone_call_at = Column(DateTime(), nullable=True)
    rx_written_at = Column(DateTime(), nullable=True)
    video = Column(JSONAlchemy(Text(200)))
    cancellation_policy_id = Column(Integer, ForeignKey("cancellation_policy.id"))
    cancellation_policy = relationship("CancellationPolicy")
    cancelled_at = Column(DateTime(), nullable=True)
    cancelled_by_user_id = Column(Integer, ForeignKey("user.id"), nullable=True)
    cancelled_by = relationship("User")
    disputed_at = Column(DateTime(), nullable=True)
    reminder_sent_at = Column(DateTime(), nullable=True)
    client_notes = Column(Text)
    practitioner_notes = Column(Text)
    json = Column(JSONAlchemy(Text(1000)), default={})
    admin_comments = Column(Text)
    privilege_type = Column(
        db.Enum(PrivilegeType, values_callable=lambda _enum: [e.value for e in _enum])
    )
    state_match_type = Column(
        db.Enum(StateMatchType, values_callable=lambda _enum: [e.value for e in _enum])
    )
    need = relationship("Need", secondary="need_appointment", uselist=False)

    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        product = kwargs.get("product")
        scheduled_start = kwargs.get("scheduled_start")
        scheduled_end = kwargs.get("scheduled_end")

        if (
            scheduled_end
            and scheduled_start
            and product
            and ((scheduled_end - scheduled_start).seconds / 60) != product.minutes
        ):
            log.warning("%s has time that doesn't match product!", self)

        if scheduled_start and product and not scheduled_end:
            kwargs["scheduled_end"] = scheduled_start + datetime.timedelta(
                minutes=product.minutes
            )

        kwargs["video"] = kwargs.get("video", {})
        kwargs["json"] = kwargs.get("json", {})
        super().__init__(*args, **kwargs)

    def __repr__(self) -> str:
        if self.id:
            return f"<Appointment {self.id} [{self.state} @ {self.scheduled_start}]>"
        else:
            return f"<Appointment (Prospective) [{self.scheduled_start} - {self.scheduled_end}]>"

    __str__ = __repr__

    def __contains__(self, prospective) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        """
        Prospective should be an object with scheduled_start
        and scheduled_end, both of which should be datetime.datetime
        instances.
        """
        return self.contains(prospective)

    def contains(self, prospective, prep=0) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        prep_start = self.scheduled_start - datetime.timedelta(minutes=prep)
        pros_prep_start = prospective.scheduled_start - datetime.timedelta(minutes=prep)
        return (
            # prospective starts during this appointment
            (self.scheduled_start <= pros_prep_start < self.scheduled_end)
            or
            # prospective ends during this appointment
            (prep_start < prospective.scheduled_end <= self.scheduled_end)
            or
            # prospective completely overlaps this appointment
            (
                pros_prep_start <= self.scheduled_start
                and prospective.scheduled_end >= self.scheduled_end
            )
        )

    @property
    def rx_written_via(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (self.json or {}).get("rx_written_via")

    @property
    def pre_session(self) -> dict:
        return {"notes": self.client_notes}

    @property
    def admin_booked(self) -> bool:
        return (self.json or {}).get("admin_booked", False)

    @property
    def post_session_notes(self):  # type: ignore[no-untyped-def]
        model = f"{self.__tablename__}.appointment_metadata"
        try:
            results = (
                db.session.query(AppointmentMetaData)
                .filter(AppointmentMetaData.appointment_id == self.id)
                .order_by(
                    desc(AppointmentMetaData.modified_at),
                    desc(AppointmentMetaData.created_at),
                    desc(AppointmentMetaData.id),
                )
                .all()
            )
            increment_metric(True, model)
            return results
        except Exception as e:
            error_message = "Error in getting appointment_metadata in Appointment"
            log.error(error_message, error_type=e.__class__.__name__, error_msg=str(e))
            increment_metric(True, model, error_message)
            raise e

    def latest_post_session_note(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.post_session_notes[0] if self.post_session_notes else None

    @property
    def post_session(self) -> dict:
        latest_note = self.latest_post_session_note()
        if latest_note is None:
            return {"draft": None, "notes": "", "created_at": None, "modified_at": None}

        return {
            "draft": latest_note.draft,
            "notes": latest_note.content,
            "created_at": latest_note.created_at,
            "modified_at": latest_note.modified_at,
        }

    @hybrid_property
    def video_info_generated(self) -> bool:
        # Indicates whether *all* video info properties have been generated. For example:
        # {"session_id": "123"} -> False
        # {"session_id": "123", "member_token": "a", "practitioner_token": "b"} -> True
        return all(k in self.video for k in _VIDEO_PROPERTIES)

    @video_info_generated.expression  # type: ignore[no-redef]
    def video_info_generated(cls):
        # video.contains is an appropriate filter since we expect those property names not to show up as values.
        return and_(*(cls.video.contains(k) for k in _VIDEO_PROPERTIES))  # type: ignore[union-attr]

    @hybrid_property
    def is_first_for_practitioner_in_month(self) -> bool:
        start_of_month = datetime.datetime(
            year=self.scheduled_start.year, month=self.scheduled_start.month, day=1
        )
        if not self.practitioner:
            return True

        practitioner_product_ids = [p.id for p in (self.practitioner.products or [])]
        previous_appt = (
            db.session.query(Appointment)
            .filter(
                self.__class__.product_id.in_(practitioner_product_ids),
                self.__class__.cancelled_at.is_(None),
                self.__class__.scheduled_start >= start_of_month,
                self.__class__.scheduled_start < self.scheduled_start,
            )
            .first()
        )

        is_first = False if previous_appt else True
        log.debug(
            "Is first appt for practitioner this month",
            is_first=is_first,
            appointment_id=self.id,
            practitioner_id=self.practitioner.id,
        )
        return is_first

    @hybrid_property
    def is_intro(self):
        from appointments.services.common import purpose_is_intro

        return purpose_is_intro(self.purpose)

    @is_intro.expression  # type: ignore[no-redef] # Name "is_intro" already defined on line 276
    def is_intro(cls):
        if not cls.purpose:
            return False
        return case(
            [
                (
                    or_(
                        cls.purpose.like("%introduction_%"),
                        cls.purpose.in_(
                            [
                                "introduction",
                                "birth_needs_assessment",
                                "postpartum_needs_assessment",
                            ]
                        ),
                    ),
                    True,
                )
            ],
            else_=False,
        )

    def update_post_session(
        self, note: str, draft: bool = False
    ) -> PostSessionNoteUpdate:
        latest_note = self.latest_post_session_note()
        if latest_note is None:
            log.info(
                "Create a post appointment note.",
                draft=draft,
                appointment_id=self.id,
            )
            return PostSessionNoteUpdate(
                post_session=self.create_post_session(note, draft),
                should_send=not draft,
            )

        if (latest_note.content == note) and (latest_note.draft == draft):
            return PostSessionNoteUpdate(post_session=latest_note, should_send=False)

        if not latest_note.draft and draft:
            log.warning(
                "AppointmentMetaData went from draft: false to draft: true",
                appointment_metadata_id=latest_note.id,
            )

        latest_note.content = note
        latest_note.draft = draft
        log.info(
            "Update a post appointment note.",
            draft=draft,
            appointment_id=self.id,
        )
        return PostSessionNoteUpdate(post_session=latest_note, should_send=not draft)

    def create_post_session(self, note: str, draft: bool = False) -> AppointmentMetaData:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return AppointmentMetaData(
            type=AppointmentMetaDataTypes.PRACTITIONER_NOTE,
            appointment_id=self.id,
            content=note,
            draft=draft,
        )

    @property
    def payment(self) -> PaymentAccountingEntry | None:
        return (
            db.session.query(PaymentAccountingEntry)
            .filter(PaymentAccountingEntry.appointment_id == self.id)
            .first()
        )

    @property
    def staff_cost(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (self.json or {}).get("staff_cost")

    @staff_cost.setter
    def staff_cost(self, val):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        log.debug("Setting staff_cost for Appointment: (%s) to %s", self.id, val)
        self.json["staff_cost"] = val

    @property
    def practitioner_fee_paid(self) -> int:
        if self.fees:
            return sum(fee.amount for fee in self.fees)
        return 0

    @property
    def fee_paid(self) -> Decimal:
        fee_collected = Decimal(0)

        if self.payment and self.payment.captured_at:
            if self.payment.amount:
                fee_collected += Decimal(self.payment.amount)

        if self.credits:
            fee_collected += sum(
                credit.amount for credit in self.credits if credit.used_at is not None
            )

        return fee_collected

    @property
    def fee_paid_at(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        candidates = []

        if self.payment and self.payment.captured_at:
            candidates.append(self.payment.captured_at)

        if self.credits:
            used_ats = [c.used_at for c in self.credits if c.used_at is not None]
            if used_ats:
                candidates.append(max(used_ats))

        return max(candidates) if candidates else None

    @property
    def fee_creator(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return AppointmentFeeCreator.for_appointment(self)

    @property
    def member(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.member_schedule.user if self.member_schedule else None

    @property
    def member_name(self) -> str:
        member_name = "an anonymous user"
        if not self.is_anonymous:
            member_name = self.member.full_name
        return member_name

    @property
    def member_id(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.member.id if self.member else None

    @property
    def practitioner(self) -> User | None:
        return self.product.practitioner if self.product else None

    @property
    def practitioner_id(self) -> int | None:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.practitioner.id if self.practitioner else None

    @property
    def started_at(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.member_started_at and self.practitioner_started_at:
            return max(self.member_started_at, self.practitioner_started_at)

    @property
    def ended_at(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.started_at and self.member_ended_at and self.practitioner_ended_at:
            return min(self.member_ended_at, self.practitioner_ended_at)

    @property
    def total_available_credits(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        with db.session.no_autoflush:
            available = Credit.available_for_appointment(self)
            return sum(a.amount for a in available) if available else 0

    @property
    def is_anonymous(self) -> bool:
        return self.privacy == PRIVACY_CHOICES.anonymous

    @property
    def ratings(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.json.get("ratings", {})

    @property
    def rating(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not self.ratings:
            return
        i = 0
        score = 0.0
        for r in self.ratings:
            score_i = self.ratings[r]
            if score_i:
                try:
                    score_i = int(score_i)
                except ValueError:
                    log.debug(
                        "Appointment rating cannot be parsed as an integer.",
                        appointment_id=self.id,
                        rating_key=r,
                    )
                    continue
                else:
                    i += 1
                    score += score_i
        if i > 0:
            score = score / i
        return score

    @property
    def cancelled_note(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.json.get("cancelled_note")

    @property
    def provider_addenda(self):  # type: ignore[no-untyped-def]
        from models.questionnaires import ProviderAddendum

        model = f"{self.__tablename__}.provider_addendum"
        try:
            results = (
                db.session.query(ProviderAddendum)
                .filter_by(appointment_id=self.id)
                .order_by(ProviderAddendum.submitted_at.desc())
                .all()
            )
            increment_metric(True, model)
            return results
        except Exception as e:
            error_message = "Error in getting provider_addendum in Appointment"
            log.error(error_message, error_type=e.__class__.__name__, error_msg=str(e))
            increment_metric(True, model, error_message)
            raise e

    # When updating the logic for state computation,
    # make sure to update the corresponding logic in mpractice/models/appointment.py
    @property
    def state(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.cancelled_at:
            return self.states.cancelled
        elif self.disputed_at:
            return self.states.disputed
        elif self.scheduled_start and self.started_at:
            if self.ended_at:
                if self.fee_paid_at and self.fee_paid != 0:
                    return self.states.payment_resolved
                else:
                    return self.states.payment_pending
            elif self.scheduled_end > datetime.datetime.utcnow() and not (
                self.member_ended_at or self.practitioner_ended_at
            ):
                return self.states.occurring
            elif (
                self.scheduled_end
                and self.scheduled_end < datetime.datetime.utcnow()
                and not self.ended_at
            ):
                return self.states.overflowing
            elif self.member_ended_at or self.practitioner_ended_at:
                return self.states.incomplete
        elif self.scheduled_start:
            if self.scheduled_start < datetime.datetime.utcnow():
                return self.states.overdue
            else:
                return self.states.scheduled

        log.warning(f"State of Appointment: ({self.id}) is going to be None!")

    @property
    def is_international(self) -> bool:
        if self.privilege_type:
            return self.privilege_type == PrivilegeType.INTERNATIONAL
        return False

    @property
    def requires_fee(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.member.email.endswith("@mavenclinic.com"):
            log.info(
                "Appointment for internal user, does not require fee.",
                appointment_id=self.id,
            )
            return False

        if not self.practitioner:
            log.info(
                "Appointment with no practitioner, does not require fee.",
                appointment_id=self.id,
            )
            return False

        if self.practitioner.is_care_coordinator:
            log.info(
                "Appointment with care coordinator, does not require fee.",
                appointment_id=self.id,
            )
            return False

        prac_id = self.practitioner.id
        prac_profile = self.practitioner.practitioner_profile
        appt_id = self.id
        prac_is_staff = prac_profile.is_staff

        prac_active_contract = prac_profile.active_contract
        if not prac_active_contract:
            # Notify Provider Ops that practitioner has no contract
            notification_title = "Provider has no active contract"
            notification_text = (
                f"Provider [{prac_id}] has no active contract.\n"
                f"Appointment {appt_id} has been completed, but the provider has no active contract, so it's unclear if a fee should be generated.\n"
                f"For now, we are falling back to using the provider's is_staff value, which is {prac_is_staff}, "
                f"so a fee will {'not ' if prac_is_staff else ''}be generated for the appointment.\n"
                "Please set an active contract for this provider."  # Add 'and alert engineering if a fee needs to be created.' when fallback to is_staff is removed
            )

            send_message(
                to_email=PROVIDER_CONTRACTS_EMAIL,
                subject=notification_title,
                text=notification_text,
                internal_alert=True,
                production_only=True,
            )
            # DD log monitor: https://app.datadoghq.com/monitors/121681314
            log.warning(
                notification_title,
                practitioner_id=prac_id,
                appointment_id=appt_id,
                prac_is_staff=prac_is_staff,
            )
            # Fallback to using is_staff to decide if generating a fee (which means do nothing else in this if statement given that the is_staff check is down the road)
            # Note: fallback to be deprecated once is_staff is deprecated
        else:
            # If contract emits_fee is inconsistent with is_staff, notify Provider Ops and fallback to is_staff
            # Note: fallback to be deprecated once is_staff is deprecated
            if prac_active_contract.emits_fees == prac_profile.is_staff:
                notification_title = (
                    "Provider active contract inconsistent with is_staff value"
                )
                notification_text = (
                    f"Provider [{prac_id}] active contract [{prac_active_contract.id}] is of type {prac_active_contract.contract_type.value}, "
                    f"but their is_staff value is {prac_is_staff}, which is inconsistent for that contract type.\n"
                    f"Appointment {appt_id} has been completed and we need the provider's active contract to decide if a fee should be generated.\n"
                    "Given this inconsistency, we are falling back to using the provider's is_staff value, "
                    f'so a fee will {"not " if prac_is_staff else ""}be generated for the appointment'
                    "Please update either the is_staff value or the contract type for this provider to make them consistent."  # Add 'and alert engineering if a fee needs to be created.' when fallback to is_staff is removed
                )

                send_message(
                    to_email=PROVIDER_CONTRACTS_EMAIL,
                    subject=notification_title,
                    text=notification_text,
                    internal_alert=True,
                    production_only=True,
                )
                # DD log monitor: https://app.datadoghq.com/monitors/121685718
                log.warning(
                    notification_title,
                    practitioner_id=prac_id,
                    appointment_id=appt_id,
                    prac_is_staff=prac_is_staff,
                    contract_type=prac_active_contract.contract_type.value,
                )
            else:  # This is the happy path (practitioner contract exists and is consistent with is_staff)
                active_contract_emits_fee = prac_active_contract.emits_fees
                log.info(
                    "Correctly using active_contract.emits_fee to decide if Appointment fee should be generated",
                    practitioner_id=prac_id,
                    appointment_id=appt_id,
                    prac_is_staff=prac_is_staff,
                    contract_type=prac_active_contract.contract_type.value,
                    active_contract_emits_fee=active_contract_emits_fee,
                )
                return active_contract_emits_fee

        # Fallback
        if self.practitioner.practitioner_profile.is_staff:
            log.info(
                "Appointment for staff provider does not require fee.",
                practitioner_id=prac_id,
                appointment_id=appt_id,
                prac_is_staff=prac_is_staff,
            )
            return False
        return True

    def pay_with_reserved_credits(self, amount=None, skip_commit=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # amount can be less than product price in the event of a cancellation
        amount = amount or self.product.price
        reserved = Credit.reserved_for_appointment(self)

        total_credit = Decimal(0)
        for credit in sorted(reserved, key=lambda x: x.amount, reverse=True):
            if total_credit >= amount:
                credit.appointment_id = None
                log.info(
                    "Releasing unnecessary credit",
                    credit_id=credit.id,
                    appointment_id=self.id,
                )
            elif (credit.amount + total_credit) > amount:
                import payments.utils

                credit, new_credit = payments.utils.split_credit(
                    credit,
                    amount - total_credit,
                )
                db.session.add(new_credit)

                log.info(
                    "Releasing unnecessary credit",
                    new_credit_id=new_credit.id,
                    appointment_id=self.id,
                )
                credit.used_at = datetime.datetime.utcnow()
                total_credit += credit.amount
            elif (credit.amount + total_credit) <= amount:
                credit.used_at = datetime.datetime.utcnow()
                total_credit += credit.amount
            db.session.add(credit)
        if skip_commit:
            db.session.flush()
        else:
            db.session.commit()
        log.info(
            "Paying Appointment with credits.",
            total_credit=total_credit,
            amount=amount,
            appointment_id=self.id,
        )

        return Decimal(amount) - Decimal(total_credit)

    def authorize_payment(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        from payments.services.appointment_payments import AppointmentPaymentsService

        if self.id is None:
            log.error(
                "Attempted to call authorize_payment() for a null appt-id!",
                product_id=self.product.id,
                member_id=self.member_id,
                scheduled_start=self.scheduled_start,
            )
            return None

        return AppointmentPaymentsService(db.session).authorize_payment(
            appointment_id=self.id,
            product_id=self.product.id,
            member_id=self.member_id,
            scheduled_start=self.scheduled_start,
        )

    def collect_practitioner_fees(self, price=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Price can be less than product price if the appointment is cancelled
        and we pay fees based on a partial payment.
        """
        log.info("Starting collect_practitioner_fees", appointment_id=self.id)
        if not self.requires_fee:
            log.info(
                "Won't collect fees, appointment does not require one",
                appointment_id=self.id,
            )
            return
        if not self.practitioner:
            log.info(
                "Practitioner not found when attempting to collect fees",
                appointment_id=self.id,
            )
            return

        price = price or self.product.price
        log.info(
            "Collecting fees for practitioner",
            price=price,
            practitioner_id=self.practitioner.id,
            appointment_id=self.id,
        )

        fee_creator = self.fee_creator
        if fee_creator:
            fee_amount = float(price) * (fee_creator.fee_percentage / 100)
            entry = FeeAccountingEntry(
                appointment=self,
                amount=fee_amount,
                practitioner_id=self.practitioner.id,
                type=FeeAccountingEntryTypes.APPOINTMENT,
            )
            db.session.add(entry)
            log.info(
                "Fee created for appointment",
                appointment_id=self.id,
                fee_amount=fee_amount,
                price=str(price),
                fee_percentage=fee_creator.fee_percentage,
                practitioner_id=self.practitioner.id,
            )
            return entry
        else:
            log.warning(
                "No FeeCreator for practitioner!", practitoner_id=self.practitioner.id
            )
            # Log monitored by https://app.datadoghq.com/monitors/114414327

    def is_first_malpractice_charge_in_month(self) -> bool:
        """
        We use this check to flag potential double charges but this check should not be used on it's own as it
        relies on malpractice charges to be $10 and to have appointment + message to be None
        """
        start_of_month = datetime.datetime(
            year=self.scheduled_start.year, month=self.scheduled_start.month, day=1
        )

        if not self.practitioner:
            log.error(
                "No practitioner found when attempting to check if this is the first malpractice charge in the month",
                appointment_id=self.id,
            )
            return False

        malpractice_charge = FeeAccountingEntry.query.filter(
            FeeAccountingEntry.practitioner_id == self.practitioner.id,
            FeeAccountingEntry.created_at >= start_of_month,
            FeeAccountingEntry.amount == -10,
            FeeAccountingEntry.appointment_id.is_(None),
            FeeAccountingEntry.message_id.is_(None),
        ).first()

        return False if malpractice_charge else True

    def collect_malpractice_fee(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        is_first_appt = self.is_first_for_practitioner_in_month

        if not self.practitioner:
            log.error(
                "No practitioner found when attempting to collect malpractice fee",
                appointment_id=self.id,
            )
            return

        if is_first_appt and (self.cancelled_at is None):
            profile = self.practitioner.practitioner_profile
            if profile.malpractice_opt_out:
                log.debug(
                    "Not charging practitioner for malpractice (optout)",
                    practitioner_id=self.practitioner.id,
                )
            else:
                # Double checking here to see if this is the first malpractice charge this month
                is_first_malpractice_charge = (
                    self.is_first_malpractice_charge_in_month()
                )
                if is_first_malpractice_charge:
                    log.debug(
                        "Charging malpractice for practitioner",
                        appointment_id=self.id,
                        practitioner_id=self.practitioner.id,
                    )
                    fee = FeeAccountingEntry(
                        amount=-10,
                        practitioner=self.practitioner,
                        type=FeeAccountingEntryTypes.MALPRACTICE,
                    )
                    db.session.add(fee)
                    log.debug(
                        "Added fae for malpractice fee for practitioner",
                        fae_id=fee.id,
                        appointment_id=self.id,
                        practitioner_id=self.practitioner.id,
                    )
                    return fee
                else:
                    log.error(
                        "Double malpractice charge detected",
                        appointment_id=self.id,
                        practitioner_id=self.practitioner.id,
                    )
                    stats.increment(
                        metric_name="api.appointments.models.appointment.collect_malpractice_fee.malpractice_double_charge",
                        pod_name=stats.PodNames.CARE_DISCOVERY,
                    )

    def cancel(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        user_id: int,
        cancelled_note: str = None,  # type: ignore[assignment] # Incompatible default for argument "cancelled_note" (default has type "None", argument has type "str")
        admin_initiated: bool = False,
        skip_commit: bool = False,
    ):
        from appointments.tasks.appointment_notifications import (
            cancel_member_appointment_confirmation,
            send_member_cancellation_note,
            send_practitioner_cancellation_note,
        )

        log.info(
            "Starting to cancel appointment",
            appointment_id=self.id,
            admin_initiated=admin_initiated,
        )

        def _cancel() -> None:
            self.cancelled_at = datetime.datetime.utcnow()
            self.cancelled_by_user_id = user_id
            self.json["cancelled_note"] = cancelled_note
            cancel_member_appointment_confirmation.delay(self.id)

        if user_id == self.product.practitioner.id:
            log.info(
                "Canceling appointment for practitioner",
                appointment_id=self.id,
                practitioner_id=user_id,
                admin_initiated=admin_initiated,
            )

            if self.payment:
                self.payment.cancel()

            self.release_credits()

            if not admin_initiated:
                send_member_cancellation_note.delay(
                    self.id, cancelled_note, team_ns="virtual_care"
                )

            _cancel()
            return self

        elif user_id == self.member.id:
            log.info(
                "Canceling appointment for member",
                appointment_id=self.id,
                member_id=user_id,
                admin_initiated=admin_initiated,
            )

            # update the number of member cancellations
            self._update_member_cancellations(admin_initiated)
            # Use the cancellation policy from the provider at the time of cancellation
            cancellation_policy = (
                self.product.practitioner.practitioner_profile.default_cancellation_policy
            )
            to_pay = cancellation_policy.payment_required_for_appointment(self)
            entry = None

            log.info(
                "Canceling appointment using cancellation policy",
                appointment_id=self.id,
                to_pay=to_pay,
                cancellation_policy_name=cancellation_policy.name,
            )

            if to_pay and self.payment:
                balance = self.pay_with_reserved_credits(
                    amount=to_pay, skip_commit=skip_commit
                )
                self.payment.capture(amount=balance)
                entry = self.collect_practitioner_fees(price=to_pay)
                log.info(
                    "Captured payment for cancel appointment", appointment_id=self.id
                )
            elif to_pay:
                balance = self.pay_with_reserved_credits(
                    amount=to_pay, skip_commit=skip_commit
                )
                if balance != 0:
                    log.warning(
                        "Balance should be 0 for cancel appointment",
                        appointment_id=self.id,
                    )
                entry = self.collect_practitioner_fees(price=to_pay)
            else:
                if self.payment:
                    self.payment.cancel(skip_commit=skip_commit)
                log.info(
                    "No payment required to cancel appointment",
                    appointment_id=self.id,
                    user_id=user_id,
                )

            self.release_credits()

            if not admin_initiated:
                practitioner_receives = str(entry.amount) if entry else str(0)
                send_practitioner_cancellation_note.delay(
                    self.id,
                    float(practitioner_receives),
                    cancelled_note,
                    team_ns="virtual_care",
                )

            _cancel()
            return self

        else:
            log.error(
                "Not canceling appointment for unaffiliated user",
                appointment_id=self.id,
                user_id=user_id,
            )

    def _update_member_cancellations(self, admin_initiated: bool = False) -> None:  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Updates the number of member cancellations.
        Includes both member initiated and member no-show cancellations.
        """
        from appointments.tasks.appointments import update_member_cancellations

        service_ns_tag = "appointments"
        team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
        update_member_cancellations.delay(
            self.id, admin_initiated, service_ns=service_ns_tag, team_ns=team_ns_tag
        )

    def _collect_plan_cancellation_fees(self, to_pay):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        mp = self.member.member_profile

        if mp.json.get("payment_collection_failed"):
            log.info(
                "Member already failed pymt - not collecting!", user_id=self.member.id
            )
            return

        try:
            stripe_client = StripeCustomerClient(PAYMENTS_STRIPE_API_KEY)
            penalty_charge = stripe_client.create_charge(
                to_pay, user=self.member, capture=True
            )
            log.debug("Charged member for cancellation penalty %s", penalty_charge)
        except stripe.error.CardError:
            log.info(
                f"Cannot charge cancel for {self} - marking bad {self.member} for now"
            )

            now = datetime.datetime.utcnow()
            mp.json["payment_collection_failed"] = str(now)
            db.session.add(mp)

            return

        entry = self.collect_practitioner_fees(price=to_pay)
        log.info(
            f"Collected practitioner fee {entry} for Appointment: ({self.id}) in cancellation."
        )

        if penalty_charge:
            self.json["plan_cancellation_paid_amount"] = round(
                float(penalty_charge.amount / 100), 3
            )
            self.json["plan_cancellation_charge_id"] = str(penalty_charge.id)

        return entry

    def uncancel(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if (self.cancelled_at is None) or (self.cancelled_by_user_id is None):
            log.info(
                "Unable to uncancel appointment - not a cancelled appointment",
                appointment_id=self.id,
            )
            return

        if not self.practitioner_id:
            log.info(
                "Unable to uncancel appointment - no associated provider",
                appointment_id=self.id,
            )
            return

        # NB: it would be nice to use managed_appointment_booking_availability
        # to check for conflicts here, but it doesn't work properly on past appointments,
        # and evidently it's an ops workflow to uncancel past appointments so providers can
        # get paid for them in cases where our system marked them as cancelled but they actually happened.
        # Common cases are phone appointments or back-to-back booked appts w/ the same member where
        # they just stay on the same call.
        log.info("Un-canceling appointment", appointment_id=self.id)

        self.json["uncancellation"] = {
            "cancelled_at": str(self.cancelled_at),
            "cancelled_by_user_id": self.cancelled_by_user_id,
        }
        self.cancelled_at = None
        self.cancelled_by_user_id = None
        db.session.add(self)
        db.session.commit()
        log.info("Completed uncanceling appointment", appointment_id=self.id)

    def release_credits(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        reserved = Credit.reserved_for_appointment(self)
        i = 0

        for credit in reserved:
            if not credit.used_at:
                credit.appointment_id = None
                db.session.add(credit)
                i += 1

        log.info("Released credits for appointment", credits=i, appointment_id=self.id)

    @classmethod
    def retain_data_for_user(cls, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return any(a.state != cls.states.cancelled for a in user.schedule.appointments)

    @classmethod
    def pending_for_user(cls, user, scheduled_after=None, practitioner=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        scheduled_start = scheduled_after or datetime.datetime.utcnow()

        pending = (
            db.session.query(cls)
            .filter(
                cls.scheduled_start > scheduled_start,
                cls.member_schedule_id == user.schedule.id,
                cls.cancelled_at == None,
            )
            .order_by(cls.scheduled_start.asc())
        )

        if practitioner:
            pending = pending.filter(
                cls.product_id.in_([p.id for p in practitioner.products])
            )

        return pending.all()

    @classmethod
    def completed_for_user(cls, member_profile: MemberProfile, completed_before=None):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        completed = db.session.query(cls).filter(
            cls.member_started_at is not None,
            cls.member_ended_at is not None,
            cls.practitioner_started_at is not None,
            cls.practitioner_ended_at is not None,
            cls.member_schedule_id == member_profile.schedule.id,
            cls.cancelled_at is None,
        )

        if completed_before:
            completed = completed.filter(cls.scheduled_end <= completed_before)

        completed = completed.all()
        log.debug(
            f"Got {len(completed)} completed appts for User: ({member_profile.user_id})"
        )
        return completed

    @classmethod
    def completed(cls) -> List[Appointment]:
        completed = (
            db.session.query(cls)
            .filter(
                cls.member_started_at is not None,
                cls.member_ended_at is not None,
                cls.practitioner_started_at is not None,
                cls.practitioner_ended_at is not None,
                cls.cancelled_at is None,
            )
            .all()
        )
        return completed

    def is_completed(self) -> bool:
        return (
            self.member_started_at is not None
            and self.member_ended_at is not None
            and self.practitioner_started_at is not None
            and self.practitioner_ended_at is not None
            and self.cancelled_at is None
        )

    def _starts_in_minutes(self, now: datetime.datetime | None = None) -> int:
        """Add one min so we force to round up since we use an integer"""
        now = now or datetime.datetime.utcnow()
        return int(((self.scheduled_start - now).total_seconds()) / 60) + 1

    def starts_in(self, now=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        starts_in_seconds = self._starts_in_minutes(now=now) * 60
        return str(datetime.timedelta(seconds=starts_in_seconds))

    @hybrid_property
    def api_id(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        A helper for getting an API ID that is expensive due to delayed import.
        If possible do this in the view where the import is already availible.
        """
        from appointments.services.common import obfuscate_appointment_id

        if self.id:
            return obfuscate_appointment_id(self.id)

    @property
    def user_recent_code(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        from models.referrals import ReferralCodeUse

        if self.payment and (self.payment.amount == self.product.price):
            return

        if self.json.get("user_recent_code"):
            log.debug("Returning override code for: Appointment: (%s)", self.id)
            return self.json["user_recent_code"]

        else:
            x_days_ago = self.scheduled_start - datetime.timedelta(days=1000)

            recent_use_query = (
                db.session.query(ReferralCodeUse)
                .filter(
                    ReferralCodeUse.user_id == self.member.id,
                    ReferralCodeUse.created_at > x_days_ago,
                    ReferralCodeUse.created_at < self.scheduled_start,
                )
                .order_by(ReferralCodeUse.created_at.desc())
            )

            recent_use = recent_use_query.first()
            if recent_use:
                return recent_use.code.code

    def rx_from_appointment(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        log.debug("Checking RX written for Appointment: (%s)", self.id)

        if not self.practitioner:
            log.error(
                "No practitioner found when locating rx from appointment",
                appointment_id=self.id,
            )
            return []

        profile = self.practitioner.practitioner_profile
        dosespot = DoseSpotAPI(
            clinic_id=DOSESPOT_GLOBAL_CLINIC_ID_V2,
            clinic_key=DOSESPOT_GLOBAL_CLINIC_KEY_V2,
            user_id=profile.dosespot["user_id"],
            maven_user_id=profile.user_id,
        )

        patient = self.member.member_profile
        patient_info = patient.get_patient_info(profile.user_id)
        pharmacy_info = patient.get_prescription_info()
        patient_id = patient_info.get("patient_id")

        if not patient_id:
            log.info(f"NO patient ID for Appointment: ({self.id}) for rx written")
            return []

        user_next_appts = self.__class__.pending_for_user(
            self.member,
            scheduled_after=self.scheduled_end,
            practitioner=self.practitioner,
        )
        upper_limit = None
        if user_next_appts:
            upper_limit = user_next_appts[0].scheduled_start

        from_appt = []
        meds = dosespot.medication_list(
            patient_id=patient_id, start_date=self.scheduled_end, end_date=upper_limit
        )
        for med in meds:
            # TODO: remove checks on DateWritten after DoseSpot v2 is fully rolled out.
            #  The medication_list() function call should only return medications written between
            #  the previous appointment's end time and the next appointment's start time if exists.
            if med.get("DateWritten") is None:
                log.debug("No DateWritten for med: %s", med.get("PrescriptionId"))
                continue

            if med.get("DateWritten") > self.scheduled_end:
                if upper_limit and med.get("DateWritten") > upper_limit:
                    continue
                if med.get("PharmacyId") == pharmacy_info.get("pharmacy_id"):
                    med["pharmacy_name"] = (
                        pharmacy_info.get("pharmacy_info") or {}
                    ).get("StoreName")

                # should have been after this appt ended and
                # before next started
                log.debug(
                    "RX written for Appointment: (%s) - DS Med ID %s (Patient ID %s)",
                    self.id,
                    med.get("MedicationId"),
                    patient_id,
                )
                from_appt.append(med)

        log.debug("%d meds for Appointment: (%s)", len(from_appt), self.id)
        return from_appt

    @property
    def is_rx_ready(self) -> bool:
        rx = self.rx_from_appointment()
        return bool(
            len(rx) > 0
            and rx[0].get("PrescriptionStatus")
            and (rx[0].get("PrescriptionStatus") != "Error")
        )

    @property
    def repeat_patient(self) -> bool:
        past_appointments_with_this_practitioner_count = (
            Appointment.query.filter(
                Appointment.member_schedule_id == self.member_schedule_id
            )
            .filter(Appointment.cancelled_at == None)
            .filter(Appointment.scheduled_start < datetime.datetime.now())
            .filter(Appointment.id != self.id)
            .join(Product)
            .filter(Product.user_id == self.product.user_id)
            .count()
        )

        return past_appointments_with_this_practitioner_count > 0

    @property
    def rx_enabled(self) -> bool:
        if not self.practitioner:
            log.error(
                "No practitioner found when locating rx from appointment",
                appointment_id=self.id,
            )
            return False

        from providers.service.provider import ProviderService

        if self.practitioner is None:
            raise AttributeError("Missing practitioner")
        elif self.practitioner.profile is None:
            raise AttributeError("Missing practitioner profile")

        return all(
            [
                not self.is_anonymous,
                self.member.member_profile.enabled_for_prescription,
                ProviderService().can_prescribe_to_member(
                    self.practitioner.profile.user_id,  # type: ignore[union-attr] # Item "None" of "Union[PractitionerProfile, MemberProfile, None]" has no attribute "user_id"
                    self.member.member_profile.prescribable_state,
                    # if the practitioner profile is available when calling
                    # `can_prescribe_to_member` always include it to avoid
                    # downstream implementations from refetching it. The
                    # additional fetch is a non-trivial cost and can be as much
                    # as 30 additional queries per appointment.
                    self.practitioner.profile,
                ),
            ]
        )

    @property
    def rx_reason(self) -> Optional[String]:
        prescription_info = self.member.profile.get_prescription_info()
        if self.rx_enabled:
            return RX_REASONS.IS_ALLOWED.value  # type: ignore[return-value] # Incompatible return value type (got "str", expected "Optional[String]")
        if self.member.organization and (
            not self.member.organization.rx_enabled
            or self.member.organization.education_only
        ):
            return RX_REASONS.NOT_ALLOWED_BY_ORG.value  # type: ignore[return-value] # Incompatible return value type (got "str", expected "Optional[String]")
        if (
            not prescription_info["pharmacy_id"]
            or not prescription_info["pharmacy_info"]
            or not self.member.profile.enabled_for_prescription
        ):
            return RX_REASONS.PHARMACY_INFO_NOT_ADDED.value  # type: ignore[return-value] # Incompatible return value type (got "str", expected "Optional[String]")
        return None

    @staticmethod
    def get_appointment_type_from_privilege_type(
        privilege_type: str, privacy: str | None
    ) -> AppointmentTypes:
        if not privacy:
            privacy = "basic"

        # NB: we are retiring the Anonymous types for new appointments as part of Scope of Practice
        # (https://docs.google.com/document/d/1ttelbf3aQfaqB8r4YdHi-E8C4ek6QI0lgXQu6N1DYJM/edit?tab=t.0)
        # but this code remains to deal with existing appointments with anonymous type.
        if privilege_type == PrivilegeType.ANONYMOUS.value:
            return AppointmentTypes.ANONYMOUS
        elif privilege_type == PrivilegeType.EDUCATION_ONLY.value:
            return AppointmentTypes.EDUCATION_ONLY
        elif privilege_type == PrivilegeType.INTERNATIONAL.value:
            if privacy == PRIVACY_CHOICES.anonymous:
                return AppointmentTypes.ANONYMOUS
            else:
                return AppointmentTypes.EDUCATION_ONLY
        # Default value
        return AppointmentTypes.STANDARD

    @property
    def appointment_type(self) -> AppointmentTypes:
        return Appointment.get_appointment_type_from_privilege_type(
            self.privilege_type, self.privacy
        )

    @property
    def need_id(self) -> int | None:
        return self.need.id if self.need else None

    @classmethod
    @tracer.wrap()
    def appointments_from_date_range(
        cls,
        practitioner_id: int,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> Query:
        start_of_range = start_date.replace(
            hour=0, minute=0, second=0, microsecond=0
        ).astimezone(UTC)
        end_of_range = end_date.replace(
            hour=23, minute=59, second=59, microsecond=999999
        ).astimezone(UTC)

        return (
            db.session.query(Appointment)
            .join(Product)
            .filter(
                Product.user_id == practitioner_id,
                Appointment.cancelled_at.is_(None),
                Appointment.scheduled_start >= start_of_range,
                Appointment.scheduled_start <= end_of_range,
            )
        )

    @classmethod
    @tracer.wrap()
    def intro_appointments_from_date_range(
        cls,
        practitioner_id: int,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
        load_only_scheduled_start: bool = True,
    ) -> List[Appointment]:
        start_of_range = start_date.replace(
            hour=0, minute=0, second=0, microsecond=0
        ).astimezone(UTC)
        end_of_range = end_date.replace(
            hour=23, minute=59, second=59, microsecond=999999
        ).astimezone(UTC)

        intro_appts_in_date_range_query = (
            db.session.query(Appointment)
            .join(Product)
            .filter(
                Product.user_id == practitioner_id,
                Appointment.cancelled_at.is_(None),
                Appointment.scheduled_start >= start_of_range,
                Appointment.scheduled_start <= end_of_range,
                Appointment.is_intro == True,
            )
        )

        if load_only_scheduled_start:
            intro_appts_in_date_range = intro_appts_in_date_range_query.options(
                load_only("scheduled_start")
            ).all()
        else:
            intro_appts_in_date_range = intro_appts_in_date_range_query.all()

        # TODO: We always use this method to just count how many intro appts happened, we dont really need to return the intro appts and later on count them, we should be able to do the counting in the db query straight away. This would be a major refactor though.

        # TODO: Although we are discovering this issue when testing pooled_calendar, the fact is that intro_appointments_from_date_range is alredy being used when calling
        # products/<prod_id>/availability, when getting CAs availability. How come we have not being alerted that this endpoint is also super slow for CAs given its using this same function
        # Can we find traces specific for intro_appointments_from_date_range so we can look at latency for it when callend from the /avaialbility endpoint?

        return intro_appts_in_date_range

    @classmethod
    @tracer.wrap()
    def intro_appointments_from_date_range_with_tz(
        cls,
        practitioner_id: int,
        start_datetime: datetime.datetime,
        end_datetime: datetime.datetime,
        tz: BaseTzInfo,
    ) -> Query:
        start_datetime_in_tz = UTC.localize(start_datetime).astimezone(tz)
        end_datetime_in_tz = UTC.localize(end_datetime).astimezone(tz)

        start_of_range_in_tz = datetime.datetime.combine(
            start_datetime_in_tz, datetime.datetime.min.time()
        )
        end_of_range_in_tz = datetime.datetime.combine(
            end_datetime_in_tz, datetime.datetime.max.time()
        )

        start_of_range_in_utc = start_of_range_in_tz.astimezone(UTC)
        end_of_range_in_utc = end_of_range_in_tz.astimezone(UTC)

        return (
            db.session.query(Appointment)
            .join(Product)
            .filter(
                Product.user_id == practitioner_id,
                Appointment.cancelled_at.is_(None),
                Appointment.scheduled_start >= start_of_range_in_utc,
                Appointment.scheduled_start <= end_of_range_in_utc,
                Appointment.is_intro == True,
            )
        )

    @classmethod
    @tracer.wrap()
    def number_of_appointments_on_date(
        cls, practitioner_id: int, date: datetime.datetime
    ) -> int:
        return (
            cls.appointments_from_date_range(practitioner_id, date, date)
            .with_entities(func.count())
            .as_scalar()
        )

    @property
    def recorded_answer_sets(self) -> List[RecordedAnswerSet]:
        model = f"{self.__tablename__}.recorded_answer_sets"

        try:
            results = (
                db.session.query(RecordedAnswerSet)
                .filter(RecordedAnswerSet.appointment_id == self.id)
                .all()
            )
            increment_metric(read=True, model_name=model)
            return results
        except Exception as e:
            error_message = "Error in getting recorded answer set in Appointment"
            log.error(error_message, error_type=e.__class__.__name__, error_msg=str(e))
            increment_metric(read=True, model_name=model, failure=error_message)
            raise e

    @recorded_answer_sets.setter
    def recorded_answer_sets(
        self, recorded_answer_sets: List[RecordedAnswerSet]
    ) -> None:
        model = f"{self.__tablename__}.recorded_answer_sets"
        log.warn(
            "This approach of upserting recorded answer sets is not allowed. Use a different way to do so",
            model=model,
        )

        try:
            current_recorded_answer_sets = (
                db.session.query(RecordedAnswerSet).filter(
                    RecordedAnswerSet.appointment_id == self.id
                )
            ).all()

            for recorded_answer_set in current_recorded_answer_sets:
                recorded_answer_set.appointment_id = None
                db.session.add(recorded_answer_set)

            for recorded_answer_set in recorded_answer_sets:
                recorded_answer_set.appointment_id = self.id
                db.session.add(recorded_answer_set)

            increment_metric(read=False, model_name=model)
        except Exception as e:
            error_message = "Error in updating recorded answer sets in Appointment"
            log.error(error_message, error_type=e.__class__.__name__, error_msg=str(e))
            increment_metric(read=False, model_name=model, failure=error_message)
            raise e

    @property
    def recorded_answers(self) -> List[RecordedAnswer]:
        model = f"{self.__tablename__}.recorded_answers"

        try:
            results = (
                db.session.query(RecordedAnswer)
                .filter(RecordedAnswer.appointment_id == self.id)
                .all()
            )
            increment_metric(read=True, model_name=model)
            return results
        except Exception as e:
            error_message = "Error in getting recorded answers in Appointment"
            log.error(error_message, error_type=e.__class__.__name__, error_msg=str(e))
            increment_metric(read=True, model_name=model, failure=error_message)
            raise e

    @recorded_answers.setter
    def recorded_answers(self, recorded_answers: List[RecordedAnswer]) -> None:
        model = f"{self.__tablename__}.recorded_answers"
        log.warn(
            "This approach of upserting recorded answers is not allowed. Use a different way to do so",
            model=model,
        )

        try:
            current_recorded_answers = (
                db.session.query(RecordedAnswer).filter(
                    RecordedAnswer.appointment_id == self.id
                )
            ).all()

            for recorded_answer in current_recorded_answers:
                recorded_answer.appointment_id = None
                db.session.add(recorded_answer)

            for recorded_answer in recorded_answers:
                recorded_answer.appointment_id = self.id
                db.session.add(recorded_answer)

            increment_metric(read=False, model_name=model)
        except Exception as e:
            error_message = "Error in updating recorded answers in Appointment"
            log.error(error_message, error_type=e.__class__.__name__, error_msg=str(e))
            increment_metric(read=False, model_name=model, failure=error_message)
            raise e
