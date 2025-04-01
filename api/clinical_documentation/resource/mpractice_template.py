import ddtrace
from flask import make_response, request
from flask_restful import abort
from marshmallow import ValidationError

from clinical_documentation.error import DuplicateTitleError
from clinical_documentation.schema.mpractice_template import (
    GetMPracticeTemplateResponseSchema,
    PatchMPracticeTemplateRequestSchema,
)
from clinical_documentation.services.mpractice_template import MPracticeTemplateService
from common.services.api import AuthenticatedResource
from utils.log import logger

log = logger(__name__)


class MPracticeTemplateResource(AuthenticatedResource):
    @ddtrace.tracer.wrap()
    def patch(self, template_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        schema = PatchMPracticeTemplateRequestSchema()
        try:
            request_json = request.json if request.is_json else None
            args = schema.load(request_json)
        except ValidationError:
            abort(400, message="Invalid request, failed validation")
        try:
            # sort_order = args.get("sort_order")
            # is_global = args.get("is_global")
            title = args.get("title") or None
            text = args.get("text") or None

            template_service = MPracticeTemplateService()

            edited_template = None

            if title is not None or text is not None:
                edited_template = template_service.edit_mpractice_template_by_id(
                    user=self.user,
                    template_id=template_id,
                    title=title,
                    text=text,
                )
            else:
                return make_response(
                    "No accepted arguments provided when editing an mpractice template",
                    400,
                )

            if edited_template is None:
                return make_response("Could not find or edit mpractice template", 404)

            response_schema = GetMPracticeTemplateResponseSchema()

            data = {"data": edited_template}
            return make_response(response_schema.dump(data), 200)
        except DuplicateTitleError as e:
            log.error(
                "Failed to edit mpractice template",
                exception=e,
            )
            abort(409)
        except Exception as e:
            log.error(
                "Failed to edit mpractice template",
                exception=e,
            )
            abort(500)

    @ddtrace.tracer.wrap()
    def delete(self, template_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        template_service = MPracticeTemplateService()

        try:
            delete_success = template_service.delete_mpractice_template_by_id(
                user=self.user, template_id=template_id
            )
            if delete_success:
                return make_response("Successfully deleted", 204)

            return make_response("Not found", 404)
        except Exception as e:
            log.error(
                "Failed to delete mpractice template",
                exception=e,
            )
            abort(500)
