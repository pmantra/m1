from typing import Any, Dict, Union

from flask import jsonify, make_response, request
from flask_restful import abort

from common import stats
from common.services.api import AuthenticatedResource, UnauthenticatedResource
from messaging.schemas.zendesk import get_zendesk_webhook
from messaging.services import zendesk_messaging
from messaging.services.zendesk_client import ZENDESK_VENDOR_NAME
from messaging.services.zendesk_messaging import (
    InvalidUserIdException,
    InvalidZendeskUserIdException,
    MissingZendeskEnvException,
)
from models.failed_external_api_call import Status
from tasks.zendesk_v2 import process_zendesk_webhook
from utils.constants import ZENDESK_WEBHOOK_RECEIVED
from utils.failed_external_api_call_recorder import FailedVendorAPICallRecorder
from utils.log import LogLevel, generate_user_trace_log, logger
from utils.rotatable_token import ZENDESK_WEBHOOK_TOKEN
from utils.service_owner_mapper import service_ns_team_mapper

log = logger(__name__)


class AuthenticationViaZenDeskResource(AuthenticatedResource):
    def get(self) -> Union[Dict[str, Any], Any]:
        """
        Generate Zendesk JWT tokens to SSO members direclty into help center.
        Reference: https://support.zendesk.com/hc/en-us/articles/4408845838874-Enabling-JWT-single-sign-on#topic_xml_kdj_zj
        """
        user_id = self.user.id
        jwt_token = None
        try:
            jwt_token = zendesk_messaging.generate_jwt(user_id)
        except MissingZendeskEnvException as e:
            abort(400, message=str(e))
        except InvalidUserIdException:
            abort(400, message="invalid user_id")
        except InvalidZendeskUserIdException:
            abort(400, message="missing zendesk user")

        response_data = {"jwt": jwt_token}
        return make_response(jsonify(response_data), 200)


class MessageViaZenDeskResource(UnauthenticatedResource):
    def __init__(self) -> None:
        self.failed_vendor_api_call_recorder = FailedVendorAPICallRecorder()
        super().__init__()

    def _record_failed_call(self, user_id, payload):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        called_by = self.__class__.__name__
        api_name = "zendesk.webhook"
        external_id = FailedVendorAPICallRecorder.generate_external_id(
            user_id, called_by, ZENDESK_VENDOR_NAME, api_name
        )

        self.failed_vendor_api_call_recorder.create_record(
            external_id=external_id,
            payload=payload,
            called_by=called_by,
            vendor_name=ZENDESK_VENDOR_NAME,
            api_name=api_name,
            status=Status.pending,
        )

    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        This endpoint pushes the data onto a queue for async processing and
        immediately returns to avoid DB flakiness.
        New functionality should be added in the `process_zendesk_webhook` task
        """
        data = request.get_json(force=True)

        zendesk_user_id = data.get("zendesk_user_id", "")
        comment_id = data.get("comment_id", "")
        generate_user_trace_log(
            log,
            LogLevel.INFO,
            zendesk_user_id,
            f"Processing Zendesk webhook with keys: {', '.join(data.keys())}.",
            comment_id=comment_id,
        )

        try:
            args = get_zendesk_webhook(data)
        except Exception as e:
            exception_type = e.__class__.__name__
            exception_message = str(e)
            stats.increment(
                metric_name=ZENDESK_WEBHOOK_RECEIVED,
                tags=["result:failure", "reason:schema_load_failure"],
                pod_name=stats.PodNames.VIRTUAL_CARE,
            )
            generate_user_trace_log(
                log,
                LogLevel.ERROR,
                zendesk_user_id,
                f"Could not load Zendesk webhook payload: {', '.join(data.keys())}.",
                exception_type=exception_type,
                exception_message=exception_message,
                comment_id=comment_id,
            )
            self._record_failed_call(
                zendesk_user_id,
                {
                    "exception_type": exception_type,
                    "exception_message": exception_message,
                    "zendesk_user_id": zendesk_user_id,
                    "comment_id": comment_id,
                },
            )
            return {}, 202

        if self.token_not_valid(args.get("token")):
            stats.increment(
                metric_name=ZENDESK_WEBHOOK_RECEIVED,
                tags=["result:failure", "reason:invalid_token"],
                pod_name=stats.PodNames.VIRTUAL_CARE,
            )
            self._record_failed_call(
                zendesk_user_id,
                {
                    "error": "token not valid",
                    "zendesk_user_id": zendesk_user_id,
                    "comment_id": comment_id,
                },
            )
            return {}, 202

        service_ns_tag = "messaging_system"
        process_zendesk_webhook.delay(
            args,
            service_ns=service_ns_tag,
            team_ns=service_ns_team_mapper.get(service_ns_tag),
        )
        stats.increment(
            metric_name=ZENDESK_WEBHOOK_RECEIVED,
            tags=["result:success"],
            pod_name=stats.PodNames.VIRTUAL_CARE,
        )
        return {}, 201

    @classmethod
    def token_not_valid(cls, token) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        if ZENDESK_WEBHOOK_TOKEN.check_token(token):
            return False
        log.warn("Zendesk webhook token failed authentication.")
        return True
