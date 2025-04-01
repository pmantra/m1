from types import MappingProxyType

from geography.resources.country_resource import CountryResource
from geography.resources.subdivision_resource import SubdivisionResource

_urls = MappingProxyType(
    {
        "/v1/_/geography": CountryResource,
        "/v1/_/geography/<string:country_code>": SubdivisionResource,
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
