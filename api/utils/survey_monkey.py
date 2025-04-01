import json
import os

import requests

from authn.models.user import User
from utils.log import logger

log = logger(__name__)

SURVEY_MONKEY_ACCESS_TOKEN = os.environ.get("SURVEY_MONKEY_IMPORTER_API_KEY")
SURVEY_MONKEY_WALLET_FOLDER_ID = os.environ.get("SURVEY_MONKEY_WALLET_FOLDER_ID")
API_BASE = "https://api.surveymonkey.com/v3"


def get_member_id_hash(survey_response):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return survey_response["custom_variables"].get("member_id_hash")


def get_user(survey_response):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    esp_id = get_member_id_hash(survey_response)
    if esp_id:
        return User.query.filter_by(esp_id=esp_id).one_or_none()


def get_submission_time(survey_response):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return survey_response["date_modified"]


def get_question_and_answer(question):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return {
        "question": question["heading"],
        "answer": ", ".join(
            [a.get("simple_text", a.get("choice_id", "")) for a in question["answers"]]
        ),
    }


def get_page_answers(page):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return [get_question_and_answer(q) for q in page["questions"]]


def get_all_answers(survey_response):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return [
        answers
        for page in survey_response["pages"]
        for answers in get_page_answers(page)
    ]


def get_submission_id(survey_response):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return survey_response["id"]


def get_from_survey_monkey(path, params=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if params is None:
        params = {}

    headers = {
        "Authorization": f"Bearer {SURVEY_MONKEY_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    resp = requests.get(f"{API_BASE}/{path}", headers=headers, params=params)
    response = resp.json()

    if resp.status_code != 200:
        error_message = response["error"]["message"]
        log.error(
            "survey_monkey_error",
            status_code=resp.status_code,
            path=path,
            message=error_message,
        )
        return []

    if response.get("data"):
        return response["data"]
    return response


def update_survey_monkey_webhook(path, data=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    Make an API request and pass the current access token in the headers.
    """
    if data is None:
        data = {}

    headers = {
        "Authorization": f"Bearer {SURVEY_MONKEY_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    response = requests.patch(
        f"{API_BASE}/{path}", headers=headers, data=json.dumps(data)
    )
    return response


def get_collector_url_slug(url):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return [x for x in url.split("/") if x][-1]


def load_all_surveys():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    surveys = get_from_survey_monkey(
        "surveys", {"folder_id": SURVEY_MONKEY_WALLET_FOLDER_ID}
    )
    return surveys


def find_collectors_for_survey(survey_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    collectors = get_from_survey_monkey(
        f"surveys/{survey_id}/collectors", {"include": "url"}
    )
    collectors = [c.get("url") for c in collectors if c.get("url")]
    return {
        get_collector_url_slug(c["url"]): survey_id
        for c in collectors
        if get_collector_url_slug(c["url"])
    }


def map_collectors_to_survey_ids():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    surveys = load_all_surveys()
    collectors = [find_collectors_for_survey(s["id"]) for s in surveys]
    collector_lookup = {k: v for c in collectors for (k, v) in c.items() if c}
    return collector_lookup


def find_results_by_collector_url(url):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    slug = get_collector_url_slug(url)
    survey_id = map_collectors_to_survey_ids().get(slug)
    return get_results_for_survey(survey_id)


def get_results_for_survey(survey_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    survey_responses = get_from_survey_monkey(
        f"surveys/{survey_id}/responses/bulk",
        {"per_page": 100, "sort_order": "DESC", "simple": True, "status": "completed"},
    )
    return [
        {
            "submission_id": get_submission_id(r),
            "member_id_hash": get_member_id_hash(r),
            "submitted_at": get_submission_time(r),
            "answers": get_all_answers(r),
            "user": get_user(r),
        }
        for r in survey_responses
    ]


def get_results_for_all_surveys():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    surveys = load_all_surveys()
    return [r for s in surveys for r in get_results_for_survey(s["id"])]


def get_result_for_single_survey(survey_id, response_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return get_from_survey_monkey(f"surveys/{survey_id}/responses/{response_id}")


def get_survey_details(survey_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return get_from_survey_monkey(f"surveys/{survey_id}/details")


def get_survey_ids():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    surveys = load_all_surveys()

    if surveys:
        survey_ids = []
        for survey in surveys:
            try:
                survey_id = survey.get("id")
                if survey_id is not None:
                    survey_ids.append(survey_id)
                else:
                    log.warning("Survey missing 'id' field: %s")
            except Exception as e:
                log.error("Error getting survey id", error=e)
        return survey_ids

    return surveys


def get_webhook_id():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # We only have a single webhook for SurveyMonkey
    webhooks = get_from_survey_monkey("webhooks")
    if webhooks:
        return int(webhooks[0].get("id"))
    return webhooks


def update_webhook_survey_ids() -> bool:
    webhook_id = get_webhook_id()
    survey_ids = get_survey_ids()
    data = {
        "object_ids": survey_ids,
    }
    log.info(
        "Got survey_ids and webhook_id", survey_ids=survey_ids, webhook_id=webhook_id
    )
    if webhook_id and survey_ids:
        response = update_survey_monkey_webhook(f"webhooks/{webhook_id}", data=data)
        if response.status_code not in [200, 201]:
            log.error(
                "survey_monkey update_webhook_survey_ids",
                status_code=response.status_code,
            )
            return False
        return True
    else:
        log.error("survey_monkey_webhook_not_updated. Missing Ids")
        return False
