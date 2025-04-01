from typing import List, Tuple

import ddtrace
from flask import make_response, request
from flask_restful import abort
from marshmallow import ValidationError

from clinical_documentation.error import DuplicateTitleError
from clinical_documentation.models.mpractice_template import (
    MPracticeTemplate,
    MPracticeTemplateLitePagination,
    PostMPracticeTemplate,
)
from clinical_documentation.schema.mpractice_template import (
    GetMPracticeTemplateResponseSchema,
    GetMPracticeTemplatesResponseSchema,
    PostMPracticeTemplateRequestSchema,
)
from clinical_documentation.services.mpractice_template import MPracticeTemplateService
from common.services.api import AuthenticatedResource
from utils.log import logger

log = logger(__name__)


class MPracticeTemplatesResource(AuthenticatedResource):
    @ddtrace.tracer.wrap()
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            template_service = MPracticeTemplateService()

            sorted_templates: Tuple[
                List[MPracticeTemplate],
                MPracticeTemplateLitePagination,
            ] = template_service.get_sorted_mpractice_templates(user=self.user)

            [templates, pagination] = sorted_templates

            response_schema = GetMPracticeTemplatesResponseSchema()

            data = {"data": templates, "pagination": pagination}
            return make_response(response_schema.dump(data), 200)
        except Exception as e:
            log.error(
                "Failed to get mpractice templates",
                exception=e,
            )
            abort(500)

    @ddtrace.tracer.wrap()
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        schema = PostMPracticeTemplateRequestSchema()
        try:
            request_json = request.json if request.is_json else None
            args = schema.load(request_json)
        except ValidationError:
            abort(400, message="Invalid request, failed validation")

        template_service = MPracticeTemplateService()

        template = PostMPracticeTemplate(
            sort_order=args.get("sort_order"),
            is_global=args.get("is_global"),
            title=args.get("title"),
            text=args.get("text"),
        )

        try:
            created_template = template_service.create_mpractice_template(
                user=self.user, template_args=template
            )

            if not created_template:
                return make_response(
                    "Failed to create mpractice template; error in input", 400
                )

            response_schema = GetMPracticeTemplateResponseSchema()
            data = {"data": created_template}
            return make_response(response_schema.dump(data), 201)
        except DuplicateTitleError as e:
            log.error(
                "Failed to create mpractice template",
                template=template,
                exception=e,
            )
            abort(409)
        except Exception as e:
            log.error(
                "Failed to create mpractice template",
                template=template,
                exception=e,
            )
            abort(500)
