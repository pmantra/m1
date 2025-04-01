from __future__ import annotations

import datetime
from typing import TypedDict

from flask import request
from flask_restful import abort
from sqlalchemy.dialects import mysql
from sqlalchemy.exc import IntegrityError
from werkzeug.local import LocalProxy

from appointments.services.common import get_platform
from common import stats
from common.services.api import AuthenticatedResource
from models import profiles
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class InvalidUserAgentException(Exception):
    pass


class UserDevicesPostResponse(TypedDict):
    id: str
    device_token: str
    """Mapped from the device.device_id field."""
    application_name: str
    user_id: str


class UserDevicesResource(AuthenticatedResource):
    def post_request(self, request: LocalProxy) -> dict:
        headers = str(request.headers["User-Agent"])
        if "com.mavenclinic.Forum" in headers:
            user_agent_value = "forum"
        elif "com.mavenclinic.Practitioner" in headers:
            user_agent_value = "practitioner"
        elif "com.mavenclinic.Maven" in headers:
            user_agent_value = "member"
        else:
            raise InvalidUserAgentException(
                f"Bad User-Agent for application name: {headers}"
            )
        request_json = request.json if request.is_json else None
        return {
            "device_token": str(request_json["device_token"]),
            "User-Agent": user_agent_value,
        }

    def post(self, user_id: int) -> tuple[UserDevicesPostResponse, int]:
        args = self.post_request(request)  # type: ignore[arg-type] # Argument 1 to "post_request" of "UserDevicesResource" has incompatible type "Request"; expected "LocalProxy"

        if not args or not args.get("device_token") or not args.get("User-Agent"):
            if not not args.get("User-Agent"):
                log.warn("No user agent for User", user_id=str(user_id))
            if not args.get("device_token"):
                log.warn("No device_token for User", user_id=str(user_id))
            abort(
                400,
                message=f"Malformed request or missing data for registering <User {user_id}> device!",
            )

        device_token = args["device_token"]
        user_agent = args["User-Agent"]

        # TODO: Upon creation of a V2 for this endpoint, we should consider enforcing proper validation and error handling for tokens that exceed
        #  the expected length; for now, we are truncating manually
        if len(device_token) > 191:
            device_token = device_token[:191]
            stats.increment(
                metric_name="api.views.settings.token_length_exceeded",
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=[f"platform:{get_platform(user_agent)}"],
            )

        log.debug(f"Device Args: {args}")

        if not user_id == self.user.id:
            abort(403, message="Can only add a device for yourself!")

        insert = mysql.insert(profiles.Device).values(
            user_id=user_id,
            device_id=device_token,
            application_name=user_agent,
            is_active=True,
        )
        # resolve race condition due to concurrent POST requests
        statement = insert.on_duplicate_key_update(
            user_id=user_id,
            application_name=insert.inserted.application_name,
            is_active=insert.inserted.is_active,
            modified_at=datetime.datetime.utcnow(),
        )

        try:
            db.session.execute(statement)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            log.info(
                "Failed to persist Device for member - session has been rolled back.",
                user_id=user_id,
            )
            abort(400, message="Failed to persist Device for member")

        # query the updated `Device` to ensure a fresh session state
        device = (
            db.session.query(profiles.Device)
            .filter_by(device_id=device_token)
            .one_or_none()
        )

        if not device:
            abort(404, message="No device found for member")

        response = UserDevicesPostResponse(
            id=str(device.id),
            device_token=str(device.device_id),
            application_name=device.application_name,
            user_id=str(device.user_id),
        )
        return response, 200
