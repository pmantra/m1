from __future__ import annotations

from flask import make_response, request
from flask_restful import abort

from appointments.services.common import deobfuscate_appointment_id
from common.services.api import AuthenticatedResource
from mpractice.models.translated_appointment import TranslatedProviderAppointment
from mpractice.schema.appointment import (
    GetProviderAppointmentRequestSchemaV3,
    ProviderAppointmentSchemaV3,
)
from mpractice.service.provider_appointment import ProviderAppointmentService
from utils.log import logger

log = logger(__name__)


# TODO: delete V1 resource after clients are migrated off
class ProviderAppointmentResource(AuthenticatedResource):
    def get(self, appointment_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        appointment: TranslatedProviderAppointment | None = None
        try:
            provider_appointment_service = ProviderAppointmentService()
            appointment = provider_appointment_service.get_provider_appointment_by_id(
                appointment_id=deobfuscate_appointment_id(appointment_id),
                user=self.user,
            )
        except Exception as e:
            log.error(
                "Failed to get provider appointment",
                appointment_id=appointment_id,
                exception=e,
            )
            abort(500)

        if not appointment:
            log.warning("Appointment not found", appointment_id=appointment_id)
            abort(404)

        if appointment.product and appointment.product.practitioner:  # type: ignore[union-attr] # Item "None" of "Optional[TranslatedProviderAppointment]" has no attribute "product"
            practitioner_id = appointment.product.practitioner.id  # type: ignore[union-attr] # Item "None" of "Optional[TranslatedProviderAppointment]" has no attribute "product"
            if practitioner_id != self.user.id:
                log.warning(
                    "User cannot access appointment",
                    user_id=self.user.id,
                    appointment_id=appointment_id,
                )
                abort(403)

        schema = ProviderAppointmentSchemaV3()
        return make_response(schema.dump(appointment), 200)


# The V2 resource was created as a copy of V1. It contains the most up-to-date implementation going forward.
class ProviderAppointmentResourceV2(AuthenticatedResource):
    def get(self, appointment_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        request_schema = GetProviderAppointmentRequestSchemaV3()
        args = request_schema.load(request.args)
        include_soft_deleted_question_sets = args.get(
            "include_soft_deleted_question_sets", False
        )

        appointment: TranslatedProviderAppointment | None = None
        try:
            provider_appointment_service = ProviderAppointmentService(
                include_soft_deleted_question_sets=include_soft_deleted_question_sets
            )
            appointment = provider_appointment_service.get_provider_appointment_by_id(
                appointment_id=deobfuscate_appointment_id(appointment_id),
                user=self.user,
            )
        except Exception as e:
            log.error(
                f"Failed to get provider appointment due to: {e}",
                appointment_id=appointment_id,
            )
            abort(500)

        if not appointment:
            log.warning("Appointment not found", appointment_id=appointment_id)
            abort(404, message="Invalid appointment ID")

        if appointment.product and appointment.product.practitioner:  # type: ignore[union-attr] # Item "None" of "Optional[TranslatedProviderAppointment]" has no attribute "product"
            practitioner_id = appointment.product.practitioner.id  # type: ignore[union-attr] # Item "None" of "Optional[TranslatedProviderAppointment]" has no attribute "product"
            if practitioner_id != self.user.id:
                log.warning(
                    "User cannot access appointment",
                    user_id=self.user.id,
                    appointment_id=appointment_id,
                )
                abort(403, message="Cannot view that appointment!")

        schema = ProviderAppointmentSchemaV3()
        return make_response(schema.dump(appointment), 200)
