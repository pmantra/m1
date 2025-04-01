import warnings

from flask import request

from braze.client.utils import rq_delay_with_feature_flag
from common.services.api import PermissionedUserResource
from preferences.utils import set_member_communications_preference
from tasks.braze import (
    opt_into_member_communications,
    unsubscribe_from_member_communications,
)
from utils.log import logger
from utils.service_owner_mapper import service_ns_team_mapper

log = logger(__name__)


class OptInMemberCommunicationsResource(PermissionedUserResource):
    def post(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        warnings.warn(  # noqa  B028  TODO:  No explicit stacklevel keyword argument found. The warn method from the warnings module uses a stacklevel of 1 by default. This will only show a stack trace for the line on which the warn method is called. It is therefore recommended to use a stacklevel of 2 or greater to provide more information to the user.
            "OptInMemberCommunicationsResource will be deprecated in a future release. Use MemberCommunicationsResource instead",
            DeprecationWarning,
        )
        self._user_or_404(user_id)

        service_ns_tag = "account_settings"
        team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
        rq_delay_with_feature_flag(
            func=opt_into_member_communications,
            user_id=user_id,
            service_ns=service_ns_tag,
            team_ns=team_ns_tag,
        )
        set_member_communications_preference(user_id, True)
        return {}, 200


class UnsubscribeMemberCommunicationsResource(PermissionedUserResource):
    def post(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        warnings.warn(  # noqa  B028  TODO:  No explicit stacklevel keyword argument found. The warn method from the warnings module uses a stacklevel of 1 by default. This will only show a stack trace for the line on which the warn method is called. It is therefore recommended to use a stacklevel of 2 or greater to provide more information to the user.
            "UnsubscribeMemberCommunicationsResource will be deprecated in a future release. Use MemberCommunicationsResource instead",
            DeprecationWarning,
        )
        self._user_or_404(user_id)

        service_ns_tag = "account_settings"
        team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
        rq_delay_with_feature_flag(
            func=unsubscribe_from_member_communications,
            user_id=user_id,
            service_ns=service_ns_tag,
            team_ns=team_ns_tag,
        )
        set_member_communications_preference(user_id, False)
        return {}, 200


class MemberCommunicationsResource(PermissionedUserResource):
    def post(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._user_or_404(user_id)

        args = member_comm_post_request(request.json if request.is_json else {})
        if not args:
            return {
                "error": "Missing data for required field.",
                "status_code": 400,
                "errors": [
                    {
                        "status": 400,
                        "title": "Bad Request",
                        "detail": "Missing data for required field.",
                    }
                ],
            }, 400
        opted_in = args.get("opted_in")
        service_ns_tag = "account_settings"
        team_ns_tag = service_ns_team_mapper.get(service_ns_tag)

        if opted_in:
            rq_delay_with_feature_flag(
                func=opt_into_member_communications,
                user_id=user_id,
                service_ns=service_ns_tag,
                team_ns=team_ns_tag,
            )
        else:
            rq_delay_with_feature_flag(
                func=unsubscribe_from_member_communications,
                user_id=user_id,
                service_ns=service_ns_tag,
                team_ns=team_ns_tag,
            )

        set_member_communications_preference(user_id, opted_in)
        return {}, 200


def member_comm_post_request(request_json: dict) -> dict:
    if not request_json:
        return {}
    return {"opted_in": request_json["opted_in"]}
