from types import MappingProxyType

from members.resources.async_encounter_summaries import AsyncEncounterSummariesResource
from members.resources.member_profile_summary import MemberProfileSummaryResource
from members.resources.search import MemberSearchResource

_urls = MappingProxyType(
    {
        "/v1/members/<int:member_id>": MemberProfileSummaryResource,
        "/v1/members/<int:member_id>/async_encounter_summaries": AsyncEncounterSummariesResource,
        "/v1/members/search": MemberSearchResource,
    }
)


def add_routes(api):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    for url_path, view in _urls.items():
        api.add_resource(view, url_path)
    return api


def _fetch_url_mappings():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    for url_path, view in _urls.items():
        yield url_path, view, {},


def get_routes():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    yield from _fetch_url_mappings()


def get_blueprints():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    ...
