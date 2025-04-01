from __future__ import annotations

from flask_restful import abort

from utils.rotatable_token import BRAZE_CONNECTED_CONTENT_TOKEN
from views.schemas.base import ListWithDefaultV3, MavenSchemaV3, StringWithDefaultV3


def _validate_token(value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # TODO: remove this after QA testing
    if not BRAZE_CONNECTED_CONTENT_TOKEN.primary:
        return True
    if BRAZE_CONNECTED_CONTENT_TOKEN.check_token(value):
        return True
    abort(403, message="Invalid Token")


class BrazeConnectedContentSchemaV3(MavenSchemaV3):
    token = StringWithDefaultV3(
        required=True, dump_default="", validate=_validate_token
    )
    esp_id = StringWithDefaultV3(required=True, dump_default="")
    type = StringWithDefaultV3(dump_default="")
    types = ListWithDefaultV3(StringWithDefaultV3(dump_default=""), dump_default=[])
