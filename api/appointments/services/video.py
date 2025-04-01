from __future__ import annotations

import ddtrace

from appointments.schemas.appointment_connection import VideoPlatform
from appointments.services.video_provider import zoom
from utils.log import logger

log = logger(__name__)

DEFAULT_VIDEO_PLATFORM = VideoPlatform.ZOOM


@ddtrace.tracer.wrap()
def get_video_platform_session_id_for_appointment(
    appointment_id: int,
) -> str:
    if not appointment_id:
        raise Exception("appointment_id required to generate video session id")
    return zoom.generate_session_id(appointment_id)


@ddtrace.tracer.wrap()
def get_video_platform_access_token_for_appointment_session(
    appointment_id: int,
    session_id: str | None,
    user_id: int | None = None,
    optional_token_user_data: dict | None = None,
) -> str:
    return zoom.generate_access_token(
        appointment_id=appointment_id,
        session_id=session_id,
        optional_token_user_data=optional_token_user_data,
        user_id=user_id,
    )


def get_video_platform_api_key(
    video_platform: VideoPlatform | None,
) -> str | None:

    return zoom.api_key()
