from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Column,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from direct_payment.clinic.models.clinic import FertilityClinic
from models.base import ModelBase, TimeLoggedExternalUuidModelBase
from models.profiles import RoleProfile

if TYPE_CHECKING:
    from authn.domain import model


class FertilityClinicUserProfileFertilityClinic(ModelBase):
    """
    Mapping between a FertilityClinicUserProfile and a FertilityClinic with additional metadata for that relationship.
    """

    __tablename__ = "fertility_clinic_user_profile_fertility_clinic"
    constraints = (
        UniqueConstraint("fertility_clinic_user_profile_id", "fertility_clinic_id"),  # type: ignore[assignment]
    )

    id = Column(Integer, primary_key=True)
    fertility_clinic_id = Column(
        BigInteger, ForeignKey("fertility_clinic.id"), nullable=False
    )
    fertility_clinic_user_profile_id = Column(
        BigInteger, ForeignKey("fertility_clinic_user_profile.id"), nullable=False
    )
    fertility_clinic = relationship(FertilityClinic)

    def __repr__(self) -> str:
        return f"Fertility Clinic User Profile Fertility Clinic {self.id}"


class AccountStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"

    def __str__(self) -> str:  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return str(self.value)


class FertilityClinicUserProfile(TimeLoggedExternalUuidModelBase):
    """
    FertilityClinicUserProfile represents information for a user acting on behalf of a FertilityClinic
    """

    __tablename__ = "fertility_clinic_user_profile"

    first_name = Column(String(40), nullable=False)
    last_name = Column(String(40), nullable=False)
    # Links to a specific User
    user_id = Column(Integer, nullable=False)
    status = Column(Enum(AccountStatus), nullable=False)

    clinics = relationship(
        FertilityClinic,
        uselist=True,
        secondary="fertility_clinic_user_profile_fertility_clinic",
    )

    # cache the user after first fetch to avoid multiple db calls
    _cached_user: model.User | None = None

    @property
    def user(self) -> model.User | None:
        if self._cached_user:
            return self._cached_user

        from authn.domain.service.user import UserService

        # if a user is not found, we will continue to make DB calls
        # in the future we can optimize this if we feel it is necessary
        self._cached_user = UserService().get_user(user_id=self.user_id)
        return self._cached_user

    @property
    def email(self) -> str | None:
        if self.user:
            return self.user.email
        return None

    @property
    def email_domain(self) -> str | None:
        if self.email:
            return self.email.split("@")[1]
        return None

    @property
    def active(self) -> bool:
        return self.status == AccountStatus.ACTIVE

    @property
    def full_name(self) -> str:
        return f"{self.first_name or ''} {self.last_name or ''}".strip()

    @property
    def role(self) -> str | None:
        role = RoleProfile.query.filter(RoleProfile.user_id == self.user_id).first()
        return role.role_name if role else None

    def __repr__(self) -> str:
        return f"Fertility Clinic User Profile {self.id}"
