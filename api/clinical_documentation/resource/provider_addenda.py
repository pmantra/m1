import ddtrace
from flask import make_response, request
from flask_restful import abort
from marshmallow import ValidationError

from appointments.services.common import deobfuscate_appointment_id
from clinical_documentation.models.translated_note import (
    MPracticeProviderAddendaAndQuestionnaire,
)
from clinical_documentation.schema.note import ProviderAddendaAndQuestionnaireSchemaV3
from clinical_documentation.services.note import ClinicalDocumentationNoteService
from common.services.api import AuthenticatedResource
from utils.log import logger

APPOINTMENT_ID = "appointment_id"
PRACTITIONER_ID = "practitioner_id"
INCLUDE_SOFT_DELETED_QUESTION_SETS = "include_soft_deleted_question_sets"

log = logger(__name__)


class ProviderAddendaResource(AuthenticatedResource):
    @ddtrace.tracer.wrap()
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            args = self._validate_args()
        except ValidationError:
            abort(400, message="Invalid request argument to get provider addenda.")
        try:
            include_soft_deleted_question_sets = args.get(
                INCLUDE_SOFT_DELETED_QUESTION_SETS, False
            )
            note_service = ClinicalDocumentationNoteService(
                include_soft_deleted_question_sets=include_soft_deleted_question_sets
            )
            appointment_id = args.get(APPOINTMENT_ID)
            practitioner_id = args.get(PRACTITIONER_ID)
            provider_addenda_and_questionnaire: MPracticeProviderAddendaAndQuestionnaire = note_service.get_provider_addenda_and_questionnaire(
                appointment_id=deobfuscate_appointment_id(int(appointment_id)),  # type: ignore[arg-type] # Argument 1 to "int" has incompatible type "Optional[Any]"; expected "Union[str, Buffer, SupportsInt, SupportsIndex, SupportsTrunc]"
                practitioner_id=practitioner_id,
            )

            response_schema = ProviderAddendaAndQuestionnaireSchemaV3()
            return make_response(
                response_schema.dump(provider_addenda_and_questionnaire), 200
            )
        except Exception as e:
            log.error(
                "Failed to get provider addenda.",
                appointment_id=args.get(APPOINTMENT_ID),
                practitioner_id=args.get(PRACTITIONER_ID),
                exception=e,
            )
            abort(500)

    def _validate_args(self) -> dict:
        args = {
            PRACTITIONER_ID: request.args.get(PRACTITIONER_ID, None),
            APPOINTMENT_ID: request.args.get(APPOINTMENT_ID, None),
        }

        errors = []
        if not args[APPOINTMENT_ID]:
            errors.append("Missing or empty 'appointment_id'")
        if not args[PRACTITIONER_ID]:
            errors.append("Missing or empty 'practitioner_id'")

        if errors:
            err_msg = " and ".join(errors) + " request argument(s)."
            log.info(err_msg)
            abort(400, description=err_msg)

        return args
