import datetime
import random

from maven import feature_flags
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import DOUBLE
from sqlalchemy.orm import relationship

from appointments.models.appointment import Appointment
from appointments.models.payments import MONEY_PRECISION, AppointmentFeeCreator, Credit
from authn.models.user import User
from authz.models.roles import ROLES
from models import base
from models.profiles import CareTeamTypes
from storage.connection import db
from utils.data import JSONAlchemy
from utils.log import logger

log = logger(__name__)

# $ dollars for default referral
DEFAULT_MEMBER_VALUE = 0.01

REFERRAL_PAYMENT_TYPES = frozenset(
    (
        "Amazon Gift Card",
        "Swag Bag",
        "Tote",
        "Glossier",
        "Nike Gift Card",
        "Sephora Gift Card",
        "Enterprise Incentive",
    )
)


def add_referral_code_for_user(user_id: int, value=DEFAULT_MEMBER_VALUE):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    code = ReferralCode(
        allowed_uses=None,
        user_id=user_id,
        only_use_before_booking=True,
        expires_at=None,
    )
    db.session.add(code)
    db.session.flush()

    for_member = ReferralCodeValue(code=code, value=value, for_user_type=ROLES.member)

    db.session.add(for_member)
    db.session.flush()

    # override default, set it to non-expire
    for_member.expires_at = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "datetime")
    db.session.add(for_member)
    db.session.flush()

    return code


class PractitionerInvite(base.TimeLoggedModelBase):
    __tablename__ = "practitioner_invite"

    id = Column(Integer, primary_key=True)
    claimed_at = Column(DateTime(), nullable=True)

    image_id = Column(Integer, ForeignKey("image.id"), nullable=True)
    image = relationship("Image")
    email = Column(String(50), unique=True)
    json = Column(JSONAlchemy(Text), default={})

    def __repr__(self) -> str:
        return f"<PractitionerInvite ({self.id}) [Claimed at: {self.claimed_at}]>"

    __str__ = __repr__


class ReferralCodeValueTypes:
    practitioner = ROLES.practitioner
    member = ROLES.member
    referrer = "referrer"
    free_forever = "free_forever"


class ReferralCodeValue(base.TimeLoggedModelBase):
    """
    This model specify the value of the refer code.
    Each ReferCode may have one or multiple ReferralCodeValues.
    """

    __tablename__ = "referral_code_value"
    constraints = (UniqueConstraint("for_user_type", "code_id"),)

    user_types = (
        ROLES.practitioner,
        ROLES.member,
        ReferralCodeValueTypes.referrer,
        ReferralCodeValueTypes.free_forever,
    )

    id = Column(Integer, primary_key=True)
    code_id = Column(Integer, ForeignKey("referral_code.id"), nullable=False)
    for_user_type = Column(Enum(*user_types, name="user_type"), nullable=False)
    value = Column(Float)
    expires_at = Column(
        DateTime(),
        default=lambda: (datetime.datetime.utcnow() + datetime.timedelta(days=120)),
    )
    description = Column(String(280))

    code = relationship("ReferralCode", backref="values")

    payment_rep = Column(DOUBLE(precision=MONEY_PRECISION, scale=2), nullable=True)
    rep_email_address = Column(String(120), nullable=True)

    payment_user = Column(DOUBLE(precision=MONEY_PRECISION, scale=2), nullable=True)
    user_payment_type = Column(Enum(*REFERRAL_PAYMENT_TYPES), nullable=True)

    def __repr__(self) -> str:
        return f"<ReferralCodeValue (ID: {self.id}) [{self.value} for {self.for_user_type}]>"

    __str__ = __repr__


class ReferralCode(base.TimeLoggedModelBase):
    __tablename__ = "referral_code"

    __table_args__ = (
        ForeignKeyConstraint(
            ["category_name", "subcategory_name"],
            [
                "referral_code_subcategory.category_name",
                "referral_code_subcategory.name",
            ],
        ),
    )

    id = Column(Integer, primary_key=True)
    description = Column(String(280))

    code = Column(
        String(100), default=lambda: str(_unique_referral_code()), unique=True
    )

    expires_at = Column(
        DateTime().evaluates_none(),
        nullable=True,
        default=lambda: (datetime.datetime.utcnow() + datetime.timedelta(days=120)),
    )
    allowed_uses = Column(Integer, nullable=True)
    only_use_before_booking = Column(Boolean, default=True, nullable=False)

    user_id = Column(Integer, ForeignKey("user.id"), nullable=True)
    user = relationship(User, backref="codes")
    activity = Column(Text)

    total_code_cost = Column(DOUBLE(precision=MONEY_PRECISION, scale=2))

    category_name = Column(String(120), nullable=True)
    subcategory_name = Column(String(120), nullable=True)

    subcategory = relationship("ReferralCodeSubCategory")

    def __repr__(self) -> str:
        return f"<ReferralCode (ID: {self.id}) [{self.code}]>"

    __str__ = __repr__

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        else:
            return self.expires_at < datetime.datetime.utcnow()

    @property
    def is_valid(self) -> bool:
        return (
            (self.available_uses > 0) or self.allowed_uses is None
        ) and not self.is_expired

    @property
    def available_uses(self) -> int:
        if self.allowed_uses is not None:
            return self.allowed_uses - len(self.uses)
        return 1

    @property
    def is_global(self) -> bool:
        return self.user_id is None

    @property
    def sorted_values(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        ordering = [
            ReferralCodeValueTypes.free_forever,
            ReferralCodeValueTypes.referrer,
            ReferralCodeValueTypes.member,
            ReferralCodeValueTypes.practitioner,
        ]
        values = sorted(self.values, key=lambda x: ordering.index(x.for_user_type))
        return values

    def use(self, user: User):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        log.info("%s using %s", user, self)

        if self.is_valid:
            return self._process_values(user)[0]
        else:
            log.info("Code is invalid: %s", self)

    def use_with_reason(self, user: User):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        log.info("%s using %s", user, self)

        if self.is_valid:
            return self._process_values(user)
        else:
            log.info("Code is invalid: %s", self)
            return None, "invalid_code"

    def is_valid_for_user(self, user: User):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        _bad = None

        if self.is_expired:
            log.debug("%s expired...", self)
            _bad = "expired"
            return None, _bad
        if not self.is_valid:
            log.debug("%s not globally valid...", self)
            _bad = "globally_invalid"
            return None, _bad
        if user.id == self.user_id:
            log.info("Cannot use your own referral code!")
            _bad = "own_code"
            return None, _bad
        if user is None:
            log.debug("No user -  returning generic validity...")
            _bad = "no_user"
            # should always be yes - we just checked this
            return self.is_valid, _bad

        pending_referrals = ReferralCodeUse.pending_for_user(user.id)
        activated_referrals = ReferralCodeUse.activated_for_user(user.id)
        already_referred = activated_referrals or pending_referrals
        try:
            has_booked = bool(
                db.session.query(Appointment)
                .filter(Appointment.member_schedule_id == user.schedule.id)
                .first()
            )
        except AttributeError as e:
            has_booked = False
            log.debug("%s. Most likely schedule has yet to be created.", e)

        already_used_code = (
            db.session.query(ReferralCodeUse)
            .filter(
                ReferralCodeUse.code_id == self.id,
                ReferralCodeUse.user_id == user.id,
            )
            .first()
        )
        if already_used_code:
            log.info("User has already used code, returning.")
            _bad = "already_used_code"
            return None, _bad

        for value in self.sorted_values:
            if value.for_user_type in user.user_types:
                if already_referred and not self.is_global:
                    log.info(
                        "User has already been referred!",
                        user_id=user.id,
                    )
                    _bad = "already_referred"
                    break
                if has_booked and self.only_use_before_booking:
                    log.info(
                        "User has already booked - cannot use referral.",
                        user_id=user.id,
                        referral_id=self.id,
                    )
                    _bad = "has_booked"
                    break
            elif value.for_user_type == ReferralCodeValueTypes.referrer:
                if already_referred and not self.is_global:
                    log.info(
                        "User has already been referred!",
                        user_id=user.id,
                    )
                    _bad = "already_referred_referrer"
                    break
            elif value.for_user_type == ReferralCodeValueTypes.free_forever:
                if not self.user:
                    log.info("No user for value in free_forever.", value=value)
                    _bad = "free_forever_no_user"
                    break
                if not self.user.practitioner_profile:
                    log.info("Value is not for a practitioner!", value=value)
                    _bad = "free_forever_no_practitioner"
                    break

                already_free = ReferralCodeUse.already_free_with_practitioner(
                    user.id, self.user_id
                )
                if already_free:
                    log.debug(
                        "User already free with referrer.",
                        user_id=user.id,
                        referrer_id=self.user_id,
                    )
                    _bad = "free_forever_already_free"
                    break
        else:
            # nobreak
            return True, None

        log.info(
            "Referral not valid for user!",
            referral_id=self.id,
            user_id=user.id,
            message=_bad,
        )
        return False, _bad

    def _process_values(self, user: User):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not self.is_valid_for_user(user)[0]:
            log.debug(
                "%s not valid for user id %s - cannot use.",
                self,
                user.id,
            )
            return self.is_valid_for_user(user)

        use = ReferralCodeUse(user_id=user.id, code_id=self.id)
        for value in self.sorted_values:
            if value.for_user_type in user.user_types:
                if not (value.user_payment_type or value.payment_rep or value.value):
                    # code must have incentive payment or value...
                    break
                if value.user_payment_type or value.payment_rep:
                    db.session.add(
                        IncentivePayment(
                            referral_code_use=use, referral_code_value=value
                        )
                    )
                if value.value:
                    amount = value.value
                    log.debug(
                        "Got a $%s value for user id %s (%s)",
                        amount,
                        user.id,
                        user.role_name,
                    )
                    credit = self.add_credit(amount, user.id, value.expires_at, use)
                    if not credit:
                        break

                    credit.activated_at = datetime.datetime.utcnow().replace(
                        microsecond=0
                    )
                    db.session.add(credit)
            elif value.for_user_type == ReferralCodeValueTypes.referrer:
                amount = value.value
                log.debug("Got a $%s value for %s (referrer)", amount, self.user)
                credit = self.add_credit(amount, self.user.id, value.expires_at, use)
                if not credit:
                    break

                db.session.add(credit)
                if Appointment.completed_for_user(user):
                    credit.activated_at = datetime.datetime.utcnow().replace(
                        microsecond=0
                    )
                    use.credit_activated = True
            elif value.for_user_type == ReferralCodeValueTypes.free_forever:
                always_70_percent_payout = feature_flags.bool_variation(
                    "enable-always-70-percent-fee-creator",
                    default=False,
                )
                fee_percentage = 70 if always_70_percent_payout else 95
                fee_creator = AppointmentFeeCreator(
                    practitioner=self.user, fee_percentage=fee_percentage
                )
                db.session.add(fee_creator)

                fee_creator.members.append(user)
                log.debug("Added %s for free_forever.", fee_creator)

                use.credit_activated = True
                user.add_practitioner_to_care_team(
                    self.user_id, CareTeamTypes.FREE_FOREVER_CODE
                )
        else:
            if self.is_global:
                use.credit_activated = True

            self.uses.append(use)
            db.session.add(self)
            db.session.commit()
            return use, None

        # if we hit a break statement above, we return None here...
        log.info("Code is not allowed: %s", self)
        return None, "code_not_allowed"

    def add_credit(self, amount, user_id, expires_at, use=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # avoid circular import
        from eligibility import EnterpriseVerificationService, get_verification_service

        verification_svc: EnterpriseVerificationService = get_verification_service()
        verification_list = verification_svc.get_all_verifications_for_user(
            user_id=user_id,
        )
        verification = verification_list[0] if verification_list else None
        if amount:
            credit = Credit(
                user_id=user_id,
                amount=amount,
                expires_at=expires_at,
                referral_code_use=use,
                eligibility_member_id=verification.eligibility_member_id
                if verification
                else None,
                eligibility_verification_id=verification.verification_id
                if verification
                else None,
                eligibility_member_2_id=verification.eligibility_member_2_id
                if verification
                else None,
                eligibility_verification_2_id=verification.verification_2_id
                if verification
                else None,
                eligibility_member_2_version=verification.eligibility_member_2_version
                if verification
                else None,
            )

            return credit
        log.info("No amount to add credit for %s", self)


class ReferralCodeUse(base.TimeLoggedModelBase):
    __tablename__ = "referral_code_use"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)

    code_id = Column(Integer, ForeignKey("referral_code.id"), nullable=False)
    code = relationship(ReferralCode, backref="uses")

    credit_activated = Column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return f"<ReferralCodeUse (ID: {self.id}) [code {self.code_id} used by {self.user_id}]>"

    __str__ = __repr__

    @classmethod
    def already_free_with_practitioner(cls, user_id: int, practitioner_id):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        return (
            db.session.query(cls)
            .join(ReferralCode)
            .join(ReferralCodeValue)
            .filter(
                ReferralCode.user_id == practitioner_id,
                (
                    ReferralCodeValue.for_user_type
                    == ReferralCodeValueTypes.free_forever
                ),
                cls.user_id == user_id,
            )
            .all()
        )

    @classmethod
    def free_practitioner_codes_for_member(cls, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            db.session.query(ReferralCode)
            .join(cls)
            .join(ReferralCodeValue)
            .filter(
                (
                    ReferralCodeValue.for_user_type
                    == ReferralCodeValueTypes.free_forever
                ),
                cls.user_id == user_id,
            )
            .all()
        )

    @classmethod
    def pending_for_user(cls, user_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (
            db.session.query(cls)
            .join(ReferralCode)
            .join(ReferralCodeValue)
            .filter(
                (ReferralCodeValue.for_user_type == ReferralCodeValueTypes.referrer),
                cls.user_id == user_id,
                cls.credit_activated == False,
            )
            .all()
        )

    @classmethod
    def activated_for_user(cls, user_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (
            db.session.query(cls)
            .join(ReferralCode)
            .join(ReferralCodeValue)
            .filter(
                (ReferralCodeValue.for_user_type == ReferralCodeValueTypes.referrer),
                cls.user_id == user_id,
                cls.credit_activated != False,
            )
            .all()
        )


class IncentivePayment(base.TimeLoggedModelBase):

    __tablename__ = "incentive_payment"

    id = Column(Integer, primary_key=True)

    referral_code_use_id = Column(
        Integer, ForeignKey("referral_code_use.id"), nullable=False
    )
    referral_code_use = relationship(ReferralCodeUse, backref="incentive_payments")

    referral_code_value_id = Column(
        Integer, ForeignKey("referral_code_value.id"), nullable=False
    )
    referral_code_value = relationship(ReferralCodeValue, backref="incentive_payments")

    incentive_paid = Column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return f"<IncentivePayment {self.id}>"

    __str__ = __repr__


class ReferralCodeCategory(base.ModelBase):

    __tablename__ = "referral_code_category"

    name = Column(String(120), primary_key=True)

    def __repr__(self) -> str:
        return f"<ReferralCodeCategory {self.name}>"

    __str__ = __repr__


class ReferralCodeSubCategory(base.ModelBase):

    __tablename__ = "referral_code_subcategory"

    category_name = Column(
        String(120), ForeignKey("referral_code_category.name"), primary_key=True
    )
    name = Column(String(120), primary_key=True)
    category = relationship("ReferralCodeCategory")

    def __repr__(self) -> str:
        return f"<ReferralCodeSubCategory {self.category_name}/{self.name}>"

    __str__ = __repr__


def _new_referral_code(num_chars=5, code_chars="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    code = ""
    for _ in range(0, num_chars):
        slice_start = random.randint(0, len(code_chars) - 1)
        code += code_chars[slice_start : slice_start + 1]

    return code


def _unique_referral_code(**kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    code = _new_referral_code(**kwargs)

    while db.session.query(
        db.session.query(ReferralCode).filter(ReferralCode.code == code).exists()
    ).one()[0]:
        log.debug("Conflict with existing code! (%s)", code)
        code = _new_referral_code(**kwargs)

    return code
