from flask import make_response, request
from flask_restful import abort
from marshmallow import ValidationError

from appointments.services.schedule import validate_member_schedule
from common.services.api import AuthenticatedResource
from mpractice.schema.appointment import (
    GetProviderAppointmentsRequestSchemaV3,
    GetProviderAppointmentsResponseSchemaV3,
)
from mpractice.service.provider_appointment import ProviderAppointmentService
from utils.log import logger

PRACTITIONER_ID = "practitioner_id"
MEMBER_ID = "member_id"
SCHEDULED_START = "scheduled_start"
SCHEDULED_END = "scheduled_end"

log = logger(__name__)


# TODO: delete V1 resource after clients are migrated off
class ProviderAppointmentsResource(AuthenticatedResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            args = self._validate_args()
        except ValidationError:
            abort(400, message="Invalid request to get appointments")

        provider_appt_service = ProviderAppointmentService()
        (appointments, pagination) = provider_appt_service.get_provider_appointments(
            args
        )
        schema = GetProviderAppointmentsResponseSchemaV3()
        data = {"data": appointments, "pagination": pagination}
        return make_response(schema.dump(data), 200)

    def _validate_args(self) -> dict:
        schema = GetProviderAppointmentsRequestSchemaV3()
        args = schema.load(request.args)

        if args.get(PRACTITIONER_ID):
            if args.get(PRACTITIONER_ID) != self.user.id:
                log.error(
                    f"Requested practitioner ID {args.get(PRACTITIONER_ID)} "
                    f"does not match current user ID {self.user.id}"
                )
                abort(403)
        elif self.user.practitioner_profile:
            args[PRACTITIONER_ID] = self.user.id

        if (args.get(SCHEDULED_START) is not None) ^ (
            args.get(SCHEDULED_END) is not None
        ):
            abort(
                http_status_code=400,
                message="Both scheduled_start and scheduled_end required",
            )

        return args


# The V2 resource was created as a copy of V1. It contains the most up-to-date implementation going forward.
class ProviderAppointmentsResourceV2(AuthenticatedResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            args = self._validate_args()
        except ValidationError:
            abort(400, message="Invalid request to get appointments")

        provider_appt_service = ProviderAppointmentService()
        (appointments, pagination) = provider_appt_service.get_provider_appointments(
            args
        )
        schema = GetProviderAppointmentsResponseSchemaV3()
        data = {"data": appointments, "pagination": pagination}
        return make_response(schema.dump(data), 200)

    def _validate_args(self) -> dict:
        schema = GetProviderAppointmentsRequestSchemaV3()
        args = schema.load(request.args)

        if args.get(PRACTITIONER_ID):
            if args.get(PRACTITIONER_ID) != self.user.id:
                log.error(
                    f"Requested practitioner ID {args.get(PRACTITIONER_ID)} "
                    f"does not match current user ID {self.user.id}"
                )
                abort(403)
        elif self.user.practitioner_profile:
            args[PRACTITIONER_ID] = self.user.id

        if args.get(MEMBER_ID):
            validate_member_schedule(args[MEMBER_ID])

        if (args.get(SCHEDULED_START) is not None) ^ (
            args.get(SCHEDULED_END) is not None
        ):
            abort(
                http_status_code=400,
                message="Both scheduled_start and scheduled_end required",
            )

        return args
