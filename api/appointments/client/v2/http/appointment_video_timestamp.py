import json

from flask import abort, request
from marshmallow import ValidationError

from appointments.schemas.v2.member_appointment_video_timestamp import (
    VideoTimestampPostRequestSchema,
)
from appointments.services.common import deobfuscate_appointment_id
from appointments.services.v2.appointment_timestamp import AppointmentTimestampService
from appointments.utils.errors import (
    AppointmentNotFoundException,
    MemberNotFoundException,
)
from common.services.api import AuthenticatedResource


class AppointmentVideoTimestampResource(AuthenticatedResource):
    def post(self, appointment_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        HTTP resource to add to a member's video timestamps

        NOTE: Values of "None" will be ignored by this endpoint
        - If member_started_at, member_ended_at, practitioner_started_at, or practitioner_ended_at
        are already set, we will not overwrite them.
        - If an ended_at exists and an accompanying started_at value does not exist, started_at will
        be defaulted to utcnow.

        :param appointment_id: obfuscated appointment_id
        :param started_at: appointment started at time
        :param ended_at: appointment end at time
        :param disconnected_at:
            The appointment's disconnected at time. This will also be used to set the
            "member_started_at" time if it is both not set in the database, nor
            passed in with the `started_at` parameter.
        """
        try:
            deobfuscated_appt_id = deobfuscate_appointment_id(appointment_id)
            args_schema = VideoTimestampPostRequestSchema()
            request_json = request.json if request.is_json else None
            request_params = args_schema.load(request_json)
            if not request_params:
                abort(400, "Need to send at least one parameter")

            user_agent = request.headers.get("User-Agent")
            AppointmentTimestampService().add_video_timestamp(
                self.user.id,
                deobfuscated_appt_id,
                started_at=request_params["started_at"],
                ended_at=request_params["ended_at"],
                disconnected_at=request_params["disconnected_at"],
                phone_call_at=request_params["phone_call_at"],
                user_agent=user_agent,
            )
        except ValidationError as e:
            abort(400, e.messages)
        except AppointmentNotFoundException as e:
            abort(404, e.message)
        except MemberNotFoundException as e:
            abort(500, e.message)
        except json.decoder.JSONDecodeError:
            abort(500, "Invalid appointment JSON")

        return {
            "appointment_id": appointment_id,
        }
