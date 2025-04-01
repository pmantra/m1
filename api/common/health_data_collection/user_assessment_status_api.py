from typing import List, Union

from common.health_data_collection.base_api import make_hdc_request
from common.health_data_collection.models import (
    AssessmentMetadata,
    UserAssessmentStatus,
)
from utils.log import logger

log = logger(__name__)

USER_ASSESSMENT_STATUS_API_URL = "/user-assessments"


def get_user_answer_slug_endpoint(assessment_slug: str) -> str:
    return f"/assessments/{assessment_slug}{USER_ASSESSMENT_STATUS_API_URL}/answers"


def get_user_assessments_by_user_id(
    user_id: int,
) -> List[UserAssessmentStatus]:
    log.info(f"Fetching UserAssessmentStatus for User ID={user_id}")

    try:
        response = make_hdc_request(
            url=USER_ASSESSMENT_STATUS_API_URL,
            params={"user_id": user_id},
            extra_headers={"X-Maven-User-ID": str(user_id)},
            method="GET",
        )

        if not response or response.status_code != 200:
            log.error(
                "Unable to fetch UserAssessmentStatus for User",
                user_id=user_id,
                exception=response.content if response else None,  # type: ignore[attr-defined] # "Response" has no attribute "content"
            )
            return []

        return [UserAssessmentStatus(**ua) for ua in response.json()]
    except Exception as e:
        log.error(
            "Unable to fetch UserAssessmentStatus for User",
            user_id=user_id,
            exception=e,
        )
        return []


def get_user_assessment_by_user_id_and_slug(
    user_id: int, assessment_slug: str
) -> Union[AssessmentMetadata, None]:
    log.info(
        "Fetching MetadataAssessment", user_id=user_id, assessment_slug=assessment_slug
    )

    try:
        response = make_hdc_request(
            url=get_user_answer_slug_endpoint(assessment_slug),
            params={"user_id": user_id},
            extra_headers={"X-Maven-User-ID": str(user_id)},
            method="GET",
        )
        if not response or response.status_code != 200:
            log.error(
                "Unable to fetch MetadataAssessment",
                exception=response.content if response else None,  # type: ignore[attr-defined] # "Response" has no attribute "content"
                user_id=user_id,
                assessment_slug=assessment_slug,
            )
            return  # type: ignore[return-value] # Return value expected

        res = response.json()
        return AssessmentMetadata.create_from_api_response(res)

    except Exception as e:
        log.error(
            "Unable to fetch MetadataAssessment",
            exception=e,
            user_id=user_id,
            assessment_slug=assessment_slug,
        )
    return None
