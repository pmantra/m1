from flask_restful import abort
from marshmallow_v1 import fields

from utils.rotatable_token import BRAZE_CONNECTED_CONTENT_TOKEN
from views.schemas.common import MavenSchema


def _validate_token(value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # TODO: remove this after QA testing
    if not BRAZE_CONNECTED_CONTENT_TOKEN.primary:
        return True
    if BRAZE_CONNECTED_CONTENT_TOKEN.check_token(value):
        return True
    abort(403, message="Invalid Token")


class BrazeConnectedContentSchema(MavenSchema):
    token = fields.String(required=True, validate=_validate_token)
    esp_id = fields.String(required=True)
    type = fields.String()
    types = fields.List(fields.String())
