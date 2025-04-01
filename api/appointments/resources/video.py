from functools import wraps

from flask import abort, request
from flask_admin.model.helpers import get_mdict_item_or_list

from appointments.schemas.video import (
    VideoSessionSchema,
    VideoSessionSchemaV2,
    VideoSessionTokenSchema,
)
from appointments.services import video
from common.constants import Environment
from common.services import ratelimiting
from common.services.api import AuthenticatedResource
from glidepath import glidepath

QUERY_PARAM_KEY_OBFUSCATED_APPOINTMENT_ID = "oaid"
QUERY_PARAM_KEY_VIDEO_PLATFORM = "vp"


# In non-prod envs we call generate session id and tokens with a fake appointment ID
FAKE_APPOINTMENT_ID = -1


def abort_in_prod(f):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    @wraps(f)
    def decorated_function(*args, **kwargs) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        if Environment.current() == Environment.PRODUCTION:
            # This endpoint is used for non prod envs only
            abort(403)
        return f(*args, **kwargs)

    return decorated_function


class VideoSessionResource(AuthenticatedResource):
    @ratelimiting.ratelimited(attempts=25, cooldown=(60 * 3))
    @abort_in_prod
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation

        # In non prod envs we call generate session with a placeholder appt id to comply with function required args
        session_id = video.get_video_platform_session_id_for_appointment(
            appointment_id=FAKE_APPOINTMENT_ID,
            appointment=None,
            video_platform=video.DEFAULT_VIDEO_PLATFORM,
        )

        with glidepath.respond():
            schema = VideoSessionSchema()
            data = {
                "id": session_id,
            }
            return schema.dump(data)


class VideoSessionResourceV2(AuthenticatedResource):
    @ratelimiting.ratelimited(attempts=25, cooldown=(60 * 3))
    @abort_in_prod
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # get appointment_id from query param
        appointment_api_id = int(
            get_mdict_item_or_list(
                request.args,
                QUERY_PARAM_KEY_OBFUSCATED_APPOINTMENT_ID,
            )
        )

        session_id = video.get_video_platform_session_id_for_appointment(
            appointment_id=appointment_api_id,
        )

        with glidepath.respond():
            schema = VideoSessionSchemaV2()
            data = {
                "session_id": session_id,
            }
            return schema.dump(data)


class VideoSessionTokenResource(AuthenticatedResource):
    @ratelimiting.ratelimited(attempts=50, cooldown=(60 * 3))
    @abort_in_prod
    def get(self, session_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation

        # In non prod envs we call generate session with a placeholder appt id to comply with function required args
        access_token = video.get_video_platform_access_token_for_appointment_session(
            appointment_id=FAKE_APPOINTMENT_ID,
            session_id=session_id,
        )

        with glidepath.respond():
            schema = VideoSessionTokenSchema()
            data = {
                "session_id": session_id,
                "token": access_token,
            }
            return schema.dump(data)


class VideoSessionTokenResourceV2(AuthenticatedResource):
    @ratelimiting.ratelimited(attempts=50, cooldown=(60 * 3))
    @abort_in_prod
    def get(self, session_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        appointment_api_id = int(
            get_mdict_item_or_list(
                request.args,
                QUERY_PARAM_KEY_OBFUSCATED_APPOINTMENT_ID,
            )
        )
        access_token = video.get_video_platform_access_token_for_appointment_session(
            appointment_id=appointment_api_id,
            session_id=session_id,
        )
        with glidepath.respond():
            schema = VideoSessionTokenSchema()
            data = {
                "session_id": session_id,
                "token": access_token,
            }
            return schema.dump(data)
