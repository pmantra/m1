"""
Iterates through all resources and removes those ineligible for search from the
Elasticsearch index.  Meant to be run once, as functionality now exists for
this to happen to a resource automatically when it is updated.
"""
import datetime

from models import marketing
from utils import index_resources


def remove_em() -> None:
    offset = 0
    limit = 500
    now = datetime.datetime.now()
    resources = (
        marketing.Resource.query.outerjoin(marketing.ResourceTrack)
        .outerjoin(marketing.tags_resources)
        .limit(limit)
        .offset(offset)
        .all()
    )
    while resources:
        for resource in resources:
            if (
                not resource.published_at
                or resource.published_at > now
                or resource.resource_type != marketing.ResourceTypes.ENTERPRISE
                or not resource.allowed_tracks
                or (
                    resource.content_type
                    in ["article", "real_talk", "ask_a_practitioner", "curriculum_step"]
                    and not resource.tags
                )
            ):
                index_resources.remove_from_index(resource)
        offset += limit
        resources = (
            marketing.Resource.query.outerjoin(marketing.ResourceTrack)
            .outerjoin(marketing.tags_resources)
            .limit(limit)
            .offset(offset)
            .all()
        )
