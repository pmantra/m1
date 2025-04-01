from __future__ import annotations

import dataclasses
import datetime

__all__ = (
    "IdentityProvider",
    "IdentityProviderFieldAlias",
    "User",
    "UserAuth",
    "UserExternalIdentity",
    "UserMetadata",
    "UserMFA",
    "UserMigration",
    "OrganizationAuth",
)

from typing import Literal


@dataclasses.dataclass
class User:
    """Class to represent a user"""

    email: str
    password: str
    id: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    email_confirmed: bool = False
    active: bool = True
    created_at: datetime.datetime | None = None
    modified_at: datetime.datetime | None = None


@dataclasses.dataclass
class UserMigration:
    """Class to represent a user for the data migration"""

    email: str
    password: str
    id: int | None = None
    esp_id: str | None = None
    first_name: str | None = None
    middle_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    email_confirmed: bool = False
    active: bool = True
    image_id: int | None = None
    zendesk_user_id: int | None = None
    mfa_state: str | None = None
    sms_phone_number: str | None = None
    created_at: datetime.datetime | None = None
    modified_at: datetime.datetime | None = None


@dataclasses.dataclass
class UserAuth:
    """Class to represent a user authentication object"""

    user_id: int
    id: int | None = None
    refresh_token: str | None = None
    external_id: str | None = None
    created_at: datetime.datetime | None = None
    modified_at: datetime.datetime | None = None


@dataclasses.dataclass
class UserMFA:
    """Class to capture a user's MFA related data"""

    user_id: int
    sms_phone_number: str
    external_user_id: int
    verified: bool = False
    otp_secret: str | None = None
    created_at: datetime.datetime | None = None
    modified_at: datetime.datetime | None = None
    mfa_state: MFAState | None = None

    @property
    def id(self) -> int:
        return self.user_id


MFAState = Literal["disabled", "pending_verification", "enabled"]


@dataclasses.dataclass
class UserMetadata:
    """Class to represent a user's metadata"""

    first_name: str
    last_name: str
    user_id: int = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "int")
    timezone: str = "UTC"
    middle_name: str | None = None
    image_id: int | None = None
    zendesk_user_id: int | None = None
    created_at: datetime.datetime | None = None
    modified_at: datetime.datetime | None = None

    @property
    def id(self) -> int:
        return self.user_id


@dataclasses.dataclass
class UserExternalIdentity:
    """Class to represent relationship between a user and an identity provider"""

    user_id: int
    identity_provider_id: int
    external_user_id: str
    external_organization_id: str | None = None
    reporting_id: str | None = None
    unique_corp_id: str | None = None
    id: int | None = None
    sso_email: str | None = None
    auth0_user_id: str | None = None
    sso_user_first_name: str | None = None
    sso_user_last_name: str | None = None
    created_at: datetime.datetime | None = None
    modified_at: datetime.datetime | None = None


@dataclasses.dataclass
class IdentityProvider:
    """Class to represent an identity provider"""

    name: str
    metadata: str
    id: int | None = None
    created_at: datetime.datetime | None = None
    modified_at: datetime.datetime | None = None


@dataclasses.dataclass
class IdentityProviderFieldAlias:
    """Class which represents a mapping between an IDP-provided field and a UserExternalIdentity field."""

    field: str
    alias: str
    identity_provider_id: int
    id: int | None = None
    created_at: datetime.datetime | None = None
    modified_at: datetime.datetime | None = None


@dataclasses.dataclass
class OrganizationAuth:
    """Class which represents the authentication settings of an organization"""

    organization_id: int
    id: int | None = None
    mfa_required: bool = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "bool")
    created_at: datetime.datetime | None = None
    modified_at: datetime.datetime | None = None


@dataclasses.dataclass
class MFAData:
    """Class which represents the MFA data returned to FE"""

    jwt: str | None = None
    message: str | None = None
    sms_phone_number_last_four: str | None = None
    enforcement_reason: str | None = None
