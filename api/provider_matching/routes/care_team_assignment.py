from flask import jsonify
from flask_restful import abort

from authn.models.user import User
from common.services.api import AuthenticatedResource
from provider_matching.services.care_team_assignment import (
    replace_care_team_members_during_onboarding,
)
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class CareTeamReassignEndpointMessage(str):
    MISSING_USER_ID = "Did not provide user_id"
    INVALID_USER_ID = "Invalid User ID"


class CareTeamAssignmentReassignResource(AuthenticatedResource):
    def post(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not user_id:
            log.warn(CareTeamReassignEndpointMessage.MISSING_USER_ID)
            abort(400, message=CareTeamReassignEndpointMessage.MISSING_USER_ID)

        user = User.query.get(user_id)
        if not user:
            log.warn(CareTeamReassignEndpointMessage.INVALID_USER_ID)
            abort(400, message=CareTeamReassignEndpointMessage.INVALID_USER_ID)

        replace_care_team_members_during_onboarding(user=user)
        db.session.commit()
        return jsonify({"success": True})


def add_routes(api):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    api.add_resource(
        CareTeamAssignmentReassignResource,
        "/v1/care-team-assignment/reassign/<int:user_id>",
    )
    return api
