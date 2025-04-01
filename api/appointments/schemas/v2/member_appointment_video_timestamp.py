from marshmallow import Schema

from views.schemas.common_v3 import MavenDateTime


class VideoTimestampPostRequestSchema(Schema):
    started_at = MavenDateTime(required=False, load_default=None)
    ended_at = MavenDateTime(required=False, load_default=None)
    disconnected_at = MavenDateTime(required=False, load_default=None)
    phone_call_at = MavenDateTime(required=False, load_default=None)
