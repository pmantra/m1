import dataclasses
import json
import os
from datetime import datetime, timedelta
from typing import List, Optional

import requests
from sqlalchemy import func, text

from authn.models.user import User
from models.zoom import Webinar
from utils.log import logger

log = logger(__name__)

ZOOM_API_URL = "https://api.zoom.us/v2"
ZOOM_OAUTH_TOKEN_URL = "https://zoom.us/oauth/token"
ZOOM_OAUTH_TOKEN_GRANT_TYPE = "account_credentials"
CONTENT_TYPE_HEADER = "application/json"
TIMEOUT = 15


ZOOM_API_ACCOUNT_ID = os.environ.get("ZOOM_API_ACCOUNT_ID")
ZOOM_SERVER_TO_SERVER_OAUTH_CLIENT_ID = os.environ.get(
    "ZOOM_SERVER_TO_SERVER_OAUTH_CLIENT_ID"
)
ZOOM_SERVER_TO_SERVER_OAUTH_SECRET = os.environ.get(
    "ZOOM_SERVER_TO_SERVER_OAUTH_SECRET"
)

# Zoom account used to create the webinars
ZOOM_WEBINAR_HOST_ID = "63yK847_RqiKObz4_WsGCQ"


@dataclasses.dataclass
class PersistentAccessTokenData:
    access_token: Optional[str] = None
    token_expiration_timestamp: Optional[datetime] = None


access_token_data = None


def get_webinars():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Find all webinars including those in the past and future.
    """
    endpoint = f"users/{ZOOM_WEBINAR_HOST_ID}/webinars"
    webinars = _fetch_all_records(endpoint, agg_prop="webinars")
    return webinars


def get_upcoming_webinars():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Find all upcoming webinars.
    """
    now = datetime.utcnow()
    all_webinars = get_webinars()

    upcoming_webinars = []
    for webinar in all_webinars:
        start_time = datetime.strptime(webinar["start_time"], "%Y-%m-%dT%H:%M:%SZ")

        if start_time > now:
            upcoming_webinars.append(webinar)

    return upcoming_webinars


def get_webinars_since_days_ago(since_days: int) -> List[Webinar]:
    now = datetime.utcnow()
    since_date = now - timedelta(days=since_days)
    return Webinar.query.filter(
        (Webinar.start_time >= since_date.date())
        & (
            func.timestampadd(text("MINUTE"), Webinar.duration, Webinar.start_time)
            < now
        )
    ).all()


def get_webinar_info(webinar_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Get detailed information about the specified webinar.
    """
    endpoint = f"webinars/{webinar_id}"
    response = make_zoom_request(endpoint)
    return response


def get_past_webinar_absentees(webinar_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Get the absentees for the specified webinar.
    """
    endpoint = f"past_webinars/{webinar_id}/absentees"
    absentees = _fetch_all_records(endpoint, agg_prop="registrants")
    return absentees


def get_past_webinar_participants(webinar_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Get the participants for the specified webinar.
    """
    endpoint = f"past_webinars/{webinar_id}/participants"
    participants = _fetch_all_records(endpoint, agg_prop="participants")
    return participants


def get_users_who_participated_in_webinar(webinar_id: int) -> List[User]:
    """
    Find the users who participated in the specified webinar.
    """
    participants = get_past_webinar_participants(webinar_id)

    participant_emails = {p["user_email"] for p in participants}
    users = User.query.filter(User.email.in_(participant_emails)).all()

    return users


def get_users_who_missed_webinar(webinar_id: int) -> list[User]:
    """
    Find the users who registered for the specified webinar, but did not attend.
    """
    registrants = get_past_webinar_absentees(webinar_id)

    registrant_emails = {r["email"] for r in registrants}
    users = User.query.filter(User.email.in_(registrant_emails)).all()

    return users


def make_zoom_request(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    endpoint: str,
    method: str = "GET",
    data: Optional[dict] = None,
    params: Optional[dict] = None,
):
    try:
        if (
            not access_token_data
            or not access_token_data.token_expiration_timestamp
            or access_token_data.token_expiration_timestamp <= datetime.utcnow()
        ):
            _get_access_token()
        response = requests.request(
            method,
            f"{ZOOM_API_URL}/{endpoint}",
            data=json.dumps(data) if data else {},
            params=params if params else {},
            headers={
                "Content-type": CONTENT_TYPE_HEADER,
                "Authorization": "Bearer " + access_token_data.access_token,  # type: ignore[attr-defined] # "None" has no attribute "access_token"
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        return response
    except requests.HTTPError as error:
        log.error(
            "Zoom API request failed.",
            zoom_endpoint=endpoint,
            exception=error,
            response=error.response.json(),
            exc_info=True,
        )
        return error.response


def _get_access_token():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    response = requests.request(
        "POST",
        ZOOM_OAUTH_TOKEN_URL,
        params={
            "grant_type": ZOOM_OAUTH_TOKEN_GRANT_TYPE,
            "account_id": ZOOM_API_ACCOUNT_ID,
        },
        auth=(  # type: ignore[arg-type] # Argument "auth" to "request" has incompatible type "Tuple[Optional[str], Optional[str]]"; expected "Optional[Union[Tuple[str, str], AuthBase, Callable[[PreparedRequest], PreparedRequest]]]"
            ZOOM_SERVER_TO_SERVER_OAUTH_CLIENT_ID,
            ZOOM_SERVER_TO_SERVER_OAUTH_SECRET,
        ),
    )
    json_response = response.json()
    access_token = json_response["access_token"]
    # add 5 minute buffer
    time_to_expire = json_response["expires_in"] - 300

    global access_token_data
    access_token_data = PersistentAccessTokenData(
        access_token=access_token,
        token_expiration_timestamp=datetime.utcnow()
        + timedelta(seconds=time_to_expire),
    )


def _fetch_all_records(endpoint, agg_prop, data=None, method="GET", params=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    Collect all records found in `agg_prop` by iterating through the pages of the Zoom response.
    """
    records = []
    response = make_zoom_request(endpoint, data=data, method=method, params=params)

    if response:
        res_json = response.json()
        records = res_json.get(agg_prop, [])
        page_size = res_json.get("page_size", 0)
        total_records = res_json.get("total_records", 0)

        additional_pages_to_fetch = total_records // page_size

        for _ in range(additional_pages_to_fetch):
            fetch_params = {"next_page_token": res_json.get("next_page_token")}
            fetch_params.update({k: v for k, v in params.items()} if params else {})
            response = make_zoom_request(
                endpoint, data=data, method=method, params=fetch_params
            )
            if response:
                res_json = response.json()
                records += res_json.get(agg_prop, [])
    return records
