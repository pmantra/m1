from dataclasses import asdict

from flask import abort, request
from marshmallow import ValidationError
from maven import feature_flags

from appointments.schemas.v2.member_appointments import (
    MemberAppointmentsListGetRequestSchema,
    MemberAppointmentsListGetResponse,
)
from appointments.services.common import obfuscate_appointment_id
from appointments.services.v2.member_appointment import MemberAppointmentService
from common.services.api import AuthenticatedResource
from utils import launchdarkly


class MemberAppointmentsListResource(AuthenticatedResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Gets all of a member's appointments in a specified time range

        order_direction: string
        limit: int
        offset: int
        scheduled_start: timestamp
        scheduled_end: timestamp
        """
        l10n_flag = feature_flags.bool_variation(
            "release-disco-be-localization",
            launchdarkly.user_context(self.user),
            default=False,
        )

        args_schema = MemberAppointmentsListGetRequestSchema()
        request_params = args_schema.load(request.args)

        try:
            (
                appointments,
                pagination,
            ) = MemberAppointmentService().list_member_appointments(
                self.user,
                self.user.id,
                scheduled_start=request_params.get("scheduled_start"),
                scheduled_end=request_params.get("scheduled_end"),
                limit=request_params.get("limit"),
                offset=request_params.get("offset"),
                order_direction=request_params.get("order_direction"),
            )
        except ValidationError as e:
            abort(400, e.messages)

        if l10n_flag:
            appointments = [a.translate() for a in appointments]

        response_schema = MemberAppointmentsListGetResponse()
        response = response_schema.dump(
            {"data": [asdict(a) for a in appointments], "pagination": pagination}
        )
        # Obfuscate ids on before sending back
        for a in response["data"]:
            a["id"] = obfuscate_appointment_id(a["id"])
        return response
