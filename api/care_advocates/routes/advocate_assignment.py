import datetime

from flask import jsonify, request
from flask_restful import abort

from authn.models.user import User
from common import stats
from common.services.api import AuthenticatedResource
from models.base import db
from models.profiles import CareTeamTypes, MemberPractitionerAssociation
from provider_matching.services.care_team_assignment import ensure_care_advocate
from utils.lock import prevent_concurrent_requests
from utils.log import logger

log = logger(__name__)


class AdvocateAssignmentResource(AuthenticatedResource):
    # adding lock decorator to prevent DB duplicate key error triggered at commit
    @prevent_concurrent_requests(lambda self, user_id: f"advocate_assignment:{user_id}")
    def post(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        log.info("Starting Advocate Assignment Reassign", user_id=user_id)
        user: User = User.query.get(user_id)
        if not user:
            abort(400, message="Invalid User ID")
        multitrack_onboarding = False
        if request.data:
            request_json = request.json if request.is_json else None
            need_updated_risk_factors = request_json.get(
                "need_updated_risk_factors", False
            )
            # a user will have back to back assessments if they are enrolling in multiple tracks
            # during onboarding
            multitrack_onboarding = request_json.get("back_to_back_assessments", False)
            if need_updated_risk_factors:
                log.info(
                    "Updated risk factors needed from HDC endpoint",
                    need_updated_risk_factors=need_updated_risk_factors,
                    user_id=user_id,
                )
                if _is_a_2nd_aa_call(user_id):
                    log.info(
                        "CA MemberPractitionerAssociation created within last 6 seconds. Skipping Advocate Assignment Reassign.",
                        user_id=user_id,
                    )
                    stats.increment(
                        metric_name="care_advocates.routes.advocate_assignment.reassign.disregard_2nd_aa_call",
                        pod_name=stats.PodNames.CARE_DISCOVERY,
                    )
                    return jsonify(
                        {
                            "success": True,
                            "message": "CA MemberPractitionerAssociation created within last 6 seconds. Skipping Advocate Assignment Reassign.",
                        }
                    )
        replaced = ensure_care_advocate(
            user=user,
            multitrack_onboarding=multitrack_onboarding,
        )

        if replaced:
            db.session.commit()
            return jsonify({"success": True})
        else:
            log.info("User already has a CA and is on a second track.", user_id=user_id)
            return jsonify(
                {
                    "success": True,
                    "message": "User already has a CA and is on a second track.",
                }
            )


def _is_a_2nd_aa_call(user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    duplicate_hit_time = datetime.datetime.now() - datetime.timedelta(seconds=6)
    ca_mpas_just_created = MemberPractitionerAssociation.query.filter(
        MemberPractitionerAssociation.user_id == user_id,
        MemberPractitionerAssociation.type == CareTeamTypes.CARE_COORDINATOR,
        MemberPractitionerAssociation.created_at >= duplicate_hit_time,
    ).all()
    return ca_mpas_just_created
