from typing import Any, Optional

from ddtrace import tracer
from flask import request

from common.services.api import InternalServiceResource
from models.images import Image
from utils.index_resources import (
    build_article_record_from_contentful_resource_slugs,
    build_article_record_from_not_contentful_resource_slugs,
    build_course_record_from_course_slugs,
    build_virtual_event_record_from_event_ids,
)


class ContentSingleResource(InternalServiceResource):
    @tracer.wrap()
    def get(self, resource_slug: str) -> Optional[dict[str, Any]]:
        args = request.args
        learning_type: Optional[str] = args.get("learning_type")
        # Fetch event
        if learning_type == "EVENT":
            event_id = int(resource_slug)
            events_dict = build_virtual_event_record_from_event_ids([event_id])
            return events_dict.get(event_id)
        # Fetch course
        if learning_type == "COURSE":
            courses_dict = build_course_record_from_course_slugs([resource_slug])
            return courses_dict.get(resource_slug)

        content_source: Optional[str] = args.get("content_source")
        if content_source == "NOT_CONTENTFUL":
            records_dict = build_article_record_from_not_contentful_resource_slugs(
                [resource_slug]
            )
            # Generate image_url based on thumbor for downstream client usage
            records_dict = {
                slug: {
                    **record,
                    "image_url": Image(
                        storage_key=record["image_storage_key"]
                    ).asset_url(90, 120, smart=False),
                }
                for slug, record in records_dict.items()
            }
        else:
            records_dict = build_article_record_from_contentful_resource_slugs(
                [resource_slug]
            )
        return records_dict.get(resource_slug)
