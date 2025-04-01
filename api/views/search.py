import dataclasses
import functools
import os
from typing import List, Optional
from uuid import uuid4

from elastic_enterprise_search import AppSearch
from flask import make_response, request
from flask_restful import abort
from marshmallow import Schema, ValidationError, fields

from common.services.api import AuthenticatedResource
from learn.services.read_time_service import ReadTimeService
from learn.utils.resource_utils import get_estimated_read_time_and_media_type
from models.images import Image
from models.tracks import MemberTrack
from utils.log import logger

log = logger(__name__)

APP_SEARCH_HOST = os.environ.get("APP_SEARCH_SERVICE_HOST", "app-search")
APP_SEARCH_PORT = os.environ.get("APP_SEARCH_SERVICE_PORT", "3002")
APP_SEARCH_ENGINE_PREFIX = os.environ.get("APP_SEARCH_ENGINE_PREFIX", "")
APP_SEARCH_API_KEY = os.environ.get("APP_SEARCH_API_KEY", "")
DEFAULT_PAGE_SIZE = 50
IMAGE_WIDTH = 400
IMAGE_HEIGHT = 220


def prefix(engine_name: str) -> str:
    if APP_SEARCH_ENGINE_PREFIX:
        return f"{APP_SEARCH_ENGINE_PREFIX}-{engine_name}"
    return engine_name


@dataclasses.dataclass
class SearchResult:
    page: int = 1
    total_pages: int = 1
    total_results: int = 0
    page_size: int = DEFAULT_PAGE_SIZE
    request_id: str = dataclasses.field(default_factory=lambda: str(uuid4()))
    results: List[dict] = dataclasses.field(default_factory=list)


class SearchClickRequestSchema(Schema):
    request_id = fields.String(required=True)
    document_id = fields.String(required=True)
    query = fields.String(required=True)


# This is returned when app search is disabled (aka when API key is unset)
EMPTY_RESULT = SearchResult()


def app_search_enabled() -> bool:
    if not APP_SEARCH_API_KEY:
        log.warn(
            "App search is disabled (no api key set), search will return no results"
        )
        return False
    return True


@functools.lru_cache(maxsize=1)
def get_client() -> AppSearch:
    return AppSearch(
        f"http://{APP_SEARCH_HOST}:{APP_SEARCH_PORT}", http_auth=APP_SEARCH_API_KEY
    )


def get_resources_engine() -> str:
    return prefix("resources-v1")


def to_image_url(storage_key: Optional[str]) -> Optional[str]:
    if not storage_key:
        return None
    img = Image(storage_key=storage_key)
    return img.asset_url(width=IMAGE_WIDTH, height=IMAGE_HEIGHT)


def get_resource_from_result(result: dict):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """Converts an app search result object into a resource for the API"""
    image_url = flatten_field(result, "image_url")
    if not image_url:
        image_url = to_image_url(flatten_field(result, "image_storage_key"))

    return {
        # App Search stores its internal IDs as strings, so the actual model ID is
        # stored raw_id
        "id": int(flatten_field(result, "raw_id")),  # type: ignore[arg-type] # Argument 1 to "int" has incompatible type "Optional[str]"; expected "Union[str, Buffer, SupportsInt, SupportsIndex, SupportsTrunc]"
        "title": flatten_field(result, "title"),
        "body_content": flatten_field(result, "body_content"),
        "slug": flatten_field(result, "slug"),
        "image_url": image_url,
        "type": flatten_field(result, "article_type"),
        "document_id": flatten_field(result, "id"),
    }


def flatten_field(result: dict, key: str) -> Optional[str]:
    """
    App search fields come back like this:
    1. null
    2. { "raw": "..." }
    3. { "snippet": "...", "raw": "..." }
    This method tries to return the SNIPPET, but falls back either to RAW or None
    """
    if key not in result:
        return None
    field = result[key]
    return field["snippet"] if "snippet" in field else field["raw"]


def perform_search(
    resource_type: str, query: str, track: Optional[MemberTrack]
) -> SearchResult:
    if resource_type != "resources":
        # TODO: search other types of resources
        raise ValueError(f"Invalid resource type: {resource_type}")

    if not app_search_enabled():
        return EMPTY_RESULT

    # TODO: this depends on resource_type
    result_fields = {
        "title": {"raw": {}},
        "body_content": {"snippet": {"size": 150}},
        "raw_id": {"raw": {}},
        "slug": {"raw": {}},
        "image_storage_key": {"raw": {}},
        "image_url": {"raw": {}},
        "article_type": {"raw": {}},
    }
    engine_name = get_resources_engine()
    client = get_client()
    options = {
        "result_fields": result_fields,
        "page": {"size": DEFAULT_PAGE_SIZE, "current": 1},
    }
    if track:
        # Boost scores of articles related to this track by 3x
        options["boosts"] = {
            "tracks": [
                {
                    "type": "value",
                    "value": track.name,
                    "operation": "multiply",
                    "factor": 3,
                }
            ]
        }
    options["query"] = query
    response = client.search(engine_name, options)

    resources = [get_resource_from_result(result) for result in response["results"]]
    estimated_read_times_minutes = ReadTimeService().get_values_without_filtering(
        slugs=[resource["slug"] for resource in resources]
    )
    for resource in resources:
        (
            resource["estimated_read_time_minutes"],
            resource["media_type"],
        ) = get_estimated_read_time_and_media_type(
            slug=resource["slug"],
            estimated_read_times_minutes=estimated_read_times_minutes,
        )

    meta = response["meta"]
    result = SearchResult()
    result.page = meta["page"]["current"]
    result.total_pages = meta["page"]["total_pages"]
    result.total_results = meta["page"]["total_results"]
    result.page_size = meta["page"]["size"]
    result.request_id = meta["request_id"]
    result.results = [
        {
            "type": "resource",
            # front ends require a specific document ID from the resource, but this field should not be present in
            # the `data` field
            "document_id": resource["document_id"],
            # TODO: the method to use here depends on resource type
            "data": {
                key: value for key, value in resource.items() if key != "document_id"
            },
        }
        for resource in resources
    ]

    return result


def record_click(resource_type: str, request_id: str, document_id: str, query: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    if resource_type != "resources":
        # TODO: search other types of resources
        raise ValueError(f"Invalid resource type: {resource_type}")

    if not app_search_enabled():
        return

    engine_name = get_resources_engine()
    client = get_client()
    client.log_clickthrough(
        engine_name, request_id=request_id, document_id=document_id, query_text=query
    )


class SearchResource(AuthenticatedResource):
    def get(self, resource_type: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        query = request.args.get("query", "")
        if not query:
            return abort(400, message="Search query cannot be empty")
        try:
            # TODO: [multitrack] Make sure this changes when user changes track context
            track = self.user.current_member_track
            result = perform_search(resource_type, query, track)
            return make_response(dataclasses.asdict(result), 200)
        except ValueError as e:
            abort(400, message=str(e))
        # TODO: handle these errors? For now, this is commented out so that these go to
        #  stackdriver
        # except TransportError as e:
        #     abort(500, message="There was an error while performing this search")


class SearchClickResource(AuthenticatedResource):
    def post(self, resource_type: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        schema = SearchClickRequestSchema()
        try:
            args = schema.load(request.json if request.is_json else {})
            record_click(
                resource_type=resource_type,
                request_id=args["request_id"],
                document_id=args["document_id"],
                query=args["query"],
            )
            return make_response({"success": True}, 200)
        except (ValidationError, ValueError) as e:
            abort(400, message=str(e))
        # TODO: handle these errors? For now, this is commented out so that these go to
        #  stackdriver
        # except TransportError as e:
        #     abort(500, message="There was an error while performing this search")
