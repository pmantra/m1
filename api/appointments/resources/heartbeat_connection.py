from __future__ import annotations

from dataclasses import asdict

import ddtrace
from flask import request
from flask_restful import abort

from appointments.models.appointment import Appointment
from appointments.schemas.appointment_connection import AppointmentConnectionResponse
from appointments.services.video_connection import (
    generate_heartbeat_config,
    generate_launch_configuration,
    get_appointment_user_role,
)
from common.services.api import AuthenticatedResource
from utils.log import logger

from .middleware import with_valid_appointment

log = logger(__name__)


class HeartbeatConnectionResource(AuthenticatedResource):
    @with_valid_appointment
    @ddtrace.tracer.wrap()
    def post(self, appointment: Appointment):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        user = self.user
        user_id = user.id
        appointment_id = appointment.id
        data = request.get_json(force=True)

        try:
            log.info("Processing request that contain keys", keys=list(data.keys()))
        except Exception as e:
            log.exception(
                "Exception parsing connection client info",
                exception=e,
            )
            abort(400)

            launch_configuration = generate_launch_configuration(
                appointment_id=appointment_id,
                user_id=user_id,
                user_role=get_appointment_user_role(self.user.identities),
            )
            heartbeat_configuration = generate_heartbeat_config(
                appointment_api_id=appointment.api_id,
            )

            # Build the Connection response
            res = AppointmentConnectionResponse(
                heartbeat=heartbeat_configuration,
                launch_configuration=launch_configuration,
            )
            resp_dict = asdict(res)

            return resp_dict, 200
