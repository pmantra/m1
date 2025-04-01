from __future__ import annotations

import ddtrace
from maven import feature_flags

from appointments.schemas.appointment_connection import (
    HEARTBEAT_CONNECTION_INTERVAL_DEFAULT,
    HEARTBEAT_CONNECTION_INTERVAL_FLAG,
    HEARTBEAT_CONNECTION_PATH,
    AppointmentConnectionType,
    HeartbeatConnectionSchema,
    LaunchConfigurationSchema,
    VideoPlatform,
)
from authz.models.roles import ROLES
from utils.log import logger

from .video import (
    get_video_platform_access_token_for_appointment_session,
    get_video_platform_session_id_for_appointment,
)

log = logger(__name__)


@ddtrace.tracer.wrap()
def generate_launch_configuration(
    appointment_id: int,
    user_id: int,
    user_role: str | None = None,
) -> LaunchConfigurationSchema | None:
    if any(arg is None for arg in (appointment_id, user_id, user_role)):
        raise ValueError(
            "appointment state, appointment_id, user_id, and user_role must be provided to generate a launch configuration.",
        )
    session_id = get_video_platform_session_id_for_appointment(
        appointment_id=appointment_id
    )
    log.info(
        "created session ID for appointment ID",
        appointment_id=appointment_id,
        session_id=session_id,
    )
    # tokens are generated every time to ensure expiry is carried forward
    token = get_video_platform_access_token_for_appointment_session(
        appointment_id=appointment_id,
        session_id=session_id,
        user_id=user_id,
        optional_token_user_data={
            "appointment_id": appointment_id,
            "user_id": user_id,
            "role": user_role,
        },
    )

    return LaunchConfigurationSchema(
        connection_type=AppointmentConnectionType.VIDEO,
        video_platform=VideoPlatform.ZOOM,
        session_id=session_id,
        token=token,
        api_key=None,
    )


@ddtrace.tracer.wrap()
def generate_heartbeat_config(
    appointment_api_id: int,
) -> HeartbeatConnectionSchema:
    if not appointment_api_id:
        raise ValueError("appointment_api_id must be provided")

    return HeartbeatConnectionSchema(
        period_millis=feature_flags.int_variation(
            HEARTBEAT_CONNECTION_INTERVAL_FLAG,
            default=HEARTBEAT_CONNECTION_INTERVAL_DEFAULT,
        ),
        heartbeat_path=HEARTBEAT_CONNECTION_PATH.format(
            appointment_api_id=appointment_api_id,
        ),
    )


@ddtrace.tracer.wrap()
def get_appointment_user_role(
    user_roles: list[str] | None,
) -> str | None:
    """
    Given a list of user roles, return the first role that appears in the set of
    roles relevant to appointment connections. If no roles are provided, return
    None.
    It is recommended to call this with `user.identities` as the argument.

    Allowed roles are:
    - ROLES.practitioner
    - ROLES.member
    """
    if not user_roles:
        return None

    allowed_roles: list[str] = [
        ROLES.practitioner,
        ROLES.member,
    ]

    # return the first role that appears in our allowed roles list
    match = next(role for role in user_roles if role in allowed_roles)
    return match if match else None
