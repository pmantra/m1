from __future__ import annotations

import datetime
import enum
import os

from google.api_core.exceptions import GoogleAPIError
from google.cloud import recaptchaenterprise_v1

from utils.exceptions import log_exception, log_exception_message
from utils.gcp import safe_get_project_id
from utils.log import logger

log = logger(__name__)


"""
Utils for dealing with Google's reCAPTCHA Enterprise service.

Used to detect forum spam posts.
"""


class ActionName(str, enum.Enum):
    CREATE_POST = "create_post"


def get_recaptcha_key() -> str | None:
    return os.environ.get("GOOGLE_RECAPTCHA_SITE_KEY")


def get_recaptcha_score(token: str, user_id: int, action_name: ActionName):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    site_key = get_recaptcha_key()
    now_iso = datetime.datetime.now().isoformat()
    assessment_name = f"forum_{action_name}_{user_id}_{now_iso}"
    parent_project = f"projects/{safe_get_project_id()}"

    client = recaptchaenterprise_v1.RecaptchaEnterpriseServiceClient()

    event = recaptchaenterprise_v1.Event()
    event.site_key = site_key
    event.token = token
    event.expected_action = action_name

    assessment = recaptchaenterprise_v1.Assessment()
    assessment.event = event
    assessment.name = assessment_name

    request = recaptchaenterprise_v1.CreateAssessmentRequest()
    request.assessment = assessment
    request.parent = parent_project

    try:
        response = client.create_assessment(request)
    except GoogleAPIError as e:
        log.warn("Got error while trying to create reCAPTCHA assessment")
        log_exception(e)
        return None, None

    if not response.token_properties.valid:
        log_exception_message("Got invalid reCAPTCHA token")
        log.warn(
            "Got invalid reCAPTCHA token",
            reasons=str(response.token_properties.invalid_reason),
        )
        return None, None
    else:
        if response.event.expected_action == action_name:
            return response.risk_analysis.score, response.risk_analysis.reasons
        else:
            log_exception_message(
                f"Got invalid reCAPTCHA action name: {response.event.expected_action}"
            )
            return None, None
