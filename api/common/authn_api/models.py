from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List


@dataclass
class AuthnApiUser:
    id: int
    email: str
    username: str
    first_name: str
    middle_name: str
    last_name: str
    active: bool
    email_confirmed: bool
    mfa_state: str
    sms_phone_number: str

    def __init__(self, data: dict) -> None:
        for key, value in data.items():
            setattr(self, key, value)


@dataclass
class AuthnApiUserAuth:
    id: int
    user_id: int
    refresh_token: str
    external_id: str

    def __init__(self, data: dict) -> None:
        for key, value in data.items():
            setattr(self, key, value)


@dataclass
class AuthnApiUserExternalIdentity:
    id: int
    user_id: int
    identity_provider_id: int
    external_user_id: str
    external_organization_id: str
    unique_corp_id: str
    reporting_id: str

    def __init__(self, data: dict) -> None:
        for key, value in data.items():
            setattr(self, key, value)


@dataclass
class AuthnApiOrgAuth:
    id: int
    organization_id: int
    mfa_required: bool

    def __init__(self, data: dict) -> None:
        for key, value in data.items():
            setattr(self, key, value)


class AuthnApiIdentityProvider:
    id: int
    name: str

    def __init__(self, data: dict) -> None:
        for key, value in data.items():
            setattr(self, key, value)


@dataclass
class GetUserAllResponse:
    users: List[AuthnApiUser]

    @staticmethod
    def from_dict(data: Any) -> GetUserAllResponse:
        users_data = [AuthnApiUser(data=item) for item in data]
        return GetUserAllResponse(users=users_data)


@dataclass()
class GetUserAuthAllResponse:
    user_auths: List[AuthnApiUserAuth]

    @staticmethod
    def from_dict(data: Any) -> GetUserAuthAllResponse:
        user_auth_data = [AuthnApiUserAuth(data=item) for item in data]
        return GetUserAuthAllResponse(user_auths=user_auth_data)


@dataclass()
class GetUserExternalIdentityAllResponse:
    user_external_identities: List[AuthnApiUserExternalIdentity]

    @staticmethod
    def from_dict(data: Any) -> GetUserExternalIdentityAllResponse:
        user_external_identity_data = [
            AuthnApiUserExternalIdentity(data=item) for item in data
        ]
        return GetUserExternalIdentityAllResponse(
            user_external_identities=user_external_identity_data
        )


@dataclass
class GetOrgAuthAllResponse:
    org_auths: List[AuthnApiOrgAuth]

    @staticmethod
    def from_dict(data: Any) -> GetOrgAuthAllResponse:
        org_auth_data = [AuthnApiOrgAuth(data=item) for item in data]
        return GetOrgAuthAllResponse(org_auths=org_auth_data)


@dataclass
class GetIdentityProviderAllResponse:
    identity_providers: List[AuthnApiIdentityProvider]

    @staticmethod
    def from_dict(data: Any) -> GetIdentityProviderAllResponse:
        org_auth_data = [AuthnApiIdentityProvider(data=item) for item in data]
        return GetIdentityProviderAllResponse(identity_providers=org_auth_data)
