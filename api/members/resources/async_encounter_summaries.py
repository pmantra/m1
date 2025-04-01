import ddtrace
from flask import request
from flask_restful import abort
from marshmallow import ValidationError

from authn.domain.repository import UserRepository
from authn.models.user import User
from common.services.api import PermissionedCareTeamResource
from members.repository.async_encounter_summary import AsyncEncounterSummaryRepository
from members.schemas.async_encounter_summaries import (
    AsyncEncounterSummariesGetArgsSchema,
    AsyncEncounterSummariesGetSchema,
    AsyncEncounterSummaryPostSchema,
    AsyncEncounterSummarySchema,
)
from members.services.async_encounter_summaries import AsyncEncounterSummariesService
from utils.log import logger

log = logger(__name__)


class AsyncEncounterSummariesResource(PermissionedCareTeamResource):
    @ddtrace.tracer.wrap()
    def get(self, member_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        patient = User.query.get(member_id)
        current_user_id = self.user.id
        if not patient:
            abort(403, message=f"Patient {current_user_id} does not exist")
        self._user_has_access_to_user_or_403(self.user, patient)

        in_schema = AsyncEncounterSummariesGetArgsSchema()
        request_args = request.args.to_dict()
        verticals = request.args.getlist("provider_types")
        request_args["provider_types"] = verticals
        args = in_schema.load(request_args)

        args["user_id"] = member_id
        args["provider_id"] = self.user.id
        if verticals:
            args["verticals"] = verticals
        if (not args.get("my_encounters")) and (
            not patient.member_profile.opted_in_notes_sharing
            and current_user_id != patient.id
        ):
            args["my_encounters"] = True

        async_encounter_summaries_service = AsyncEncounterSummariesService()
        async_encounter_summaries = async_encounter_summaries_service.get(args=args)

        schema = AsyncEncounterSummariesGetSchema()
        schema.context[
            "questionnaire"
        ] = async_encounter_summaries_service.build_async_encounter_questionnaire_data(
            async_encounter_summaries
        )
        (
            provider_name,
            provider_verticals,
        ) = async_encounter_summaries_service.build_async_encounter_provider_data(
            async_encounter_summaries
        )
        schema.context["provider_name"] = provider_name
        schema.context["provider_verticals"] = provider_verticals

        results = {
            "data": async_encounter_summaries,
            "pagination": {
                "total": len(async_encounter_summaries),
                "limit": args["limit"],
                "offset": args["offset"],
                "order_direction": "desc",
            },
        }
        return schema.dump(results)

    @ddtrace.tracer.wrap()
    def post(self, member_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        user_repo = UserRepository()
        if not user_repo.get_all_by_ids([member_id]):
            abort(404, message="Member not found.")

        current_user_id = self.user.id
        self._user_id_has_access_to_member_id_or_403(current_user_id, member_id)

        schema = AsyncEncounterSummarySchema()
        try:
            args = schema.load(request.json if request.is_json else {})
        except ValidationError:
            abort(
                400,
                message="Invalid request body. Answers must include answer_id, text or date.",
            )

        async_encounter_summary_repo = AsyncEncounterSummaryRepository()
        async_encounter_summary_data = args["async_encounter_summary"]
        async_encounter_summary = async_encounter_summary_repo.create(
            provider_id=current_user_id,
            user_id=member_id,
            questionnaire_id=async_encounter_summary_data["questionnaire_id"],
            encounter_date=async_encounter_summary_data["encounter_date"],
            async_encounter_summary_answers=async_encounter_summary_data[
                "async_encounter_summary_answers"
            ],
        )

        schema = AsyncEncounterSummaryPostSchema()  # type: ignore[assignment] # Incompatible types in assignment (expression has type "AsyncEncounterSummaryPostSchema", variable has type "AsyncEncounterSummarySchema")
        if not async_encounter_summary:
            abort(500)

        return schema.dump({"async_encounter_summary": async_encounter_summary})
