from __future__ import annotations

import hashlib
import os
import time

import jwt

from appointments.services.video_provider.errors import RequiredParameterException
from common.constants import Environment

# These values can be found under "SDK credentials" in the Zoom developer console
ZOOM_SDK_KEY: str = os.getenv("APPT_ZOOM_SDK_KEY") or ""
ZOOM_SDK_SECRET: str = os.getenv("APPT_ZOOM_SDK_SECRET") or ""

# max length allowed for a zoom session id
MAX_ZOOM_SESSION_ID_LEN = 200

# prefix to use when generating session ids for unknown environments
UNKNOWN_ENV_PREFIX = "unknown"


def session_id_env_prefix_for_env(env: Environment) -> str:
    """
    Returns a unique prefix for the given environment. This prefix is used to
    ensure that session ids generated in different environments do not collide.
    """
    prefix_map = {
        Environment.LOCAL: "local",
        Environment.QA1: "qa1",
        Environment.QA2: "qa2",
        Environment.QA3: "qa3",
        Environment.SANDBOX: "sand",
        Environment.STAGING: "stag",
        Environment.PRODUCTION: "p",
    }
    prefix = prefix_map.get(env)
    return prefix or UNKNOWN_ENV_PREFIX


# https://developers.zoom.us/docs/video-sdk/auth/
def generate_session_id(
    appointment_id: int | None,
) -> str:
    if not appointment_id:
        raise RequiredParameterException(
            "appointment_id required to generate zoom video session id"
        )
    # Zoom does not provide separate authentication credentials for dev and prod
    # environments. To ensure a non prod session id could not ever match a prod
    # session id, we add a plain text prefix per environment.
    session_id_env_prefix = session_id_env_prefix_for_env(Environment.current())

    # NOTE: this is a naive approach to generating a session id. The
    # implementation was chosen given only the constraint of uniqueness against
    # an (env,appointment_id) pair. In the future their may be a need to add
    # other values to his seed string. Changes to this implementation during
    # live calls was previously accounted for by storing the calculated session
    # id on the appt state object once generated instead of recalculating it on
    # every request. Before modification you should confirm that constraint is
    # still valid.
    #
    # It should be noted that if during a active call the session_id_seed_str
    # implementation changes (due to a deploy) state object is lost and for what
    # ever reason the state object is not found, the state recovery process will
    # generate a different session id than before kicking clients out of the
    # current zoom call and into a new one. This is a very slim edge case but
    # should be considered non the less.
    session_id_seed_str: str = f"{session_id_env_prefix}-maven-{appointment_id}"
    hashed_val = hashlib.md5(session_id_seed_str.encode()).hexdigest()

    # the total length of the session id must not exceed 200 characters
    return hashed_val[:MAX_ZOOM_SESSION_ID_LEN]


def generate_access_token(
    appointment_id: int | None,
    session_id: str | None,
    user_id: int | None,
    # NOTE: this is not currently used but could potentially provide value in
    # the future. It appears here to maintain the common generate_access_token
    # interface to video_provider.
    optional_token_user_data: dict | None = None,
) -> str:
    if not appointment_id:
        raise RequiredParameterException(
            "appointment_id required to generate zoom access token"
        )

    if not session_id:
        raise RequiredParameterException(
            "session_id required to generate zoom access token"
        )

    epoch_time = int(time.time())
    token_ttl = 60 * 60 * 2  # 2 hours

    jwt_algo = "HS256"
    token_header = {
        "alg": jwt_algo,
        "typ": "JWT",
    }

    # stringifying inside the payload doesn't work, it gets reset during encoding
    user_id_string = str(user_id) if user_id is not None else None

    # From zoom's documentation:
    # https://developers.zoom.us/docs/video-sdk/auth/
    token_payload = {
        "version": 1,  # specified in the documentation
        "app_key": ZOOM_SDK_KEY,
        # this is the video session identifier
        "tpc": session_id,
        # A role value of 1 indicates a host. A value of 0 indicates a
        # participant
        "role_type": 0,
        # The time at which the token was issued (epoch)
        "iat": epoch_time,
        # The expiration time of the token (epoch+TTL)
        "exp": epoch_time + token_ttl,
        # The member or provider ID
        "user_identity": user_id_string,
    }
    access_token = jwt.encode(
        token_payload,
        ZOOM_SDK_SECRET,
        algorithm=jwt_algo,
        headers=token_header,
    )
    return access_token


def api_key() -> str | None:
    # we do not get an api key from zoom
    return None
