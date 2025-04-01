from flask import current_app, request
from flask_restful import abort
from marshmallow import ValidationError
from marshmallow_v1.exceptions import UnmarshallingError

from authn.models.user import User
from authz.models.roles import ROLES
from common import stats
from common.services import ratelimiting
from common.services.api import InternalServiceResource, UnauthenticatedResource
from l10n.utils import message_with_enforced_locale
from messaging.schemas.sms import (
    SMS_TEMPLATES,
    InternalSMSSchema,
    SMSSchema,
    SMSSchemaV3,
)
from storage.connection import db
from utils.constants import (
    MAVEN_SMS_DELIVERY_ERROR,
    SMS_MISSING_PROFILE_NUMBER,
    TWILIO_SMS_DELIVERY_SUCCESS_COUNT_METRICS,
)
from utils.log import logger
from utils.marshmallow_experiment import marshmallow_experiment_enabled
from utils.sms import country_accepts_url_in_sms, parse_phone_number, send_sms

log = logger(__name__)


def _get_to_number():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # launch darkly flag
    experiment_enabled = marshmallow_experiment_enabled(
        "experiment-marshmallow-sms-resource",
        None,  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        default=False,
    )
    schema_in = SMSSchemaV3() if experiment_enabled else SMSSchema()
    try:
        if experiment_enabled:
            args = schema_in.load(request.json if request.is_json else None)  # type: ignore[attr-defined]
        else:
            args = schema_in.load(request.json if request.is_json else None).data  # type: ignore[attr-defined]
        return args["phone_number"]
    except UnmarshallingError:
        return "NO_NUMBER"
    except ValidationError as e:
        return abort(400, message=e.messages)


class SMSResource(UnauthenticatedResource):
    @ratelimiting.ratelimited(attempts=2, cooldown=60, scope=_get_to_number)
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # launch darkly flag
        experiment_enabled = marshmallow_experiment_enabled(
            "experiment-marshmallow-sms-resource",
            self.user.esp_id if self.user else None,
            self.user.email if self.user else None,
            default=False,
        )
        schema_in = SMSSchemaV3() if experiment_enabled else SMSSchema()
        try:
            if experiment_enabled:
                args = schema_in.load(request.json if request.is_json else None)  # type: ignore[attr-defined]
            else:
                args = schema_in.load(request.json if request.is_json else None).data  # type: ignore[attr-defined]
        except ValidationError as e:
            return abort(400, message=e.messages)

        to_number = args["phone_number"]
        parsed_phone_number = parse_phone_number(to_number)
        # if we were unable to parse the phone number we adhere to the default condition of including the url
        if not parsed_phone_number or country_accepts_url_in_sms(parsed_phone_number):
            contents = SMS_TEMPLATES[args["template"]]
        else:
            contents = SMS_TEMPLATES["no_url"]

        try:
            send_sms(contents, to_number, notification_type="onboarding")
        except Exception as e:
            log.exception(
                "Exception found when attempting to send onboarding SMS notification",
                exception=e,
            )

            stats.increment(
                metric_name=MAVEN_SMS_DELIVERY_ERROR,
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=[
                    "result:failure",
                    "notification_type:onboarding",
                    "reason:maven_server_exception",
                    "source:SMSResource",
                ],
            )


class InternalSMSResource(InternalServiceResource):
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        This endpoint triggers an SMS message to notify a member about a new message from an Ask Maven agent
        :return:
        """
        self._check_permissions()

        schema_in = InternalSMSSchema()
        args = schema_in.load(request.json if request.is_json else None)  # type: ignore[attr-defined]

        user_id = args["user_id"]
        user = User.query.get(user_id)
        if not user:
            abort(400, message="Invalid user_id")

        profile = user.member_profile
        to_number = profile.phone_number
        if not to_number:
            log.warning(
                "Unable to send SMS for new Maven message - profile number unavailable",
                user_id=user.id,
            )
            stats.increment(
                metric_name=SMS_MISSING_PROFILE_NUMBER,
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=[
                    "result:failure",
                    "notification_type:messaging",
                    f"user_role:{ROLES.member}",
                    "source:InternalSMSResource",
                ],
            )
            abort(400, message="User has no phone number")

        message = message_with_enforced_locale(
            user=user, text_key="generic_maven_message_body"
        )

        parsed_phone_number = parse_phone_number(to_number)
        # if we were unable to parse the phone number we adhere to the default condition of including the url
        if not parsed_phone_number or country_accepts_url_in_sms(parsed_phone_number):
            message_cta = message_with_enforced_locale(
                user=user, text_key="cta_message_link"
            ).format(link=current_app.config["BASE_URL"])
            message = f"{message} {message_cta}"

        try:
            result = send_sms(
                message=message,
                to_phone_number=to_number,
                user_id=user_id,
                notification_type="messaging",
            )
        except Exception as e:
            log.exception(
                "Exception found when attempting to send SMS",
                exception=e,
            )

            stats.increment(
                metric_name=MAVEN_SMS_DELIVERY_ERROR,
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=[
                    "result:failure",
                    "notification_type:internal_sms",
                    "reason:maven_server_exception",
                    "source:InternalSMSResource",
                ],
            )
            return "", 500

        if result.is_ok:
            log.info(
                "Successfully sent SMS for new Maven message to Member",
                user_id=user_id,
            )
            stats.increment(
                metric_name=TWILIO_SMS_DELIVERY_SUCCESS_COUNT_METRICS,
                pod_name=stats.PodNames.VIRTUAL_CARE,
                tags=["result:success", "notification_type:messaging"],
            )
            return "", 200
        else:
            if result.is_blocked:
                log.warning(
                    "Couldn't send SMS for new Maven message to Member - member profile has a phone number that is sms blocked",
                    user_id=profile.user_id,
                    error_message=result.error_message,
                )
                db.session.add(profile)
                profile.mark_as_sms_blocked(result.error_code)
                db.session.commit()
                return "", 204

            # if we failed to send for an unknown reason, return a 500
            log.exception(
                "Couldn't send SMS for new Maven message to Member", user_id=user_id
            )
            return "", 500
