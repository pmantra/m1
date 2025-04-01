from flask import abort, request

from authn.models.user import User
from common import stats
from common.services.api import UnauthenticatedResource
from messaging.logic.messaging import can_send_automated_message
from models.actions import audit
from storage.connection import db
from tasks.messaging import create_cx_message, send_to_zendesk
from tasks.notifications import notify_new_message
from utils.log import logger
from utils.rotatable_token import BRAZE_BULK_MESSAGING_TOKEN
from utils.service_owner_mapper import service_ns_team_mapper

log = logger(__name__)


CA_AUTOMATED_MESSAGE = "ca_automated_message"


def _validate_token(value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if not BRAZE_BULK_MESSAGING_TOKEN.check_token(value):
        abort(403)


class BrazeBulkMessageResource(UnauthenticatedResource):
    def get(self) -> dict:
        return {}

    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        params = request.get_json(force=True)
        message_text = params["message"]
        esp_id = params["user_id"]
        token = params["token"]
        braze_campaign_id = params.get("campaign_id")
        braze_dispatch_id = params.get("dispatch_id")
        message_type = params.get("message_type")

        _validate_token(token)

        log.info(
            "Braze bulk message received",
            esp_id=esp_id,
            braze_campaign_id=braze_campaign_id,
            braze_dispatch_id=braze_dispatch_id,
        )

        user = User.query.filter(User.esp_id == esp_id).first()

        if not user:
            log.error("User not found for bulk message", esp_id=esp_id)
            abort(404)

        if message_type == CA_AUTOMATED_MESSAGE:
            req_days_since_last_member_message = int(
                params["req_days_since_last_member_message"]
            )
            req_days_since_last_ca_message = int(
                params["req_days_since_last_ca_message"]
            )
            if not can_send_automated_message(
                user, req_days_since_last_ca_message, req_days_since_last_member_message
            ):
                log.error(
                    "Invalid Automated CA Message received from Braze",
                    braze_campaign_id=braze_campaign_id,
                    braze_dispatch_id=braze_dispatch_id,
                    user_id=user.id,
                )
                stats.increment(
                    "api.messaging.resources.braze.invalid_ca_automated_message",
                    stats.PodNames.MPRACTICE_CORE,
                )
                abort(424)

        message = create_cx_message(user, message=message_text, only_first=False)

        if message:
            message.braze_campaign_id = braze_campaign_id
            message.braze_dispatch_id = braze_dispatch_id
            db.session.commit()
            log.info("Braze bulk message committed to database", message_id=message.id)

            service_ns_tag = "messaging_system"
            team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
            notify_new_message.delay(
                user.id, message.id, service_ns=service_ns_tag, team_ns=team_ns_tag
            )
            send_to_zendesk.delay(
                message.id,
                initial_cx_message=True,
                user_need_when_solving_ticket="customer-need-member-proactive-outreach-other",
                service_ns=service_ns_tag,
                team_ns=team_ns_tag,
                caller=self.__class__.__name__,
            )

            audit("success_bulk_cx_message", user_id=user.id)
            return {"success": True, "message_id": message.id}
        else:
            audit("problem_bulk_cx_message", user_id=user.id)
            log.warning("Braze bulk message: Problem adding message", user_id=user.id)
            return {"success": False, "error": "Problem adding message"}
