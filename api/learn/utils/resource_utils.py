from typing import Dict, List, Optional, Tuple

from learn.models.media_type import MediaType
from learn.services.read_time_service import ReadTimeService
from models.marketing import Resource


def populate_estimated_read_times_and_media_types(
    resources: List[Resource],
) -> List[Resource]:
    estimated_read_times_minutes = ReadTimeService().get_values_without_filtering(
        [
            resource.slug
            for resource in resources
            if resource.is_contentful_article_ish()
        ]
    )

    for resource in resources:
        if resource.content_type == "on_demand_class":
            resource.media_type = MediaType.ON_DEMAND_CLASS
        else:
            (
                resource.estimated_read_time_minutes,
                resource.media_type,
            ) = get_estimated_read_time_and_media_type(
                slug=resource.slug,
                estimated_read_times_minutes=estimated_read_times_minutes,
            )

    return resources


def get_estimated_read_time_and_media_type(
    slug: str, estimated_read_times_minutes: Dict[str, int]
) -> Tuple[Optional[int], Optional[MediaType]]:
    if slug in estimated_read_times_minutes:
        if estimated_read_times_minutes[slug] == -1:
            return None, MediaType.VIDEO
        else:
            return estimated_read_times_minutes[slug], MediaType.ARTICLE
    return None, None
