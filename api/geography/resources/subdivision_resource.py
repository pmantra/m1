from __future__ import annotations

from flask_restful import abort
from maven import feature_flags

from caching.redis import redis_cache_manager
from common import stats
from common.services.api import UnauthenticatedResource
from geography.repository import SubdivisionRepository
from utils.log import logger

log = logger(__name__)


class SubdivisionResource(UnauthenticatedResource):
    """
    All valid country codes will return a set of subdivisions, although it might be empty
    so if you get a NoneType back from a country code it is safe to assume it is invalid.
    """

    def get(self, country_code: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        localization_enabled = feature_flags.bool_variation(
            "release-pycountry-localization",
            default=False,
        )

        if localization_enabled:
            return get_subdivisions(country_code)

        return get_cached_subdivisions(country_code)


ONE_DAY_IN_SECONDS = 60 * 60 * 24


@redis_cache_manager.ttl_cache(
    namespace="subdivision_code",
    ttl_in_seconds=ONE_DAY_IN_SECONDS,
    pod_name=stats.PodNames.ENROLLMENTS,
)
def get_cached_subdivisions(country_code: str) -> list[dict]:
    return get_subdivisions(country_code)


def get_subdivisions(country_code: str) -> list[dict]:
    subdivision_repo = SubdivisionRepository()
    subdivisions = subdivision_repo.get_subdivisions_by_country_code(
        country_code=country_code
    )
    if subdivisions is None:
        abort(400, message=f"{country_code} is not a valid country code")

    data = (
        [
            {
                "subdivision_code": sub.code,
                "abbreviation": sub.abbreviation,
                "name": sub.name,
            }
            for sub in sorted(subdivisions, key=lambda x: x.code)
        ]
        if subdivisions
        else []
    )

    data.sort(key=lambda k: k["abbreviation"])
    return data or []
