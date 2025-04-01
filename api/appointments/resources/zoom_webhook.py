from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import Any, Dict, Optional, Union

from flask import jsonify, make_response, request
from werkzeug.datastructures import EnvironHeaders

from common.services.api import UnauthenticatedResource
from utils.log import logger

ZOOM_API_SECRET_TOKEN: Optional[str] = os.environ.get("ZOOM_API_SECRET_TOKEN")

log = logger(__name__)


class ZoomWebhookResource(UnauthenticatedResource):
    def post(self) -> Union[Dict[str, Any], Any]:
        """
        Webhook to register callbacks from Zoom whenever a connection has been
        created or disconnected.

        Zoom documentation:
        https://developers.zoom.us/docs/api/rest/webhook-reference/
        """

        headers = request.headers
        data = request.json

        secret_token = str(ZOOM_API_SECRET_TOKEN)

        zoom_signature_verified = verify_zoom_signature(headers, data, secret_token)
        if not zoom_signature_verified:
            return make_response(
                jsonify(
                    {
                        "message": "Signatures do not match! Webhook request did not come from Zoom and may be fraudulent."
                    }
                ),
                400,
            )

        event = data.get("event")
        if event == "endpoint.url_validation":
            response = validate_zoom_url(data, secret_token)
            return make_response(jsonify(response), 200)

        # extract session data
        event_data = data.get("payload", {}).get("object", {})

        # all events of type 'session' will have 'session_name' in the request body
        # session_name maps to our session_id, the session_id that comes from zoom is something used on their side
        session_id = event_data.get("session_name")
        issues = event_data.get("issues")

        # If session id is not found, this means we are receiving another event type, such as 'meeting'
        if session_id and issues:
            log.warn(
                "Issue encountered during the appointment",
                session_id=session_id,
                zoom_event=event,
                issues=issues,
            )

        return make_response(jsonify({"message": "Signatures match!"}), 200)


def verify_zoom_signature(
    headers: EnvironHeaders, data: dict, secret_token: str
) -> bool:
    """
    Verify that the request came from Zoom by comparing the received signature
    with the computed signature.
    """
    x_zm_signature = headers.get("X-Zm-Signature")
    x_zm_request_timestamp = headers.get("X-Zm-Request-Timestamp")

    # Create message to hash
    json_data = json.dumps(data, separators=(",", ":"))
    message = f"v0:{x_zm_request_timestamp}:{json_data}"

    # Compute hash using secret token
    hashed_message = hmac.new(
        secret_token.encode(), msg=message.encode(), digestmod=hashlib.sha256
    ).hexdigest()

    # Create signature
    signature = f"v0={hashed_message}"

    return x_zm_signature == signature


def validate_zoom_url(data: dict, secret_token: str) -> dict:
    """
    Handle URL validation event by returning the plain token and its hashed value.
    """
    plain_token = data.get("payload", {}).get("plainToken")
    hashed_token = hmac.new(
        secret_token.encode(),
        msg=plain_token.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()

    return {"plainToken": plain_token, "encryptedToken": hashed_token}
