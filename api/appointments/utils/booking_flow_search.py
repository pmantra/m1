from __future__ import annotations

import json
import os
from collections import defaultdict
from typing import Optional

import requests
from maven import feature_flags

from appointments.models.needs_and_categories import (
    Need,
    NeedCategoryTrack,
    NeedTrack,
    need_need_category,
)
from appointments.utils.errors import SearchApiError, SearchApiRequestsError
from authn.models.user import User
from common import stats
from l10n.db_strings.translate import TranslateDBFields
from models.tracks import TrackName
from models.verticals_and_specialties import is_cx_vertical_name
from providers.service.provider import ProviderService
from storage.connection import db
from utils.log import logger

log = logger(__name__)

SEARCH_API_URL = (os.getenv("SEARCH_API_URL") or "") + "search"


def search_api_booking_flow(
    query_str: str,
    limit: int,
    member: User,
    enable_semantic_search: bool,
    enable_l10n: bool,
) -> tuple[list[dict], list[dict], list[dict], list[User], list[dict], list[Need]]:
    """
    This method will hit elasticsearch for the top 2*limit most relevant results, group
    the result by type (index), filter and apply business logic, and then limit the
    result

    Notes:
        - Pagination is not supported by this method, as we do not plan on using this
          in any of our FE clients
        - The return types are a mix of both lists of dicts and lists of sqla objects
    """
    hits = _query_search_api(query_str, 2 * limit, enable_semantic_search)

    # Group hits by index
    index_map = defaultdict(list)
    index_map["provider_search_index_specialty"] = (specialties := [])
    index_map["provider_search_index_specialty_keyword"] = (keywords := [])
    index_map["provider_search_index_vertical"] = (verticals := [])
    index_map["provider_search_index_practitioner_profile"] = (practitioners := [])
    index_map["provider_search_index_need_category"] = (need_categories := [])
    index_map["provider_search_index_need"] = (need_hits := [])
    for hit in hits:
        index_map[hit["_index"]].append(hit["_source"])

    # Filter Verticals
    verticals = _filter_verticals(verticals)

    # Filter Practitioners
    provider_ids = [p["user_id"] for p in practitioners]
    practitioners = ProviderService().search_for_search_api(
        current_user=member,
        user_ids=provider_ids,
        limit=limit,
    )

    # Filter Need Categories
    active_track_names = {at.name for at in member.active_tracks}
    if not member.is_enterprise:  # member.is_enterprise makes a DB call
        # Marketplace users do not have a track, but we will treat them as though they were on the
        # General Wellness track for booking only.
        # https://mavenclinic.atlassian.net/jira/software/c/projects/DISCO/boards/216?assignee=712020%3A49deb732-f61f-4665-9284-92e5dd333f2c&selectedIssue=DISCO-3202
        active_track_names.add(TrackName.GENERAL_WELLNESS)
    member_is_multitrack = len(active_track_names) > 1
    need_category_ids_in_member_track = _get_need_category_ids_in_member_track(
        active_track_names
    )
    need_categories = _filter_need_categories(
        need_categories,
        member_is_multitrack,
        need_category_ids_in_member_track,
        query_str,
        enable_l10n,
    )

    # If there is a matching need_category then only use needs that match that category
    if need_categories:
        log.info(
            "Found a need category match",
            query_str=query_str,
            need_category=need_categories[0],
        )
        needs = _get_needs_from_need_category(
            need_categories[0]["id"], active_track_names
        )
    else:
        log.info("Did not find a need category match", query_str=query_str)
        # Filter and fetch Needs
        need_ids = [n["id"] for n in need_hits]
        needs = _get_needs(
            need_ids,
            query_str,
            active_track_names,
            member_is_multitrack,
            limit,
        )

    # Apply limit, practitioners are limited in ProviderService
    specialties = specialties[:limit]
    keywords = keywords[:limit]
    verticals = verticals[:limit]
    need_categories = need_categories[:limit]
    needs = needs[:limit]

    return (
        specialties,
        keywords,
        verticals,
        practitioners,
        need_categories,
        needs,
    )


def _filter_verticals(verticals) -> list[dict]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    filtered_verticals = []
    for vertical in verticals:
        vertical["id"] = int(vertical["id"])

        if vertical["deleted_at"]:
            continue
        elif is_cx_vertical_name(vertical["name"]):
            continue
        else:
            filtered_verticals.append(vertical)

    return filtered_verticals


def _get_need_category_ids_in_member_track(active_track_names) -> set[int]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    nc_ids = (
        db.session.query(NeedCategoryTrack.need_category_id)
        .filter(NeedCategoryTrack.track_name.in_(active_track_names))
        .all()
    )
    return {t[0] for t in nc_ids}


def _localize_need_category_name(
    need_category: dict,
    translate: Optional[TranslateDBFields],
) -> str:
    en_name = need_category["name"]
    if not translate:
        return en_name

    return translate.get_translated_need_category(
        slug=need_category.get("slug", ""),
        field="name",
        default=en_name,
        lazy=False,
    )


def _filter_need_categories(
    need_categories: list[dict],
    member_is_multitrack: bool,
    need_category_ids_in_member_track: set[int],
    query_str: str,
    enable_l10n: bool,
) -> list[dict]:
    """
    It is assumed that need_categories only support exact matches in the query itself,
    therefore only one need_category at most will be returned.

    NOTE: we are still returning a list type here to fit in with the rest of the flow
    """
    # Filter need_categories to be exact matches with the query string
    translate = TranslateDBFields() if enable_l10n else None
    filtered_need_categories = [
        nc
        for nc in need_categories
        if _localize_need_category_name(nc, translate) == query_str
    ]
    log.info(
        "Filtered need_categories by name",
        need_categories=need_categories,
        filtered_need_categories=filtered_need_categories,
        query_str=query_str,
    )

    if len(filtered_need_categories) < 1:
        log.info("No exact need_category match")
        return []
    elif len(filtered_need_categories) > 1:
        log.error(
            "More than one exact match on need_category has been found",
            need_categories=filtered_need_categories,
        )
        return []
    else:
        need_category = filtered_need_categories[0]

    # Filter multitrack users if "hide_from_multitrack" is set
    if member_is_multitrack and need_category["hide_from_multitrack"] == 1:
        log.info("Filtering need_category due to multitrack")
        return []

    # Filter by member track
    if need_category["id"] not in need_category_ids_in_member_track:
        log.info(
            "Filtering need_category due to member track",
            need_category_ids_in_member_track=need_category_ids_in_member_track,
            nc_id=str(need_category["id"]),
        )
        return []

    return [need_category]


def _get_needs(
    need_ids: list[int],
    query_str: str,
    active_track_names: set[int],
    member_is_multitrack: bool,
    limit: int,
) -> list[Need]:
    """
    Get needs that match the current user's track, or are a part of need_category
    matches
    """
    need_query = (
        db.session.query(Need)
        .join(NeedTrack)
        .filter(
            NeedTrack.track_name.in_(active_track_names),
            Need.id.in_(need_ids),
        )
    )

    if member_is_multitrack:
        need_query = need_query.filter(Need.hide_from_multitrack == False)

    need_query = need_query.order_by(
        Need.display_order.is_(None).asc(), Need.display_order.asc()
    ).limit(limit)

    return list(need_query.all())


def _get_needs_from_need_category(
    need_category_id: int,
    active_track_names: set[int],
) -> list[Need]:
    return (
        db.session.query(Need)
        .join(NeedTrack)
        .join(need_need_category)
        .filter(
            NeedTrack.track_name.in_(active_track_names),
            need_need_category.c.category_id == need_category_id,
        )
        .all()
    )


def _query_search_api(
    query_str: str, size: int, enable_semantic_search: bool
) -> list[dict]:
    """
    Query our internal search-api service, which uses elasticsearch, configured for
    booking flow search

    The "cluster" field is no longer needed, as this is set to default to the correct
    value based on environment in search-api. The values are "shared-dev-es" for qa2 and
    "shared-prod-es" for production.
    """
    if enable_semantic_search:
        payload = {
            "index": "provider_search_alias_*",
            "query": _create_search_query(query_str),
            "elser_query": query_str,
            "elser_model_id": ".elser_model_2_linux-x86_64",
            "source_includes": ["*"],
            "from_": 0,  # offset
            "size": size,  # limit
        }
    else:
        payload = {
            "index": "provider_search_alias_*",
            "query": _create_search_query(query_str),
            "from_": 0,  # offset
            "size": size,  # limit
        }
    headers = {"Content-type": "application/json"}

    try:
        response = requests.post(
            SEARCH_API_URL, headers=headers, json=payload, timeout=2
        )
    except requests.exceptions.HTTPError as http_e:
        log.error("HTTP error when hitting search api", error=str(http_e))
        raise SearchApiRequestsError("HTTP error when hitting search api")
    except requests.exceptions.ConnectionError as conn_e:
        log.error("Connection error when hitting search api", error=str(conn_e))
        raise SearchApiRequestsError("Connection error when hitting search api")
    except requests.exceptions.Timeout as timeout_e:
        log.error("Timeout error when hitting search api", error=str(timeout_e))
        raise SearchApiRequestsError("Timeout error when hitting search api")
    except Exception as e:
        log.error("An unknown error occured while hitting search api", error=str(e))
        raise SearchApiRequestsError(
            "An unknown error occured when hitting the search api"
        )

    if response.status_code != 200:
        log.error(
            "An error occurred hitting the search api: Status code != 200",
            query_str=query_str,
            status_code=response.status_code,
            response=response.text,
        )
        raise SearchApiError("Status code is not 200")

    res_json = response.json()
    if not res_json:
        log.error(
            "An error occurred hitting the search api: No response json",
            query_str=query_str,
            status_code=response.status_code,
            response=response.text,
        )
        raise SearchApiError("No response json")

    try:
        total = res_json["hits"]["total"]["value"]
        hits = res_json["hits"]["hits"]
    except KeyError:
        log.error(
            "An error occurred hitting the search api: Invalid response format",
            query_str=query_str,
            status_code=response.status_code,
            response=response.text,
        )
        raise SearchApiError("Invalid response format")

    metric_name = "api.appointments.utils.booking_flow_search._query_search_api.total"
    stats.increment(
        metric_name=metric_name,
        tags=["success:true"],
        pod_name=stats.PodNames.CARE_DISCOVERY,
        metric_value=total,
    )

    return hits


def _create_search_query(query_str: str) -> str:
    # This flag does not need context as it is a kill-switch
    booking_flow_search_prefix_matching = feature_flags.bool_variation(
        "enable-booking-flow-search-prefix-matching",
        default=False,
    )

    # Specialty keywords are currently left out of this query as they are no longer used
    query = {
        "bool": {
            "minimum_should_match": 1,
            "should": [
                {
                    "bool": {
                        "must": [
                            {"term": {"_index": "provider_search_index_specialty"}},
                            {
                                "multi_match": {
                                    "query": query_str,
                                    "fields": ["name", "searchable_localized_data"],
                                    "fuzziness": "AUTO",
                                }
                            },
                        ]
                    }
                },
                {
                    "bool": {
                        "must": [
                            {"term": {"_index": "provider_search_index_vertical"}},
                            {
                                "multi_match": {
                                    "query": query_str,
                                    "fields": ["name", "searchable_localized_data"],
                                    "fuzziness": "AUTO",
                                }
                            },
                        ]
                    }
                },
                # Provider Search: cross_fields does not support fuzziness
                {
                    "bool": {
                        "must": [
                            {
                                "term": {
                                    "_index": "provider_search_index_practitioner_profile"
                                }
                            },
                            {
                                "multi_match": {
                                    "query": query_str,
                                    "fields": ["first_name", "last_name"],
                                    "type": "cross_fields",
                                }
                            },
                        ]
                    }
                },
                # Need categories only support exact matches
                {
                    "bool": {
                        "must": [
                            {"term": {"_index": "provider_search_index_need_category"}},
                            {
                                "multi_match": {
                                    "query": query_str,
                                    "fields": ["name", "searchable_localized_data"],
                                }
                            },
                        ]
                    }
                },
                {
                    "bool": {
                        "must": [
                            {"term": {"_index": "provider_search_index_need"}},
                            {
                                "multi_match": {
                                    "query": query_str,
                                    "fields": [
                                        "name",
                                        "description",
                                        "searchable_localized_data",
                                    ],
                                    "fuzziness": "AUTO",
                                }
                            },
                        ]
                    }
                },
            ],
        }
    }

    # Add prefix matching if the flag is enabled
    # NOTE: need_categories are not included here as they only support exact matching
    if booking_flow_search_prefix_matching:
        query["bool"]["should"].extend(  # type: ignore[attr-defined] # "object" has no attribute "extend"
            [
                {
                    "bool": {
                        "must": [
                            {"term": {"_index": "provider_search_index_specialty"}},
                            {
                                "multi_match": {
                                    "query": query_str,
                                    "fields": ["name", "searchable_localized_data"],
                                    "type": "phrase_prefix",
                                }
                            },
                        ]
                    }
                },
                {
                    "bool": {
                        "must": [
                            {"term": {"_index": "provider_search_index_vertical"}},
                            {
                                "multi_match": {
                                    "query": query_str,
                                    "fields": ["name", "searchable_localized_data"],
                                    "type": "phrase_prefix",
                                }
                            },
                        ]
                    }
                },
                {
                    "bool": {
                        "must": [
                            {
                                "term": {
                                    "_index": "provider_search_index_practitioner_profile"
                                }
                            },
                            {
                                "multi_match": {
                                    "query": query_str,
                                    "fields": ["first_name", "last_name"],
                                    "type": "phrase_prefix",
                                }
                            },
                        ]
                    }
                },
                {
                    "bool": {
                        "must": [
                            {"term": {"_index": "provider_search_index_need"}},
                            {
                                "multi_match": {
                                    "query": query_str,
                                    "fields": ["name", "searchable_localized_data"],
                                    "type": "phrase_prefix",
                                }
                            },
                        ]
                    }
                },
            ]
        )

    return json.dumps(query)
