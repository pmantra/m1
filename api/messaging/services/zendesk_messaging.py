# Code related to the Zendesk Messaging API functionality
import datetime
import os
import uuid

import jwt

from authn.models.user import User
from messaging.services.zendesk import get_zenpy_user_from_zendesk
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class MissingZendeskEnvException(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class InvalidUserIdException(Exception):
    pass


class InvalidZendeskUserIdException(Exception):
    pass


def generate_jwt(user_id: int) -> str:
    user = db.session.query(User).get(user_id)
    if not user:
        log.info("Invalid user_id", user_id=user_id)
        raise InvalidUserIdException()
    zendesk_sso_secret = os.environ.get("ZENDESK_SSO_SECRET")

    if not zendesk_sso_secret:
        raise MissingZendeskEnvException(
            message="ZENDESK_SSO_SECRET env var is missing"
        )
    zd_user = get_zenpy_user_from_zendesk(
        zendesk_user_id=str(user.zendesk_user_id),
        user_id=user.id,
        called_by="zendesk_messaging_generate_jwt",
    )
    if not zd_user:
        raise InvalidZendeskUserIdException()
    # Assign the timestamp at which the token was generated
    issued_at_timestamp = int(datetime.datetime.utcnow().timestamp())

    # Generate and assign a unique id for the token (to prevent token replay attacks)
    json_token_id = str(uuid.uuid4())

    jwt_token = jwt.encode(
        {
            "scope": "user",
            "name": zd_user.name,
            "email": zd_user.email,
            "iat": issued_at_timestamp,
            "jti": json_token_id,
        },
        # TODO: Do we want to add expiration? 5 min
        zendesk_sso_secret,
        algorithm="HS256",
        headers={"typ": "JWT"},
    )
    return jwt_token
