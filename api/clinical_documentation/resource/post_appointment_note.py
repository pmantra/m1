import ddtrace
from flask import make_response, request
from flask_restful import abort
from marshmallow import ValidationError

from appointments.services.common import deobfuscate_appointment_id
from clinical_documentation.models.role import Role
from clinical_documentation.models.translated_note import TranslatedPostAppointmentNotes
from clinical_documentation.schema.note import GetPostAppointmentNotesResponseSchemaV3
from clinical_documentation.services.note import ClinicalDocumentationNoteService
from common.services.api import AuthenticatedResource
from utils.log import logger

APPOINTMENT_IDS = "appointment_ids"
ROLE = "role"

log = logger(__name__)


class PostAppointmentNoteResource(AuthenticatedResource):
    @ddtrace.tracer.wrap()
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            args = self._validate_args()
        except ValidationError:
            abort(
                400, message="Invalid request argument to get a post appointment note."
            )
        try:
            note_service = ClinicalDocumentationNoteService()
            appointment_ids = args.get(APPOINTMENT_IDS)
            appointment_ids = [
                deobfuscate_appointment_id(int(appointment_id))
                for appointment_id in appointment_ids  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "__iter__" (not iterable)
            ]
            role = args.get(ROLE)
            log.info(f"appointment_ids: {str(appointment_ids)}")
            translate_post_appointment_notes: TranslatedPostAppointmentNotes = (
                note_service.get_post_appointment_notes(
                    appointment_ids=appointment_ids, role=role
                )
            )

            response_schema = GetPostAppointmentNotesResponseSchemaV3()
            return make_response(
                response_schema.dump(translate_post_appointment_notes), 200
            )
        except Exception as e:
            log.error(
                "Failed to get post appointment notes",
                appointment_ids=args.get(APPOINTMENT_IDS),
                exception=e,
            )
            abort(500)

    def _validate_args(self) -> dict:
        args = {
            ROLE: request.args.get(ROLE, "No role provided"),
            APPOINTMENT_IDS: request.args.getlist(APPOINTMENT_IDS, type=int),
        }

        if not args[APPOINTMENT_IDS]:
            err_msg = "Missing or empty 'appointment_ids' request argument."
            log.info(err_msg)
            abort(400, description=err_msg)

        if not args.get(ROLE) or not self._is_valid_role_name(args.get(ROLE)):  # type: ignore[arg-type] # Argument 1 to "_is_valid_role_name" of "PostAppointmentNoteResource" has incompatible type "Optional[Any]"; expected "str"
            err_msg = f"Invalid or missing role value: {args[ROLE]}"
            log.info(err_msg)
            abort(400, message=err_msg)

        return args

    def _is_valid_role_name(self, role: str) -> bool:
        role = role.upper()
        return hasattr(Role, role)
