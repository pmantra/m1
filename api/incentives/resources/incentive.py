from flask import request
from flask_restful import abort
from marshmallow import ValidationError

from common.services.api import PermissionedUserResource
from incentives.schemas.incentive import (
    UserIncentiveArgsSchema,
    UserIncentiveResponseSchema,
)
from incentives.services.incentive_organization import (
    IncentiveOrganizationService,
    report_incentives_for_user,
)
from storage.connection import db
from utils.log import logger
from utils.service_owner_mapper import service_ns_team_mapper

log = logger(__name__)


class UserIncentiveResource(PermissionedUserResource):
    @db.from_app_replica
    def get(self, user_id) -> UserIncentiveResponseSchema:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        # Validate user_id
        self._user_or_404(user_id)

        # Validate args
        request_schema = UserIncentiveArgsSchema()
        try:
            args = request_schema.load(request.args)
        except ValidationError as e:
            log.warn("Exception validating UserIncentive args", exception=e.messages)
            abort(400, message=e.messages)

        log.info(
            "Starting get request for UserIncentiveResource",
            user_id=user_id,
            incentivized_action=args["incentivized_action"],
            track=args["track"],
        )

        user_incentive = IncentiveOrganizationService().get_user_incentive(
            user_id=user_id,
            incentivized_action=args["incentivized_action"],
            track=args["track"],
        )
        # trigger job to send incentives to braze
        service_ns = "incentive"
        report_incentives_for_user.delay(
            user_id=user_id,
            track=args["track"],
            service_ns=service_ns,
            team_ns=service_ns_team_mapper.get(service_ns),
        )

        if user_incentive:
            log.info(
                "Successfully got user incentive",
                user_id=user_id,
                incentivized_action=args["incentivized_action"],
                track=args["track"],
                user_incentive_id=user_incentive.id,
            )
            response_schema = UserIncentiveResponseSchema()
            return response_schema.dump(
                {
                    "incentive_id": user_incentive.id,
                    "incentive_type": user_incentive.type._name_.lower(),
                    "design_asset": user_incentive.design_asset._name_.lower(),
                    "amount": user_incentive.amount,
                }
            )
        return {}  # type: ignore[return-value] # Incompatible return value type (got "Dict[Never, Never]", expected "UserIncentiveResponseSchema")
