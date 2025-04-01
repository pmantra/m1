import base64
import hashlib
import hmac
import os
from datetime import timedelta

from flask import abort, request

from common.services.api import UnauthenticatedResource
from utils.cache import redis_client
from utils.log import logger
from utils.slack_v2 import notify_wallet_ops_alerts_channel
from utils.survey_monkey import (
    get_member_id_hash,
    get_result_for_single_survey,
    get_survey_details,
)

log = logger(__name__)

SURVEY_MONKEY_SECRET = "SURVEY_MONKEY_SECRET"
SURVEY_MONKEY_CLIENT_ID = "SURVEY_MONKEY_CLIENT_ID"


def compare_signatures(payload: bytes, header_signature: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    api_key = os.getenv(SURVEY_MONKEY_CLIENT_ID)
    api_secret = os.getenv(SURVEY_MONKEY_SECRET)

    key = f"{api_key}&{api_secret}".encode()
    signature = hmac.new(key, msg=payload, digestmod=hashlib.sha1)

    signature_digest = signature.digest()
    signature = base64.b64encode(signature_digest)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "bytes", variable has type "HMAC")

    return hmac.compare_digest(signature, header_signature.encode())  # type: ignore[call-overload] # No overload variant of "compare_digest" matches argument types "HMAC", "bytes"


def _get_survey_title(survey_id: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    redis = redis_client()
    key = f"wallet_survey_title:{survey_id}"
    survey_title = redis.get(key)
    if not survey_title:
        survey_details = get_survey_details(survey_id)
        if survey_details:
            survey_title = survey_details.get("title")
            if survey_title:
                redis.setex(key, timedelta(days=30), survey_title)
    return survey_title


def _get_subject_and_text(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    survey_title: str = None,  # type: ignore[assignment] # Incompatible default for argument "survey_title" (default has type "None", argument has type "str")
    member_id_hash: str = None,  # type: ignore[assignment] # Incompatible default for argument "member_id_hash" (default has type "None", argument has type "str")
    survey_url: str = None,  # type: ignore[assignment] # Incompatible default for argument "survey_url" (default has type "None", argument has type "str")
):
    subject = "Survey Completed"
    text = ""
    html = ""
    if survey_title:
        subject = f"{survey_title} just completed a survey!"
    if not member_id_hash and not survey_url:
        text = "Webhook Error - Please review logs"
        html = "<p>Webhook Error - Please review logs</p>"
    if member_id_hash:
        text = f"Member Hash Id: {member_id_hash}\n"
        html = f"<p>Member Hash Id: {member_id_hash}</p>\n"
    if survey_url:
        text += f"Analyze Survey URL: {survey_url}"
        html += f"<a href={survey_url}>Analyze Survey URL</a>"

    return subject, text, html


class SurveyMonkeyWebHookResource(UnauthenticatedResource):
    """Webhook that receives completed survey events from the SurveyMonkey."""

    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return "", 200

    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        raw_data = request.get_data()
        header_signature = request.headers.get("Sm-Signature")

        if not raw_data or not header_signature:
            abort(400, "survey_monkey_webhook: missing authentication information.")

        if not compare_signatures(raw_data, header_signature):
            abort(401, "survey_monkey_webhook: Not Authorized")

        data = request.get_json()
        survey_title = None

        # Abort if data or resources within data is empty
        if data is None or data.get("resources") is None:
            subject, text, html = _get_subject_and_text(survey_title)  # type: ignore[arg-type] # Argument 1 to "_get_subject_and_text" has incompatible type "None"; expected "str"
            notify_wallet_ops_alerts_channel(
                notification_title=subject,
                notification_body=text,
                notification_html=html,
            )
            abort(400, "survey_monkey_webhook: data or response empty")

        resources = data["resources"]
        survey_id = resources.get("survey_id")
        response_id = data.get("object_id")

        # Get the survey title as early as possible to assist ops in finding the survey
        if survey_id:
            survey_title = _get_survey_title(survey_id)

        # Abort if we do not have the response or the survey ids
        if response_id is None or survey_id is None:
            subject, text, html = _get_subject_and_text(survey_title)  # type: ignore[arg-type] # Argument 1 to "_get_subject_and_text" has incompatible type "Optional[Any]"; expected "str"
            notify_wallet_ops_alerts_channel(
                notification_title=subject,
                notification_body=text,
                notification_html=html,
            )
            abort(400, "survey_monkey_webhook: response_id or survey_id empty.")

        survey_response = get_result_for_single_survey(survey_id, response_id)
        # Abort if we do not have the survey response
        if not survey_response:
            subject, text, html = _get_subject_and_text(survey_title)  # type: ignore[arg-type] # Argument 1 to "_get_subject_and_text" has incompatible type "Optional[Any]"; expected "str"
            notify_wallet_ops_alerts_channel(
                notification_title=subject,
                notification_body=text,
                notification_html=html,
            )
            abort(400, "survey_monkey_webhook: survey_response empty.")

        member_id_hash = get_member_id_hash(survey_response)
        survey_url = survey_response.get("analyze_url")
        subject, text, html = _get_subject_and_text(
            survey_title, member_id_hash, survey_url  # type: ignore[arg-type] # Argument 1 to "_get_subject_and_text" has incompatible type "Optional[Any]"; expected "str"
        )
        notify_wallet_ops_alerts_channel(
            notification_title=subject,
            notification_body=text,
            notification_html=html,
        )
        return "", 200
