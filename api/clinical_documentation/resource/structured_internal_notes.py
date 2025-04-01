import ddtrace
from flask import make_response, request
from flask_restful import abort
from marshmallow import ValidationError

from appointments.services.common import deobfuscate_appointment_id
from clinical_documentation.models.translated_note import StructuredInternalNote
from clinical_documentation.schema.note import (
    GetStructuredInternalNoteRequestSchemaV3,
    StructuredInternalNoteSchemaV3,
)
from clinical_documentation.services.note import ClinicalDocumentationNoteService
from common.services.api import AuthenticatedResource
from utils.log import logger

APPOINTMENT_ID = "appointment_id"
PRACTITIONER_ID = "practitioner_id"
INCLUDE_SOFT_DELETED_QUESTION_SETS = "include_soft_deleted_question_sets"

log = logger(__name__)


class StructuredInternalNoteResource(AuthenticatedResource):
    @ddtrace.tracer.wrap()
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            args = self._validate_args()
        except ValidationError:
            abort(
                400, message="Invalid request argument to get structured internal note."
            )
        try:
            include_soft_deleted_question_sets = args.get(
                INCLUDE_SOFT_DELETED_QUESTION_SETS, False
            )
            note_service = ClinicalDocumentationNoteService(
                include_soft_deleted_question_sets=include_soft_deleted_question_sets
            )

            appointment_id = args.get(APPOINTMENT_ID)
            practitioner_id = args.get(PRACTITIONER_ID)
            structured_internal_note: StructuredInternalNote = (
                note_service.get_structured_internal_notes(
                    appointment_id=deobfuscate_appointment_id(int(appointment_id)),
                    practitioner_id=practitioner_id,
                )
            )

            response_schema = StructuredInternalNoteSchemaV3()
            return make_response(response_schema.dump(structured_internal_note), 200)
        except Exception as e:
            log.error(
                "Failed to get structured internal note.",
                appointment_id=args.get(APPOINTMENT_ID),
                practitioner_id=args.get(PRACTITIONER_ID),
                exception=e,
            )
            abort(500)

    @ddtrace.tracer.wrap()
    def _validate_args(self) -> dict:
        schema = GetStructuredInternalNoteRequestSchemaV3()
        args = schema.load(request.args)
        return args
