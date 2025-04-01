from typing import Union

from common.health_data_collection.base_api import make_hdc_request
from common.health_data_collection.models import HDCQuestion
from utils.log import logger

log = logger(__name__)


def get_question_answer_endpoint(question_slug: str) -> str:
    return f"/questions/{question_slug}/answers"


def get_question_slug_user_answers(  # type: ignore[return] # Missing return statement
    user_id: int, question_slug: str
) -> Union[HDCQuestion, None]:
    try:
        response = make_hdc_request(
            url=get_question_answer_endpoint(question_slug),
            params={"user_id": user_id},
            extra_headers={"X-Maven-User-ID": str(user_id)},
            method="GET",
        )
        if not response or response.status_code != 200:
            log.error(
                "Call to HDC for Question with User Answers failed",
                exception=response.content if response else None,  # type: ignore[attr-defined] # "Response" has no attribute "content"
                question_slug=question_slug,
            )
            return  # type: ignore[return-value] # Return value expected

        json_response = response.json()
        return HDCQuestion.create_from_api_response(json_response=json_response)
    except Exception as ex:
        log.error(
            "Call to HDC for Question with User Answers failed",
            exception=ex,
            question_slug=question_slug,
        )
