from flask import request
from flask_restful import abort
from marshmallow import ValidationError

from appointments.services.common import deobfuscate_appointment_id
from appointments.utils.appointment_utils import check_appointment_by_ids
from appointments.utils.flask_redis_ext import APPOINTMENT_REDIS, invalidate_cache
from clinical_documentation.error import InvalidRecordedAnswersError
from clinical_documentation.models.questionnaire_answers import RecordedAnswer
from clinical_documentation.schema.questionnaire_answers import AnswersSchemaV3
from clinical_documentation.services.questionnaire_answers_service import (
    QuestionnaireAnswerService,
)
from common.services.api import AuthenticatedResource
from utils.log import logger
from utils.marshmallow_experiment import marshmallow_experiment_enabled

log = logger(__name__)


class QuestionnaireAnswersResource(AuthenticatedResource):
    def redis_cache_key(self, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(request.json, list) and len(request.json) > 0:
            return f"appointment_details:{self.user.id}:{request.json[0].get('appointment_id')}"
        else:
            # empty request
            return None

    def redis_tags(self, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(request.json, list) and len(request.json) > 0:
            return [
                f"appointment_data:{request.json[0].get('appointment_id')}",
                f"user_appointments:{self.user.id}",
            ]
        else:
            return None

    def experiment_enabled(self, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return marshmallow_experiment_enabled(
            "experiment-enable-appointments-redis-cache",
            self.user.esp_id,
            self.user.email,
            default=False,
        )

    @invalidate_cache(redis_name=APPOINTMENT_REDIS, namespace="appointment_detail")
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        schema = AnswersSchemaV3()
        try:
            request_json = request.json if request.is_json else None
            args = schema.load(request_json, many=True)
        except ValidationError:
            abort(400, message="Invalid request, failed validation")

        check_appointment_by_ids(
            [deobfuscate_appointment_id(answer["appointment_id"]) for answer in args],
            True,
        )

        answers = [
            RecordedAnswer(
                question_id=answer["question_id"],
                answer_id=answer.get("answer_id"),
                text=answer.get("text"),
                # All external appointment ids are obfuscated. We want to deobfuscate it up here
                # in the client layer so that no other service code in our API needs to worry about this.
                appointment_id=deobfuscate_appointment_id(answer["appointment_id"]),
                user_id=answer["user_id"],
            )
            for answer in args
        ]
        service = QuestionnaireAnswerService()
        try:
            service.submit_answers(answers)
        except InvalidRecordedAnswersError as e:
            log.error("Invalid request, failed db checks", answers=answers, exception=e)
            abort(400, message="Invalid request, failed db checks")
