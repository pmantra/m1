from __future__ import annotations

import enum
import os
from calendar import timegm
from datetime import datetime
from typing import TypedDict

import jwt

JWT_SECRET = os.getenv("MFA_JWT_SECRET")


class VerificationRequiredActions(str, enum.Enum):
    LOGIN = "login"
    ENABLE_MFA = "enable_mfa"
    DISABLE_MFA = "disable_mfa"
    REQUIRE_MFA = "require_mfa"

    def __str__(self) -> str:
        return self.value


VerificationRequiredActionNames = frozenset(
    a.value for a in VerificationRequiredActions
)


def message_for_sms_code_sent(phone_number: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    last_four = phone_number[-4:]
    message = f"Enter the code we sent to your phone number ending in {last_four}"
    return message


def encode_jwt(action: VerificationRequiredActions, user, expiry_seconds=None):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    if not isinstance(action, VerificationRequiredActions):
        raise TypeError("action must be a VerificationRequiredActions enum")

    if expiry_seconds is None:
        expiry_seconds = 10 * 60  # 10 minutes from now

    expiry = timegm(datetime.utcnow().utctimetuple()) + expiry_seconds
    payload = {
        "action": action.value,
        "exp": expiry,
        "sub": "mfa_verification",
        "user_id": user.id,
    }

    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_jwt(encoded: bytes) -> _DecodedJWT:
    return jwt.decode(
        jwt=encoded,
        key=JWT_SECRET,
        algorithms="HS256",
        options={"verify_signature": True, "verify_exp": True},
    )


class _DecodedJWT(TypedDict, total=False):
    action: VerificationRequiredActions
    user_id: int
    exp: int
    sub: str
