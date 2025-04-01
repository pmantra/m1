from __future__ import annotations

import datetime
import enum
import uuid
from typing import TYPE_CHECKING, Any, List, MutableMapping, Optional, Union

import pycountry
from dateutil.relativedelta import relativedelta
from flask_babel import lazy_gettext
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    and_,
    event,
    func,
    inspect,
)
from sqlalchemy.dialects.mysql import FLOAT, MEDIUMTEXT
from sqlalchemy.engine.base import Connection
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapper, backref, joinedload, relationship, validates
from sqlalchemy.sql.expression import or_, select

import geography
from authn.domain.repository import UserRepository
from authz.models.roles import ROLES, default_role
from geography.repository import CountryRepository, SubdivisionRepository
from messaging.services.zendesk_client import IdentityType
from models import base
from models.actions import ACTIONS, audit
from models.base import IntJSONProperty, ModelBase, db
from models.mixins import SVGImageMixin
from models.phone import BlockedPhoneNumber
from models.tracks.member_track import MemberTrack
from models.verticals_and_specialties import is_cx_vertical_name
from payments.models.practitioner_contract import PractitionerContract
from utils.cache import ViewCache
from utils.data import PHONE_NUMBER_LENGTH, JSONAlchemy, normalize_phone_number
from utils.log import logger

# These will cause a circular imports at run-time but are valid for static type-checking
if TYPE_CHECKING:
    from models.enterprise import Organization, OrganizationEmployee  # noqa: F401
    from models.programs import CareProgram, CareProgramPhase, Module  # noqa: F401
    from models.tracks import TrackConfig  # noqa: F401

log = logger(__name__)


practitioner_certifications = db.Table(
    "practitioner_certifications",
    Column("user_id", Integer, ForeignKey("practitioner_profile.user_id")),
    Column("certification_id", Integer, ForeignKey("certification.id")),
    UniqueConstraint("user_id", "certification_id"),
)

practitioner_categories = db.Table(
    "practitioner_categories",
    Column("user_id", Integer, ForeignKey("practitioner_profile.user_id")),
    Column("category_id", Integer, ForeignKey("category.id")),
    UniqueConstraint("user_id", "category_id"),
)

practitioner_states = db.Table(
    "practitioner_states",
    Column("user_id", Integer, ForeignKey("practitioner_profile.user_id")),
    Column("state_id", Integer, ForeignKey("state.id")),
    UniqueConstraint("user_id", "state_id"),
)

practitioner_verticals = db.Table(
    "practitioner_verticals",
    Column("user_id", Integer, ForeignKey("practitioner_profile.user_id")),
    Column("vertical_id", Integer, ForeignKey("vertical.id")),
    UniqueConstraint("user_id", "vertical_id"),
)

practitioner_specialties = db.Table(
    "practitioner_specialties",
    Column("user_id", Integer, ForeignKey("practitioner_profile.user_id")),
    Column("specialty_id", Integer, ForeignKey("specialty.id")),
    UniqueConstraint("user_id", "specialty_id"),
)

practitioner_languages = db.Table(
    "practitioner_languages",
    Column("user_id", Integer, ForeignKey("practitioner_profile.user_id")),
    Column("language_id", Integer, ForeignKey("language.id")),
    UniqueConstraint("user_id", "language_id"),
)


category_versions = db.Table(
    "category_versions",
    Column("category_version_id", Integer, ForeignKey("category_version.id")),
    Column("category_id", Integer, ForeignKey("category.id")),
    UniqueConstraint("category_version_id", "category_id"),
)


class HasAddressMixin:
    def add_or_update_address(self, address_dict):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        log.debug("Updating address for User: (%s)", self.user.id)  # type: ignore[attr-defined] # "HasAddressMixin" has no attribute "user"

        existing = db.session.query(Address).filter(Address.user == self.user).first()  # type: ignore[attr-defined] # "HasAddressMixin" has no attribute "user"

        # Eliminate blank rows
        is_not_valid = any(
            (value is None) or (value == "") for value in address_dict.values()
        )

        if is_not_valid:
            log.info(f"Address for User: ({self.user.id}) not valid!")  # type: ignore[attr-defined] # "HasAddressMixin" has no attribute "user"
            return

        address_dict["country"] = address_dict.get("country", "US")

        if existing:
            address = existing
            for k, v in address_dict.items():
                setattr(address, k, v.strip())
        else:
            address = Address(**address_dict)
            address.user = self.user  # type: ignore[attr-defined] # "HasAddressMixin" has no attribute "user"

        db.session.add(address)
        db.session.commit()
        return address

    @property
    def address(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.user.addresses[0] if self.user.addresses else {}  # type: ignore[attr-defined] # "HasAddressMixin" has no attribute "user"


class SettingsMixin:
    settings = ("1hr_left_practitioner_respond_alert",)

    @property
    def notification_setting(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (self.json or {}).get("notifications", {})  # type: ignore[has-type] # Cannot determine type of "json"

    @notification_setting.setter
    def notification_setting(self, val):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not isinstance(val, dict):
            log.debug("Invalid notification setting. Skipped")
            return

        normalized_val = {k: val[k] for k in val if k in self.settings}
        obj = self.json or {}  # type: ignore[has-type] # Cannot determine type of "json"
        obj["notifications"] = normalized_val
        # only direct assignment triggers JSONField saving event
        self.json = obj

    def set_notification_setting_by_name(self, name, val):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if name not in self.settings:
            log.debug("Invalid notification setting name. Skipped")
            return

        obj = self.json or {}
        notifications = obj.get("notifications", {})
        notifications[name] = val
        obj["notifications"] = notifications
        # only direct assignment triggers JSONField saving event
        self.json = obj

    @property
    def sms_blocked(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return bool(
            BlockedPhoneNumber.query.filter(
                BlockedPhoneNumber.digits == self.phone_number  # type: ignore[attr-defined] # "SettingsMixin" has no attribute "phone_number"
            ).first()
        )

    def mark_as_sms_blocked(self, error_code=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        bpn = BlockedPhoneNumber.query.filter(
            BlockedPhoneNumber.digits == self.phone_number  # type: ignore[attr-defined] # "SettingsMixin" has no attribute "phone_number"
        ).first() or BlockedPhoneNumber(
            digits=self.phone_number  # type: ignore[attr-defined] # "SettingsMixin" has no attribute "phone_number"
        )  # type: ignore[attr-defined] # "SettingsMixin" has no attribute "phone_number"
        if error_code:
            bpn.error_code = error_code

        session = db.session
        session.add(bpn)


class RoleProfile(base.TimeLoggedModelBase, HasAddressMixin):
    """
    Associate an user with role capabilities.
    """

    __tablename__ = "role_profile"

    constraints = (UniqueConstraint("user_id", "role_id"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"))
    user = relationship("User")
    role_id = Column(Integer, ForeignKey("role.id"))
    role = relationship("Role")

    def __repr__(self) -> str:
        return f"<RoleProfile [User {self.user_id}]>"

    __str__ = __repr__

    @property
    def role_name(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.role.name


class MemberProfile(base.TimeLoggedModelBase, HasAddressMixin, SettingsMixin):
    """
    Associate a user with member capabilities.
    """

    __tablename__ = "member_profile"

    constraints = (UniqueConstraint("user_id", "role_id"),)
    user_id = Column(Integer, ForeignKey("user.id"), primary_key=True)
    user = relationship("User", back_populates="member_profile", uselist=False)
    role_id = Column(Integer, ForeignKey("role.id"), default=default_role(ROLES.member))
    role = relationship("Role")

    first_name = Column(String(40))
    middle_name = Column(String(40))
    last_name = Column(String(40))
    username = Column(String(100), unique=True)
    zendesk_user_id = Column(BigInteger, unique=True)
    timezone = Column(String(128), nullable=False, default="UTC")

    country_code = Column(String(2), nullable=True)
    subdivision_code = Column(String(6), nullable=True)

    state_id = Column(Integer, ForeignKey("state.id"))
    state = relationship("State")
    phone_number = Column(String(PHONE_NUMBER_LENGTH))

    esp_id = Column(String(36), default=lambda: str(uuid.uuid4()))
    dosespot = Column(JSONAlchemy(Text(1000)), default={})
    stripe_customer_id = Column(String(50), unique=True)
    stripe_account_id = Column(String(50))

    note = Column(Text)
    follow_up_reminder_send_time = Column(DateTime)

    zendesk_verification_ticket_id = Column(BigInteger, unique=True)

    json = Column(JSONAlchemy(Text(1000)), default={})

    has_care_plan = Column(Boolean, nullable=False, default=False)
    care_plan_id = Column(Integer, nullable=True, default=None)

    care_team = relationship(
        "MemberPractitionerAssociation",
        primaryjoin="MemberProfile.user_id == MemberPractitionerAssociation.user_id",
        foreign_keys="MemberPractitionerAssociation.user_id",
        cascade="all,delete-orphan",
    )

    active_tracks = relationship(
        MemberTrack,
        uselist=True,
        viewonly=True,
        primaryjoin=lambda: MemberProfile.active_tracks_join_expression(),
        foreign_keys="MemberTrack.user_id",
        order_by="MemberTrack.created_at",
    )

    schedule = relationship(
        "Schedule",
        primaryjoin="MemberProfile.user_id == Schedule.user_id",
        foreign_keys="Schedule.user_id",
        uselist=False,
    )

    @classmethod
    def active_tracks_join_expression(cls):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (cls.user_id == MemberTrack.user_id) & MemberTrack.active

    def __repr__(self) -> str:
        return f"<MemberProfile [User {self.user_id}]>"

    __str__ = __repr__

    @validates("phone_number")
    def validate_phone_no(self, key, phone_number):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if phone_number:
            phone_number, _ = normalize_phone_number(phone_number, None)
        return phone_number

    @property
    def subdivision(self) -> Optional[pycountry.Subdivision]:
        if self.subdivision_code:
            return pycountry.subdivisions.get(code=self.subdivision_code)
        return  # type: ignore[return-value] # Return value expected

    @property
    def country(self) -> Optional[geography.repository.Country]:
        return CountryRepository(session=db.session).get(country_code=self.country_code)  # type: ignore[arg-type] # Argument "country_code" to "get" of "CountryRepository" has incompatible type "Optional[str]"; expected "str"

    @property
    def enabled_for_prescription(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        enabled = True
        if not self.user.first_name and self.user.last_name:
            enabled = False
        if not self.address:
            enabled = False
        if not self.phone_number:
            enabled = False

        health_profile = self.user.health_profile.json
        if not health_profile.get("birthday"):
            enabled = False
        return enabled

    @property
    def opted_in_notes_sharing(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # notes sharing default to False for existing users
        return bool(self.json and self.json.get("opted_in_notes_sharing"))

    @opted_in_notes_sharing.setter
    def opted_in_notes_sharing(self, val):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self.json is None:
            self.json = {}
        self.json["opted_in_notes_sharing"] = bool(val)

    @property
    def color_hex(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.json and self.json.get("color_hex"):
            return self.json["color_hex"]

    @color_hex.setter
    def color_hex(self, hex_code):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        session = db.session
        if self.json:
            self.json["color_hex"] = hex_code
            session.add(self)

    @property
    def pending_enterprise_verification(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.json and self.json.get("pending_enterprise_verification"):
            return self.json["pending_enterprise_verification"]

    @pending_enterprise_verification.setter
    def pending_enterprise_verification(self, val):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        session = db.session
        if self.json:
            self.json["pending_enterprise_verification"] = bool(val)
            session.add(self)

    @property
    def zendesk_ticket_id(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.json.get("zendesk_ticket_id") if self.json else None

    @zendesk_ticket_id.setter
    def zendesk_ticket_id(self, ticket_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        current_json = self.json or {}
        self.json = {**current_json, "zendesk_ticket_id": ticket_id}

    @property
    def is_international(self) -> bool:
        if self.state:
            return self.state.abbreviation == State.INTERNATIONAL_FLAG
        return False

    @property
    def id(self) -> int:
        return self.user_id

    @property
    def email(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        u = UserRepository().get(id=self.user_id)
        return u.email if u is not None else None

    @property
    def care_team_with_type(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return MemberPractitionerAssociation.care_team_for_user(self.user_id)

    @property
    def care_coordinators(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        coordinators = []
        if self.care_team:
            coordinators = [
                ct[0]
                for ct in self.care_team_with_type
                if ct[1] == CareTeamTypes.CARE_COORDINATOR.value
            ]
        return coordinators

    GLOBAL_PHARMACY_KEY = "global_pharmacy"

    def _get_prac_key(self, practitioner_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return f"practitioner:{practitioner_id}"

    def get_patient_info(self, practitioner_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        practitioner_info = self.dosespot.get(self._get_prac_key(practitioner_id), {})
        return {"patient_id": practitioner_info.get("patient_id")}

    def set_patient_info(self, practitioner_id, patient_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        new = self.dosespot.get(self._get_prac_key(practitioner_id), {})
        new.update({"patient_id": patient_id})
        self.dosespot[self._get_prac_key(practitioner_id)] = new
        return self.dosespot

    def get_prescription_info(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        pharmacy_info = self.dosespot.get(self.GLOBAL_PHARMACY_KEY, {})
        dosespot_keys = [key for key in self.dosespot.keys() if "practitioner:" in key]
        if pharmacy_info == {} and len(dosespot_keys) > 0:
            last_key = dosespot_keys.pop()
            pharmacy_info = self.dosespot.get(last_key, {})
        return {
            "pharmacy_id": pharmacy_info.get("pharmacy_id"),
            "pharmacy_info": pharmacy_info.get("pharmacy_info"),
        }

    def set_prescription_info(self, **info):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        new = self.dosespot.get(self.GLOBAL_PHARMACY_KEY, {})
        new.update(info)
        self.dosespot[self.GLOBAL_PHARMACY_KEY] = new
        return self.dosespot

    def get_cancellations(self) -> int | None:
        """
        Gets the number of member cancellations.
        """
        cancellations = self.json.get("number_cancellations", None)
        return int(cancellations) if cancellations else None

    def add_or_update_cancellations(self) -> None:
        """
        Adds or updates the number of member cancellations.
        Should not exceed the max number of member cancellations.
        """
        cancellations = self.json.get("number_cancellations", None)
        self.json["number_cancellations"] = (
            int(cancellations + 1) if cancellations else 1
        )

    def set_repeat_offender(self) -> None:
        self.json["notified:repeat_offender"] = datetime.datetime.utcnow().isoformat()

    def get_repeat_offender(self) -> str | None:
        return self.json.get("notified:repeat_offender", None)

    @property
    def prescribable_state(self) -> Optional[str]:  # type: ignore[return] # Missing return statement
        """
        In what state can this member receive a prescription?
        :return State abbreviation in which member can receive prescriptions
        """

        if all(
            [
                (self.user.organization.rx_enabled if self.user.organization else True),
                (
                    not self.user.organization.education_only
                    if self.user.organization
                    else True
                ),
                # We currently only allow prescriptions inside the US
                # We assume members are in the US if they have no country set.
                ((not self.country_code) or self.country_code == "US"),
                # ZZ is the value of "Other" in the state drop down.
                self.state and self.state.abbreviation != "ZZ",
            ]
        ):
            return self.state.abbreviation

    def add_practitioner_to_care_team(self, practitioner_id: int, _type):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self.user.add_practitioner_to_care_team(practitioner_id, _type)

    @property
    def user_types(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.user.user_types

    @property
    def role_name(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return ROLES.member

    @property
    def has_recently_ended_track(self) -> bool:
        return any(
            track.ended_at >= datetime.datetime.today() - datetime.timedelta(days=30)
            for track in self.user.inactive_tracks
        )

    @property
    def avatar_url(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.user.avatar_url


class BillingTypes(enum.Enum):
    DCW_PC = "DCW PC"
    DCW_PA = "DCW PA"
    DN = "DN"


class PractitionerSubdivision(ModelBase):
    __tablename__ = "practitioner_subdivisions"
    constraints = (UniqueConstraint("practitioner_id", "subdivision_code"),)

    id = Column(Integer, primary_key=True)
    practitioner_id = Column(
        Integer, ForeignKey("practitioner_profile.user_id"), nullable=False
    )
    practitioner_profile = relationship("PractitionerProfile")
    subdivision_code = Column(String(6), nullable=False)

    @validates("subdivision_code")
    def validate_subdivision_code(self, key, subdivision_code):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        subdivision = pycountry.subdivisions.get(code=subdivision_code)

        # We want to keep "US-ZZ" as a valid subdivision code, even if it's not technically valid.
        # This is in line with how we currently handle international members.
        if not subdivision and subdivision_code != "US-ZZ":
            raise ValueError(f"Error: '{subdivision_code}' is not a valid subdivision")
        return subdivision_code


class PractitionerProfile(base.TimeLoggedModelBase, HasAddressMixin, SettingsMixin):
    """
    Associate a user with practitioner capabilities.
    """

    __tablename__ = "practitioner_profile"
    constraints = (UniqueConstraint("user_id", "role_id"),)

    role_name = ROLES.practitioner
    rounding_minutes = 10
    user_id = Column(Integer, ForeignKey("user.id"), primary_key=True)
    user = relationship("User", back_populates="practitioner_profile", uselist=False)
    active = Column(Boolean, nullable=False, default=True)
    role_id = Column(
        Integer, ForeignKey("role.id"), default=default_role(ROLES.practitioner)
    )
    role = relationship("Role")

    first_name = Column(String(40))
    middle_name = Column(String(40))
    last_name = Column(String(40))
    username = Column(String(100), unique=True)
    zendesk_user_id = Column(BigInteger, unique=True)
    timezone = Column(String(128), nullable=False, default="UTC")

    country_code = Column(String(2), nullable=True)
    subdivision_code = Column(String(6), nullable=True)

    esp_id = Column(String(36), default=lambda: str(uuid.uuid4()))
    stripe_account_id = Column(String(50), unique=True)
    default_cancellation_policy_id = Column(
        Integer, ForeignKey("cancellation_policy.id")
    )
    default_cancellation_policy = relationship("CancellationPolicy")
    phone_number = Column(String(PHONE_NUMBER_LENGTH))
    reference_quote = Column(String(1000))
    state_id = Column(Integer, ForeignKey("state.id"))
    state = relationship("State")
    education = Column(String(100))
    work_experience = Column(String(400))
    awards = Column(String(400))
    experience_started = Column(Date)
    dosespot = Column(JSONAlchemy(Text(1000)), default={})
    booking_buffer = Column(Integer, default=10)
    default_prep_buffer = Column(Integer)

    languages = relationship(
        "Language",
        backref="practitioners",
        secondary=practitioner_languages,
        lazy="selectin",
    )
    certified_states = relationship(
        "State",
        backref="practitioners",
        secondary=practitioner_states,
        lazy="selectin",
    )
    certifications = relationship(
        "Certification",
        backref="practitioners",
        secondary=practitioner_certifications,
        lazy="selectin",
    )
    categories = relationship(
        "Category",
        backref="practitioners",
        secondary=practitioner_categories,
        lazy="selectin",
    )
    specialties = relationship(
        "Specialty", backref="practitioners", secondary=practitioner_specialties
    )
    verticals = relationship(
        "Vertical", backref="practitioners", secondary="practitioner_verticals"
    )

    certified_practitioner_subdivisions = relationship(
        PractitionerSubdivision, uselist=True
    )

    next_availability = Column(DateTime(), nullable=True)
    show_when_unavailable = Column(Boolean, nullable=False, default=False)
    messaging_enabled = Column(Boolean, default=False)
    response_time = Column(
        Integer, nullable=True, default=None
    )  # guaranteed response in hours
    anonymous_allowed = Column(Boolean, nullable=False, default=True)
    ent_national = Column(Boolean, nullable=False, default=False)
    rating = Column(FLOAT(precision=4, scale=3), nullable=True, default=None)
    show_in_marketplace = Column(Boolean, nullable=False, default=True)
    show_in_enterprise = Column(Boolean, nullable=False, default=True)
    billing_org = Column(Enum(BillingTypes), nullable=True)
    is_staff = Column(Boolean, nullable=False, default=False)
    zendesk_email = Column(String(120), unique=True)
    credential_start = Column(
        DateTime(),
        doc="Start time for when a practitioner was last credentialed",
        nullable=True,
    )

    json = Column(JSONAlchemy(Text(1000)), default={})
    care_team_patients = association_proxy("patient_associations", "user")

    note = Column(Text)

    def __repr__(self) -> str:
        return f"<PractitionerProfile [User {self.user_id}]>"

    __str__ = __repr__

    @hybrid_property
    def full_name(self) -> str:
        return f"{self.first_name or ''} {self.last_name or ''}".strip()

    @full_name.expression  # type: ignore[no-redef] # Name "full_name" already defined on line 662
    def full_name(cls):
        return db.func.concat(
            PractitionerProfile.first_name, " ", PractitionerProfile.last_name
        )

    @property
    def email(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        u = UserRepository().get(id=self.user_id)
        return u.email if u is not None else None

    @property
    def is_international(self) -> bool:
        # For now, we are assuming that null country_code means US.
        return self.country_code is not None and self.country_code != "US"

    @validates("phone_number")
    def validate_phone_no(self, key, phone_number):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if phone_number:
            phone_number, _ = normalize_phone_number(phone_number, None)
        return phone_number

    @property
    def subdivision(self) -> Optional[pycountry.Subdivision]:
        if self.subdivision_code:
            return pycountry.subdivisions.get(code=self.subdivision_code)
        return  # type: ignore[return-value] # Return value expected

    @property
    def country(self) -> Optional[geography.repository.Country]:
        return CountryRepository(session=db.session).get(country_code=self.country_code)  # type: ignore[arg-type] # Argument "country_code" to "get" of "CountryRepository" has incompatible type "Optional[str]"; expected "str"

    @property
    def certified_subdivision_codes(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return [
            subdivision.subdivision_code
            for subdivision in self.certified_practitioner_subdivisions
        ]

    @property
    def certified_subdivisions(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        subdivisions = []
        for subdivision_code in self.certified_subdivision_codes:
            if subdivision := pycountry.subdivisions.get(code=subdivision_code):
                subdivisions.append(subdivision)
        return subdivisions

    @property
    def admin_verticals(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return ", ".join(v.marketing_name for v in self.verticals)

    @property
    def agreed_service_agreements(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        current_acceptances = (
            db.session.query(AgreementAcceptance)
            .filter(AgreementAcceptance.user_id == self.user_id)
            .order_by(AgreementAcceptance.created_at.desc())
        )

        return current_acceptances

    @property
    def agreed_service_agreement(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        current_acceptance = (
            db.session.query(AgreementAcceptance)
            .filter(AgreementAcceptance.user_id == self.user_id)
            .order_by(AgreementAcceptance.created_at.desc())
            .first()
        )

        if current_acceptance:
            current_agreement = Agreement.latest_version(AgreementNames.SERVICE)
            if current_acceptance.agreement.version == current_agreement.version:
                # auto-renew agreement until we have a new version
                return True
            else:
                thirty_days_before_renewal = (
                    current_acceptance.created_at + relativedelta(years=1)
                ) - datetime.timedelta(days=30)
                if datetime.datetime.utcnow() < thirty_days_before_renewal:
                    return True

        return False

    @agreed_service_agreement.setter
    def agreed_service_agreement(self, val):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        acceptance = AgreementAcceptance(
            user_id=self.user_id,
            agreement=Agreement.latest_version(AgreementNames.SERVICE),
        )
        db.session.add(acceptance)
        db.session.commit()
        acceptance.audit_creation()

    @property
    def agreements(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return {"subscription": self.agreed_service_agreement}

    @property
    def cancellation_policy(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.default_cancellation_policy

    @property
    def alert_about_availability(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return bool((self.json or {}).get("alert_about_availability"))

    @alert_about_availability.setter
    def alert_about_availability(self, val):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not self.json:
            self.json = {}

        self.json["alert_about_availability"] = bool(val)

    @property
    def hourly_rate(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (self.json or {}).get("hourly_rate")

    @hourly_rate.setter
    def hourly_rate(self, val):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if val:
            self.json["hourly_rate"] = int(val)

    @property
    def percent_booked(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (self.json or {}).get("percent_booked")

    @percent_booked.setter
    def percent_booked(self, val):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if val is not None:
            self.json["percent_booked"] = int(val)

    @property
    def minutes_per_message(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (self.json or {}).get("minutes_per_message", 1)

    @minutes_per_message.setter
    def minutes_per_message(self, val):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.json["minutes_per_message"] = int(val)

    @property
    def malpractice_opt_out(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return bool((self.json or {}).get("malpractice_opt_out"))

    @malpractice_opt_out.setter
    def malpractice_opt_out(self, val):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.json["malpractice_opt_out"] = bool(val)

    @property
    def years_experience(self) -> int:
        return relativedelta(datetime.date.today(), self.experience_started).years

    def loaded_cost(self, raw_cost=None, minutes=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not self.hourly_rate:
            log.debug(
                "Practitioner Profile User: (%s) has no hourly_rate, returning...",
                self.user.id,
            )
            return

        if minutes:
            raw_cost = (self.hourly_rate / 60) * minutes
        elif raw_cost:
            # don't need to process but want to fall to the else if not here
            pass
        else:
            log.warning("Need raw_cost or minutes!")
            return

        percent_booked = self.percent_booked
        if not percent_booked:
            log.info(
                "No percent booked for Practitioner Profile User: (%s)!", self.user.id
            )
            percent_booked = 100

        cost = raw_cost / (percent_booked / 100)
        log.debug("Converted to $%s", cost)
        return cost

    @property
    def is_cx(self) -> bool:
        return any(is_cx_vertical_name(v.name) for v in self.verticals)

    @property
    def vertical(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if len(self.verticals) != 0:
            return self.verticals[0]
        else:
            return None

    @property
    def active_contract(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return (
            db.session.query(PractitionerContract)
            .filter(
                PractitionerContract.practitioner_id == self.user_id,
                PractitionerContract.active == True,
            )
            .first()
        )

    @classmethod
    def validate_prac_ids_exist(cls, validate_prac_ids: List[int]) -> bool:
        found_prac_ids = [
            pp.user_id
            for pp in db.session.query(PractitionerProfile.user_id)
            .filter(PractitionerProfile.user_id.in_(validate_prac_ids))
            .all()
        ]
        if len(validate_prac_ids) != len(found_prac_ids):
            invalid_prac_ids = [
                prac_id
                for prac_id in validate_prac_ids
                if prac_id not in set(found_prac_ids)
            ]
            raise ValueError("Invalid practitioners", invalid_prac_ids)
        return True


def set_subdivision_code(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    profile: Union[MemberProfile, PractitionerProfile], state: State, country_code: str
):
    if state and country_code:
        subdivision_repository = SubdivisionRepository()
        if verified_subdivision := subdivision_repository.get_by_country_code_and_state(
            country_code=country_code,
            state=state.abbreviation,
        ):
            profile.subdivision_code = verified_subdivision.code


@event.listens_for(MemberProfile.state, "set")
@event.listens_for(PractitionerProfile.state, "set")
def update_subdivision_code_on_state_change(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    profile: Union[MemberProfile, PractitionerProfile], value, _old_value, _initiator
):
    set_subdivision_code(profile, value, profile.country_code)  # type: ignore[arg-type] # Argument 3 to "set_subdivision_code" has incompatible type "Optional[str]"; expected "str"


@event.listens_for(MemberProfile.country_code, "set")
@event.listens_for(PractitionerProfile.country_code, "set")
def update_subdivision_code_on_country_code_change(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    profile: Union[MemberProfile, PractitionerProfile], value, _old_value, _initiator
):
    set_subdivision_code(profile, profile.state, value)


ProfilesMappingT = MutableMapping[
    str, Union[RoleProfile, PractitionerProfile, MemberProfile]
]


@event.listens_for(MemberProfile, "after_update")
def update_zendesk_user_on_phone_number_update(
    mapper: Mapper, connection: Connection, target: MemberProfile
) -> None:
    # avoid circular import
    from messaging.services.zendesk import (
        should_update_zendesk_user_profile,
        update_zendesk_user,
    )

    # determine whether the MemberProfile's 'phone_number' or 'email' attribute was updated
    phone_number_history = inspect(target).get_history("phone_number", True)
    if phone_number_history.has_changes() and should_update_zendesk_user_profile():
        user = target.user
        log.info(
            "Updating Zendesk Profile for user due to an updated phone number",
            user_id=user.id,
        )

        # update the profile with the new phone number
        update_zendesk_user.delay(
            user_id=user.id,
            update_identity=IdentityType.PHONE,
            team_ns="virtual_care",
            caller="update_zendesk_user_on_phone_number_update",
        )


class MFAState(enum.Enum):
    DISABLED = "disabled"
    # MFA should be on for this user, but the user needs to complete verification.
    PENDING_VERIFICATION = "pending_verification"
    # MFA has fully set up (enabled and verified).
    ENABLED = "enabled"


class CareTeamTypes(enum.Enum):
    APPOINTMENT = "APPOINTMENT"
    MESSAGE = "MESSAGE"
    QUIZ = "QUIZ"
    FREE_FOREVER_CODE = "FREE_FOREVER_CODE"
    CARE_COORDINATOR = "CARE_COORDINATOR"


class MemberPractitionerAssociation(base.TimeLoggedModelBase):
    __tablename__ = "member_care_team"
    __table_args__ = (UniqueConstraint("user_id", "practitioner_id", "type"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"))
    practitioner_id = Column(Integer, ForeignKey("practitioner_profile.user_id"))
    type = Column(Enum(CareTeamTypes), nullable=False)
    json = Column(JSONAlchemy(Text), default={})

    user = relationship(
        "User",
        backref=backref("practitioner_associations", cascade="all,delete-orphan"),
    )
    practitioner_profile = relationship(
        "PractitionerProfile",
        backref=backref("patient_associations", cascade="all,delete-orphan"),
    )

    member_track_id = IntJSONProperty("member_track_id")

    def __repr__(self) -> str:
        return f"<User[{self.user_id}] is matched with Practitioner[{self.practitioner_id}] via {self.type}>"

    __str__ = __repr__

    @classmethod
    def care_team_for_user(cls, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Returns a list of care team practitioners
        and their corresponding care team types for the user.
        :param user_id:
        :return: List of (Practitioner, Care Team Type) tuples.
        """
        associations = (
            db.session.query(cls)
            .filter_by(user_id=user_id)
            .options(
                joinedload(cls.practitioner_profile).joinedload(
                    PractitionerProfile.user
                )
            )
            .all()
        )
        return [(a.practitioner_profile.user, a.type.value) for a in associations]


@event.listens_for(MemberPractitionerAssociation, "after_insert")
def update_zendesk_user_on_ca_assignment(
    mapper: Mapper,
    connection: Connection,
    target: MemberPractitionerAssociation,
) -> None:
    # avoid circular imports
    from messaging.services.zendesk import (
        should_update_zendesk_user_profile,
        update_zendesk_user,
    )

    # see if it's a CA relationship that was updated or created
    if (
        target.type == CareTeamTypes.CARE_COORDINATOR
        and should_update_zendesk_user_profile()
    ):
        log.info(
            "Updating Zendesk Profile for user due to CA assignment",
            user_id=target.user.id,
            mpa_id=target.id,
        )

        # update the profile with the CA association
        update_zendesk_user.delay(
            user_id=target.user.id,
            update_identity=IdentityType.CARE_ADVOCATE,
            team_ns="virtual_care",
            caller="update_zendesk_user_on_ca_assignment",
        )


@event.listens_for(MemberPractitionerAssociation.practitioner_profile, "set")
def update_zendesk_user_on_ca_update(
    target: MemberPractitionerAssociation, value: Any, oldvalue: Any, initiator: Any
) -> None:
    # avoid circular imports
    from messaging.services.zendesk import (
        should_update_zendesk_user_profile,
        update_zendesk_user,
    )

    # see if it's a CA relationship that was updated or created
    if (
        target.type == CareTeamTypes.CARE_COORDINATOR
        and should_update_zendesk_user_profile()
    ):
        log.info(
            "Updating Zendesk Profile for user due to CA change",
            user_id=target.user.id,
            mpa_id=target.id,
        )

        # update the profile with the CA association
        update_zendesk_user.delay(
            user_id=target.user.id,
            update_identity=IdentityType.CARE_ADVOCATE,
            team_ns="virtual_care",
            caller="update_zendesk_user_on_ca_update",
        )


class Address(base.TimeLoggedModelBase):
    __tablename__ = "address"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"))
    user = relationship("User", backref="addresses")
    street_address = Column(String(200), nullable=False)
    city = Column(String(40), nullable=False)
    zip_code = Column(String(20), nullable=False)
    state = Column(String(40), nullable=False)
    country = Column(String(40), nullable=False)

    def __repr__(self) -> str:
        return f"<Address {self.id} [User {self.user_id}]>"

    __str__ = __repr__


class Device(base.TimeLoggedModelBase):
    __tablename__ = "device"

    id = Column(Integer, primary_key=True)
    device_id = Column(String(191), nullable=False, unique=True)
    is_active = Column(Boolean, nullable=False, default=True)
    application_name = Column(String(20), nullable=False)

    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    user = relationship("User", backref="devices")

    def __repr__(self) -> str:
        return f"<Device [{self.device_id}] {self.is_active} user {self.user_id}>"

    __str__ = __repr__

    @classmethod
    def for_user(cls, user, application_name="forum"):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            db.session.query(cls)
            .filter(
                Device.user == user,
                Device.is_active == True,
                Device.application_name == application_name,
            )
            .all()
        )


class Certification(base.ModelBase):
    __tablename__ = "certification"

    id = Column(Integer, primary_key=True)
    name = Column(String(70), nullable=False, unique=True)

    def __repr__(self) -> str:
        return f"<Certification [{self.name}]>"

    __str__ = __repr__


class CategoryVersion(base.ModelBase):
    __tablename__ = "category_version"

    id = Column(Integer, primary_key=True)
    name = Column(String(70), nullable=False, unique=True)

    def __repr__(self) -> str:
        return f"<CategoryVersion [{self.name}]>"

    __str__ = __repr__


class Category(base.ModelBase, SVGImageMixin):
    __tablename__ = "category"

    id = Column(Integer, primary_key=True)
    name = Column(String(70), nullable=False, unique=True)
    image_id = Column(String(70), nullable=True)

    display_name = Column(String(70), nullable=True)
    ordering_weight = Column(Integer, nullable=True)

    versions = relationship(
        "CategoryVersion", backref="categories", secondary=category_versions
    )

    def __repr__(self) -> str:
        return f"<Category [{self.name}]>"

    __str__ = __repr__


class State(base.ModelBase):
    __tablename__ = "state"
    INTERNATIONAL_FLAG = "ZZ"

    id = Column(Integer, primary_key=True)
    name = Column(String(40), nullable=False, unique=True)
    abbreviation = Column(String(2), nullable=False, unique=True)

    def __repr__(self) -> str:
        return f"<State [{self.name} ({self.abbreviation})]>"

    def __str__(self) -> str:
        return f"{self.name} ({self.abbreviation})"


class Language(base.ModelBase):
    __tablename__ = "language"
    ENGLISH = "English"

    id = Column(Integer, primary_key=True)
    name = Column(String(70), nullable=False, unique=True)
    abbreviation = Column(String(10), nullable=True, unique=True)
    iso_639_3 = Column("iso-639-3", String(10), nullable=True, unique=True)
    inverted_name = Column(String(255), nullable=True)
    slug = Column(String(128), unique=True)

    def __repr__(self) -> str:
        return self.name

    __str__ = __repr__


@enum.unique
class AgreementNames(enum.Enum):
    SERVICE = "service"
    TERMS_OF_USE = "terms"
    PRIVACY_POLICY = "privacy"
    GINA = "gina"
    MICROSOFT = "Microsoft"
    CHEESECAKE_FACTORY = "cheesecake_factory"
    MARATHON_PETROLEUM = "marathon_petroleum"


_AGREEMENT_DISPLAY_NAME_REGISTRY = {
    AgreementNames.SERVICE: lazy_gettext("profiles_practitioner_service_agreement"),
    AgreementNames.TERMS_OF_USE: lazy_gettext("profiles_terms_of_use"),
    AgreementNames.PRIVACY_POLICY: lazy_gettext("profiles_privacy_policy"),
    AgreementNames.GINA: lazy_gettext("profiles_gina_authorization"),
    AgreementNames.MICROSOFT: lazy_gettext("profiles_microsoft_employee_consent_form"),
    AgreementNames.CHEESECAKE_FACTORY: lazy_gettext(
        "profiles_employee_incentive_consent_form"
    ),
    AgreementNames.MARATHON_PETROLEUM: lazy_gettext(
        "profiles_employee_incentive_consent_form"
    ),
}
assert all(
    a in _AGREEMENT_DISPLAY_NAME_REGISTRY for a in AgreementNames
), "A display name must be defined for each kind of user agreement."

_AGREEMENT_ADMIN_DISPLAY_NAME_REGISTRY = {
    **_AGREEMENT_DISPLAY_NAME_REGISTRY,
    AgreementNames.CHEESECAKE_FACTORY: lazy_gettext(
        "profiles_employee_incentive_consent_form_cheesecake_factory"
    ),
    AgreementNames.MARATHON_PETROLEUM: lazy_gettext(
        "profiles_employee_incentive_consent_form_marathon_petroleum"
    ),
}


def agreement_display_name(a: AgreementNames) -> str:
    return _AGREEMENT_DISPLAY_NAME_REGISTRY[a]


def agreement_admin_display_name(a: AgreementNames) -> str:
    return _AGREEMENT_ADMIN_DISPLAY_NAME_REGISTRY[a]


class Agreement(base.ModelBase):
    __tablename__ = "agreement"

    id = Column(Integer, primary_key=True)
    version = Column(Integer, default=1, nullable=False)
    name = Column(
        Enum(
            AgreementNames,
            native_enum=False,
            values_callable=lambda obj: [e.value for e in obj],
        )
    )
    html = Column(MEDIUMTEXT, nullable=False)
    constraints = (UniqueConstraint("version", "name"),)
    accept_on_registration = Column(Boolean, default=True, nullable=False)
    optional = Column(Boolean, default=False, nullable=True)
    language_id = Column(
        Integer,
        ForeignKey("language.id"),
        default=select([Language.id]).where(Language.name == "English"),
    )
    language = relationship("Language")

    def __repr__(self) -> str:
        return f"<Agreement [{self.id}] Name: {self.name} Version: {self.version}>"

    @property
    def display_name(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return agreement_display_name(self.name)  # type: ignore[arg-type] # Argument 1 to "agreement_display_name" has incompatible type "Optional[str]"; expected "AgreementNames"

    @property
    def admin_display_name(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return agreement_admin_display_name(self.name)  # type: ignore[arg-type] # Argument 1 to "agreement_admin_display_name" has incompatible type "Optional[str]"; expected "AgreementNames"

    @classmethod
    def get_by_version(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls, agreement_name, version: int, language: Language | None = None
    ):
        query = db.session.query(cls).filter_by(name=agreement_name, version=version)

        if not language:
            language = Language.query.filter_by(name=Language.ENGLISH).one_or_none()
            query = query.filter(
                or_(cls.language_id == None, cls.language_id == language.id),  # type: ignore[union-attr] # Item "None" of "Optional[Language]" has no attribute "id"
            )
        else:
            query = query.filter(cls.language_id == language.id)

        return query.one()

    @classmethod
    def latest_version(cls, agreement_name, language: Language | None = None):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        query = db.session.query(cls).order_by(cls.version.desc())

        # if no language was passed, or the agreement does not have a language,
        # find English agreements
        if not language:
            language = Language.query.filter_by(name=Language.ENGLISH).one_or_none()
            query = query.filter(
                cls.name == agreement_name,
                or_(cls.language_id == None, cls.language_id == language.id),  # type: ignore[union-attr] # Item "None" of "Optional[Language]" has no attribute "id"
            )
        else:
            query = query.filter(
                cls.name == agreement_name, cls.language_id == language.id
            )

        return query.first()

    @classmethod
    def latest_versions(cls, agreement_names, language: Language | None = None):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        """
        Find the latest version of each agreement.

        If no language was specified or the agreement does not have a language,
        find the latest English version of the agreements.
        """

        if not language:
            language = Language.query.filter_by(name=Language.ENGLISH).one_or_none()

        subquery = (
            db.session.query(
                cls.name,
                func.max(cls.version).label("version"),
                cls.language_id,
            )
            .filter(
                cls.name.in_(agreement_names),
                cls.language_id == language.id,  # type: ignore[union-attr] # Item "None" of "Optional[Language]" has no attribute "id"
            )
            .group_by(cls.name, cls.language_id)
            .subquery()
        )

        return (
            db.session.query(cls)
            .join(
                subquery,
                and_(
                    subquery.c.name == cls.name,
                    subquery.c.version == cls.version,
                    subquery.c.language_id == cls.language_id,
                ),
            )
            .all()
        )

    @staticmethod
    def get_agreements(user) -> [AgreementNames]:  # type: ignore[valid-type,no-untyped-def] # Bracketed expression "[...]" is not valid as a type #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        if user.practitioner_profile is not None:
            return [AgreementNames.SERVICE]
        elif user.member_profile is not None:
            return [
                AgreementNames.TERMS_OF_USE,
                AgreementNames.PRIVACY_POLICY,
                AgreementNames.GINA,
                AgreementNames.MICROSOFT,
                AgreementNames.CHEESECAKE_FACTORY,
                AgreementNames.MARATHON_PETROLEUM,
            ]
        else:
            log.warning(
                "User is neither a practitioner nor a member and has no agreements.",
                user_id=user.id,
            )
            return []

    @classmethod
    def latest_agreements(cls, user, language: Language | None = None):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        agreement_names = cls.get_agreements(user)
        if not agreement_names:
            return []

        return cls.latest_versions(agreement_names, language=language)


class AgreementAcceptance(base.TimeLoggedModelBase):
    """
    created_at is agreement datetime
    """

    __tablename__ = "agreement_acceptance"

    id = Column(Integer, primary_key=True)
    agreement_id = Column(Integer, ForeignKey("agreement.id"))
    agreement = relationship("Agreement")
    user_id = Column(Integer, ForeignKey("user.id"))
    user = relationship("User")
    accepted = Column(Boolean, nullable=True, default=True)

    def __repr__(self) -> str:
        return f"<AgreementAcceptance [{self.agreement_id}/{self.user_id}] @ {self.created_at}>"

    __str__ = __repr__

    def audit_creation(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        audit(
            ACTIONS.agreement_accepted,
            **{  # type: ignore[arg-type] # Argument 2 to "audit" has incompatible type "**Dict[str, Union[str, int, None]]"; expected "Optional[int]" #type: ignore[arg-type] # Argument 2 to "audit" has incompatible type "**Dict[str, Union[str, int, None]]"; expected "Optional[str]"
                "agreement_id": self.agreement_id,
                "user_id": self.user_id,
                "created_at": self.created_at.isoformat(),
                "accepted": self.accepted,
            },
        )

    def audit_update(self) -> None:
        audit(
            ACTIONS.agreement_updated,
            **{  # type: ignore[arg-type] # Argument 2 to "audit" has incompatible type "**Dict[str, Union[str, int, None]]"; expected "Optional[int]" #type: ignore[arg-type] # Argument 2 to "audit" has incompatible type "**Dict[str, Union[str, int, None]]"; expected "Optional[str]"
                "agreement_id": self.agreement_id,
                "user_id": self.user_id,
                "modified_at": self.modified_at.isoformat(),
                "accepted": self.accepted,
            },
        )


practitioner_characteristics = db.Table(
    "practitioner_characteristics",
    Column(
        "practitioner_id",
        Integer,
        ForeignKey("practitioner_profile.user_id"),
        primary_key=True,
    ),
    Column(
        "characteristic_id", Integer, ForeignKey("characteristic.id"), primary_key=True
    ),
)


class OrganizationAgreement(base.ModelBase):
    __tablename__ = "organization_agreements"

    id = Column(BigInteger, primary_key=True)

    agreement_id = Column(Integer, ForeignKey("agreement.id"))
    agreement = relationship("Agreement", backref="organization_agreements")

    organization_id = Column(Integer, ForeignKey("organization.id"))
    organization = relationship("Organization", backref="organization_agreements")

    def __repr__(self) -> str:
        return (
            f"<OrganizationAgreement [{self.id}] "
            f"Agreement [{self.agreement_id}]: {self.agreement.name} "
            f"Organization [{self.organization_id}]: {self.organization.name}>"
        )


class Characteristic(base.TimeLoggedModelBase):
    __tablename__ = "characteristic"

    def __repr__(self) -> str:
        return f"<Characteristic[{self.id}]: {self.name}>"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), nullable=False, unique=True)

    practitioners = relationship(
        "PractitionerProfile",
        backref="characteristics",
        secondary=practitioner_characteristics,
    )


class PractitionerData(base.ModelBase):
    __tablename__ = "practitioner_data"

    user_id = Column(Integer, ForeignKey("user.id"), primary_key=True)
    created_at = Column(
        DateTime,
        default=lambda: datetime.datetime.utcnow(),
        doc="When this record was created.",
    )
    practitioner_profile_json = Column(Text, nullable=True)
    practitioner_profile_modified_at = Column(DateTime, nullable=True)
    need_json = Column(Text, nullable=True)
    need_modified_at = Column(DateTime, nullable=True)
    vertical_json = Column(Text, nullable=True)
    vertical_modified_at = Column(DateTime, nullable=True)
    specialty_json = Column(Text, nullable=True)
    specialty_modified_at = Column(DateTime, nullable=True)
    next_availability = Column(DateTime, nullable=True)


def verticals_added_listener(profile, vertical, initiator):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    from models.products import Product

    log.debug(
        f"Adding products for {vertical} for Practitioner Profile User: ({profile.user.id})"
    )

    practitioner = profile.user
    for product in vertical.products:
        _product = Product.query.filter(
            Product.vertical == vertical,
            Product.minutes == product["minutes"],
            Product.practitioner == practitioner,
        ).first()

        if _product:
            if not _product.is_active:
                log.debug("Activating %s for User: (%s)", _product, practitioner.id)
                _product.is_active = True
                db.session.add(_product)
            else:
                log.debug(
                    f"{product['minutes']} mins product already active for User: ({practitioner.id})"
                )
            continue
        else:
            new = Product(
                minutes=product["minutes"],
                price=product["price"],
                purpose=product.get("purpose"),
                vertical=vertical,
                practitioner=practitioner,
            )
            profile.user.products.append(new)
            log.debug("Adding %s for User: (%s)", new, practitioner.id)

    log.debug("Added products for %s", profile)


def verticals_removed_listener(profile, vertical, initiator):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.debug(
        "Removing products for %s for Practitioner Profile User: (%s)",
        vertical,
        profile.user.id,
    )

    session = inspect(profile).session
    for product in profile.user.products:
        if product.vertical == vertical:
            product.is_active = False
            session.add(product)

    log.debug(
        f"Removed products for {vertical} for Practitioner Profile User: ({profile.user.id})"
    )


event.listen(PractitionerProfile.verticals, "append", verticals_added_listener)

event.listen(PractitionerProfile.verticals, "remove", verticals_removed_listener)


class PractitionersViewCache(ViewCache):
    """Deprecated and admin actions removed"""

    id_namespace = "practitioners"


class VerticalGroupsViewCache(ViewCache):
    id_namespace = "vertical_groups"
